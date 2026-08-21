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
"""Module implementing a dummy device used for automatic testing of the code base."""

import copy
from typing import ClassVar

from pyvisa import rname

from matr1x import scpi_tcpserver
from matr1x.devices.scpi_dev import makeSCPIdevice
from matr1x.util import Command, Get, Set
from matr1x.visa_helpers import validate_local_tcpip_socket_visa_resource

cmd_list: dict[str, Command] = {
    "*idn": Get(str, lambda: "dummy_device name\nwith newline"),
    ":p1": Command(str, "_p1", "_p1"),
    ":p2": Command(float, "_p2", "_p2"),
    ":p3": Command([float, float], "_p3", "_p3"),
    ":p4": Command([float, float, float, float], "_p4", "_p4"),
    ":p5": Command(float, "_p5", "_p5"),
    ":p6": Command(bool, "_p6", "_p6"),
    ":p7": Command(bool, "_p7", "_p7"),
    "*trg": Set(None, "trigger"),
}

dummy_dev = makeSCPIdevice(cmd_list)


def _get_dummy_server_address(adapter: str) -> tuple[str, int]:
    """Return the host and port from a supported dummy-device address."""
    validate_local_tcpip_socket_visa_resource(adapter)
    resource = rname.parse_resource_name(adapter)
    if not isinstance(resource, rname.TCPIPSocket):
        raise RuntimeError("Validated dummy adapter is not a TCP/IP socket")
    return resource.host_address, int(resource.port)


class dummy(dummy_dev):  # ty: ignore[unsupported-base]
    """
    Dummy device for testing.

    Upon initialization the device starts a socket server which processes
    queries received via this network socket. The server is hosted on the
    loopback interface (localhost) and uses a high TCP/IP port number.

    Parameters
    ----------
    adapter : str
        Local VISA TCPIP socket address, e.g.
        "TCPIP::localhost::10007::SOCKET".
    **kwargs : dict, optional
        Optionally starting values for the fake measurement parameters
        can be given as entries to the keyword arguments dictionary.
        Parameters match the data types defined in `cmd_list`:

        * p1 through p7
            Parameters with types matching command list definitions
    """

    config_params: ClassVar[dict[str, str]] = {
        "name": "*idn?",
        "conf": "_p1",
    }

    def __init__(self, adapter: str, **kwargs):
        host, port = _get_dummy_server_address(adapter)
        self.localServer = None

        self._p1 = kwargs.pop("p1", "0")
        self._p2 = kwargs.pop("p2", 0.0)
        self._p3 = kwargs.pop("p3", [0] * 2)
        self._p4 = kwargs.pop("p4", [0] * 4)
        self._p5 = kwargs.pop("p5", 0.0)
        self._p6 = kwargs.pop("p6", False)
        self._p7 = kwargs.pop("p7", False)
        # regenerate function entries in cmd_list
        self.cmd_list = copy.deepcopy(cmd_list)  # keep original for reopening
        for cmd in self.cmd_list.values():
            # replace with real functions. This is more comprehensively
            # implemented in GuiDict.set_cmd_funcs
            if isinstance(cmd.getfunc, str):
                attr = getattr(self, cmd.getfunc)
                if callable(attr):
                    cmd.getfunc = attr
                else:
                    cmd.getfunc = lambda a=cmd.getfunc: getattr(self, a)
            if isinstance(cmd.setfunc, str):
                attr = getattr(self, cmd.setfunc)
                if callable(attr):
                    cmd.setfunc = attr
                else:
                    cmd.setfunc = lambda v, a=cmd.setfunc: setattr(self, a, v)

        self.localServer = scpi_tcpserver.SCPI_TCP_Server(self.cmd_list, host=host, port=port)
        self.localServer.start()
        super().__init__(adapter, name="Dummy device")

    def close(self):
        """
        Close the device server.

        Stops the local server and closes the adapter connection.
        """
        self.localServer.stop()
        self.adapter.close()

    # high level functions
    def trigger(self):
        """
        Simulate device triggering.

        Fake trigger function which allows to show the trigger
        functionality in the dummy system files, but actually has no
        real impact on the device.
        """

    def configure(self, **kwargs):
        """
        Configure the dummy device.

        Fake configure function to demonstrate configuration upon
        initialization.

        Parameters
        ----------
        **kwargs : dict, optional
            Configuration parameters to set.
        """
