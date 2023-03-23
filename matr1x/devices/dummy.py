# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2023 matr1x developers. All rights reserved.
# ---
"""
module implementing a dummy device used for automatic testing of the code base.
"""
import logging

from .. import scpi_tcpserver
from ..util import Command, Get, Set
from .scpi_dev import makeSCPIdevice

logger = logging.getLogger(__name__)

cmd_list = {"*idn": Get(str, lambda: "dummy_device"),
            ":p1": Command(int, "_p1", "_p1"),
            ":p2": Command(float, "_p2", "_p2"),
            ":p3": Command([float, float], "_p3", "_p3"),
            ":p4": Command([float, float, float, float], "_p4", "_p4"),
            ":p5": Command(float, "_p5", "_p5"),
            ":p6": Command(bool, "_p6", "_p6"),
            ":p7": Command(bool, "_p7", "_p7"),
            "*trg": Set(None, "trigger"),
            }

dummy_dev = makeSCPIdevice(cmd_list)


class dummy(dummy_dev):
    """
    Dummy device for testing. Upon initialization the device starts a socket
    server which processes queries received via this network socket. Typically
    this will be done via the loopback interface (localhost) and on a high
    TCP/IP port number.

    Parameters
    ----------
    adapter: str
      VISA TCPIP socket address. e.g. "TCPIP::localhost::10007::SOCKET".
    kwargs: dict, optional
      optionally starting values for the fake measurement parameters p1, p2,
      p3, p4 can be given as entries to the keyword arguments dictionary.
      Possible entries include:

       * p1: Parameter of type int
       * p2: Parameter of type float
       * p3: Parameter with list of two floats
       * p4: Parameter with list of four floats
       * p5: Parameter of type float
       * p6: Parameter of type bool
       * p7: Parameter of type bool
    """
    config_params = {"conf": "_p1"}

    def __init__(self, adapter, **kwargs):
        self.running = False
        self.terminated = False
        self.localServer = None

        self._p1 = kwargs.pop("p1", 0)
        self._p2 = kwargs.pop("p2", 0.)
        self._p3 = kwargs.pop("p3", [0]*2)
        self._p4 = kwargs.pop("p4", [0]*4)
        self._p5 = kwargs.pop("p5", 0.)
        self._p6 = kwargs.pop("p6", False)
        self._p7 = kwargs.pop("p7", False)
        # regenerate function entries in cmd_list
        self.cmd_list = cmd_list
        for cmd in self.cmd_list.values():
            # replace with real functions. This is more comprehensively
            # implemented in GuiDict.set_cmd_funcs
            if cmd.getfunc is not None and not callable(cmd.getfunc):
                attr = getattr(self, cmd.getfunc)
                if callable(attr):
                    cmd.getfunc = attr
                else:
                    cmd.getfunc = lambda a=cmd.getfunc: getattr(self, a)
            if cmd.setfunc is not None and not callable(cmd.setfunc):
                attr = getattr(self, cmd.setfunc)
                if callable(attr):
                    cmd.setfunc = attr
                else:
                    cmd.setfunc = lambda v, a=cmd.setfunc: setattr(self, a, v)

        self.localServer = scpi_tcpserver.SCPI_TCP_Server(
            self.cmd_list, port=int(adapter.split("::")[2]))
        self.localServer.start()
        super().__init__(adapter)

    # high level functions
    def trigger(self):
        """
        fake trigger function which allows to show the trigger functionality in
        the dummy system files, but actually has no real impact on the device.
        """

    def configure(self, **kwargs):
        """
        fake configure function to demonstrate configuration upon
        initialization.
        """
