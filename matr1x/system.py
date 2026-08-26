# This file is part of a software collection for data acquisition (matr1x).
# Copyright (C) 2006-2026 matr1x developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
Module containing the System class definition and utility functions.

These can be used for data acquisition and instrument control.
"""

from __future__ import annotations

import builtins
import importlib
import inspect
import keyword
import logging
import os
import re
import sys
import time
from collections import defaultdict
from collections.abc import Callable, Iterable
from functools import cached_property
from operator import attrgetter
from pathlib import Path
from typing import Any, ClassVar, TypeGuard, TypeVar, cast

import h5py
import numpy as np
from pydantic import BaseModel, ValidationError
from pymeasure.instruments import Instrument

import matr1x
from matr1x.devices.visadevice import VisaDevice
from matr1x.error_handling import Error, Result, Success
from matr1x.models import (
    MeasurementData,
    Message,
    SystemCapability,
    SystemMethod,
    SystemReference,
    SystemSelectionInfo,
    SystemVariable,
    UntypedConfigModel,
)

from .util import (
    construct_query_string,
    default_separator,
    flatten,
    init_ascii_header,
    init_hdf5_skel,
    module_from_path,
    resolve_config_path,
    save_dict_to_hdf5,
)

VALID_META_KEYS = {
    "creator": True,
    "date": False,
    "identifier": True,
    "relation": True,
    "description": True,
    "source": True,
    "type": True,
    "publisher": True,
    "format": False,
    "language": False,
}
"""
Valid metadata keys for the dublin core metadata.

