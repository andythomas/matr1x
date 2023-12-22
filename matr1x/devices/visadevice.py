# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
"""
In this module the base class for all device drivers in this package is
defined. It is itself based on the pyvisa library which handles all the low
level communication.
"""


import logging
import threading
import time
from functools import wraps

import pyvisa
from wrapt import synchronized

logger = logging.getLogger(__name__)


def output_name_on_error(func):
    """
    decorator to log and print the class instance 'name' attribute in case of
    an raised Exception. This decorator can be only used with class methods.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            ret = func(self, *args, **kwargs)
        except Exception:
            if hasattr(self, "name"):
                print('I am here.')
                print(f"Exception occured inside {self.name}")
            raise
        return ret
    return wrapper


class VisaDevice(object):
    """
    The VISA device class.

    Parameters
    ----------
    interface : str
      The used interface as VISA address.
      e.g. 'TCPIP::192.98.143.1::5025::SOCKET'
    cmdpers : int, optional
      The maxiumum amount of commands to be send per second.
      If None (default), no limit is imposed.
    **kwargs : dict, optional
      Keyword arguments, e.g. a='b'. Used keywords are:
       * pts : bool
         'Print to screen'. If True, read and written strings are printerd to
         the console.  Usefull  for debuging.
       * visadebug : bool
         If True, enables the output of debugging information
         from the pyVISA library.
       * All other kwargs are passed to VISAdev and can serve to configure
         the interface. Most common are:

         * write_termination : str
         * read_termination : str
         * timeout : float
         * query_delay : float
         * baud_rate : int
         * data_bits : int
         * stop_bits : int
         * parity : int
         * flow_control : int

    Attributes
    ----------
    interface : str
        The used interface.
    VISAdev : pyVISA resource
        The pyVISA resource used for communication with the device.
        Usually only important if new features are to be implemented.
        Please refer to the pyVISA documentation for more information.

    Returns
    -------
    dev : VISAdevice
        The created device.
    """
    config_params = {}
    """
    Parameters provided in dictionary need to be one of:
      * an attribute or method name (if callable without arguments)
      of the device object
      * a query string for the device
      * a list of the following scheme
      [method_name : str, args : tuple, kwargs : dict]
    """

    @output_name_on_error
    def __init__(self, interface, cmdpers=None, **kwargs):
        self.interface = interface
        self.name = f"{type(self).__name__}@{self.interface}"
        # have never tested these myself
        self.pts = kwargs.pop("pts", False)
        if kwargs.pop("visadebug", False):
            pyvisa.log_to_screen()
        # mutex lock to synchronize devices sharing the same connection
        # currently this is needed only by IsobusDevices
        self.sharedlock = kwargs.pop("sharedlock", threading.RLock())

        # set number of commands which can be sent per second
        if cmdpers is not None:
            try:
                cmdpers = int(cmdpers)
            except TypeError:
                # Use a d efault number of commands per second of 30
                cmdpers = 30
            if 0 == cmdpers:
                # prevent division by 0
                cmdpers = 1
            self.timedelay = 1. / cmdpers
            self.timer = time.time()
        else:
            self.timedelay = None

        # Open the connection to the device
        VISArm = pyvisa.ResourceManager(kwargs.pop("backend", ""))
        if isinstance(self.interface, pyvisa.resources.Resource):
            self.VISAdev = self.interface
            return
        self.VISAdev = VISArm.open_resource(self.interface)
        if self.pts:
            print(f"C: {self.name}")
        logger.info(f"Connection to {self.name} opened")
        # apply kwargs to visadevice (say baudrate)
        # should only modify available properties, so should be immune
        # against "wrong" device parameters
        # needs to be tested!
        for key, val in kwargs.items():
            if hasattr(self.VISAdev, key):
                setattr(self.VISAdev, key, val)

    @synchronized
    @output_name_on_error
    def read_very_eager(self):
        """read from device without blocking IO (timeout=0)"""
        t = self.VISAdev.timeout
        if isinstance(self.VISAdev, pyvisa.resources.GPIBInstrument):
            # GPIB instruments need a finite timeout here since messages are
            # sent on demand? Please extensively test if you change this!
            self.VISAdev.timeout = 10  # ms
        else:
            self.VISAdev.timeout = 0  # ms
        ret = ""
        try:
            while True:
                ret += self.VISAdev.read()
        except pyvisa.errors.VisaIOError:
            pass
        self.VISAdev.timeout = t
        return ret

    @synchronized
    @output_name_on_error
    def read(self, nbytes=None):
        """
        Read data from the device.
        If nbytes is set, only so many bytes are read.
        If not, bytes are read until terminated by the specified character.

        Parameters
        ----------
        nbytes : int
             (Default = None)
            The number of bytes to be read.

        Returns
        -------
        readout : str or bytes
            The recived information.
        """
        if nbytes is None:
            readout = self.VISAdev.read()
        else:
            readout = self.VISAdev.read_bytes(nbytes)

        logger.debug(f"{self.name} read {str(readout)}")
        if self.pts:
            print('R: %s' % ('(%i) %s' % (nbytes,
                                          readout) if nbytes else readout))
        return readout

    @synchronized
    @output_name_on_error
    def write(self, command):
        """
        Write a message to the device.

        Parameters
        ----------
        command : str
            The string to be sent.
        """
        logger.debug(f"{self.name}: Write: {command}")
        if self.pts:
            print('W: %s' % command)
        if self.timedelay is not None:
            # make sure that enough time has passed so that a new command
            # can be send
            while (self.timedelay > time.time() - self.timer):
                # do we really want to do a busy wait here? I think since the
                # typical timings are on the order of ms, there is not much
                # else to do right?
                pass
            self.timer = time.time()
        self.VISAdev.write(command)

    @synchronized
    @output_name_on_error
    def query(self, command):
        """
        Send a message to the device and read the response.

        Parameters
        ----------
        command : str
            The string to be sent.

        Returns
        -------
        readout : str
            The recieved information.
        """
        logger.debug(f"{self.name}: Query: {command}")

        if self.timedelay is not None:
            # make sure that enough time has passed so that a new command
            # can be send
            while (self.timedelay > time.time() - self.timer):
                pass
            self.timer = time.time()
        if self.pts:
            print('W: %s' % command)
        resp = self.VISAdev.query(command)
        logger.debug('Answer: %s' % str(resp))
        if self.pts:
            print('R: %s' % resp)
        return (resp)

    def id(self):
        r"""
        Sends a '\*IDN?' command to the device, which should
        answer with a self-identifing string.

        Returns
        -------
        idstr : str
            The recieved string.
        """
        return self.query('*IDN?')