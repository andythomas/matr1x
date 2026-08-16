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
from typing import Any, TypeGuard, TypeVar

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
    SystemMethod,
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
            if key in ref.keys():
                if ref[key]:
                    # only append to available value if it exists (not None)
                    ref[key] = sep.join([ref[key], value])
                    return
            ref[key] = sep[1:] + value
        else:
            # append meta data to current current array
            if key in self.keys():
                if self[key]:
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
            if dtypes is not None:
                if len(name) != len(dtypes):
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
                    ValueError(f"Invalid type, expected list for chunks, but received {chunks}.")
            else:
                self.chunks = self.verify(chunks, int)

    def __lt__(self, other: object) -> bool:
        """Define comparison function for sorting."""
        if isinstance(other, Parameter):
            if "timeUTC" in other.name:
                return True
        return False

    def __eq__(self, other: object) -> bool:
        """Define equivalence of parameters."""
        if isinstance(other, Parameter):
            if self.name == other.name and self.unit == other.unit:
                return True
        return False

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
        Optional instance name. ControlWindow binds a valid name here as the
        subsystem's accessor name after merging.
    """

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

        self._config = matr1x.config.matr1x.scripts.matrix_script
        # define merged system reference
        self.merged_system: MergedSystem | None = None
        # initialize lists for later use
        self.parameters: list[Parameter] = []

        # initialize devices dict
        self.devs = {}
        self._devs_init = {}  # variable holding dev init info for reopeneing
        self.query_dict = {}  # store device information query

        # Allow warnings
        self.warnings: list[str] = []

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
        if self.name is not None and self.name.isidentifier() and not keyword.iskeyword(self.name):
            return self.name
        return self.__class__.__name__

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
            # Use defaults from the model if validation fails
            try:
                validated_config = model_class()
            except (ValidationError, TypeError, ValueError):
                logger.debug(
                    "Could not instantiate default config for %s after validation error",
                    section,
                    exc_info=True,
                )
                if not hasattr(model_class, "model_construct"):
                    raise
                validated_config = model_class.model_construct()

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
    def from_file(cls, filename: Path) -> Result["System", str]:
        """
        Load a system from a file.

        If a file with the given name cannot be found the system
        installed files are searched. A system module must define exactly one
        local ``System`` subclass, which is instantiated after import. Legacy
        initialized ``system`` exports remain supported with a
        deprecation warning.

        Parameters
        ----------
        filename : str or Path
            Path to file (can include '.py' extension).

        Returns
        -------
        System or ErrorMessage
            System as defined in the file or an error string.
        """
        normfilename = filename.expanduser()
        legacy_warning: str | None = None
        if normfilename.is_file():
            try:
                mod = module_from_path(normfilename)
            except PermissionError:
                return Error("System file is not readable.")
            except ImportError as error:
                return Error(f"{type(error).__name__}: {error}")
        else:
            if normfilename.suffix == ".py":
                normfilename = normfilename.stem
            normfilestr = str(normfilename)
            candidates = [normfilestr, f"matr1x.systems.{normfilestr}"]
            for name in candidates:
                try:
                    if name in sys.modules:
                        mod = importlib.reload(sys.modules[name])
                    else:
                        mod = importlib.import_module(name)
                    break

                except ModuleNotFoundError as e:
                    if e.name != name:
                        return Error(f"{type(e).__name__}: {e}")
                    continue
                except ImportError as e:
                    return Error(f"{type(e).__name__}: {e}")
            else:
                return Error(
                    f"Could neither import '{normfilestr}' nor 'matr1x.systems.{normfilestr}'"
                )
        legacy_name = "system"
        system = getattr(mod, legacy_name, None)

        if isinstance(system, System):
            legacy_warning = (
                f"Using an initialized System instance exported as '{legacy_name}' is deprecated; "
                "define exactly one local System subclass instead."
            )
        else:
            # Imported base classes do not qualify: the system file itself
            # must define the single concrete class that Matrix instantiates.
            system_classes = {
                value
                for value in vars(mod).values()
                if inspect.isclass(value)
                and value is not System
                and issubclass(value, System)
                and value.__module__ == mod.__name__
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
            system = system_classes.pop()()
        # set the name of the system to reflect the filename
        system.__name__ = str(normfilename)
        if legacy_warning:
            system.warnings.append(legacy_warning)
        return Success(system)

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
                if not isinstance(parm.name, (list, tuple)):
                    self.hdf5 = True
                elif any([isinstance(p, (tuple,)) for p in parm.chunks]):
                    self.hdf5 = True
                elif any([p > 1 for p in parm.chunks]):
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
            entry = [descriptor, tuple(), kwargs]
        elif args is not None:
            entry = [descriptor, args]
        else:
            # device instance can be initialized without arguments
            entry = [descriptor, tuple()]
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

        For this to function the method needs to be injected into the MergedSystem.

        Parameters
        ----------
        data : MeasurementData
            The data to report.
        """
        # Defer to merged_system if it is present
        if self.merged_system:
            self.merged_system.report(data)

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
                info += f" with list-like property: {str(func)}."
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
                if key in self.system_config_params.keys() and hasattr(dev, "config_params"):
                    # device config_params are specified in system and device
                    retquery[key] = System._device_query(
                        dev, {**self.system_config_params[key], **dev.config_params}
                    )
                elif key in self.system_config_params.keys():
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
                    pass
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
            if hasattr(dev, "close"):  # VisaDevice and other custom devices
                if callable(dev.close):
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
        parameter_methods = set()
        cls_name = self.__class__.__name__
        for param in self.parameters:
            # Check if setter/getter is a string (method name) and add to exclusion list
            if isinstance(param.setter, str):
                parameter_methods.add(param.setter)
            if isinstance(param.getter, str):
                parameter_methods.add(param.getter)
        base_attrs = set(dir(System()))
        for key in dir(self):
            if key not in base_attrs and not key.startswith("_") and key not in parameter_methods:
                attribute = getattr(self, key)
                if callable(attribute):
                    signature = None
                    docstring = None
                    try:
                        signature = str(self._buildins_signature(getattr(type(self), key)))
                    except (TypeError, ValueError):
                        pass
                    if attribute.__doc__:
                        docstring = attribute.__doc__.strip()
                    method = SystemMethod(
                        name=key,
                        prefix=cls_name,
                        signature=signature,
                        docstring=docstring,
                        callable=attribute,
                    )
                    methods.append(method)
                else:
                    type_var = type(attribute).__name__
                    if type_var == "NoneType":
                        type_var = None
                    variable = SystemVariable(name=key, prefix=cls_name, signature=type_var)
                    variables.append(variable)
        return methods, variables

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

    def _add_attributes_to_dict(self, info_dict: dict[str, Any]) -> None:
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
        cls_name = self.__class__.__name__
        for items, category in ((methods, "methods"), (variables, "variables")):
            target = info_dict[category]
            for item in items:
                if item.name in target:
                    info_dict["warnings"].append(
                        f"'{item.name}' from '{cls_name}' would shadow a pre-existing entry "
                        f"and will not accesible via 'system'."
                    )
                else:
                    target[item.name] = item.model_dump(exclude={"callable"})

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

        # Add devices
        for dev, device_entry in self.devs.items():
            # Extract device class name from the device entry
            # Device class is the first element in the device_entry list
            device_class = device_entry[0]
            if hasattr(device_class, "__name__"):
                class_name = device_class.__name__
            else:
                class_name = str(device_class).split()[0].strip("'<>")

            # Extract arguments and keyword arguments
            args_str = ""
            if len(device_entry) > 1:
                args = device_entry[1]
                if args and len(args) > 0:
                    args_str = f", args={str(args)}"

            kwargs_str = ""
            if len(device_entry) > 2:
                kwargs = device_entry[2]
                if kwargs and len(kwargs) > 0:
                    kwargs_str = f", kwargs={str(kwargs)}"

            # Format the device information
            info["devices"][dev] = {
                "name": dev,
                "description": f"Device of class {class_name}{args_str}{kwargs_str}",
            }

        # Add parameters
        for index, param in enumerate(self.parameters):
            name = param.name
            display_name = ", ".join(name) if isinstance(name, list) else name
            unit = param.unit
            display_unit = ", ".join(unit) if isinstance(unit, list) else unit
            # Create an entry with the index as key
            # (use string prefix to avoid numeric parsing issues)
            param_key = f"param_{index}"
            info["parameters"][param_key] = {
                "name": display_name,
                "unit": display_unit,
                "index": index,
                "settable": param.setter is not None,
            }

        # Add custom methods and variables
        if self.__class__ != MergedSystem:
            self._add_attributes_to_dict(info)

        system_name = getattr(self, "__name__", str(self.__class__.__name__))

        # Add config options organized by system name (excluding sensitive_config)
        # Add configuration of this system
        if self.config:
            if hasattr(self.config, "model_dump"):
                info["config"][system_name] = {
                    "value": self.config.model_dump(
                        by_alias=True, exclude=set(self._sensitive_keys)
                    ),
                    "schema": self.config.__class__.model_json_schema(),
                }
            else:
                info["config"][system_name] = self.config

        # Note: sensitive_config is intentionally NOT included in the query results
        # to prevent sensitive information from being stored in file headers

        return info

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
                    if dckey not in VALID_META_KEYS.keys():
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
                    if dckey not in VALID_META_KEYS.keys():
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
        self.__name__ = ",".join([subsys.__name__ for subsys in self.subsys])
        seen_accessors: set[str] = set()
        for subsys in self.subsys:
            if subsys.accessor_name in seen_accessors:
                raise ValueError(f"Duplicate subsystem accessor name '{subsys.accessor_name}'")
            seen_accessors.add(subsys.accessor_name)
        # merge devices, config_dicts, config and parameters
        for subsys in self.subsys:
            self.devs = {**self.devs, **subsys.devs}
            self.system_config_params = {
                **self.system_config_params,
                **subsys.system_config_params,
            }
            if hasattr(subsys.config, "model_dump"):
                subsys_config_dict = subsys.config.model_dump(
                    by_alias=True, exclude=set(subsys._sensitive_keys)
                )
            else:
                subsys_config_dict = subsys.config
            self.config: dict[str, Any] = {**self.config, **subsys_config_dict}
            self.sensitive_config = UntypedConfigModel(
                **{**self.sensitive_config.model_dump(), **subsys.sensitive_config.model_dump()}
            )
            self.parameters += subsys.parameters
            subsys.merged_system = self
        self._merge_dcdata()
        self._check_hdf5()
        # sort parameters to have timeUTC as last column
        self.parameters.sort()
        # remove duplicated columns
        self.parameters.reverse()
        for param in self.parameters:
            if self.parameters.count(param) > 1:
                print(f"removing duplicated column {param.name} from merged system")  # noqa: T201
                self.parameters.remove(param)
        self.parameters.reverse()

        # add timeUTC if not in system yet
        if "timeUTC" not in self.columns:
            self.add_param("timeUTC", "s", default=None, setter=time.sleep, getter=time.time)

    @classmethod
    def from_files(cls, system_filenames: Iterable[str | Path]) -> Result["MergedSystem", str]:
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
        systems: list[System] = []
        for filename in system_filenames:
            system = System.from_file(Path(filename))
            if isinstance(system, Error):
                return Error(system.error)
            systems.append(system.value)
        return Success(cls(systems))

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
            "devices": {},
            "parameters": {},
            "methods": {},
            "variables": {},
            "config": {},
            "warnings": [],
        }
        base_info = super().grab_information()
        # Merge the categorized dictionaries
        if "devices" in base_info:
            info["devices"].update(base_info["devices"])
        if "parameters" in base_info:
            info["parameters"].update(base_info["parameters"])
        if "methods" in base_info:
            info["methods"].update(base_info["methods"])
        # Skip config from base class to avoid duplication -
        # we'll add individual subsystem configs below
        for subsys in self.subsys:
            info["classes"].append(subsys.__class__.__name__)
            subsys._add_attributes_to_dict(info)

            subsys_config = subsys.config
            if subsys_config:
                subsys_name = getattr(subsys, "__name__", str(subsys.__class__.__name__))
                if hasattr(subsys_config, "model_dump"):
                    info["config"][subsys_name] = {
                        "value": subsys_config.model_dump(
                            by_alias=True, exclude=set(subsys._sensitive_keys)
                        ),
                        "schema": subsys_config.__class__.model_json_schema(),
                    }
                else:
                    info["config"][subsys_name] = subsys_config

            if hasattr(subsys, "warnings") and subsys.warnings:
                info["warnings"].extend(subsys.warnings)

        return info

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

    def refresh_devs(self) -> None:
        """
        Refresh the merged device dictionary from all subsystems.

        This is needed after subsystems have been opened individually,
        because System.set replaces device definitions with initialized
        device instances.
        """
        self.devs = {}
        for subsys in self.subsys:
            self.devs = {**self.devs, **subsys.devs}

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