The 'false' keys are auto-generated and cannot be set.
"""

APP_META_KEY = ["description"]
"""
The user can append to these dublin core keys.
"""
BUILTIN_TYPES = frozenset(obj for obj in vars(builtins).values() if isinstance(obj, type))

ALLOWED_SIGNATURE_TYPES = BUILTIN_TYPES | {None}

logger = logging.getLogger(__name__)


ConfigScheme = tuple[str, tuple, dict[str, Any]]
ConfigValue = str | Callable[[], Any] | ConfigScheme
ConfigParameter = dict[str, ConfigValue]

T = TypeVar("T")


class DcDict(dict):
    """
    Custom dictionary class that only allows append if key already exists.

    This class extends the built-in dictionary class to modify its behavior
    when in append mode or when a merged system exists.
    In append mode non-empty entries are extended.

    Methods
    -------
    overwrite_value(key, value)
        Overwrite the value for a given key.
    """

    def __init__(self, system_ref, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.append = False
        self.system_ref = system_ref

    def __setitem__(self, key, value):
        """
        Set item in the dictionary with modified behavior.

        This method wraps dict.__setitem__ to change behavior when in append mode
        or when a merged system exists (append in that case).

        Parameters
        ----------
        key : hashable
            The key to set.
        value : Any
            The value to set for the given key.
        """
        if self.system_ref.merged_system:
            # initialized subsystem, write into merged parent
            if key not in APP_META_KEY:
                # is meta key is non-editable, no append is allowed
                super().__setitem__(key, value)
                return
            self._append_value(key, value, ";@set:", ref=self.system_ref.merged_system.dcdata)
        elif self.append and self[key]:
            # read only mode is enabled, append values
            if key not in APP_META_KEY:
                # is meta key is non-editable, no append is allowed
                super().__setitem__(key, value)
                return
            self._append_value(key, value, ";@ap:")
        else:
            super().__setitem__(key, value)

    def _append_value(self, key, value, sep, ref=None):
        if not value:
            # only append values that are not None
            return
        if ref:
            # reference system is defined, write meta_data to that system
            if ref.get(key):
                # only append to available value if it exists (not None)
                ref[key] = sep.join([ref[key], value])
                return
            ref[key] = sep[1:] + value
        else:
            # append meta data to current current array
            if key in self.keys() and self[key]:
                super().__setitem__(key, sep.join([self[key], value]))
                return
            super().__setitem__(key, sep[1:] + value)


class Parameter:
    """
    Define a measurement parameter.

    This class describes one parameter in matrix. It can define a
    single or multiple columns of the measurement.

    Parameters
    ----------
    name : str or list of str
        Name of the column(s) as string or list of strings. If this is
        a list, make sure unit, default and chunks have same length.
    unit : str or list of str
        Unit of the column(s) as string or list of strings.
    default : float or list of floats, optional
        Default value for parameter. If not None this value is always
        used unless another value is specified in the measurement.
        If None (default), no default value is set/used.
    dtypes : str or list of str, optional
        Dtype specified for saving into hdf5 files, not used for ascii
        files. Default value is "f8" (8 byte float).
    chunks : int or list of int, optional
        Length of the readback value. If a list is returned for a
        single parameter, set to the length of that list.
        If None (default), a chunk of 1 is assumed (readback of
        parameter is single float).
    setter : callable, str, or list, optional
        Function which should be called to set the values.
        Must be one of:

        * A callable function with the call signature
          `func(value, *args, **kwargs)`. For optional arguments and
          kwargs see setter_args/setter_kwargs.
        * A string with a system method/property name. If it
          corresponds to a method its call signature and arguments must
          be equal to the callable function above.
        * A list of the following scheme
          [device_name : str, method_name : str, args : tuple, kwargs : dict].
          The args and kwargs entries are deprecated and should be
          replaced by the setter_args, setter_kwargs parameters.
    getter : callable, str, or list, optional
        Function which should be called to fetch the values.
        Must be one of:

        * A callable function with the call signature
          `func(*args, **kwargs)`. The arguments and kwargs are
          optional and can be supplied via getter_args/getter_kwargs.
        * A string with a system method/property name. If it
          corresponds to a method its call signature and arguments must
          be equal to the callable function above.
        * A list of the following scheme
          [device_name : str, method_name : str, args : tuple, kwargs : dict].
          The args and kwargs entries are deprecated and should be
          replaced by the getter_args, getter_kwargs parameters.
    trigger : callable, str, or list, optional
        Takes a trigger function. The options are equal to the getter
        options. For the optional arguments and kwargs use
        trigger_args/trigger_kwargs.
    label : str, optional
        Parameters label if different from name. This might be in
        particular needed if an automatically generated label from a
        name-list is not describing the content very well.

    Attributes
    ----------
    All parameters are set as attributes of same name.

    Raises
    ------
    ValueError
        If parameter types or lengths are inconsistent.
    TypeError
        If parameter types are incorrect.
    """

    def __init__(
        self,
        name: str | list[str],
        unit: str | list[str],
        setter=None,
        getter=None,
        default: float | list[float] | None = None,
        dtypes: str | list[str] | None = None,
        chunks=None,
        trigger=None,
        setter_args: tuple[Any] | list[Any] | None = None,
        setter_kwargs: dict[str, Any] | None = None,
        getter_args: tuple[Any] | list[Any] | None = None,
        getter_kwargs: dict[str, Any] | None = None,
        trigger_args: tuple[Any] | list[Any] | None = None,
        trigger_kwargs: dict[str, Any] | None = None,
        label: str | None = None,
    ):
        # general error checking
        if any([isinstance(name, (list, tuple)), isinstance(unit, (list, tuple))]):
            if not (
                isinstance(unit, (list, tuple))
                and isinstance(name, (list, tuple))
                and (dtypes is None or isinstance(dtypes, (list, type)))
            ):
                raise TypeError(
                    "Name, unit must be of the same type"
                    " together with dtypes "
                    "(i.e. all list or all string, "
                    "dtypes can also be None)"
                )
            if len(name) != len(unit):
                raise ValueError("Name and unit have unequal length")
            if dtypes is not None and len(name) != len(dtypes):
                raise ValueError("Name and dtypes have unequal length")
            for val, key in zip([chunks, default], ["chunks", "default"]):
                if val is not None:
                    if not isinstance(val, (list, tuple)):
                        raise TypeError(f"{key} must be list if name is list")
                    if len(name) != len(val):
                        raise ValueError(f"{key} must have same length as name")

        # set functions
        self.setter = setter
        self.getter = getter
        self.trigger = trigger
        # store optional function args/kwargs
        self.setter_args: tuple[Any] | list[Any] | None = setter_args
        self.setter_kwargs: dict[str, Any] | None = setter_kwargs
        self.getter_args: tuple[Any] | list[Any] | None = getter_args
        self.getter_kwargs: dict[str, Any] | None = getter_kwargs
        self.trigger_args: tuple[Any] | list[Any] | None = trigger_args
        self.trigger_kwargs: dict[str, Any] | None = trigger_kwargs
        # set identifiers
        self.unit: str | list[str] = self.verify(unit, str)
        self.name: str | list[str] = self.verify(name, str)
        self.label: str
        if label:
            self.label = self.make_command_line_compatible(label)
        else:
            self.label = self.make_command_line_compatible(self.name)
        self.dtypes: str | list[str] | None
        if dtypes is None:
            # initialize dtypes to default value if unspecified
            if isinstance(self.unit, (list, tuple)):
                self.dtypes = ["f8"] * len(self.unit)
            else:
                self.dtypes = "f8"
        else:
            self.dtypes = self.verify(dtypes, str)
        # generate defaults or set to None
        self.default: float | list[float] | None
        if default is not None:
            # make sure default are all floats or raise error
            self.default = self.verify(default, (int, float))
        else:
            self.default = default
        # generate or set chunks
        if chunks is None:
            if isinstance(name, (list, tuple)):
                self.chunks = [1 for i in name]
            else:
                self.chunks = 1
        else:
            # make sure chunks are all int or raise error
            if isinstance(name, (list, tuple)):
                # if multiple columns are present, check each set of chunks
                # individually. Required as verify has depth limit of 1, so
                # cannot work with nested lists as required for multi
                # dimensional chunked columns
                self.chunks = []
                if isinstance(chunks, list):
                    for chunk in chunks:
                        self.chunks.append(self.verify(chunk, int))
                else:
                    raise ValueError(
                        f"Invalid type, expected list for chunks, but received {chunks}."
                    )
            else:
                self.chunks = self.verify(chunks, int)

    def __lt__(self, other: object) -> bool:
        """Define comparison function for sorting."""
        return bool(isinstance(other, Parameter) and "timeUTC" in other.name)

    def __eq__(self, other: object) -> bool:
        """Define equivalence of parameters."""
        return bool(
            isinstance(other, Parameter) and self.name == other.name and self.unit == other.unit
        )

    @staticmethod
    def make_command_line_compatible(s: str | list[str]) -> str:
        """
        Convert input string(s) to command line argument format.

        Replaces non-alphanumeric characters with hyphens, converts to
        lowercase, and prepends with double dashes. If a list of strings is
        given only the first entry is used for the output generation.

        Parameters
        ----------
        s : str or list of str
            Input string(s) to convert to command line argument format.

        Returns
        -------
        str
            Command line argument compatible representation of the input string.
        """
        # If input is a list/tuple, use first element
        if isinstance(s, (list, tuple)):
            s = s[0]

        # Replace non-alphanumeric characters with hyphens,
        # convert to lowercase, and strip extra hyphens
        s = re.sub(r"[^a-zA-Z0-9]", "-", s).strip("-").lower()

        # Handle empty string fallback
        return s if s else "arg"

    def verify(self, param: T, cast: type[T] | tuple[type[T], ...]) -> T:
        """
        Verify param is of correct type or raise error.

        Parameters
        ----------
        param : Any
            Parameter to verify.
        cast : type or tuple of types
            Type(s) to check against.

        Returns
        -------
        Any
            The verified parameter.

        Raises
        ------
        ValueError
            If param is not of the correct type.
        """
        if isinstance(param, (list, tuple)):
            for val in param:
                if isinstance(val, (list, tuple)):
                    raise ValueError("Nested sequences are not allowed")
                if not isinstance(val, cast):
                    raise ValueError(f"Invalid type, expected {cast}")
            return param

        if isinstance(param, cast):
            return param

        raise ValueError(f"Invalid type, expected {cast}")


class System:
    """
    Define a measurement setup/system.

    It is mostly defined by the individual `Parameter`s (stored in
    `parameters`) that are used in the system as well as the list of
    devices stored in `devs`. Additionally, it provides functions to
    set, trigger and read the individual parameters using the
    specifications provided there. Finally, it defines the set, query
    and reset function, which are used to open and initialize the
    devices, query the device configuration/status and return the system
    to a defined state, respectively.

    Attributes
    ----------
    parameters : list
        Contains the individual parameters that make up the system.
    columns : list
        Contains the column names extracted from the individual parameters.
    units : list
        Contains the units extracted from the individual parameters.
    dtypes : list
        Contains the dtypes extracted from the individual parameters.
    default_values : list
        Contains the default_values extracted from the individual parameters.
    chunks : list
        Contains the chunks extracted from the individual parameters.
    devs : dict
        Contains the individual devices that belong to the system.
    dcdata : dict
        Contains telemetry according to the Dublin Core specification
        that can be used to generate specific header information. see
        `VALID_META_KEYS`
    system_config_params : dict
        Contains the definition for custom device queries to read the
        configuration. Keys match the device names in .devs.
    name : str or None
        Optional instance name used by control GUIs and as the subsystem
        accessor for ordinary systems.
    """

    stateful: ClassVar[bool] = False
    """Whether construction requires one predefined state."""

    states: ClassVar[tuple[str, ...]] = ()
    """Ordered states exposed by a stateful system."""

    state_exclusion_groups: ClassVar[dict[str, str]] = {}
    """Optional state-to-exclusion-group declarations."""

    def __init__(self, name=None):
        """
        Initialize the System.

        Parameters
        ----------
        name : str, optional
            Name of the measurement system.
        """
        self._name: str | None = None
        self.name = name
        self._state: str | None = None
        self.source: str | None = None
        self.config_section: str | None = None

        self._config = matr1x.config.matr1x.scripts.matrix_script
        # define merged system reference
        self.merged_system: MergedSystem | None = None
        self._reporter: Callable[[MeasurementData], None] | None = None
        # initialize lists for later use
        self.parameters: list[Parameter] = []

        # initialize devices dict
        self.devs = {}
        self._devs_init = {}  # variable holding dev init info for reopeneing
        self.query_dict = {}  # store device information query

        # Allow warnings
        self.warnings: list[tuple[str, int]] = []

        # initialize flag to check whether system has been set
        self.opened = False
        self.system_config_params = {}

        # initialize HDF5 flag
        self._hdf5: bool = False
        # data filename variables
        self._filename: Path | None = None
        self._file_mode = "w"
        self._datafile_initialized = False

        # initialize empty config dictionary for system-specific configuration
        self.config: Any = {}

        # initialize empty sensitive_config dictionary for sensitive information
        # This dictionary will NOT be included in query results or file headers
        self.sensitive_config: UntypedConfigModel = UntypedConfigModel()
        self._sensitive_keys = []

        # Dublin Core metadata default entries
        self.dcdata: DcDict = DcDict(
            self,
            creator="",  # measurement user
            date=time.strftime(f"{matr1x.datetimefmt}", time.localtime()),
            identifier="",  # sample name
            relation="",  # parent sample
            description="",  # comment
            source="",  # measurement system
            type="",  # type of measurement data (e.g., transport)
            publisher="",  # published of data, e.g., university/institute
            format="text/plain; charset=UTF-8",
            language="en",
        )

    @staticmethod
    def _is_config_scheme(value: object) -> TypeGuard[ConfigScheme]:
        """Return True if the value is a valid ConfigScheme tuple."""
        return (
            type(value) is tuple
            and len(value) == 3
            and isinstance(value[0], str)
            and isinstance(value[1], tuple)
            and isinstance(value[2], dict)
        )

    @staticmethod
    def _query_device_config(device_handle: VisaDevice | Instrument, query: str) -> str:
        """Query a device config string via ``query`` or ``ask``."""
        query_method = getattr(device_handle, "query", None)
        if callable(query_method):
            return str(query_method(query))

        ask_method = getattr(device_handle, "ask", None)
        if callable(ask_method):
            return str(ask_method(query))

        raise AttributeError(
            f"config_params entry {query!r} needs a device query method, "
            "but neither query() nor ask() is available"
        )

    @staticmethod
    def _device_query(
        device_handle: VisaDevice | Instrument, config_params: ConfigParameter
    ) -> dict[str, Any]:
        """
        Query the current configuration of the device.

        Parameters
        ----------
        device_handle : VisaDevice or pymeasure device
            Must be an open device that implements the query function.
        config_params : dict
            Dictionary must adhere to the following format. Key is
            descriptor which is used to identify the parameter. The
            corresponding values must be one of:

            * An attribute or method name (if callable without arguments of
              the device object)
            * A callable function (without arguments)
            * A query string for the device
            * A list of the following scheme
            [method_name : str, args : tuple, kwargs : dict]

        Returns
        -------
        dict
            A dictionary of dictionaries containing the configuration. The
            keys of are the parameters that were queried.
        """
        if hasattr(device_handle, "name"):
            device_id = device_handle.name
        else:
            device_id = device_handle.__class__.__name__
        adapter = getattr(device_handle, "adapter", None)
        connection = getattr(adapter, "connection", None)
        resource_name = getattr(connection, "resource_name", None)
        if resource_name:
            device_id += f" {resource_name}"
        retquery: dict[str, Any] = {}
        for k, q in config_params.items():
            try:
                if isinstance(q, str) and not callable(q):
                    try:
                        attr = getattr(device_handle, q)
                    except AttributeError:
                        line = System._query_device_config(device_handle, q)
                    else:
                        if callable(attr):
                            line = attr()
                        else:
                            line = attr
                elif callable(q) and not isinstance(q, tuple) and not isinstance(q, str):
                    line = q()
                elif System._is_config_scheme(q) and not callable(q):
                    method = getattr(device_handle, q[0])
                    if not callable(method):
                        raise ValueError(f"config_params: method '{q[0]}' is not callable")
                    line = str(method(*q[1], **q[2]))
                else:
                    raise ValueError(f"config_params: Ambiguous class of {q!r}")
            except Exception:
                logger.exception("exception during config query of %s", device_id)
                raise
            retquery[k] = line
        return retquery

    @property
    def name(self) -> str | None:
        """Return the optional instance name."""
        return self._name

    @name.setter
    def name(self, value: str | None) -> None:
        """Set the instance name while retaining the legacy ``__name__`` field."""
        self._name = None if value is None else str(value)
        self.__name__ = str(value)

    @property
    def accessor_name(self) -> str:
        """Return the attribute name used to expose this subsystem after merging."""
        if self.stateful and self.state is not None:
            return f"{self.__class__.__name__}_{self.state}"
        if self.name is not None and self.name.isidentifier() and not keyword.iskeyword(self.name):
            return self.name
        return self.__class__.__name__

    @property
    def state(self) -> str | None:
        """Return the immutable construction state, if any."""
        return self._state

    def load_config(
        self,
        model_class: type[BaseModel],
        section: str,
        sensitive_keys: list[str] | None = None,
    ) -> None:
        """
        Load and validate a configuration section from the matr1x TOML file.

        The configuration is loaded from the specified section of the global
        matr1x configuration and validated against the provided Pydantic
        model class.

        Parameters
        ----------
        model_class : type[BaseModel]
            The Pydantic model class to use for validation.
        section : str
            The TOML section name to load (e.g., 'matr1x.systems.my_system').
        sensitive_keys : list[str], optional
            A list of keys that should be moved to sensitive_config.
        """
        self._load_config_section(model_class, section, sensitive_keys)

    def _load_config_section(
        self,
        model_class: type[BaseModel],
        section: str,
        sensitive_keys: list[str] | None = None,
    ) -> None:
        """Load one already resolved static or instance-specific config section."""
        self.config_section = section
        config_data = resolve_config_path(matr1x.config, section)

        # If it is a model (e.g. from MainConfig.model_extra), convert to dict
        if hasattr(config_data, "model_dump"):
            config_data = config_data.model_dump(by_alias=True)

        try:
            # Validate the config data
            validated_config = model_class.model_validate(config_data)
        except (ValidationError, TypeError, ValueError) as e:
            from . import format_validation_error, validation_errors

            msg = format_validation_error(e, base=f"{section}.")
            validation_errors.append(msg)
            # Preserve supplied values and model defaults for the config editor.
            # Execution applications block invalid configurations before running.
            validated_config = model_class.model_construct(**config_data)

        if sensitive_keys:
            # Move sensitive keys to sensitive_config
            sensitive_data = {}
            for key in sensitive_keys:
                # Check if the key exists as a field or in extra attributes
                # Standard BaseModel doesn't support 'in', so we use getattr
                sentinel = object()
                val = getattr(validated_config, key, sentinel)
                if val is not sentinel:
                    sensitive_data[key] = val
            self.sensitive_config = UntypedConfigModel(
                **{**self.sensitive_config.model_dump(), **sensitive_data}
            )
            self._sensitive_keys = sensitive_keys

        self.config = validated_config

    @property
    def filename(self) -> Path | None:
        """Path of the data file used to store measurement data."""
        return self._filename

    @filename.setter
    def filename(self, value: Path | str | None) -> None:
        value = Path(value) if value is not None else None
        self._filename = value

    @classmethod
    def from_file(
        cls,
        filename: str | Path | SystemReference,
    ) -> Result[System, str]:
        """Load and construct a static or stateful system."""
        return cls._from_file(filename)

    @classmethod
    def _load_definition(
        cls,
        source: str,
    ) -> Result[tuple[type[System] | System, Path | str, tuple[str, int] | None], str]:
        """Import a system source and return its class or legacy instance."""
        module_result = cls._import_system_module(source)
        if isinstance(module_result, Error):
            return module_result
        module, normfilename = module_result.value
        return cls._system_definition_from_module(module, normfilename)

    @staticmethod
    def _import_system_module(source: str) -> Result[tuple[Any, Path | str], str]:
        """Import a system module from a path or an installed module name."""
        normfilename = Path(source).expanduser()
        if normfilename.is_file():
            try:
                return Success((module_from_path(normfilename), normfilename))
            except PermissionError:
                return Error("System file is not readable.")
            except ImportError as error:
                return Error(f"{type(error).__name__}: {error}")

        if normfilename.suffix == ".py":
            normfilename = normfilename.stem
        return System._import_module_by_name(str(normfilename), normfilename)

    @staticmethod
    def _import_module_by_name(
        normfilestr: str, normfilename: Path | str
    ) -> Result[tuple[Any, Path | str], str]:
        """Import an installed system module, including bundled system modules."""
        candidates = [normfilestr, f"matr1x.systems.{normfilestr}"]
        for name in candidates:
            try:
                module = (
                    importlib.reload(sys.modules[name])
                    if name in sys.modules
                    else importlib.import_module(name)
                )
                return Success((module, normfilename))
            except ModuleNotFoundError as error:
                if error.name != name:
                    return Error(f"{type(error).__name__}: {error}")
            except ImportError as error:
                return Error(f"{type(error).__name__}: {error}")
        return Error(f"Could neither import '{normfilestr}' nor 'matr1x.systems.{normfilestr}'")

    @staticmethod
    def _system_definition_from_module(
        module: Any, normfilename: Path | str
    ) -> Result[tuple[type[System] | System, Path | str, tuple[str, int] | None], str]:
        """Find the single supported system definition in an imported module."""
        legacy_name = "system"
        system = getattr(module, legacy_name, None)

        if isinstance(system, System):
            legacy_warning = (
                f"Using an initialized System instance exported as '{legacy_name}' is deprecated; "
                "define exactly one local System subclass instead.",
                logging.WARNING,
            )
        else:
            # Imported base classes do not qualify: the system file itself
            # must define the single concrete class that Matrix instantiates.
            system_classes = {
                value
                for value in vars(module).values()
                if inspect.isclass(value)
                and value is not System
                and issubclass(value, System)
                and value.__module__ == module.__name__
            }
            if not system_classes:
                return Error(
                    "The system file must define exactly one local System subclass; none found."
                )
            if len(system_classes) > 1:
                names = ", ".join(sorted(system_class.__name__ for system_class in system_classes))
                return Error(
                    "The system file must define exactly one local System subclass; "
                    f"found: {names}."
                )
            system_class = cast(type[System], system_classes.pop())
            return Success((system_class, normfilename, None))
        return Success((system, normfilename, legacy_warning))

    @classmethod
    def inspect_file(
        cls,
        filename: str | Path | SystemReference,
    ) -> Result[SystemCapability, str]:
        """Inspect a system definition without constructing a system instance."""
        try:
            reference = SystemReference.from_value(filename)
        except ValidationError as error:
            return Error(str(error))
        definition_result = cls._load_definition(reference.source)
        if isinstance(definition_result, Error):
            return definition_result

        definition, _, _ = definition_result.value
        system_class = definition if inspect.isclass(definition) else type(definition)
        stateful = issubclass(system_class, StatefulSystem)
        if not stateful and getattr(system_class, "stateful", False):
            return Error(
                f"Stateful system class '{system_class.__name__}' must inherit StatefulSystem"
            )
        states: tuple[str, ...] = ()
        groups: dict[str, str] = {}
        if stateful:
            try:
                states, groups = system_class.state_declaration()
            except ValueError as error:
                return Error(f"Stateful system '{reference.source}' is invalid: {error}")
        return Success(
            SystemCapability(
                source=reference.source,
                stateful=stateful,
                states=states,
                state_exclusion_groups=groups,
                class_name=system_class.__name__,
            )
        )

    @classmethod
    def _from_file(
        cls,
        filename: str | Path | SystemReference,
    ) -> Result[System, str]:
        """
        Load and construct a system from a file or importable module.

        A system module must define exactly one local ``System`` subclass.
        Stateful subclasses receive their required state during construction.
        Legacy initialized ``system`` exports remain supported for static
        systems with a deprecation warning.
        """
        try:
            reference = SystemReference.from_value(filename)
        except ValidationError as error:
            return Error(str(error))
        definition_result = cls._load_definition(reference.source)
        if isinstance(definition_result, Error):
            return definition_result
        definition, normfilename, legacy_warning = definition_result.value

        system_result = cls._instantiate_definition(definition, reference)
        if isinstance(system_result, Error):
            return system_result
        system = system_result.value

        system.source = reference.source
        system.__name__ = str(normfilename)
        if legacy_warning:
            system.warnings.append(legacy_warning)
        return Success(system)

    @staticmethod
    def _instantiate_definition(
        definition: type[System] | System, reference: SystemReference
    ) -> Result[System, str]:
        """Construct a static or stateful system from an imported definition."""
        if isinstance(definition, System):
            if definition.stateful:
                return Error(
                    f"Stateful system '{reference.source}' must be defined as a "
                    "StatefulSystem subclass, not an initialized module export"
                )
            if reference.state is not None:
                return Error(f"Static system '{reference.source}' does not accept a state")
            return Success(definition)
        if issubclass(definition, StatefulSystem):
            if reference.state is None:
                return Error(f"Stateful system '{reference.source}' requires a state")
            try:
                return Success(definition(reference.state))
            except ValueError as error:
                return Error(str(error))
        if definition.stateful:
            return Error(
                f"Stateful system class '{definition.__name__}' must inherit StatefulSystem"
            )
        if reference.state is not None:
            return Error(f"Static system '{reference.source}' does not accept a state")
        return Success(definition())

    @property
    def hdf5(self) -> bool:
        """
        Get whether the system requires or uses HDF5 format for data storage.

        This property determines if HDF5 format is needed based on the structure
        of parameter chunks. HDF5 is required if any parameter:
        - Has a list/tuple of chunks but single name
        - Has nested tuple chunks
        - Has any chunk size greater than 1

        Returns
        -------
        bool
            True if HDF5 format is required, False if plain text format can be used.
        """
        # check if hdf5 format has to be used
        for parm in self.parameters:
            if isinstance(parm.chunks, (list, tuple)):
                if (
                    not isinstance(parm.name, (list, tuple))
                    or any(isinstance(p, (tuple,)) for p in parm.chunks)
                    or any(p > 1 for p in parm.chunks)
                ):
                    self.hdf5 = True
            elif parm.chunks > 1:
                self.hdf5 = True
        return self._hdf5

    @hdf5.setter
    def hdf5(self, value: bool) -> None:
        """
        Set the HDF5 format flag and update the data format accordingly.

        Parameters
        ----------
        value : bool
            Whether to use HDF5 format (True) or plain text format (False)
        """
        if self._hdf5 == value:
            return
        self._hdf5 = value
        if value is True:
            self.dcdata["format"] = "application/x-hdf5"
        else:
            self.dcdata["format"] = "text/plain; charset=UTF-8"

    def add_param(
        self,
        name: str | list[str],
        unit: str | list[str],
        setter=None,
        getter=None,
        default: float | list[float] | None = None,
        dtype: str | list[str] | None = None,
        chunks=None,
        trigger=None,
        setter_args: tuple[Any] | list[Any] | None = None,
        setter_kwargs: dict[str, Any] | None = None,
        getter_args: tuple[Any] | list[Any] | None = None,
        getter_kwargs: dict[str, Any] | None = None,
        trigger_args: tuple[Any] | list[Any] | None = None,
        trigger_kwargs: dict[str, Any] | None = None,
    ):
        """Add a `Parameter` to the list of parameters."""
        self.parameters.append(
            Parameter(
                name,
                unit,
                setter=setter,
                getter=getter,
                default=default,
                dtypes=dtype,
                trigger=trigger,
                chunks=chunks,
                setter_args=setter_args,
                setter_kwargs=setter_kwargs,
                getter_args=getter_args,
                getter_kwargs=getter_kwargs,
                trigger_args=trigger_args,
                trigger_kwargs=trigger_kwargs,
            )
        )

    def add_dev(self, name, descriptor, args=None, kwargs=None, config_params=None):
        """
        Add a device to the device dictionary.

        Parameters
        ----------
        name : str
            Unique device name, will be dictionary key.
        descriptor : object
            Device instance (must neither be initialized nor opened).
        args : tuple, optional
            Tuple containing args passed upon device initialization.
        kwargs : dict, optional
            Dictionary with kwargs passed upon device initialization.
        config_params : dict, optional
            Dictionary with query configuration, see query function for details.
        """
        if args is not None and kwargs is not None:
            entry = [descriptor, args, kwargs]
        elif kwargs is not None:
            entry = [descriptor, (), kwargs]
        elif args is not None:
            entry = [descriptor, args]
        else:
            # device instance can be initialized without arguments
            entry = [descriptor, ()]
        self.devs[name] = entry
        self._devs_init[name] = entry
        if config_params is not None:
            self.system_config_params[name] = config_params

    @property
    def columns(self) -> list[str | list[str]]:
        """
        Return a list of column names extracted from parameters.

        Returns
        -------
        list
            List containing the name of each parameter column
        """
        return [parm.name for parm in self.parameters]

    @property
    def labels(self) -> list[str]:
        """
        Return a list of labels extracted from parameters.

        Returns
        -------
        list
            List containing the label of each parameter
        """
        return [parm.label for parm in self.parameters]

    @property
    def units(self) -> list[str | list[str]]:
        """
        Return a list of units extracted from parameters.

        Returns
        -------
        list
            List containing the units of each parameter
        """
        return [parm.unit for parm in self.parameters]

    @property
    def default_values(self) -> list[None | float | list | tuple]:
        """
        Return a list of default values extracted from parameters.

        Returns
        -------
        list
            List containing the default value of each parameter
        """
        return [parm.default for parm in self.parameters]

    @property
    def chunks(self) -> list[int | list | tuple]:
        """
        Return a list of chunks extracted from parameters.

        Returns
        -------
        list
            List containing the chunks of each parameter
        """
        return [parm.chunks for parm in self.parameters]

    @property
    def dtypes(self) -> list[str | list[str] | None]:
        """
        Return a list of dtypes extracted from parameters.

        Returns
        -------
        list
            List containing the dtype of each parameter
        """
        return [parm.dtypes for parm in self.parameters]

    def report(self, data: MeasurementData) -> None:
        """
        Report data through the communication layer.

        A runner can install a callback with :meth:`set_reporter` to receive
        measurement data directly.

        Parameters
        ----------
        data : MeasurementData
            The data to report.
        """
        if self._reporter is not None:
            self._reporter(data)
        # Defer to merged_system if it is present
        elif self.merged_system:
            self.merged_system.report(data)

    def set_reporter(self, reporter: Callable[[MeasurementData], None]) -> None:
        """Set the callback that forwards measurement data to the runner."""
        self._reporter = reporter

    def generate_datafilename(
        self, outputfile: str | Path = "", inputfile: str | Path = "", append=False
    ) -> Path:
        """
        Generate output datafile name.

        No file should be overwritten. If append=True an existing datafile can be amended.
        In all other cases a new file name is generated.

        The datafilename will be generated preferentially from the outputfile
        or the inputfile-name. An appropriate extension is automatically added.

        Parameters
        ----------
        outputfile : str | Path, optional
            Output filename which should be used. Potentially a running number
            will be added to avoid overwriting an existing file.
        inputfile : str | Path, optional
            If outputfile is empty this string will be used to generate a
            datafile name.
        append : bool, optional
            Flag to decide if one should append to a potentially existing datafile.

        Returns
        -------
        Path
            Generated datafile.
        """
        # check whether hdf5 is required and change output extensions
        if self.hdf5 is True:
            # append h5 to filename to discern filetypes
            file_extension = ".h5" + matr1x.output_extension
        else:
            file_extension = matr1x.output_extension
        refileext = file_extension.replace(".", r"\.")

        if outputfile:
            datafile = Path(outputfile).expanduser()
        elif inputfile:  # no output file given -> input filename as template
            datafile = Path(inputfile).expanduser().with_suffix("")
            # generate fallback option for the datafile name
        else:  # no output nor input file, generate from system names
            timestamp = time.strftime(matr1x.datetimefmt, time.localtime())
            filename = Path(self.__name__).stem
            datafile_name = f"{timestamp}_{filename}"
            if os.name == "nt":
                # Windows does not like : in filenames
                datafile_name = datafile_name.replace(":", "")
            datafile = Path(datafile_name)
        # check if file extension was provided
        if not re.search(f"{refileext}$", str(datafile)):
            # Remove existing extensions and add the correct one
            cleaned_name = re.sub(r"(\.h5)?\.ma\d$", "", str(datafile))
            datafile = Path(cleaned_name + file_extension)
        if not datafile.exists():
            # use the unmodified file name
            self.filename = datafile
            self._file_mode = "w"
            return datafile
        if append:
            self.filename = datafile
            self._file_mode = "a"
            return datafile

        # in case extension and running number are already attached to
        # the filename, replace in outputfile
        outfile_str = re.sub(r"(_\d+)?(\.h5)?\.ma\d$", "", str(datafile))
        outfile = Path(outfile_str)
        # check filename and increase "extension number" to protect existing data
        extension = None
        for extension in range(1, 10000):
            candidate_file = outfile.with_name(f"{outfile.name}_{extension}{file_extension}")
            if not candidate_file.exists():
                break
        if extension is None:
            raise RuntimeError("Could not find available filename after 10000 attempts")
        # as last resort start a new file
        # append the next possible number as file extension
        outfile = outfile.with_name(f"{outfile.name}_{extension}{file_extension}")
        self.filename = outfile
        self._file_mode = "w"
        return outfile

    def clear_parameters(self) -> None:
        """Clear all system parameters."""
        # del self.parameters
        self.parameters = []

    def _inform_exception(self, i, func, action):
        """
        Print information about an exception.

        In best case identify a device related to the exception.

        Parameters
        ----------
        i : int or str
            Index or name of the parameter where the exception occurred.
        func : callable, str, or list
            Function, parameter name or list used when the parameter occurred.
        action : str
            String with action (verb) during which the exception occurred.
        """
        # print column identifier upon any exception
        if i in self.columns:
            colid = i
        else:
            colid = self.columns[i]
        info = f"Exception occured when {action} column {colid}"
        # print device identifier if available
        if callable(func):
            info += f" via function {func.__name__}."
        elif isinstance(func, str):
            info += f" via {func}."
        elif isinstance(func, (list, tuple)):
            if len(func) >= 2:
                info += f" related to device {func[0]}, parameter {func[1]}."
            else:
                info += f" with list-like property: {func!s}."
        print(info)  # noqa: T201

    def set_value(
        self, i: int | str, values: float | list[float] | None
    ) -> float | list[float] | None:
        """
        Set a parameter i to values.

        Takes the column name or index and sets the corresponding parameter as
        defined by the setter of the parameter, take care to send a correct
        list.
        If the setter is None, returns the send values (most likely nan or None).

        Parameters
        ----------
        i : int or str
            Index or name of the parameter that should be set.
        values : float or list of floats
            Values that should be written to the parameter/device.

        Returns
        -------
        float or list of floats
            Returns the values that have been set to the device.

        Raises
        ------
        TypeError
            If column cannot be identified.
        """
        if isinstance(i, str) and i in self.columns:
            idx = self.columns.index(i)
        elif isinstance(i, int) and i < len(self.columns):
            idx = i
        else:
            raise ValueError(f"Invalid index or name: {i}")
        setter = self.parameters[idx].setter
        args = self.parameters[idx].setter_args
        kwargs = self.parameters[idx].setter_kwargs
        if setter is None or values is None:
            return values

        if isinstance(values, Iterable):
            # parameter list, verify values
            values = list(map(float, values))  # type: ignore
        else:
            values = float(values)

        try:
            if callable(setter) is True:
                self._set_by_func(setter, values, args, kwargs)
            elif isinstance(setter, str):
                self._set_by_attr(setter, values, args, kwargs)
            else:
                self._set_by_list(setter, values, args, kwargs)
        except Exception:
            self._inform_exception(i, setter, "setting")
            raise

        return values

    def _set_by_func(self, func, value, args, kwargs):
        """
        Set values by a function call.

        The function call includes optional arguments and kwarguments only when
        they are not None.

        Parameters
        ----------
        func : callable
            Function to call.
        value : Any
            Value to set.
        args : tuple or None
            Optional positional arguments.
        kwargs : dict or None
            Optional keyword arguments.
        """
        if not args and not kwargs:
            func(value)
        elif not kwargs:
            func(value, *args)
        elif not args:
            func(value, **kwargs)
        else:
            func(value, *args, **kwargs)

    def _set_by_attr(self, attr_name, value, args, kwargs):
        """
        Set attribute or call the method with the value as argument.

        Parameters
        ----------
        attr_name : str
            Attribute or method name as string.
        value : Any
            Value to which the attribute should be set.
        args : list or None
            Optional arguments to the setter function.
        kwargs : dict or None
            Optional keyword arguments to the setter function.
        """
        attr = getattr(self, attr_name)
        if callable(attr):  # attr is method
            self._set_by_func(attr, value, args, kwargs)
        else:  # attr_name corresponds to an attribute
            setattr(self, attr_name, value)

    def _set_by_list(self, setter, value, args, kwargs):
        """
        Set some device property.

        The device property can be a callable method or an attribute. The
        callable method can receive optional additional arguments and keyword
        arguments which will be preferentially taken from the `args`/`kwargs`
        arguments. If those are not given the third and fourth entry of the
        setter list are used instead.

        Parameters
        ----------
        setter : list
            List of device name, property name/method, optional arguments, kwargs.
        value : Any
            Value to which the device property should be set.
        args : list or None
            Optional arguments to the setter function.
        kwargs : dict or None
            Optional keyword arguments to the setter function.
        """
        dev = self.devs[setter[0]]
        # Use attrgetter to support nested properties
        attr = attrgetter(setter[1])(dev)
        if callable(attr):  # callable device method
            if len(setter) == 3:  # optional arguments
                self._set_by_func(attr, value, args or setter[2], kwargs)
            elif len(setter) == 4:  # optional arguments and kwargs
                self._set_by_func(attr, value, args or setter[2], kwargs or setter[3])
            else:
                self._set_by_func(attr, value, args, kwargs)
        else:
            # Direct setattr() cannot handle dotted property paths - need to traverse chain
            *parent_attrs, final_attr = setter[1].split(".")
            parent = dev
            for attr in parent_attrs:
                parent = getattr(parent, attr)
            setattr(parent, final_attr, value)

    def trigger_value(self, i: str | int) -> None:
        """
        Trigger devices specified in column i if trigger function is provided.

        Parameters
        ----------
        i : int or str
            Index or name of parameter that is supposed to be triggered.
        """
        if isinstance(i, str) and i in self.columns:
            idx = self.columns.index(i)
        elif isinstance(i, int) and i < len(self.columns):
            idx = i
        else:
            raise ValueError(f"Invalid index or name: {i}")
        trigger = self.parameters[idx].trigger
        args = self.parameters[idx].trigger_args
        kwargs = self.parameters[idx].trigger_kwargs
        if trigger is not None:
            try:
                # trigger function has been provided
                if callable(trigger) is True:
                    self._call_func(trigger, args, kwargs)
                elif isinstance(trigger, str):
                    self._call_attr(trigger, args, kwargs, needs_callable=True)
                else:
                    self._call_by_list(trigger, args, kwargs, needs_callable=True)
            except Exception:
                self._inform_exception(i, trigger, "triggering")
                raise

    def _call_func(self, func, args, kwargs):
        """
        Call a function with optional arguments/kwargs.

        The function call includes arguments and kwarguments only when they are
        not None.

        Parameters
        ----------
        func : callable
            Function to call.
        args : tuple or None
            Optional positional arguments.
        kwargs : dict or None
            Optional keyword arguments.

        Returns
        -------
        Any
            The return value of the called function.
        """
        if not args and not kwargs:
            return func()
        elif not kwargs:
            return func(*args)
        elif not args:
            return func(**kwargs)
        else:
            return func(*args, **kwargs)

    def _call_attr(self, attr_name, args, kwargs, needs_callable=False):
        """
        Call some method which is specified by its attribute name.

        The attribute name correspond to a callable method, otherwise no action
        will be taken. An exception will be raised if no callable method can be
        found and needs_callable is True.

        Parameters
        ----------
        attr_name : str
            Attribute name of a method.
        args : list or None
            Optional arguments to the callable method.
        kwargs : dict or None
            Optional keyword arguments to the callable method.
        needs_callable : bool, optional
            If True an exception will be raised if no callable method is found.

        Returns
        -------
        Any
            The return value of the called method or the attribute value.

        Raises
        ------
        AttributeError
            If needs_callable is True and the attribute is not callable.
        """
        attr = getattr(self, attr_name)
        if callable(attr):
            ret = self._call_func(attr, args, kwargs)
        elif needs_callable:
            raise AttributeError(f"Attribute {attr_name} not callable")
        else:
            ret = attr
        return ret

    def _call_by_list(self, listdef, args, kwargs, needs_callable=False):
        """
        Call some device property.

        The device property must be a callable method, otherwise no action will
        be taken. An exception will be raised if no callable method can be found
        and needs_callable is True.

        Parameters
        ----------
        listdef : list
            List of device name, property name/method, optional arguments, kwargs.
        args : list or None
            Optional arguments to the device method.
        kwargs : dict or None
            Optional keyword arguments to the device method.
        needs_callable : bool, optional
            If True an exception will be raised if no callable method is found.

        Returns
        -------
        Any
            The return value of the called method or the attribute value.

        Raises
        ------
        AttributeError
            If needs_callable is True and the attribute is not callable.
        """
        dev = self.devs[listdef[0]]
        # Use attrgetter to support nested properties
        attr = attrgetter(listdef[1])(dev)
        if callable(attr):
            if len(listdef) == 3:  # optional arguments
                ret = self._call_func(attr, args or listdef[2], kwargs)
            elif len(listdef) == 4:  # optional arguments and kwargs
                ret = self._call_func(attr, args or listdef[2], kwargs or listdef[3])
            else:
                ret = self._call_func(attr, args, kwargs)
        elif needs_callable:
            raise AttributeError("Function is not callable")
        else:
            ret = attr
        return ret

    def trigger(self) -> None:
        """Trigger measurements of all parameters in the system."""
        for i in range(len(self.columns)):
            self.trigger_value(i)

    def read_value(self, i: str | int) -> Any:
        """
        Fetch readout value of parameter using the getter.

        Takes the column name or index and reads the corresponding parameter
        as defined by the getter of the parameter.
        If the getter is None, returns nan.

        Parameters
        ----------
        i : int or str
            Index or name of parameter that is supposed to be triggered.

        Returns
        -------
        readout : Any
            The readout from the device/parameter getter. If getter is None,
            returns "nan" or a list of "nan" values.
        """
        if isinstance(i, str) and i in self.columns:
            idx = self.columns.index(i)
        elif isinstance(i, int) and i < len(self.columns):
            idx = i
        else:
            raise ValueError(f"Invalid index or name: {i}")
        getter = self.parameters[idx].getter
        args = self.parameters[idx].getter_args
        kwargs = self.parameters[idx].getter_kwargs
        if getter is not None:
            try:
                if callable(getter):
                    return self._call_func(getter, args, kwargs)
                if isinstance(getter, str):
                    return self._call_attr(getter, args, kwargs)
                return self._call_by_list(getter, args, kwargs)
            except Exception:
                self._inform_exception(i, getter, "reading")
                raise
        else:
            # if get func is None, return "nan" or list of "nan"
            if isinstance(self.parameters[idx].name, (list, tuple)):
                return ["nan"] * len(self.parameters[idx].name)
            return "nan"

    def set(self, *args, **kwargs) -> None:
        """
        Handle device opening/initialization.

        For format of devs refer to `add_dev`

        Parameters
        ----------
        *args : tuple
            Arguments that can be used here, currently not used.
        **kwargs : dict
            Keyword arguments that can be used here, currently not used.
        """
        for key, dev in self.devs.items():
            if isinstance(dev, list) is True:
                try:
                    # initializing an instance of class dev[0] with args dev[1]
                    # and optionally kwargs in dev[2]
                    cls, devargs = dev[:2]
                    devkwargs = dev[2] if len(dev) > 2 else {}
                    if len(devargs) > 1 and "sharedwith" in devargs[0]:
                        # need to get connection from other device
                        devargs = list(devargs)
                        otherdev = devargs[0].split("::")[1]
                        devargs[0] = self.devs[otherdev].connection
                        # also reuse mutex lock from other device
                        if "sharedlock" not in devkwargs:
                            devkwargs["sharedlock"] = self.devs[otherdev].sharedlock
                    self.devs[key] = cls(*devargs, **devkwargs)
                except Exception:
                    # print device identifier upon any exception
                    print(f"Exception occured when initializing device {key}")  # noqa: T201
                    raise
            else:
                # device was already initialized prior the set call.
                # do not try to reinitialize or something is amiss.
                pass
        self.opened = True

    def query(self) -> dict[str, dict[str, Any]]:
        """
        Query all devices to read their configuration state.

        The system needs to be set before this function is called.

        Parameters provided in system or device need to be one of:
        * An attribute or method name (if callable without arguments) of
          the device object
        * A query string for the device
        * A list of the following scheme [method_name : str, args : tuple,
          kwargs : dict]

        Refer also to matr1x.devices.visadevice for further information.

        Returns
        -------
        retquery : dict
            Dictionary with dictionaries containing the configuration of each
            device.
        """
        if self.opened is False:
            raise ValueError("System must be set before query can be called")
        retquery: dict[str, dict[str, Any]] = {}
        # iterate over devices to get their config
        for key, dev in self.devs.items():
            # get device
            try:
                if key in self.system_config_params and hasattr(dev, "config_params"):
                    # device config_params are specified in system and device
                    retquery[key] = System._device_query(
                        dev, {**self.system_config_params[key], **dev.config_params}
                    )
                elif key in self.system_config_params:
                    # device config query is specified in system
                    retquery[key] = System._device_query(dev, self.system_config_params[key])
                elif hasattr(dev, "config_params"):
                    # device has config query specified, should return dictionary
                    retquery[key] = System._device_query(dev, dev.config_params)
                else:
                    # no query details available
                    retquery[key] = {}
            except Exception as error:
                print(f"system: error: could not access '{key}': {dev} {error}")  # noqa: T201
                raise
        # iterate over remaining keys in system_config_params
        for key in self.system_config_params.keys() - self.devs.keys():
            obj = self.system_config_params[key]
            if callable(obj):
                retquery[key] = obj()
            else:
                retquery[key] = obj

        # Add all system-wide configuration options from self.config organized by system name
        if self.config:
            retquery["system_config"] = {}
            if hasattr(self.config, "model_dump"):
                config_dict = self.config.model_dump(
                    by_alias=True, exclude=set(self._sensitive_keys)
                )
            else:
                config_dict = self.config
            for key, value in config_dict.items():
                if key.startswith("_"):
                    continue
                retquery["system_config"][key] = value

        return retquery

    def reset(self, *args, **kwargs) -> None:
        """
        General reset function for deinitialization of system.

        Clears the read buffer of the instrument. The device will be left open
        and initialized unless the system is closed or deleted.

        Parameters
        ----------
        *args : tuple
            Arguments that can be used here, currently not used.
        **kwargs : dict
            Keyword arguments that can be used here, currently not used.
        """
        for dev in self.devs.values():
            if hasattr(dev, "adapter"):  # pymeasure device
                try:
                    dev.adapter.flush_read_buffer()
                except Exception:
                    logger.debug("Could not flush device read buffer during reset", exc_info=True)
            elif hasattr(dev, "read_very_eager"):  # VisaDevice
                # read all bytes available and ignore them
                dev.read_very_eager()
        self.opened = False

    def close(self) -> None:
        """
        Close device connections and restore the virgin system.

        After this function is called, the System can be reinitialized
        by calling System.set().
        """
        for dev in self.devs.values():
            if hasattr(dev, "close") and callable(
                dev.close
            ):  # VisaDevice and other custom devices
                dev.close()
            if isinstance(dev, Instrument):  # pymeasure Instrument
                dev.adapter.close()
        # reset devs dictionary to allow reopening
        self.devs.update(self._devs_init)

    @cached_property
    def methods_and_variables(self) -> tuple[list[SystemMethod], list[SystemVariable]]:
        """Find additional system methods and variables."""
        methods: list[SystemMethod] = []
        variables: list[SystemVariable] = []
        cls_name = self.__class__.__name__
        parameter_methods = self._parameter_method_names()
        base_attrs = set(dir(System()))
        if self.stateful:
            base_attrs.update(dir(StatefulSystem))
        for key in dir(self):
            if key in base_attrs or key.startswith("_") or key in parameter_methods:
                continue
            method, variable = self._member_information(key, cls_name)
            if method is not None:
                methods.append(method)
            elif variable is not None:
                variables.append(variable)
        return methods, variables

    def _parameter_method_names(self) -> builtins.set[str]:
        """Return string-based parameter handlers excluded from system metadata."""
        return {
            handler
            for parameter in self.parameters
            for handler in (parameter.setter, parameter.getter)
            if isinstance(handler, str)
        }

    def _member_information(
        self, key: str, prefix: str
    ) -> tuple[SystemMethod | None, SystemVariable | None]:
        """Build method or variable metadata for one public member."""
        attribute = getattr(self, key)
        if not callable(attribute):
            signature = type(attribute).__name__
            return None, SystemVariable(
                name=key,
                prefix=prefix,
                signature=None if signature == "NoneType" else signature,
            )
        try:
            signature = str(self._buildins_signature(getattr(type(self), key)))
        except (TypeError, ValueError):
            signature = None
        return (
            SystemMethod(
                name=key,
                prefix=prefix,
                signature=signature,
                docstring=attribute.__doc__.strip() if attribute.__doc__ else None,
                callable=attribute,
            ),
            None,
        )

    def _buildins_signature(self, function: Callable) -> inspect.Signature:
        """Return signature of the function with only built-ins."""
        signature = inspect.signature(function)
        new_params = []
        for param in signature.parameters.values():
            annotation = param.annotation
            if annotation not in ALLOWED_SIGNATURE_TYPES:
                annotation = inspect.Parameter.empty
            new_params.append(param.replace(annotation=annotation))
        return_annotation = signature.return_annotation
        if return_annotation not in ALLOWED_SIGNATURE_TYPES:
            return_annotation = inspect.Signature.empty
        return signature.replace(parameters=new_params, return_annotation=return_annotation)

    def _add_attributes_to_dict(
        self, info_dict: dict[str, Any], prefix: str | None = None
    ) -> None:
        """
        Add methods and variables from this system to a dictionary.

        Parameters
        ----------
        info_dict : dict
            Dictionary to add the methods/variables information to

        Returns
        -------
        None
            Updates the info_dict in place
        """
        methods, variables = self.methods_and_variables
        cls_name = prefix or self.__class__.__name__
        for items, category in ((methods, "methods"), (variables, "variables")):
            target = info_dict[category]
            for item in items:
                target_key = (
                    f"{cls_name}.{item.name}"
                    if prefix is not None and self.stateful
                    else item.name
                )
                if target_key in target:
                    info_dict["warnings"].append(
                        f"'{item.name}' from '{cls_name}' would shadow a pre-existing entry "
                        f"and will not accesible via 'system'."
                    )
                else:
                    entry = item.model_dump(exclude={"callable"})
                    entry["prefix"] = cls_name
                    target[target_key] = entry

    def grab_information(self) -> dict[str, Any]:
        """
        Obtain meta information from the system.

        Returns
        -------
        system_descriptor : dict
            Returns a dictionary with the list of devices and parameters
            available in the system (name + index) as well as
            custom-defined system methods and variables (if any).
        """
        # generate dictionary from devices, parameters, methods and config
        info = {
            "devices": {},
            "parameters": {},
            "methods": {},
            "variables": {},
            "config": {},
            "warnings": self.warnings,
        }

        self._add_devices_to_information(info)
        self._add_parameters_to_information(info)

        # Add custom methods and variables
        if self.__class__ != MergedSystem:
            self._add_attributes_to_dict(info)

        self._add_config_to_information(info)

        # Note: sensitive_config is intentionally NOT included in the query results
        # to prevent sensitive information from being stored in file headers

        return info

    def _add_devices_to_information(self, info: dict[str, Any]) -> None:
        """Serialize configured devices into system information."""
        for name, entry in self.devs.items():
            device_class = entry[0]
            class_name = getattr(
                device_class, "__name__", str(device_class).split()[0].strip("'<>")
            )
            args = f", args={entry[1]!s}" if len(entry) > 1 and entry[1] else ""
            kwargs = f", kwargs={entry[2]!s}" if len(entry) > 2 and entry[2] else ""
            info["devices"][name] = {
                "name": name,
                "description": f"Device of class {class_name}{args}{kwargs}",
            }

    def _add_parameters_to_information(self, info: dict[str, Any]) -> None:
        """Serialize parameters into system information."""
        for index, parameter in enumerate(self.parameters):
            name = (
                ", ".join(parameter.name) if isinstance(parameter.name, list) else parameter.name
            )
            unit = (
                ", ".join(parameter.unit) if isinstance(parameter.unit, list) else parameter.unit
            )
            info["parameters"][f"param_{index}"] = {
                "name": name,
                "unit": unit,
                "index": index,
                "settable": parameter.setter is not None,
            }

    def _add_config_to_information(self, info: dict[str, Any]) -> None:
        """Serialize non-sensitive configuration into system information."""
        if not self.config:
            return
        name = self.config_section or getattr(self, "__name__", self.__class__.__name__)
        if hasattr(self.config, "model_dump"):
            info["config"][name] = {
                "value": self.config.model_dump(by_alias=True, exclude=set(self._sensitive_keys)),
                "schema": self.config.__class__.model_json_schema(),
            }
            return
        info["config"][name] = self.config

    def init_datafile(self, inputfile: str) -> tuple[str, Path]:
        """
        Prepare the header of a matrix file for the matrix program.

        This function inserts all relevant information including the setstr into
        the header of a matrix file. If the file already exists, no second header
        will be added. The header will also include information queried from the
        devices.

        Parameters
        ----------
        inputfile : str
            Filename of the inputfile to be placed in the header.

        Returns
        -------
        str
            An optional message to be printed.
        Path
            The filename that will be used for the output.
        """
        if not isinstance(self.filename, Path):
            raise TypeError("filename must be initialized as Path object")
        if self.filename.exists():
            self._datafile_initialized = True
            if self._file_mode == "a":
                # in case append is true, do not create a new header
                return ("Appending to datafile", self.filename)
            return ("File already exists, not adding header", self.filename)
        # query info from the devices
        self.query_dict = self.query()
        # prepare file definitions (column header and units)
        telemetry = [list(flatten(self.columns)), list(flatten(self.units))]
        # prepare datafile
        if self.hdf5 is True:
            telemetry.append(list(flatten(self.dtypes)))
            telemetry.append(list(flatten(self.chunks, types=(list,))))
            with h5py.File(self.filename, "w", libver="latest") as data_file:
                data_file.swmr_mode = True
                assert data_file.swmr_mode
                data_file.attrs["input filename"] = inputfile
                data_file.attrs["system filename"] = self.__name__
                # store query dict in hierachical data structure
                save_dict_to_hdf5(self.query_dict, data_file, "system query")

                for dckey, dcvalue in self.dcdata.items():
                    if dckey not in VALID_META_KEYS:
                        # values that are not in the dc specifications are
                        # just added as attribute
                        data_file.attrs[f"{dckey}"] = dcvalue
                    else:
                        data_file.attrs[f"dcterms:{dckey}"] = dcvalue

                init_hdf5_skel(data_file, *telemetry)
        else:
            # the next line could have a real bug?!
            telemetry += [default_separator]  # ty: ignore[unsupported-operator]
            with Path(self.filename).open("w", encoding="utf-8") as data_file:
                for dckey, dcvalue in self.dcdata.items():
                    if dckey not in VALID_META_KEYS:
                        # values that are not in the dc specifications are
                        # just added as attribute
                        if dcvalue is not None:
                            dcentry = dcvalue.replace("\n", "\n## ")
                        dcentry = dcentry.replace('"', '"')
                        data_file.write(f'# {dckey} : "{dcentry}"\n')
                    else:
                        dcentry = dcvalue.replace("\n", "\n## ")
                        dcentry = dcentry.replace('"', '"')
                        data_file.write(f'# dcterms:{dckey} : "{dcentry}"\n')
                data_file.write(f'# input filename : "{inputfile}"\n')
                data_file.write("# system filename : ")
                data_file.write('"' + self.__name__ + '"\n')
                data_file.write("# system query : \n")
                data_file.write(construct_query_string(self.query_dict))

                init_ascii_header(data_file, *telemetry)
        self._datafile_initialized = True
        return ("Creating new datafile", self.filename)

    def take_measurement_point(self, datafilename: Path | None = None):
        """
        Take one reading from all devices and save it to the datafile.

        Parameters
        ----------
        datafilename : Path, optional
            Filename where to save the measurement. If not specified, the
            internally stored filename is used.

        Returns
        -------
        list
            List of values read from the devices.
        """
        dfilename = datafilename or self.filename
        if not isinstance(dfilename, Path):
            raise TypeError("datafilename must be specified or initialized")
        if self.hdf5:

            def h5save(h5d, val):
                csize = h5d.chunks[0]
                h5d.resize(h5d.shape[0] + csize, axis=0)
                h5d[-csize:] = val
                if csize > 1 or len(h5d.chunks) > 1:
                    return f"[{next(flatten(val))}, ...]"
                return val

        return_list = []
        for i, col in enumerate(self.columns):
            value = self.read_value(i)
            if self.hdf5 is True:
                with h5py.File(dfilename, "a", libver="latest") as datafile:
                    datafile.swmr_mode = True
                    assert datafile.swmr_mode
                    if isinstance(col, (list, tuple)):
                        for j, column in enumerate(col):
                            ret = h5save(datafile["data/" + column], value[j])
                            return_list.append(ret)
                    else:
                        ret = h5save(datafile["data/" + col], value)
                        return_list.append(ret)
            else:
                if isinstance(value, (np.ndarray, list, tuple)):
                    # in case we get an iterable cast to list and append
                    return_list += list(value)
                else:
                    return_list.append(value)

        if self.hdf5 is False:
            with Path(dfilename).open("a", encoding="utf-8") as datafile:
                # write datapoint to file
                datafile.write(default_separator.join(str(v) for v in return_list))
                datafile.write("\n")

        # return device readout as list
        return return_list

    def add_comment(self, message: str) -> None:
        """
        Add comment to the datafile.

        Parameters
        ----------
        message : str
            Comment string to be added to the datafile.
        """
        dfilename = self.filename
        if not isinstance(dfilename, Path):
            self.report(
                Message(
                    f"No datafile initialized. Comment '{message}' not added to the datafile.",
                    to_comment=False,
                    to_logfile=True,
                )
            )
            return

        timestamp = time.strftime(f"{matr1x.datetimefmt}", time.localtime())
        if self.hdf5 is True:
            with h5py.File(dfilename, "a", libver="latest") as datafile:
                datafile.swmr_mode = True
                assert datafile.swmr_mode
                comments = datafile["comments"]
                # Resize the dataset to accommodate the new comment string
                current_size = comments.shape[0]
                comments.resize((current_size + 1,))
                new_entry = np.array(
                    [
                        (
                            message,
                            timestamp,
                        )
                    ],
                    dtype=comments.dtype,
                )
                comments[current_size] = new_entry
        else:
            with Path(dfilename).open("a", encoding="utf-8") as datafile:
                # write comment to file
                datafile.write(f"# comment ({timestamp}): ")
                # add continuation line markers
                comment = "\n## ".join(message.splitlines())
                datafile.write(f"{comment}\n")

    def _write_status(self, status: str) -> None:
        """
        Write measurement status to the data file.

        Parameters
        ----------
        status : str
            The status message to be written.
        """
        dfilename = self.filename

        if dfilename is None:
            # if not valid datafile was initialized do nothing.
            return

        if self.hdf5 is True:
            with h5py.File(dfilename, "a", libver="latest") as datafile:
                datafile.swmr_mode = True
                assert datafile.swmr_mode
                datafile.attrs["status"] = status
        else:
            with Path(dfilename).open("a", encoding="utf-8") as datafile:
                # write comment to file
                datafile.write(f"# status: {status}")


class StatefulSystem(System):
    """Base class for systems constructed in one predefined state."""

    stateful: ClassVar[bool] = True
    _DEFAULT_STATE_GROUP: ClassVar[str] = "__default__"

    @classmethod
    def state_declaration(cls) -> tuple[tuple[str, ...], dict[str, str]]:
        """Validate and return states with a complete exclusion-group mapping."""
        states = cls.states
        if not isinstance(states, tuple) or not states:
            raise ValueError("'states' must be a non-empty tuple")
        if any(not isinstance(state, str) or not state.isidentifier() for state in states):
            raise ValueError("every state must be a valid Python identifier")
        if len(set(states)) != len(states):
            raise ValueError("states must be unique")

        declared_groups = cls.state_exclusion_groups
        if not isinstance(declared_groups, dict):
            raise ValueError("'state_exclusion_groups' must be a dictionary")
        unknown_states = set(declared_groups) - set(states)
        if unknown_states:
            unknown = ", ".join(sorted(unknown_states))
            raise ValueError(f"exclusion groups contain unknown states: {unknown}")
        if any(not isinstance(group, str) or not group for group in declared_groups.values()):
            raise ValueError("exclusion-group names must be non-empty strings")

        groups = {state: declared_groups.get(state, cls._DEFAULT_STATE_GROUP) for state in states}
        return states, groups

    def __init__(self, state: str):
        """Initialize a stateful system with its permanent state."""
        states, _ = self.state_declaration()
        if state not in states:
            choices = ", ".join(states)
            raise ValueError(
                f"Stateful system '{self.__class__.__name__}' does not define state "
                f"{state!r}; expected one of: {choices}"
            )
        super().__init__()
        self._state = state

    def load_config(
        self,
        model_class: type[BaseModel],
        section: str,
        sensitive_keys: list[str] | None = None,
    ) -> None:
        """Load the configuration subsection selected by this system's state."""
        assert self.state is not None
        self._load_config_section(
            model_class,
            f"{section}.{self.state}",
            sensitive_keys,
        )


