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
Module containing the System class definition and corresponding utility functions.

This module provides the core System class and related utility functions
for data acquisition and instrument control.
"""

import importlib
import inspect
import logging
import os
import re
import sys
import time
import warnings
from collections import defaultdict
from collections.abc import Iterable
from operator import attrgetter
from pathlib import Path

import h5py
import numpy as np
from pymeasure.instruments import Instrument

from . import VALID_META_KEYS, datetimefmt, get_config_dict, output_extension
from .util import (
    DcDict,
    construct_query_string,
    default_separator,
    flatten,
    init_ascii_header,
    init_hdf5_skel,
    module_from_path,
    save_dict_to_hdf5,
)

logger = logging.getLogger(__name__)


def device_query(device_handle, config_params):
    """
    Query the current configuration of the device.

    Parameters
    ----------
    device_handle : VisaDevice or pymeasure device
        Must be an open device that implements the query function.
    config_params : dict
        Dictionary must adhere to the following format. Key is descriptor which
        is used to identify the parameter. The corresponding values must be one
        of:

        * An attribute or method name (if callable without arguments of
          the device object)
        * A callable function (without arguments)
        * A query string for the device
        * A list of the following scheme [method_name : str, args : tuple,
          kwargs : dict]

    Returns
    -------
    dict
        A dictionary of dictionaries containing the configuration of each device.
        Keys of outer dictionary are device names, keys of the inner dictionary
        are parameters that were queried.
    """
    retquery = {}
    for k, q in config_params.items():
        try:
            if isinstance(q, (list, tuple)):
                assert len(q) == 3, f"config_params includes an invalid entry ({q})"
                method = getattr(device_handle, q[0])
                if not callable(method):
                    raise ValueError(f"config_params: method '{q[0]}' is not callable")
                line = str(method(*q[1], **q[2]))
            elif callable(q):
                line = q()
            else:
                try:
                    attr = getattr(device_handle, q)
                except AttributeError:
                    line = str(device_handle.query(q))
                else:
                    if callable(attr):
                        line = attr()
                    else:
                        line = attr
        except Exception:
            # print device identifier upon any exception
            if hasattr(device_handle, "name"):
                devid = device_handle.name
            else:
                devid = device_handle.__class__.__name__
            if hasattr(device_handle, "adapter"):  # it's a pymeasure Instrument
                devid += f" {device_handle.adapter.connection.resource_name}"
            logger.exception("exception during config query of %s", devid)
            raise
        retquery[k] = line
    return retquery


class Parameter:
    """
    Define a measurement parameter.

    This class describes one parameter in matrix. It can define a single or
    multiple columns of the measurement.

    Parameters
    ----------
    name : str or list of str
        Name of the column(s) as string or list of strings.
        If this is a list, make sure unit, default and chunks have same length.
    unit : str or list of str
        Unit of the column(s) as string or list of strings.
    default : float or list of floats, optional
        Default value for parameter. If not None this value is always used unless
        another value is specified in the measurement.
        If None (default), no default value is set/used.
    dtypes : str or list of str, optional
        Dtype specified for saving into hdf5 files, not used for ascii files.
        Default value is "f8" (8 byte float).
    chunks : int or list of int, optional
        Length of the readback value. If a list is returned for a single
        parameter, set to the length of that list.
        If None (default), a chunk of 1 is assumed (readback of parameter is
        single float).
    setter : callable, str, or list, optional
        Function which should be called to set the values.
        Must be one of:

        * A callable function with the call signature
          `func(value, *args, **kwargs)`. For optional arguments and kwargs see
          setter_args/setter_kwargs.
        * A string with a system method/property name. If it corresponds to a
          method its call signature and arguments must be equal to the callable
          function above.
        * A list of the following scheme [device_name : str,
          method_name : str,
          args : tuple,
          kwargs : dict]. The args and kwargs entries are deprecated and should
          be replaced by the setter_args, setter_kwargs parameters.
    getter : callable, str, or list, optional
        Function which should be called to fetch the values.
        Must be one of:

        * A callable function with the call signature
          `func(*args, **kwargs)`. The arguments and kwargs are optional and can
          be supplied via getter_args/getter_kwargs.
        * A string with a system method/property name. If it corresponds to a
          method its call signature and arguments must be equal to the callable
          function above.
        * A list of the following scheme [device_name : str,
          method_name : str,
          args : tuple,
          kwargs : dict]. The args and kwargs entries are deprecated and should
          be replaced by the getter_args, getter_kwargs parameters.
    trigger : callable, str, or list, optional
        Takes a trigger function. The options are equal to the getter options. For
        the optional arguments and kwargs use trigger_args/trigger_kwargs.
    label : str, optional
        Parameters label if different from name. This might be in particular
        needed if an automatically generated label from a name-list is not
        describing the content very well.

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
        name,
        unit,
        setter=None,
        getter=None,
        default=None,
        dtypes=None,
        chunks=None,
        trigger=None,
        setter_args=None,
        setter_kwargs=None,
        getter_args=None,
        getter_kwargs=None,
        trigger_args=None,
        trigger_kwargs=None,
        label=None,
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
        self.setter_args = setter_args
        self.setter_kwargs = setter_kwargs
        self.getter_args = getter_args
        self.getter_kwargs = getter_kwargs
        self.trigger_args = trigger_args
        self.trigger_kwargs = trigger_kwargs
        # set identifiers
        self.unit = self.verify(unit, str)
        self.name = self.verify(name, str)
        if label:
            self.label = self.make_command_line_compatible(label)
        else:
            self.label = self.make_command_line_compatible(self.name)
        if dtypes is None:
            # initialize dtypes to default value if unspecified
            if isinstance(self.unit, (list, tuple)):
                self.dtypes = ["f8"] * len(self.unit)
            else:
                self.dtypes = "f8"
        else:
            self.dtypes = self.verify(dtypes, str)
        # generate defaults or set to None
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
                for chunk in chunks:
                    self.chunks.append(self.verify(chunk, int))
            else:
                self.chunks = self.verify(chunks, int)

    def __lt__(self, other):
        """Define comparison function for sorting."""
        if "timeUTC" in other.name:
            return True
        return False

    def __eq__(self, other):
        """Define equivalence of parameters."""
        if self.name == other.name and self.unit == other.unit:
            return True
        return False

    @staticmethod
    def make_command_line_compatible(s):
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

    def verify(self, param, cast):
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
            if all(isinstance(val, (list, tuple)) for val in param):
                return param
            if all(isinstance(val, cast) for val in param):
                return param
        else:
            if isinstance(param, cast):
                return param
        raise ValueError(
            "At least one element is not of type "
            f"{cast.__name__ if not isinstance(cast, tuple) else cast}"
        )


