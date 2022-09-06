# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
"""
This module contains the System class definition and corresponding utility
functions
"""
import collections
import time

from . import datetimefmt


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
    ------
    name: str or list of str
      name of the column(s) as string or list of strings.
      If this is a list, make sure unit, default and chunks have same length).
    unit: str or list of str
      unit of the column(s) as string or list of strings.
    default: float or list of floats
      default value for parameter, if not None this value is always unless
      another value is specified in the measurement.
      If None (default), no default value is set/used.
    chunks: int or list of ints
      length of the readback value, if a list is returned for a single
      parameter, set to the length of that list.
      If None (default), a chunk of 1 is assumed (readback of parameter is
      single float).
    setter:
      function which should be called to set the values.
      Must be one of:

        * a callable function (that takes exactly one argument)
        * a list of the following scheme [device_name : str,
          method_name : str,
          args : tuple,
          kwargs : dict]
    getter:
      function which should be called to fetch the values.
      Must be one of:

        * a callable function (without arguments)
        * a list of the following scheme [device_name : str,
          method_name : str,
          args : tuple,
          kwargs : dict]
    trigger:
      takes a trigger function.
      Must be one of:

        * a callable function (without arguments)
        * a list of the following scheme [device_name : str,
          method_name : str,
          args : tuple,
          kwargs : dict]

    Attributes
    ------
    All parameters are set as attributes of same name.

    Raises
    ------
    ValueError, TypeError
    """

    def __init__(self, name, unit, setter=None, getter=None,
                 default=None, chunks=None, trigger=None):
        # general error checking
        if isinstance(name, (list, tuple)) or isinstance(unit, (list, tuple)):
            if not (isinstance(unit, (list, tuple)) and
                    isinstance(name, (list, tuple))):
                raise TypeError("Name and unit must be of the same type"
                                "(i.e. both list or both string)")
            elif len(name) != len(unit):
                raise ValueError("Name and unit have unequal length")
            for val, key in zip([chunks, default], ["chunks", "default"]):
                if val is not None:
                    if not isinstance(val, (list, tuple)):
                        raise TypeError(f"{key} must be list if name is list")
                    elif len(name) != len(val):
                        raise ValueError(
                            f"{key} must have same length as name")

        # set functions
        self.setter = setter
        self.getter = getter
        self.trigger = trigger
        # set identifiers
        self.unit = self.verify(unit, str)
        self.name = self.verify(name, str)
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
            self.chunks = self.verify(chunks, int)

    def __lt__(self, other):
        """define comparison function for sorting"""
        if "timeUTC" in other.name:
            return True
        else:
            return False

    def __eq__(self, other):
        """define equivalence of parameters"""
        if self.name == other.name and self.unit == other.unit:
            return True

    def verify(self, param, cast):
        """verifies param is of correct type or raises error"""
        if isinstance(param, (list, tuple)):
            if all([isinstance(val, cast) for val in param]):
                return param
        else:
            if isinstance(param, cast):
                return param
        raise ValueError("At least one element is not of type "
                         f"{cast.__name__ if not isinstance(cast, tuple) else cast}")


class System(object):
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

    def __init__(self):
        # initialize lists for later use
        self.parameters = []
        self.columns = []
        self.default_values = []
        self.units = []
        self.chunks = []

        # initialize devices dict
        self.devs = {}

        # initialize flag to check whether system has been set
        self.opened = False
        self.system_config_params = {}

        # initialize HDF5 flag
        self._hdf5 = False

        # Dublin Core metadata default entries
        self.dcdata = dict(
            Creator=None,  # measurement user
            Date=time.strftime(f"{datetimefmt}", time.localtime()),
            Identifier=None,  # sample name
            Description=None,  # comment
            Source="matrix powered measurement system",  # measurement system
            Type="Transport data",
            Publisher="matr1x",
            Format="text/plain; charset=UTF-8",
            Language="en",
        )

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
            self.dcdata["Format"] = "application/x-hdf5"
        else:
            self.dcdata["Format"] = "text/plain; charset=UTF-8"

    def add_param(self, name, unit, setter=None, getter=None,
                  default=None, chunks=None, trigger=None):
        """
        Adds a parameter to the list of parameters, for definition
        of the passed parameters :ref:`check parameter
        class<parameter>`
        """
        self.parameters.append(Parameter(name, unit,
                                         setter=setter,
                                         getter=getter,
                                         default=default,
                                         trigger=trigger,
                                         chunks=chunks))
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
            self.devs[name] = [descriptor, args, kwargs]
        elif kwargs is not None:
            self.devs[name] = [descriptor, tuple(), kwargs]
        elif args is not None:
            self.devs[name] = [descriptor, args]
        else:
            # device instance can be initialized without arguments
            self.devs[name] = [descriptor, tuple()]
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
        # check if hdf5 format has to be used
        if isinstance(parm.chunks, (list, tuple)):
            if not isinstance(parm.name, (list, tuple)):
                self.hdf5 = True
            elif any([p > 1 for p in parm.chunks]):
                self.hdf5 = True
        elif parm.chunks > 1:
            self.hdf5 = True

    def clear_parameters(self):
        """
        Clears all system parameters and the lists that have been generated
        """
        del (self.parameters, self.columns, self.default_values,
             self.units, self.chunks)
        self.parameters = []
        self.columns = []
        self.default_values = []
        self.units = []
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
            setter = self.parameters[self.columns.index(i)].setter
        elif isinstance(i, int):
            setter = self.parameters[i].setter
        else:
            raise TypeError(f"column '{i}' could not be identified")
        if setter is None or values is None:
            return values

        if type(values) is list:
            # parameter list, verify values
            for j, value in enumerate(values):
                values[j] = float(value)
        else:
            values = float(values)

        try:
            if callable(setter) is True:
                # directly callable
                setter(values)
            else:
                # list-like getter: get function or property for calling
                attr = getattr(self.devs[setter[0]], setter[1])
                if callable(attr):
                    # callable function
                    if len(setter) == 3:
                        attr(values, *setter[2])
                    elif len(setter) == 4:
                        attr(values, *setter[2], **setter[3])
                    else:
                        attr(values)
                else:
                    # property
                    setattr(self.devs[setter[0]], setter[1], values)
        except Exception:
            self._inform_exception(i, setter, "setting")
            raise

        return values

    def trigger_value(self, i):
        """
        Triggers devices specified in column i if trigger function is provided

        Parameters
        -----
        i : int or str
          index or name of parameter that is supposed to be triggered
        """
        if i in self.columns:
            trigger = self.parameters[self.columns.index(i)].trigger
        else:
            trigger = self.parameters[i].trigger
        if trigger is not None:
            try:
                # trigger function has been provided
                if callable(trigger) is True:
                    # directly callable trigger
                    trigger()
                else:
                    # list definition of the trigger, get callable
                    attr = getattr(self.devs[trigger[0]],
                                   trigger[1])
                    if callable(attr):
                        if len(trigger) == 3:
                            attr(*trigger[2])
                        elif len(trigger) == 4:
                            attr(*trigger[2], **trigger[3])
                        else:
                            attr()
                    else:
                        raise (AttributeError, "Trigger function is not callable")
            except Exception:
                self._inform_exception(i, trigger, "triggering")
                raise

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
        readout : float or list of floats
          returns the readout from the device/parameter getter
        """
        if i in self.columns:
            getter = self.parameters[self.columns.index(i)].getter
        else:
            getter = self.parameters[i].getter
        if getter is not None:
            try:
                if callable(getter):
                    # directly callable getter
                    return getter()
                else:
                    # list-like getter: obtain callable/property
                    attr = getattr(self.devs[getter[0]], getter[1])
                    if callable(attr):
                        if len(getter) == 3:
                            return attr(*getter[2])
                        elif len(getter) == 4:
                            return attr(*getter[2], **getter[3])
                        else:
                            return attr()
                    else:
                        return attr
            except Exception:
                self._inform_exception(i, getter, "reading")
                raise
        else:
            # if get func is None, return "nan" or list of "nan"
            if isinstance(self.parameters[i].name, (list, tuple)):
                return ["nan"] * len(self.parameters[i].name)
            else:
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
                    devkwargs = dev[2] if len(dev) > 2 else dict()
                    if len(devargs) > 1 and "sharedwith" in devargs[0]:
                        # need to get connection from other device
                        devargs = list(devargs)
                        otherdev = devargs[0].split("::")[1]
                        devargs[0] = self.devs[otherdev].VISAdev
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

    def query(self, *args, **kwargs):
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

        Parameters
        -----
        args : tuple
          args that can be used here, currently not used
        kwargs : dict
          kwargs than be used here, currently not used

        Returns
        -----
        retquery : dict
          dictionary with dictionaries containing the configuration of each
          device.
        """
        if self.opened is False:
            raise ValueError("System must be set before query can be called")
        retquery = {}
        for key, dev in self.devs.items():
            # get device
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
        return retquery

    def reset(self, *args, **kwargs):
        """
        General reset function for deinitialization of system, currently does
        nothing.

        The device will be left open/initialized unless the system is deleted.

        Parameters
        -----
        args : tuple
          args that can be used here, currently not used
        kwargs : dict
          kwargs than be used here, currently not used
        """
        self.opened = False


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
        super().__init__()
        # save subsystems into system
        self.subsys = systems
        # define __name__
        self.__name__ = ",".join([subsys.__name__ for subsys in
                                  self.subsys])
        # merge devices, config_dicts and parameters
        for sys in self.subsys:
            self.devs = {**self.devs, **sys.devs}
            self.system_config_params = {**self.system_config_params,
                                         **sys.system_config_params}
            self.parameters += sys.parameters
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

    def _merge_dcdata(self, setdate=True):
        tmpdcdata = collections.defaultdict(set)
        for sys in self.subsys:
            for key, value in sys.dcdata.items():
                if key == "Date" and not setdate:
                    continue
                if value:
                    tmpdcdata[key].add(value)
        # merge dcdata
        for key, vlist in tmpdcdata.items():
            self.dcdata[key] = ";".join(vlist)
        # set correct timestamp
        if setdate:
            self.dcdata["Date"] = time.strftime(f"{datetimefmt}",
                                                time.localtime())

    def _check_hdf5(self):
        # check whether one of the systems requires HDF5
        for sys in self.subsys:
            self.hdf5 = self.hdf5 or sys.hdf5

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
        self._merge_dcdata(setdate=False)
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
        self.opened = False
        for sys in self.subsys:
            sys.reset(*args, **kwargs)