class MergedSystem(System):
    """
    Defines a measurement setup/system of multiple individual systems.

    Gracefully combines the systems into one system instance, so that
    "mobile" parts of a system can be used together with multiple
    "stationary" systems. An example of this is e.g. a cryostat and
    different sets of measurement devices (one for DC and one for AC
    measurements).

    If duplicate parameters are found, they are removed. Parameters
    remain unsorted apart from the timeUTC parameter (used to delay the
    trigger after setting all values).

    Refer to parent System for further attributes.

    Parameters
    ----------
    systems : list[System]
        List of system instances that should be combined into the
        merged system.

    Attributes
    ----------
    subsys : list[System]
        Contains the individual System instances that go into the
        merged system.
    """

    def __init__(self, systems: list[System]):
        self.subsys: list[System] = systems
        # initialize superclass
        # here self.subsys is already used when initializing the
        # filename, so this needs to come here
        super().__init__()
        self._filename: Path | None = None
        self.__name__ = ",".join(
            SystemReference(
                source=subsys.source or subsys.__name__,
                state=subsys.state,
            ).to_token()
            for subsys in self.subsys
        )
        self._parameter_owners: list[tuple[System, int] | None] = []
        parameter_entries = self._merge_subsystems()
        self._add_merged_parameters(parameter_entries)

        self._merge_dcdata()
        self._check_hdf5()

        # add timeUTC if not in system yet
        if "timeUTC" not in self.columns:
            self.add_param("timeUTC", "s", default=None, setter=time.sleep, getter=time.time)
            self._parameter_owners.append(None)

    def _merge_subsystems(self) -> list[tuple[Parameter, System, int]]:
        """Validate and merge all subsystem-owned values."""
        parameter_entries: list[tuple[Parameter, System, int]] = []
        seen_devices: dict[str, System] = {}
        seen_accessors: set[str] = set()
        selected_groups: dict[tuple[str, str, str], str] = {}
        for subsystem in self.subsys:
            self._validate_subsystem(subsystem, seen_accessors, selected_groups)
            self._merge_subsystem_devices(subsystem, seen_devices)
            self._merge_subsystem_config(subsystem)
            parameter_entries.extend(
                (parameter, subsystem, index)
                for index, parameter in enumerate(subsystem.parameters)
            )
            subsystem.merged_system = self
        self._validate_stateful_columns(parameter_entries)
        return parameter_entries

    @staticmethod
    def _validate_subsystem(
        subsystem: System,
        seen_accessors: builtins.set[str],
        selected_groups: dict[tuple[str, str, str], str],
    ) -> None:
        """Ensure the subsystem has a unique accessor and compatible state."""
        if subsystem.accessor_name in seen_accessors:
            raise ValueError(f"Duplicate subsystem accessor name '{subsystem.accessor_name}'")
        seen_accessors.add(subsystem.accessor_name)
        if not isinstance(subsystem, StatefulSystem):
            return
        assert subsystem.state is not None
        _, groups = subsystem.state_declaration()
        source = subsystem.source or subsystem.__class__.__module__
        source_path = Path(source).expanduser()
        identity = (
            str(source_path.resolve()) if source_path.is_file() else subsystem.__class__.__module__
        )
        group = groups[subsystem.state]
        group_key = (identity, subsystem.__class__.__qualname__, group)
        if group_key in selected_groups:
            other_state = selected_groups[group_key]
            raise ValueError(
                f"States '{other_state}' and '{subsystem.state}' from '{source}' "
                f"share exclusion group '{group}'"
            )
        selected_groups[group_key] = subsystem.state

    def _merge_subsystem_devices(self, subsystem: System, seen_devices: dict[str, System]) -> None:
        """Add uniquely named devices and their configuration queries."""
        for device_name, device in subsystem.devs.items():
            if device_name in seen_devices:
                other = seen_devices[device_name]
                raise ValueError(
                    f"Duplicate device name '{device_name}' in "
                    f"'{other.accessor_name}' and '{subsystem.accessor_name}'"
                )
            seen_devices[device_name] = subsystem
            self.devs[device_name] = device
        for device_name, config_params in subsystem.system_config_params.items():
            if device_name in self.system_config_params:
                raise ValueError(f"Duplicate device configuration name '{device_name}'")
            self.system_config_params[device_name] = config_params

    def _merge_subsystem_config(self, subsystem: System) -> None:
        """Merge public and sensitive configuration from one subsystem."""
        config = subsystem.config
        config_dict = (
            config.model_dump(by_alias=True, exclude=set(subsystem._sensitive_keys))
            if hasattr(config, "model_dump")
            else config
        )
        self.config = {**self.config, **config_dict}
        self.sensitive_config = UntypedConfigModel(
            **{**self.sensitive_config.model_dump(), **subsystem.sensitive_config.model_dump()}
        )

    def _validate_stateful_columns(self, entries: list[tuple[Parameter, System, int]]) -> None:
        """Reject ambiguous output columns when a stateful system is present."""
        if not any(subsystem.stateful for subsystem in self.subsys):
            return
        seen_columns: dict[str, System] = {}
        for parameter, subsystem, _ in entries:
            names = (
                parameter.name if isinstance(parameter.name, (list, tuple)) else [parameter.name]
            )
            for column_name in names:
                if column_name in seen_columns:
                    other = seen_columns[column_name]
                    raise ValueError(
                        f"Duplicate final column name '{column_name}' in "
                        f"'{other.accessor_name}' and '{subsystem.accessor_name}'"
                    )
                seen_columns[column_name] = subsystem

    def _add_merged_parameters(self, entries: list[tuple[Parameter, System, int]]) -> None:
        """Append parameters in their legacy order while tracking owners."""
        entries.sort(key=lambda entry: "timeUTC" in self._parameter_names(entry[0]))
        for parameter, subsystem, local_index in entries:
            if not subsystem.stateful and parameter in self.parameters:
                print(f"removing duplicated column {parameter.name} from merged system")  # noqa: T201
                continue
            self.parameters.append(parameter)
            self._parameter_owners.append((subsystem, local_index))

    @staticmethod
    def _parameter_names(parameter: Parameter) -> list[str]:
        """Return all column names represented by one parameter."""
        return parameter.name if isinstance(parameter.name, (list, tuple)) else [parameter.name]

    @classmethod
    def from_references(
        cls,
        references: Iterable[str | Path | SystemReference],
    ) -> Result[MergedSystem, str]:
        """Load, bind, and merge static or stateful system references."""
        normalized: list[SystemReference] = []
        try:
            for value in references:
                reference = SystemReference.from_value(value)
                normalized.append(reference)
        except (ValidationError, ValueError) as error:
            return Error(str(error))

        systems: list[System] = []
        for reference in normalized:
            system = System.from_file(reference)
            if isinstance(system, Error):
                return Error(system.error)
            systems.append(system.value)
        try:
            return Success(cls(systems))
        except ValueError as error:
            return Error(str(error))

    @classmethod
    def from_files(cls, system_filenames: Iterable[str | Path]) -> Result[MergedSystem, str]:
        """
        Merge multiple systems and return a MergedSystem instance.

        Note that the order of the systems matters when setting/reading
        parameters during a measurement. Typically the core system (e.g.
        Magnet-cryostat) comes first and measurement systems afterwards.

        Parameters
        ----------
        system_filenames : list[str | Path]
            List of system paths that should be merged.

        Returns
        -------
        MergedSystem or str.
            MergedSystem instance that contains the description of all
            subsystems or an error message.
        """
        return cls.from_references(system_filenames)

    def __getattr__(self, attr: str) -> Any:
        """
        Return methods/variables from subsystems.

        This method is called when an attribute is not found in the
        MergedSystem instance. First, it searches for a subsystem of
        that name, then, it searches for the attribute in all
        subsystems.

        Parameters
        ----------
        attr : str
            The name of the attribute being accessed.

        Returns
        -------
        Any
            The attribute if found.

        Raises
        ------
        AttributeError
            If the attribute is not found in any subsystem.
        """
        for subsys in self.subsys:
            if attr == subsys.accessor_name:
                return subsys
            if hasattr(subsys, attr):
                return getattr(subsys, attr)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{attr}'")

    def _parameter_index(self, value: int | str) -> int:
        """Resolve a merged parameter name or index."""
        if isinstance(value, str) and value in self.columns:
            return self.columns.index(value)
        if isinstance(value, int) and value < len(self.columns):
            return value
        raise ValueError(f"Invalid index or name: {value}")

    def set_value(
        self, i: int | str, values: float | list[float] | None
    ) -> float | list[float] | None:
        """Set a value through the subsystem that owns the merged parameter."""
        index = self._parameter_index(i)
        owner = self._parameter_owners[index]
        if owner is None:
            return super().set_value(index, values)
        subsystem, local_index = owner
        return subsystem.set_value(local_index, values)

    def trigger_value(self, i: str | int) -> None:
        """Trigger a value through the subsystem that owns the merged parameter."""
        index = self._parameter_index(i)
        owner = self._parameter_owners[index]
        if owner is None:
            super().trigger_value(index)
            return
        subsystem, local_index = owner
        subsystem.trigger_value(local_index)

    def read_value(self, i: str | int) -> Any:
        """Read a value through the subsystem that owns the merged parameter."""
        index = self._parameter_index(i)
        owner = self._parameter_owners[index]
        if owner is None:
            return super().read_value(index)
        subsystem, local_index = owner
        return subsystem.read_value(local_index)

    @property
    def filename(self) -> Path | None:
        """Filename property getter."""
        return self._filename

    @filename.setter
    def filename(self, value: Path | str | None):
        """
        Set the filename property.

        This method is needed to keep the filename on the subsystems in
        sync.

        Parameters
        ----------
        value : Path | str | None
            The new filename value to be set.
        """
        value = Path(value) if value is not None else None
        for subsys in self.subsys:
            subsys.filename = value
        self._filename = value

    @property
    def _datafile_initialized(self) -> bool:
        """Datafile initialized flag property getter."""
        return all(subsys._datafile_initialized for subsys in self.subsys)

    @_datafile_initialized.setter
    def _datafile_initialized(self, value: bool):
        """
        Set the datafile initialized property.

        This method is needed to keep the flag on the subsystems in sync.

        Parameters
        ----------
        value : bool
            The new value to be set.
        """
        for subsys in self.subsys:
            subsys._datafile_initialized = value

    def _merge_dcdata(self) -> None:
        class OrderedSetList:
            def __init__(self):
                self.items = []
                self.seen = set()

            def add(self, value):
                if value not in self.seen:
                    self.items.append(value)
                    self.seen.add(value)

            def __iter__(self):
                return iter(self.items)

        tmpdcdata = defaultdict(OrderedSetList)
        for subsys in self.subsys:
            for key, value in subsys.dcdata.items():
                if key == "date":
                    # skip date
                    continue
                if value:
                    tmpdcdata[key].add(value)
        # merge dcdata
        for key, vlist in tmpdcdata.items():
            self.dcdata[key] = ";".join(vlist)
        # set correct timestamp, overwrites value
        self.dcdata["date"] = time.strftime(f"{matr1x.datetimefmt}", time.localtime())

    def _check_hdf5(self) -> None:
        """Check whether one of the systems requires HDF5."""
        for subsys in self.subsys:
            self.hdf5 = self.hdf5 or subsys.hdf5

    def grab_information(self) -> dict:
        """
        Obtain meta information from the merged system.

        Returns
        -------
        system_descriptor : dict
            System information, methods and parameters from all
            subsystems.
        """
        info = {
            "classes": [],
            "selections": [],
            "devices": {},
            "parameters": {},
            "methods": {},
            "variables": {},
            "config": {},
            "warnings": [],
        }
        base_info = super().grab_information()
        self._merge_base_information(info, base_info)
        for subsystem in self.subsys:
            self._add_subsystem_information(info, subsystem)

        return info

    @staticmethod
    def _merge_base_information(info: dict[str, Any], base_info: dict[str, Any]) -> None:
        """Copy merged devices, parameters, and methods from base metadata."""
        for category in ("devices", "parameters", "methods"):
            info[category].update(base_info.get(category, {}))

    def _add_subsystem_information(self, info: dict[str, Any], subsystem: System) -> None:
        """Add selection, attributes, configuration, and warnings for one subsystem."""
        info["classes"].append(subsystem.accessor_name)
        info["selections"].append(self._selection_information(subsystem).model_dump())
        subsystem._add_attributes_to_dict(info, prefix=subsystem.accessor_name)
        subsystem._add_config_to_information(info)
        if subsystem.warnings:
            info["warnings"].extend(subsystem.warnings)

    @staticmethod
    def _selection_information(subsystem: System) -> SystemSelectionInfo:
        """Build the structured selection record for one subsystem."""
        states: tuple[str, ...] = ()
        groups: dict[str, str] = {}
        if isinstance(subsystem, StatefulSystem):
            states, groups = subsystem.state_declaration()
        return SystemSelectionInfo(
            source=subsystem.source or subsystem.__name__,
            state=subsystem.state,
            stateful=subsystem.stateful,
            states=states,
            state_exclusion_groups=groups,
            class_name=subsystem.__class__.__name__,
            accessor_name=subsystem.accessor_name,
            config_section=subsystem.config_section,
        )

    def set(self, *args, **kwargs):
        """
        Set function that properly initializes the subsystems and updates the list of devices.

        Parameters
        ----------
        *args : tuple
            Arguments that can be used here, currently not used.
        **kwargs : dict
            Keyword arguments that can be used here, currently not used.
        """
        # use individual system for opening devices
        for subsys in self.subsys:
            subsys.set(*args, **kwargs)
        self.refresh_devs()
        # remerge potentially changed dcdata
        self.opened = True

    def query(self) -> dict[str, dict[str, Any]]:
        """Query devices and keep stateful system configuration selection-scoped."""
        if not any(subsystem.stateful for subsystem in self.subsys):
            return super().query()

        result: dict[str, Any] = {}
        system_config: dict[str, Any] = {}
        for subsystem in self.subsys:
            subsystem_result = subsystem.query()
            config = subsystem_result.pop("system_config", None)
            result.update(subsystem_result)
            if config is not None:
                key = subsystem.config_section or subsystem.accessor_name
                system_config[key] = config
        if system_config:
            result["system_config"] = system_config
        return result

    def refresh_devs(self) -> None:
        """
        Refresh the merged device dictionary from all subsystems.

        This is needed after subsystems have been opened individually,
        because System.set replaces device definitions with initialized
        device instances.
        """
        self.devs = {}
        for subsys in self.subsys:
            for device_name, device in subsys.devs.items():
                if device_name in self.devs:
                    raise ValueError(f"Duplicate device name '{device_name}' after initialization")
                self.devs[device_name] = device

    def reset(self, *args, **kwargs):
        """
        Reset function that properly deinitializes the subsystems and updates the list of devices.

        Parameters
        ----------
        *args : tuple
            Arguments that can be used here, currently not used.
        **kwargs : dict
            Keyword arguments that can be used here, currently not used.
        """
        # close all individual systems again
        if "status" in kwargs:
            self._write_status(f"{kwargs['status']}")
        self.opened = False
        for subsys in self.subsys:
            subsys.reset(*args, **kwargs)