class System:
    """
    Define a measurement setup/system.

    It is mostly defined by the individual parameters (stored in .parameters)
    that are used in the system as well as the list of devices stored in .devs.
    Additionally, it provides functions to set, trigger and read the individual
    parameters using the specifications provided there.
    Finally, it defines the set, query and reset function, which are used to
    open and initialize the devices, query the device configuration/status and
    return the system to a defined state, respectively.

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
        Contains telemetry according to the Dublin Core specification that can be
        used to generate specific header information.
    system_config_params : dict
        Contains the definition for custom device queries to read the
        configuration. Keys match the device names in .devs.
    """

    def __init__(self, name=None):
        """
        Initialize the System.

        Parameters
        ----------
        name : str, optional
            Name of the measurement system.
        """
        self.__name__ = str(name)
        self._config = get_config_dict("matr1x.scripts.matrix-script")
        # define merged system reference
        self.merged_system: MergedSystem | None = None
        # initialize lists for later use
        self.parameters = []

        # initialize devices dict
        self.devs = {}
        self._devs_init = {}  # variable holding dev init info for reopeneing
        self.query_dict = {}  # store device information query

        # initialize flag to check whether system has been set
        self.opened = False
        self.system_config_params = {}

        # initialize HDF5 flag
        self._hdf5 = False
        # data filename variables
        self._filename: Path | None = None
        self._file_mode = "w"
        self._datafile_initialized = False

        # initialize empty config dictionary for system-specific configuration
        self.config = {}

        # initialize empty sensitive_config dictionary for sensitive information
        # This dictionary will NOT be included in query results or file headers
        self.sensitive_config = {}

        # Dublin Core metadata default entries
        self.dcdata: DcDict = DcDict(
            self,
            creator=None,  # measurement user
            date=time.strftime(f"{datetimefmt}", time.localtime()),
            identifier=None,  # sample name
            relation=None,  # parent sample
            description=None,  # comment
            source=None,  # measurement system
            type=None,  # type of measurement data (e.g., transport)
            publisher=None,  # published of data, e.g., university/institute
            format="text/plain; charset=UTF-8",
            language="en",
        )

    @property
    def filename(self) -> Path | None:
        """Path of the data file used to store measurement data."""
        return self._filename

    @filename.setter
    def filename(self, value: Path | str | None) -> None:
        value = Path(value) if value is not None else None
        self._filename = value

    @classmethod
    def from_file(cls, filename):
        """
        Load a system from a file.

        If a file with the given name cannot be found the system installed files are searched.

        Parameters
        ----------
        filename : str or Path
            Path to file (can include '.py' extension).

        Returns
        -------
        System
            System as defined in the file.
        """
        normfilename = Path(filename).expanduser()
        if normfilename.is_file():
            # create module from path, automatically reloads module
            mod = module_from_path(normfilename)
        else:  # no file found, try installed system files
            if normfilename.suffix == ".py":
                normfilename = normfilename.stem
            normfilestr = str(normfilename)

            try:
                # load module, or reload if exists
                if normfilestr in sys.modules:
                    # force reimport of system
                    mod = sys.modules[normfilestr]
                    importlib.reload(mod)
                else:
                    mod = importlib.import_module(normfilestr)
            except ModuleNotFoundError:
                # try matr1x system as fallback
                modname = "matr1x.systems." + normfilestr
                if modname in sys.modules:
                    mod = sys.modules[modname]
                    importlib.reload(mod)
                else:
                    mod = importlib.import_module("." + normfilestr, "matr1x.systems")
        # get new (v8 System instance)
        try:
            system = getattr(mod, "system")
        except AttributeError:
            # try old variable name (v7 and older)
            system = getattr(mod, "sys")
            warnings.warn(
                "Using deprecated variable name 'sys' - please update to use 'system' instead",
                DeprecationWarning,
            )
        # set the name of the system to reflect the filename
        system.__name__ = str(normfilename)
        return system

    @property
    def hdf5(self):
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
        name,
        unit,
        setter=None,
        getter=None,
        default=None,
        dtype=None,
        chunks=None,
        trigger=None,
        setter_args=None,
        setter_kwargs=None,
        getter_args=None,
        getter_kwargs=None,
        trigger_args=None,
        trigger_kwargs=None,
    ):
        """
        Add a parameter to the list of parameters.

        For definition of the passed parameters, see class :class:`Parameter`.
        """
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
            Device instance (must not be initialized nor opened).
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
    def columns(self) -> list[str]:
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
    def units(self) -> list[str]:
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
    def dtypes(self) -> list[str | list | tuple]:
        """
        Return a list of dtypes extracted from parameters.

        Returns
        -------
        list
            List containing the dtype of each parameter
        """
        return [parm.dtypes for parm in self.parameters]

    def _print(self, *args, **kwargs):
        """
        Extend builtin print by optional adding the printout to the datafile.

        The behavior of this function depends on the config option
        matr1x.scripts.matrix-script.print_to_comment

        Parameters
        ----------
        *args : tuple
            Arguments to pass to print function.
        **kwargs : dict
            Keyword arguments to pass to print function.
        """
        if self._config["print_to_comment"] and self._datafile_initialized:
            message = " ".join(str(arg) for arg in args)
            self.add_comment(message.lstrip("\r"))
        print(*args, **kwargs)

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
            file_extension = ".h5" + output_extension
        else:
            file_extension = output_extension
        refileext = file_extension.replace(".", r"\.")

        if outputfile:
            datafile = Path(outputfile).expanduser()
        elif inputfile:  # no output file given -> input filename as template
            datafile = Path(inputfile).expanduser().with_suffix("")
            # generate fallback option for the datafile name
        else:  # no output nor input file, generate from system names
            timestamp = time.strftime(datetimefmt, time.localtime())
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
            candidate_file = outfile.with_name(f"{outfile.stem}_{extension}").with_suffix(
                file_extension
            )
            if not candidate_file.exists():
                break
        if extension is None:
            raise RuntimeError("Could not find available filename after 10000 attempts")
        # as last resort start a new file
        # append the next possible number as file extension
        outfile = outfile.with_name(f"{outfile.stem}_{extension}").with_suffix(file_extension)
        self.filename = outfile
        self._file_mode = "w"
        return outfile

    def clear_parameters(self):
        """Clear all system parameters."""
        del self.parameters
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
        print(info)

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
        if isinstance(i, int):
            idx = i
        elif i in self.columns:
            idx = self.columns.index(i)
        else:
            raise TypeError(f"column '{i}' could not be identified")

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

    def trigger_value(self, i):
        """
        Trigger devices specified in column i if trigger function is provided.

        Parameters
        ----------
        i : int or str
            Index or name of parameter that is supposed to be triggered.
        """
        if i in self.columns:
            idx = self.columns.index(i)
        else:
            idx = i
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

    def trigger(self):
        """Trigger measurements of all parameters in the system."""
        for i in range(len(self.columns)):
            self.trigger_value(i)

    def read_value(self, i):
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
        if i in self.columns:
            idx = self.columns.index(i)
        else:
            idx = i
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
            if isinstance(self.parameters[i].name, (list, tuple)):
                return ["nan"] * len(self.parameters[i].name)
            return "nan"

    def set(self, *args, **kwargs):
        """
        Handle device opening/initialization.

        For format of devs refer to .add_dev

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
                    print(f"Exception occured when initializing device {key}")
                    raise
            else:
                # device was already initialized prior the set call.
                # do not try to reinitialize or something is amiss.
                pass
        self.opened = True

    def query(self):
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
        retquery = {}
        # iterate over devices to get their config
        for key, dev in self.devs.items():
            # get device
            try:
                if key in self.system_config_params.keys() and hasattr(dev, "config_params"):
                    # device config_params are specified in system and device
                    retquery[key] = device_query(
                        dev, {**self.system_config_params[key], **dev.config_params}
                    )
                elif key in self.system_config_params.keys():
                    # device config query is specified in system
                    retquery[key] = device_query(dev, self.system_config_params[key])
                elif hasattr(dev, "config_params"):
                    # device has config query specified, should return dictionary
                    retquery[key] = device_query(dev, dev.config_params)
                else:
                    # no query details available
                    retquery[key] = {}
            except Exception as error:
                print(f"system: error: could not access '{key}': {dev} {error}")
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
            for key, value in self.config.items():
                if key.startswith("_"):
                    continue
                retquery["system_config"][key] = value

        return retquery

    def reset(self, *args, **kwargs):
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

    def close(self):
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

    def settable_columns(self):
        """
        Obtain the settable columns of the system.

        Used by matrix and matrix_script to verify that the input file/input script
        was generated with the same system as the one that is currently used.

        Returns
        -------
        settables : list
            List of booleans describing whether a parameter is settable or not.
        flattened_settable_names : list
            List of strings containing the names of the settable columns.
        flattened_settable_units : list
            List of strings containing the units of the settable columns.
        """
        settables = [(False if par.setter is None else True) for par in self.parameters]
        flattened_settable_names = []
        flattened_settable_units = []
        for names, units, settable in zip(self.columns, self.units, settables):
            if settable is True:
                if isinstance(names, (list, tuple)):
                    for name, unit in zip(names, units):
                        flattened_settable_names.append(name)
                        flattened_settable_units.append(unit)
                else:
                    flattened_settable_names.append(names)
                    flattened_settable_units.append(units)
        return (settables, flattened_settable_names, flattened_settable_units)

    def _add_method_info_to_dict(self, obj, info_dict, prefix="System"):
        """
        Add methods and variables from an object to a dictionary.

        Parameters
        ----------
        obj : object
            The object to extract methods and variables from
        info_dict : dict
            Dictionary to add the methods/variables information to
        prefix : str, optional
            Prefix to use in the description (default: "System")

        Returns
        -------
        None
            Updates the info_dict in place
        """
        # Find methods used as parameter getters/setters
        parameter_methods = set()
        if hasattr(obj, "parameters"):
            for param in obj.parameters:
                # Check if setter/getter is a string (method name) and add to exclusion list
                if isinstance(param.setter, str):
                    parameter_methods.add(param.setter)
                if isinstance(param.getter, str):
                    parameter_methods.add(param.getter)

        for key in dir(obj):
            if (
                key not in dir(System())
                and not key.startswith("_")
                and key not in parameter_methods
            ):
                method = getattr(obj, key)
                if callable(method):
                    # Get method signature if possible
                    signature = ""
                    doc_summary = ""
                    try:
                        signature = str(inspect.signature(method))
                        if method.__doc__:
                            doc_lines = method.__doc__.strip().split("\n")
                            if doc_lines:
                                doc_summary = doc_lines[0].strip()
                    except Exception:
                        pass

                    description = f"{prefix} method"
                    if signature:
                        description += f" - {key}{signature}"
                    if doc_summary:
                        description += f" - {doc_summary}"

                    info_dict["methods"][key] = {
                        "name": key,
                        "description": description,
                    }
                else:
                    # Get variable value summary if possible
                    value_str = ""
                    try:
                        value = getattr(obj, key)
                        value_type = type(value).__name__
                        value_str = f" ({value_type})"
                    except Exception:
                        pass

                    info_dict["methods"][key] = {
                        "name": key,
                        "description": f"{prefix} variable{value_str}",
                    }

    def grab_information(self, settables=False):
        """
        Obtain meta information from the system.

        Depending on settables, returns either a human-readable description of
        the system (devices and parameters) or the number of settable columns.

        This function is used by matrix_script to verify the system still
        corresponds to the definition with which the script was created.
        Additionally, it is used to generate the help string.

        Parameters
        ----------
        settables : bool, optional
            Controls whether to return the settable columns of the system (if
            True) or a human-readable string with the system definition (if
            False). Default is False.

        Returns
        -------
        system_descriptor : dict or tuple
            If settables is False, returns a dictionary with the list of devices
            and parameters available in the system (name + index) as well as
            custom-defined system methods and variables (if any).
            If settables is True, returns a tuple containing information about
            the settable columns of the system.
        """
        if settables is True:
            # return only settables
            return self.settable_columns()

        # generate dictionary from devices, parameters, methods and config
        info = {"devices": {}, "parameters": {}, "methods": {}, "config": {}}

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
            # Store the parameter name (either as string or joined list)
            name = param.name
            if isinstance(name, list):
                # For list parameters, join the names with comma
                display_name = ", ".join(name)
            else:
                display_name = name

            # Store the parameter unit (either as string or joined list)
            unit = param.unit
            if isinstance(unit, list):
                # For list parameters, join the units with comma
                display_unit = ", ".join(unit)
            else:
                display_unit = unit

            # Create an entry with the index as key
            # (use string prefix to avoid numeric parsing issues)
            param_key = f"param_{index}"
            if param.setter is not None:
                info["parameters"][param_key] = {
                    "name": display_name,
                    "unit": display_unit,
                    "description": f"Settable parameter at index {index}",
                    "index": index,
                    "settable": True,
                }
            else:
                info["parameters"][param_key] = {
                    "name": display_name,
                    "unit": display_unit,
                    "description": f"Read-only parameter at index {index}",
                    "index": index,
                    "settable": False,
                }

        # Add custom methods and variables
        if self.__class__ != MergedSystem:
            self._add_method_info_to_dict(self, info)

        # Add config options organized by system name (excluding sensitive_config)
        if self.config:
            system_name = self.__name__
            info["config"][system_name] = self.config

        # Note: sensitive_config is intentionally NOT included in the query results
        # to prevent sensitive information from being stored in file headers

        return info

    def init_datafile(self, inputfile, output_filename=None):
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
        output_filename : str, optional
            Filename of the output file.
        """
        if output_filename:
            self.filename = Path(output_filename)
        if not isinstance(self.filename, Path):
            raise TypeError("filename must be initialized as Path object")
        if self.filename.exists():
            self._datafile_initialized = True
            if not output_filename and self._file_mode == "a":
                # in case append is true, do not create a new header
                print(f"Appending to datafile: {self.filename}")
                return
            print(f"File {self.filename} already exists, not adding header")
            return
        # query info from the devices
        self.query_dict = self.query()
        # prepare file definitions (column header and units)
        telemetry = [list(flatten(self.columns)), list(flatten(self.units))]
        # prepare datafile
        print(f"Creating new datafile: {self.filename}")
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
                    elif dcvalue is None:
                        # mark non-existing value
                        data_file.attrs[f"dcterms:{dckey}"] = "__None__"
                    else:
                        data_file.attrs[f"dcterms:{dckey}"] = dcvalue

                init_hdf5_skel(data_file, *telemetry)
        else:
            telemetry += [default_separator]
            with Path(self.filename).open("w", encoding="utf-8") as data_file:
                for dckey, dcvalue in self.dcdata.items():
                    if dckey not in VALID_META_KEYS.keys():
                        # values that are not in the dc specifications are
                        # just added as attribute
                        if dcvalue is not None:
                            dcentry = dcvalue.replace("\n", "\n## ")
                        dcentry = dcentry.replace('"', '"')
                        data_file.write(f'# {dckey} : "{dcentry}"\n')
                    elif dcvalue is None:
                        data_file.write(f"# dcterms:{dckey} : None\n")
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

    def take_measurement_point(self, datafilename=None):
        """
        Take one reading from all devices and save it to the datafile.

        Parameters
        ----------
        datafilename : str or None, optional
            Filename where to save the measurement. If not specified, the
            internally stored filename is used.

        Returns
        -------
        list
            List of values read from the devices.
        """
        dfilename = Path(datafilename) if datafilename else self.filename
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

    def add_comment(self, message: str, datafilename=None) -> None:
        """
        Add comment to the datafile.

        Parameters
        ----------
        message : str
            Comment string to be added to the datafile.
        datafilename : str or None, optional
            Filename where to save the measurement. If not specified, the
            internally stored filename is used.

        Returns
        -------
        None
        """
        dfilename = Path(datafilename) if datafilename else self.filename
        if not isinstance(dfilename, Path):
            # if not valid datafile was initialized do nothing.
            return
        if not message:
            # do not add empty comment
            return

        timestamp = time.strftime(f"{datetimefmt}", time.localtime())
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

    def _write_status(self, status: str, datafilename=None) -> None:
        """
        Write measurement status to the data file.

        Parameters
        ----------
        status : str
            The status message to be written.
        datafilename : str, optional
            The name of the data file to write to. If None, uses the internally stored filename.
        """
        dfilename = datafilename if datafilename else self.filename

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

    Gracefully combines the systems into one system instance, so that "mobile"
    parts of a system can be used together with multiple "stationary" systems.
    An example of this is e.g. a cryostat and different sets of measurement
    devices (one for DC and one for AC measurements).

    If duplicate parameters are found, they are removed. Parameters remain
    unsorted apart from the timeUTC parameter (used to delay the trigger after
    setting all values).

    Refer to parent System for further attributes.

    Parameters
    ----------
    systems : list
        List of system instances that should be combined into the merged system.

    Attributes
    ----------
    subsys : list
        Contains the individual System instances that go into the merged system.
    """

    def __init__(self, systems):
        # save subsystems into system
        self.subsys = systems
        # initialize superclass
        # here self.subsys is already used when initializing the
        # filename, so this needs to come here
        super().__init__()
        self._filename: Path | None = None
        # define __name__
        self.__name__ = ",".join([subsys.__name__ for subsys in self.subsys])
        # merge devices, config_dicts, config and parameters
        for subsys in self.subsys:
            self.devs = {**self.devs, **subsys.devs}
            self.system_config_params = {
                **self.system_config_params,
                **subsys.system_config_params,
            }
            self.config = {**self.config, **subsys.config}
            self.sensitive_config = {**self.sensitive_config, **subsys.sensitive_config}
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
                print(f"removing duplicated column {param.name} from merged system")
                self.parameters.remove(param)
        self.parameters.reverse()

        # add timeUTC if not in system yet
        if "timeUTC" not in self.columns:
            self.add_param("timeUTC", "s", default=None, setter=time.sleep, getter=time.time)

    @classmethod
    def from_files(cls, system_filenames):
        """
        Merge multiple systems and return a MergedSystem instance.

        Note that the order of the systems matters when setting/reading
        parameters during a measurement. Typically the core system (e.g.
        Magnet-cryostat) comes first and measurement systems afterwards.

        Parameters
        ----------
        system_filenames : list
            List of system paths that should be merged.

        Returns
        -------
        MergedSystem
            MergedSystem instance that contains the description of all
            subsystems.
        """
        systems = []
        for filename in system_filenames:
            # import the individual systems
            systems.append(System.from_file(filename))
        # return merged system
        return cls(systems)

    def __getattr__(self, attr):
        """
        Return methods/variables from subsystems if they do not exist in the MergedSystem.

        This method is called when an attribute is not found in the MergedSystem instance.
        It searches for the attribute in all subsystems and returns it if found.

        Parameters
        ----------
        attr : str
            The name of the attribute being accessed.

        Returns
        -------
        Any
            The attribute from a subsystem, if found.

        Raises
        ------
        AttributeError
            If the attribute is not found in any subsystem.
        """
        for subsys in self.subsys:
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

        This method is needed to keep the filename on the subsystems in sync.

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
    def _datafile_initialized(self):
        """Datafile initialized flag property getter."""
        return all(subsys._datafile_initialized for subsys in self.subsys)

    @_datafile_initialized.setter
    def _datafile_initialized(self, value):
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

    def _merge_dcdata(self):
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
        self.dcdata["date"] = time.strftime(f"{datetimefmt}", time.localtime())

    def _check_hdf5(self):
        """Check whether one of the systems requires HDF5."""
        for subsys in self.subsys:
            self.hdf5 = self.hdf5 or subsys.hdf5

    def grab_information(self, settables=False):
        """
        Obtain meta information from the merged system.

        Returns system information, methods and parameters from all subsystems.

        Parameters
        ----------
        settables : bool, optional
            Controls whether to return the settable columns of the system (if
            True) or the dictionary with information (if False). Default is False.

        Returns
        -------
        system_descriptor : dict or tuple
            If settables is False, returns a dictionary with methods and parameters.
            If settables is True, returns a tuple containing information about
            the settable columns of the system.
        """
        if settables is True:
            # return only settables
            return self.settable_columns()

        # Dictionary to store all information
        info = {"devices": {}, "parameters": {}, "methods": {}, "config": {}}

        # Add information from the base System class
        base_info = super().grab_information(settables)
        if isinstance(base_info, dict):
            # Merge the categorized dictionaries
            if "devices" in base_info:
                info["devices"].update(base_info["devices"])
            if "parameters" in base_info:
                info["parameters"].update(base_info["parameters"])
            if "methods" in base_info:
                info["methods"].update(base_info["methods"])
            # Skip config from base class to avoid duplication -
            # we'll add individual subsystem configs below

        # Add information from all subsystems
        for subsys in self.subsys:
            self._add_method_info_to_dict(subsys, info, prefix="Subsystem")

            # Add config information from each subsystem
            subsys_config = subsys.config
            if subsys_config:
                subsys_name = getattr(subsys, "__name__", str(subsys.__class__.__name__))
                info["config"][subsys_name] = subsys_config

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
        # merge list of devices
        # needs to be redone after the devices are opened, since
        # the content of the dictionary is replaced here
        self.devs = {}
        for subsys in self.subsys:
            self.devs = {**self.devs, **subsys.devs}
        # remerge potentially changed dcdata
        self.opened = True

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
