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

import pyvisa
from wrapt import synchronized

logger = logging.getLogger(__name__)


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

    def __init__(self, interface, cmdpers=None, **kwargs):
        self.conn = False
        self.interface = interface
        self.name = f"{type(self).__name__}@{self.interface}"
        # have never tested these myself
        self.pts = 'pts' in kwargs and kwargs['pts']
        if 'visadebug' in kwargs and kwargs['visadebug']:
            pyvisa.log_to_screen()
        kwargs.pop("visadebug", None)
        kwargs.pop("pts", None)
        # mutex lock to synchronize devices sharing the same connection
        # currently this is needed only by IsobusDevices
        self.sharedlock = kwargs.pop("sharedlock", threading.RLock())
        self.backend = kwargs.pop("backend", "")

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

        # store kwargs to pass them to visa device
        self.kwargs = kwargs

        self._open()

    @synchronized
    def _open(self):
        """
        Open the connection to the device. This is an internal method and
        should not be called by the user.
        """
        if not self.conn:
            # hardcode the resource manager or allow to pass different
            # backend?
            self.VISArm = pyvisa.ResourceManager(self.backend)
            if isinstance(self.interface, pyvisa.resources.Resource):
                self.VISAdev = self.interface
                self.conn = True
                return
            self.VISAdev = self.VISArm.open_resource(self.interface)
            if self.pts:
                print(f"C: {self.name}")
            logger.info(f"Connection to {self.name} opened")
            self.conn = True
            # apply kwargs to visadevice (say baudrate)
            # should only modify available properties, so should be immune
            # against "wrong" device parameters
            # needs to be tested!
            for kwarg in self.kwargs.keys():
                if hasattr(self.VISAdev, kwarg):
                    setattr(self.VISAdev, kwarg, self.kwargs[kwarg])

    @synchronized
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
        if self.conn is False:
            return
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
    def write(self, command):
        """
        Write a message to the device.

        Parameters
        ----------
        command : str
            The string to be sent.
        """
        if self.conn is False:
            return

        logger.debug(f"{self.name}: Write: {command}")
        if self.pts:
            print('W: %s' % command)
        if self.timedelay is not None:
            # make sure that enough time has passed so that a new command
            # can be send
            while(self.timedelay > time.time() - self.timer):
                # do we really want to do a busy wait here? I think since the
                # typical timings are on the order of ms, there is not much
                # else to do right?
                pass
            self.timer = time.time()
        self.VISAdev.write(command)

    @synchronized
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
        if self.conn is False:
            return

        logger.debug(f"{self.name}: Query: {command}")

        if self.timedelay is not None:
            # make sure that enough time has passed so that a new command
            # can be send
            while(self.timedelay > time.time() - self.timer):
                pass
            self.timer = time.time()
        if self.pts:
            print('W: %s' % command)
        resp = self.VISAdev.query(command)
        logger.debug('Answer: %s' % str(resp))
        if self.pts:
            print('R: %s' % resp)
        return(resp)

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
