# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
"""
module implementing a dummy device used for automatic testing of the code base.
"""
import logging

from .. import scpi_tcpserver
from .scpi_dev import makeSCPIdevice, set_cmd_funcs

logger = logging.getLogger(__name__)

cmd_list = {"*idn": [None, None, [], str,
                     ["dummy_device"]],
            ":p1": [int,
                    "_p1", [],
                    "_p1", []],
            ":p2": [float,
                    "_p2", [],
                    "_p2", []],
            ":p3": [[float, float],
                    "_p3", [],
                    "_p3", []],
            ":p4": [[float, float, float, float],
                    "_p4", [],
                    "_p4", []],
            "*trg": [None,
                     "trigger", [],
                     None, None],
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
    """

    def __init__(self, adapter, **kwargs):
        self.running = False
        self.terminated = False
        self.localServer = None

        self._p1 = kwargs.pop("p1", 0)
        self._p2 = kwargs.pop("p2", 0.)
        self._p3 = kwargs.pop("p3", [0]*2)
        self._p4 = kwargs.pop("p4", [0]*4)
        # regenerate function entries in cmd_list
        self.cmd_list = set_cmd_funcs(self, cmd_list)

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
