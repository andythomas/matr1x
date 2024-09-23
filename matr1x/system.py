# This file is part of a software collection for data aquisition (matr1x).
# Copyright (C) 2024 matr1x developers
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
This module contains the System class definition and corresponding utility
functions
"""
import collections
import importlib
import os
import re
import time
from os.path import exists, expanduser, isfile, splitext

import h5py
import numpy as np
from pymeasure.instruments import Instrument

from . import VALID_META_KEYS, datetimefmt, output_extension
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


def device_query(device_handle, config_params):
    """
    Takes device_handle and config_params to perform a query of the current
    configuration of the device

    Parameters
    -------
    device_handle : VisaDevice or pymeasure device
      must be an open device that implements the query function
    config_params : dict
      dictionary must adhere to the following format. Key is descriptor which
      is used to identify the parameter the corresponding values must be one
      of:

        * an attribute or method name (if callable without arguments of
          the device object)
        * a callable function (without arguments)
        * a query string for the device
        * a list of the following scheme [method_name : str, args : tuple,
          kwargs : dict]

    Returns
    -------
    retdict : dict
      A dictionary of dictionaries containing the configuration of each device.
      keys of outer dictionary are device names, keys of the inner dictionary
      are parameters that were queried
    """
    retquery = {}
    for k, q in config_params.items():
        try:
            if isinstance(q, (list, tuple)):
                assert len(q) == 3, \
                    f"config_params includes an invalid entry ({q})"
                if hasattr(device_handle, q[0]) and callable(
                        getattr(device_handle, q[0])):
                    method = getattr(device_handle, q[0])
                    line = str(method(*q[1], **q[2]))
                else:
                    raise ValueError("config_params: method of entry "
                                     f"{q} not callable or non-existent")
            elif callable(q):
                line = q()
            elif hasattr(device_handle, q):
                attr = getattr(device_handle, q)
                if callable(attr):
                    line = attr()
                else:
                    line = attr
            else:
                line = str(device_handle.query(q))
        except Exception:
            # print device identifier upon any exception
            if hasattr(device_handle, "name"):
                devid = device_handle.name
            else:
                devid = device_handle.__class__.__name__
            if hasattr(device_handle, "adapter"):  # its a pymeasure Instrument
                devid += device_handle.connection.resource_name
            print(f"exception during config query of {devid}")
            raise
        retquery[k] = line
    return retquery


class Parameter():
    """
    Defines a measurement _`parameter`

    This class describes one parameter in matrix. It can define a single or
    multiple columns of the measurement depending.

    Parameters
    ----------
    name: str or list of str
      name of the column(s) as string or list of strings.
      If this is a list, make sure unit, default and chunks have same length).
    unit: str or list of str
      unit of the column(s) as string or list of strings.
    default: float or list of floats
      default value for parameter, if not None this value is always unless
      another value is specified in the measurement.
      If None (default), no default value is set/used.
    dtypes: string or list of strings
      dtype specified for saving into hdf5 files, not used for ascii files
      default value is "f8" (8 byte float)
    chunks: int or list of ints
      length of the readback value, if a list is returned for a single
      parameter, set to the length of that list.
      If None (default), a chunk of 1 is assumed (readback of parameter is
      single float).
    setter:
      function which should be called to set the values.
      Must be one of:

        * a callable function with the call signature
          `func(value, *args, **kwargs)`. For optional arguments and kwargs see
          setter_args/setter_kwargs.
        * a string with a system method/property name. If it corresponds to a
          method its call signature and arguments must be equal to the callable
          function above.
        * a list of the following scheme [device_name : str,
          method_name : str,
          args : tuple,
          kwargs : dict]. The args and kwargs entries are deprecated and should
          be replaced by the setter_args, setter_kwargs parameters.
    getter:
      function which should be called to fetch the values.
      Must be one of:

        * a callable function with the call signature
          `func(*args, **kwargs)`. The arguments and kwargs are optional and can
          be supplied via getter_args/getter_kwargs.
        * a string with a system method/property name. If it corresponds to a
          method its call signature and arguments must be equal to the callable
          function above.
        * a list of the following scheme [device_name : str,
          method_name : str,
          args : tuple,
          kwargs : dict]. The args and kwargs entries are deprecated and should
          be replaced by the getter_args, getter_kwargs parameters.
    trigger:
      takes a trigger function. The options are equal to the getter options. For
      the optional arguments and kwargs use trigger_args/trigger_kwargs.

    Attributes
    ------
    All parameters are set as attributes of same name.

    Raises
    ------
    ValueError, TypeError
    """

    def __init__(self, name, unit, setter=None, getter=None,
                 default=None, dtypes=None, chunks=None, trigger=None,
                 setter_args=None, setter_kwargs=None,
                 getter_args=None, getter_kwargs=None,
                 trigger_args=None, trigger_kwargs=None):
        # general error checking
        if any([isinstance(name, (list, tuple)),
                isinstance(unit, (list, tuple))]):
            if not (isinstance(unit, (list, tuple)) and
                    isinstance(name, (list, tuple)) and
                    (dtypes is None or isinstance(dtypes, (list, type)))):
                raise TypeError("Name, unit must be of the same type"
                                " together with dtypes "
                                "(i.e. all list or all string, "
                                "dtypes can also be None)")
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
                        raise ValueError(
                            f"{key} must have same length as name")

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
        if dtypes is None:
            # initialize dtypes to default value if unspecified
            if isinstance(self.unit, (list, tuple)):
                self.dtypes = ["f8"]*len(self.unit)
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
        """define comparison function for sorting"""
        if "timeUTC" in other.name:
            return True
        return False

    def __eq__(self, other):
        """define equivalence of parameters"""
        if self.name == other.name and self.unit == other.unit:
            return True
        return False

    def verify(self, param, cast):
        """verifies param is of correct type or raises error"""
        if isinstance(param, (list, tuple)):
            if all(isinstance(val, (list, tuple)) for val in param):
                return param
            if all(isinstance(val, cast) for val in param):
                return param
        else:
            if isinstance(param, cast):
                return param
        raise ValueError("At least one element is not of type "
                         f"{cast.__name__ if not isinstance(cast, tuple) else cast}")


class System:
    """
    Defines a measurement setup/system

    It is mostly defined by the individual parameters (stored in .parameters)
    that are used in the system as well as the list of devices stored in .devs.
    Additionally, it provides functions to set, trigger and read the individual
    parameters using the specifications provided there.
    Finally, it defines the set, query and reset function, which are used to
    open and initialize the devices, query the device configuration/status and
    return the system to a defined state, respectively.

    Attributes
    -------
    parameters : list
      contains the individual parameters that make up the system.
    columns : list
      contains the column names extracted from the individual parameters.
    units : list
      contains the units extracted from the individual parameters.
    dtypes : list
      contains the dtypes extracted from the individual parameters.
    default_values : list
      contains the default_values extracted from the individual parameters.
    chunks : list
      contains the chunks extracted from the individual parameters.
    devs : dict
      contains the individual devices that belong to the system
    dcdata : dict
      contains telemetry according to the Dublin Core specification that can be
      used to generate specific header information.
    system_config_params : dict
      contains the definition for custom device queries to read the
      configuration. Keys match the device names in .devs.
    """

    def __init__(self, name=None):
        """
        Parameters
        ----------
        name : str, optional
          name of the measurement system
        """
        self.__name__ = str(name)
        # define merged system reference
        self.merged_system = None
        # initialize lists for later use
        self.parameters = []
        self.columns = []
        self.default_values = []
        self.units = []
        self.dtypes = []
        self.chunks = []

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
        self.filename = None
        self._file_mode = 'a'

        # Dublin Core metadata default entries
        self.dcdata = DcDict(
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

    @classmethod
    def from_file(cls, filename):
        """
        Utility function to load a system from a file. If a file with the given name
        cannot be found the system installed files are searched.

        Parameters
        ------
        filename : string
          path to file (can include '.py' extension)

        Returns
        -----
        system : System
          System as defined in the file
        """
        normfilename = filename.strip()
        if isfile(normfilename):
            mod = module_from_path(normfilename)
        else:  # no file found, try installed system files
            if normfilename.endswith(".py"):
                normfilename = splitext(normfilename)[0]

            try:
                mod = importlib.import_module(normfilename)
            except ModuleNotFoundError:
                # try matr1x system as fallback
                mod = importlib.import_module(
                    "." + normfilename, "matr1x.systems")
            mod.sys.__name__ = normfilename
        return mod.sys

    @property
    def hdf5(self):
        """
        defines whether the system requires the hdf5 format (i.e. has
        readout parameters that provide a full list of values)
        """
        return self._hdf5

    @hdf5.setter
    def hdf5(self, value):
        self._hdf5 = value
        if value is True:
            self.dcdata["format"] = "application/x-hdf5"
        else:
            self.dcdata["format"] = "text/plain; charset=UTF-8"

    def add_param(self, name, unit, setter=None, getter=None,
                  default=None, dtype=None, chunks=None, trigger=None,
                  setter_args=None, setter_kwargs=None,
                  getter_args=None, getter_kwargs=None,
                  trigger_args=None, trigger_kwargs=None):
        """
        Adds a parameter to the list of parameters, for definition
        of the passed parameters :ref:`check parameter
        class<parameter>`
        """
        self.parameters.append(Parameter(name, unit,
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
                                         trigger_kwargs=trigger_kwargs))
        self.add_parameter_to_lists(self.parameters[-1])

    def add_dev(self, name, descriptor, args=None, kwargs=None,
                config_params=None):
        """
        Adds a device to the device dictionary.

        Parameters
        ----
        name : str
          unique device name, will be dictionary key
        descriptor : object/instance
          device instance (must not be initialized nor opened)
        args : tuple
          tuple containing args passed upon device initialization.
        kwargs : dict
          dictionary with kwargs passed upon device initialization
        config_params : dict
          dictionary with query configuration, see query function for details
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

    def add_parameter_to_lists(self, parm):
        """
        Takes an individual parameter and appends it to the lists
        These lists are used to interact with the matrix as well as the
        sweep_generator.
        """
        self.columns.append(parm.name)
        self.units.append(parm.unit)
        self.default_values.append(parm.default)
        self.chunks.append(parm.chunks)
        self.dtypes.append(parm.dtypes)
        # check if hdf5 format has to be used
        if isinstance(parm.chunks, (list, tuple)):
            if not isinstance(parm.name, (list, tuple)):
                self.hdf5 = True
            elif any([isinstance(p, (tuple,)) for p in parm.chunks]):
                self.hdf5 = True
            elif any([p > 1 for p in parm.chunks]):
                self.hdf5 = True
        elif parm.chunks > 1:
            self.hdf5 = True

    def generate_datafilename(self, outputfile="", inputfile="", append=False):
        """
        generate output datafile name. No file should be overwritten. If
        append=True an existing datafile can be amended. In all other cases a
        new file will name is generated.

        The datafilename will be generated preferentially from the outputfile
        or the inputfile-name. An appropriate extension is automatically added.

        Parameters
        ----------
        outputfile: str, optional
          output filename which should be used. Potentially a running number
          will be added to avoid overwriting an existing file
        inputfile: str, optional
          if outputfile is empty this string will be used to generate a
          datafile name
        append: bool, optional
          flag to decide if one should append to an potentially existing datafile

        Returns
        -------
        datafilename
        """
        # check whether hdf5 is required and change output extensions
        if self.hdf5 is True:
            # append h5 to filename to discern filetypes
            file_extension = ".h5" + output_extension
        else:
            file_extension = output_extension
        refileext = file_extension.replace('.', r'\.')

        if outputfile:
            datafile = expanduser(outputfile)
        elif inputfile:  # no output file given -> input filename as template
            datafile = expanduser(splitext(inputfile)[0])
            # generate fallback option for the datafile name
        else:  # no output nor input file, generate from system names
            timestamp = time.strftime(datetimefmt, time.localtime())
            _, filename = os.path.split(self.__name__)
            if filename.endswith(".py"):
                filename = filename[:-3]
            datafile = f"{timestamp}_{filename}"
            if os.name == 'nt':
                # Windows does not like : in filenames
                datafile = datafile.replace(":", "")
        # check if file extension was provided
        if not re.search(f"{refileext}$", datafile):
            datafile = re.sub(r"(\.h5)?\.ma\d$", "", datafile) + file_extension
        if not exists(datafile):
            # use the unmodified file name
            self.filename = datafile
            self._file_mode = "w"
            return self.filename
        if append:
            self.filename = datafile
            self._file_mode = "a"
            return self.filename

        # in case extension and running number are already attached to
        # the filename, replace in outputfile
        outfile = re.sub(r"(_\d+)?(\.h5)?\.ma\d$", "", datafile)

        # check filename and increase "extension number" to protect existing
        # data
        for extension in range(1, 10000):
            if exists(f"{outfile}_{extension}{file_extension}"):
                continue
            break

        # as last resort start a new file
        # append the next possible number as file extension
        self.filename = f"{outfile}_{extension}{file_extension}"
        self._file_mode = "w"
        return self.filename

    def clear_parameters(self):
        """
        Clears all system parameters and the lists that have been generated
        """
        del (self.parameters, self.columns, self.default_values,
             self.units, self.dtypes, self.chunks)
        self.parameters = []
        self.columns = []
        self.default_values = []
        self.units = []
        self.dtypes = []
        self.chunks = []

    def generate_lists(self):
        """
        Generate the necessary lists from the parameters defined above
        These lists are used to interact with the matrix as well as the
        sweep_generator.
        This command is only used when a new system is dynamically created from
        a list of parameters
        """
        for parm in self.parameters:
            self.add_parameter_to_lists(parm)

    def _inform_exception(self, i, func, action):
        """
        Print information about an exception.
        In best case identify a device related to the exception.

        Parameters
        ----------
        i : index or name of the parameter where the exception occurred
        func : function, parameter name or list used when the parameter occurred
        action : string with action (verb) during which the exception occurred
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

    def set_value(self, i, values):
        """
        Sets a parameter i to values.

        Takes the column name or index and sets the corresponding parameter as
        defined by the setter of the parameter, take care to send a correct
        list.
        If the setter is None, returns the send values (most likely nan or None)

        Parameters
        ------
        i : int or str
          index or name of the parameter that should be set
        values : float or list of floats
          values that should be written to the parameter/device

        Returns
        ------
        values : float or list of floats
          returns the values that have been set to the device
        """
        if i in self.columns:
            idx = self.columns.index(i)
        elif isinstance(i, int):
            idx = i
        else:
            raise TypeError(f"column '{i}' could not be identified")

        setter = self.parameters[idx].setter
        args = self.parameters[idx].setter_args
        kwargs = self.parameters[idx].setter_kwargs
        if setter is None or values is None:
            return values

        if isinstance(values, collections.abc.Iterable):
            # parameter list, verify values
            values = list(map(float, values))
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
        """set values by a function call.

        The function call includes optional arguments and kwarguments only when
        they are not None.
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
        """set attribute or call the method with the value as argument

        Parameters
        ----------
        attr_name : str
         attribute or method name as string
        value : any
         value to which the attribute should be set
        args : list or None
         optional arguments to the setter function
        kwargs : dict or None
         optional keyword arguments to the setter function
        """
        attr = getattr(self, attr_name)
        if callable(attr):  # attr is method
            self._set_by_func(attr, value, args, kwargs)
        else:  # attr_name corresponds to an attribute
            setattr(self, attr_name, value)

    def _set_by_list(self, setter, value, args, kwargs):
        """set some device property.

        The device property can be a callable method or an attribute. The
        callable method can receive optional additional arguments and keyword
        arguments which will be preferentially taken form the `args`/`kwargs`
        arguments. If those are not given the third and forth entry of the
        setter list are used instead.

        Parameters
        ----------
        setter : list
         list of device name, property name/method, optional arguments, kwargs
        value : any
         value to which the device property should be set
        args : list or None
         optional arguments to the setter function
        kwargs : dict or None
         optional keyword arguments to the setter function
        """
        dev = self.devs[setter[0]]
        attr = getattr(dev, setter[1])
        if callable(attr):  # callable device method
            if len(setter) == 3:  # optional arguments
                self._set_by_func(attr, value, args or setter[2], kwargs)
            elif len(setter) == 4:  # optional arguments and kwargs
                self._set_by_func(
                    attr, value, args or setter[2], kwargs or setter[3])
            else:
                self._set_by_func(attr, value, args, kwargs)
        else:
            setattr(dev, setter[1], value)

    def trigger_value(self, i):
        """
        Triggers devices specified in column i if trigger function is provided

        Parameters
        -----
        i : int or str
          index or name of parameter that is supposed to be triggered
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
                    self._call_by_list(trigger, args, kwargs,
                                       needs_callable=True)
            except Exception:
                self._inform_exception(i, trigger, "triggering")
                raise

    def _call_func(self, func, args, kwargs):
        """call a function with optional arguments/kwargs.

        The function call includes arguments and kwarguments only when they are
        not None.
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
        """call some method which is specified by its attribute name.

        The attribute name correspond to a callable method, otherwise no action
        will be taken. An exception will be raised if no callable method can be
        found and needs_callable is True.

        Parameters
        ----------
        attr_name : str
         attribute name of a method.
        args : list or None
         optional arguments to the callable method
        kwargs : dict or None
         optional keyword arguments to the callable method
        needs_callable: bool
         if True an exception will be raised if no callable method is found.
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
        """call some device property.

        The device property must be a callable method, otherwise no action will
        be taken. An exception will be raised if no callable method can be found
        and needs_callable is True.

        Parameters
        ----------
        listdef : list
         list of device name, property name/method, optional arguments, kwargs
        args : list or None
         optional arguments to the device method
        kwargs : dict or None
         optional keyword arguments to the device method
        needs_callable: bool
         if True an exception will be raised if no callable method is found.
        """
        dev = self.devs[listdef[0]]
        attr = getattr(dev, listdef[1])
        if callable(attr):
            if len(listdef) == 3:  # optional arguments
                ret = self._call_func(attr, args or listdef[2], kwargs)
            elif len(listdef) == 4:  # optional arguments and kwargs
                ret = self._call_func(
                    attr, args or listdef[2], kwargs or listdef[3])
            else:
                ret = self._call_func(attr, args, kwargs)
        elif needs_callable:
            raise AttributeError("Function is not callable")
        else:
            ret = attr
        return ret

    def trigger(self):
        """
        triggers a measurements of all parameters in the system.
        """
        for i in range(len(self.columns)):
            self.trigger_value(i)

    def read_value(self, i):
        """
        Fetches readout value of parameter using the getter.

        Takes the column name or index and reads the corresponding parameter
        as defined by the getter of the parameter.
        If the getter is None, returns nan

        Parameters
        -----
        i : int or str
          index or name of parameter that is supposed to be triggered

        Returns
        -----
        readout : type returned by getter or "nan"
          returns the readout from the device/parameter getter
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
        Basic set function which handles device opening/initialization.

        For format of devs refer to .add_dev

        Parameters
        -----
        args : tuple
          args that can be used here, currently not used
        kwargs : dict
          kwargs than be used here, currently not used
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
        Starts a query to all devices (system needs to be set before this
        function is called) to read their configuration state.

        Parameters provided in system or device need to be one of:
          * an attribute or method name (if callable without arguments of
            the device object
          * a query string for the device
          * a list of the following scheme [method_name : str, args : tuple,
            kwargs : dict]

        Refer also to matr1x.devices.visadevice for further information.

        Returns
        -----
        retquery : dict
          dictionary with dictionaries containing the configuration of each
          device.
        """
        if self.opened is False:
            raise ValueError("System must be set before query can be called")
        retquery = {}
        # iterate over devices to get their config
        for key, dev in self.devs.items():
            # get device
            try:
                if key in self.system_config_params.keys() and hasattr(
                        dev, "config_params"):
                    # device config_params are specified in system and device
                    retquery[key] = device_query(
                        dev, {**self.system_config_params[key],
                              **dev.config_params})
                elif key in self.system_config_params.keys():
                    # device config query is specified in system
                    retquery[key] = device_query(dev,
                                                 self.system_config_params[key])
                elif hasattr(dev, "config_params"):
                    # device has config query specified, should return dictionary
                    retquery[key] = device_query(dev, dev.config_params)
                else:
                    # no query details available
                    retquery[key] = {}
            except Exception as error:
                print(
                    f"system: error: could not access '{key}': {dev} {error}")
                raise
        # iterate over remaining keys in system_config_params
        for key in self.system_config_params.keys() - self.devs.keys():
            obj = self.system_config_params[key]
            if callable(obj):
                retquery[key] = obj()
            else:
                retquery[key] = obj
        return retquery

    def reset(self, *args, **kwargs):
        """
        General reset function for deinitialization of system, clears the read buffer of the instrument.

        The device will be left open/initialized unless the system is closed or
        deleted.

        Parameters
        -----
        args : tuple
          args that can be used here, currently not used
        kwargs : dict
          kwargs than be used here, currently not used
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
        close device connections and restore the virgin system.

        After this function is called the System can be reinitialized by
        calling System.set().
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
        Function to obtain the settable columns. Used by matrix and
        matrix_script to verify that the input file/input script was generated
        with the same system as the one that is currently used.

        Returns
        -------
        settables : list
          list of bools describing whether a parameter is settable or not
        flattened_settable_names : list
          list of strings containing the names of the settable columns
        flattened_settable_units : list
          list of strings containing the units of the settable columns
        """
        settables = [(False if par.setter is None else True)
                     for par in self.parameters]
        flattened_settable_names = []
        flattened_settable_units = []
        for names, units, settable in zip(self.columns,
                                          self.units,
                                          settables):
            if settable is True:
                if isinstance(names, (list, tuple)):
                    for name, unit in zip(names, units):
                        flattened_settable_names.append(name)
                        flattened_settable_units.append(unit)
                else:
                    flattened_settable_names.append(names)
                    flattened_settable_units.append(units)
        return (settables, flattened_settable_names, flattened_settable_units)

    def grab_information(self, settables=False):
        """
        Utility function to obtain meta information from a system

        Depending on settables, a human readable description of the system (devices
        and parameters) is returned, or the number of settable columns.

        The function is used by matrix_script to verify the system still
        corresponds to the definition with which the script was created.
        Additionally, it is used to generate the help string.

        Parameters
        ----------
        settables : bool, optional
          controls whether to return the settable columns of the system (if
          True) or whether a human readable string with the system
          definition is returned.

        Returns
        -------
        system_descriptor : string
          Returns a string with the list of devices and a string with
          parameters that are available in the system (name + index) as well
          as customly defined system methods and variables (if any)
          Alternatively, returns the settable columns of the system
        """
        if settables is True:
            # return only settables
            return self.settable_columns()

        # generate string from devices, iterates over subsystems
        dev_list = []
        for dev, devtype in self.devs.items():
            dev_list.append(f"{dev} <> {devtype}\n")
        dev_string = "device <> device type\n----------\n" + \
            "".join(dev_list)
        # generate string from setable parameters
        par_list = []
        for index, param in enumerate(self.parameters):
            if param.setter is not None:
                par_list.append(f"{index} <y> {param.name}\n")
            else:
                par_list.append(f"{index} <n> {param.name}\n")
        par_string = ("index <settable> parameter\n----------\n" +
                      "".join(par_list))
        # base methods of System should not be added to the output.
        # Same is true if the class is derived from MergedSystem.
        if self.__class__ != MergedSystem:
            fun_list = []
            for key in dir(self):
                if key not in dir(System()) and not key.startswith("_"):
                    fun_list.append(key)
            if len(fun_list) > 0:
                fun_string = ("system methods and parameters\n----------\n" +
                              "\n".join(fun_list))
                return "----------\n".join((dev_string, par_string,
                                            fun_string))
        return "----------\n".join((dev_string, par_string))

    def init_datafile(self, inputfile, output_filename=None):
        """
        prepares the header of a matrix file for the matrix program, inserts all
        relevant information including the setstr. If the file already exists no
        second header will be added.

        The header will also include information queried from the devices.

        Arguments
        ----
        inputfile : str
          filename of the inputfile to be placed in the header
        output_filename : str, optional
          filename of the ouput file
        """
        if output_filename:
            self.filename = output_filename
        if not output_filename and self._file_mode == "a":
            # in case append is true, do not create a new header
            print(f"Appending to datafile: {self.filename}")
            return
        if exists(self.filename):
            return
        # query info from the devices
        self.query_dict = self.query()
        # prepare file definitions (column header and units)
        telemetry = [list(flatten(self.columns)),
                     list(flatten(self.units))]
        # prepare datafile
        print(f"Creating new datafile: {self.filename}")
        if self.hdf5 is True:
            telemetry.append(list(flatten(self.dtypes)))
            telemetry.append(list(flatten(self.chunks, types=(list, ))))
            with h5py.File(self.filename, 'w', libver='latest') as data_file:
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
            with open(self.filename, 'w', encoding="utf-8") as data_file:
                for dckey, dcvalue in self.dcdata.items():
                    if dckey not in VALID_META_KEYS.keys():
                        # values that are not in the dc specifications are
                        # just added as attribute
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
                data_file.write("\"" + self.__name__ + "\"\n")
                data_file.write("# system query : \n")
                data_file.write(construct_query_string(self.query_dict))

                init_ascii_header(data_file, *telemetry)

    def take_measurement_point(self, datafilename=None):
        """
        takes one reading from all devices and saves it to the datafile

        Parameters
        ----------
        datafilename: None, str, optional
         filename where to save the measurement. If not specified the
         internally stored filename is used.
        """
        dfilename = datafilename if datafilename else self.filename
        if self.hdf5:

            def h5save(h5d, val):
                csize = h5d.chunks[0]
                h5d.resize(h5d.shape[0]+csize, axis=0)
                h5d[-csize:] = val
                if csize > 1 or len(h5d.chunks) > 1:
                    return f"[{next(flatten(val))}, ...]"
                return val

        return_list = []
        for i, col in enumerate(self.columns):
            value = self.read_value(i)
            if self.hdf5 is True:
                with h5py.File(dfilename, "a", libver='latest') as datafile:
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
            with open(dfilename, "a", encoding="utf-8") as datafile:
                # write datapoint to file
                datafile.write(default_separator.join(str(v)
                               for v in return_list))
                datafile.write("\n")

        # return device readout as list
        return return_list

    def add_comment(self, message: str, datafilename=None) -> None:
        """
        Adds comment to the datafile.

        Parameters
        ----------
        message: str
          comment string to be added to the datafile
        datafilename: None, str, optional
          filename where to save the measurement. If not specified the
          internally stored filename is used.
        """
        dfilename = datafilename if datafilename else self.filename

        if dfilename is None:
            # if not valid datafile was initialized do nothing.
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
            with open(dfilename, "a", encoding="utf-8") as datafile:
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

        Returns
        -------
        None
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
            with open(dfilename, "a", encoding="utf-8") as datafile:
                # write comment to file
                datafile.write(f"# status: {status}")


class MergedSystem(System):
    """
    Defines a measurement setup/system containing of multiple individual systems

    Gracefully combines the systems into one system instance, so that "mobile"
    parts of a system can be used together with multiple "stationary" systems.
    An example of this is e.g. a cryostat and different sets of measurement
    devices (one for DC and one for AC measurements).

    If duplicate parameters are found, they are removed. Parameters remain
    unsorted apart from the timeUTC parameter (used to delay the trigger after
    setting all values).

    Refer to parent System for further attributes.

    Parameters
    -----
    systems : list
      list of system instances that should be combined into the merged system.

    Attributes
    -----
    subsys : list
      contains the individual System instances that go into the merged system.
    """

    def __init__(self, systems):
        # save subsystems into system
        self.subsys = systems
        # initialize superclass
        # here self.subsys is already used when initializing the filename, so this needs to come here
        super().__init__()
        # define __name__
        self.__name__ = ",".join([subsys.__name__ for subsys in
                                  self.subsys])
        # merge devices, config_dicts and parameters
        for sys in self.subsys:
            self.devs = {**self.devs, **sys.devs}
            self.system_config_params = {**self.system_config_params,
                                         **sys.system_config_params}
            self.parameters += sys.parameters
            sys.merged_system = self
        self._merge_dcdata()
        self._check_hdf5()
        # sort parameters to have timeUTC as last column
        self.parameters.sort()
        # remove duplicated columns
        self.parameters.reverse()
        for param in self.parameters:
            if self.parameters.count(param) > 1:
                print(
                    f"removing duplicated column {param.name} from merged system")
                self.parameters.remove(param)
        self.parameters.reverse()

        # generate lists for new system
        self.generate_lists()

        # add timeUTC if not in system yet
        if "timeUTC" not in self.columns:
            self.add_param("timeUTC", "s", default=None,
                           setter=time.sleep, getter=time.time)

    @classmethod
    def from_files(cls, system_filenames):
        """
        Merges multiple systems and return a MergedSystem-instance.
        Note that the order of the systems matters when setting/reading parameters during a measurement.
        Typically the core system (e.g. Magnet-cryostat) comes first and measurement systems afterwards.

        Parameters
        -----
        system_filenames : list
          list of system paths that should be merged

        Returns
        ----
        system : MergedSystem
          MergedSystem instance that contains the descirption of all subsystems
        """
        systems = []
        for filename in system_filenames:
            # import the individual systems
            systems.append(System.from_file(filename))
        # return merged system
        return cls(systems)

    def __getattr__(self, attr):
        """
        Return methods/variables from subsystems if they do not exist in the
        MergedSystem.
        """
        for sys in self.subsys:
            if hasattr(sys, attr):
                return getattr(sys, attr)
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{attr}'")

    @property
    def filename(self):
        """Filename property getter."""
        return self._filename

    @filename.setter
    def filename(self, value):
        """The filename property setter.

        This is needed to keep the filename on the subsystems in sync."""
        for sys in self.subsys:
            sys.filename = value
        self._filename = value

    def _merge_dcdata(self):
        tmpdcdata = collections.defaultdict(set)
        for sys in self.subsys:
            for key, value in sys.dcdata.items():
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
        """check whether one of the systems requires HDF5."""
        for sys in self.subsys:
            self.hdf5 = self.hdf5 or sys.hdf5

    def grab_information(self, settables=False):
        """reimplement System method to return subsystem information."""
        ret_string = super().grab_information(settables)
        if settables is False:
            fun_list = []
            for sys in self.subsys:
                for key in dir(sys):
                    if key not in dir(System()) and not key.startswith("_"):
                        fun_list.append(key)
            if len(fun_list) > 0:
                # if system functions are present, also add them to return
                # string
                fun_string = ("system methods and parameters\n----------\n" +
                              "\n".join(fun_list))
                return "----------\n".join((ret_string, fun_string))
        return ret_string

    def set(self, *args, **kwargs):
        """
        set function that properly initializess the subsystems and updates
        the list of devices

        Parameters
        -----
        args : tuple
          args that can be used here, currently not used
        kwargs : dict
          kwargs than be used here, currently not used
        """
        # use individual system for opening devices
        for sys in self.subsys:
            sys.set(*args, **kwargs)
        # merge list of devices
        # needs to be redone after the devices are opened, since
        # the content of the dictionary is replaced here
        self.devs = {}
        for sys in self.subsys:
            self.devs = {**self.devs, **sys.devs}
        # remerge potentially changed dcdata
        self.opened = True

    def reset(self, *args, **kwargs):
        """
        reset function that properly deinitializess the subsystems and updates
        the list of devices

        Parameters
        -----
        args : tuple
          args that can be used here, currently not used
        kwargs : dict
          kwargs than be used here, currently not used
        """
        # close all individual systems again
        if "status" in kwargs:
            self._write_status(f"{kwargs['status']}")
        self.opened = False
        for sys in self.subsys:
            sys.reset(*args, **kwargs)
