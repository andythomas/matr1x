# This file is part of a software collection for data acquisition (matr3x).
# Copyright (C) 2006-2025 matr1x developers
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
"""Module for interfacing with RF switch matrices."""

from matr1x.devices.visadevice import VisaDevice


class RC_2SPDT_A18(VisaDevice):
    """Mini-Circuits RF Switch Matrix, DC - 18000 MHz, 50Ω.

    USB & Ethernet Controlled RF switch matrix device.

    """

    def __init__(self, interface, **kwargs):
        """Initialize the RC_2SPDT_A18 device.

        Parameters
        ----------
        interface : str
            Communication interface identifier.
        **kwargs : dict, optional
            Additional arguments to pass to the parent VisaDevice.

        """
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r\n"
        super().__init__(interface, **kwargs)
        # Instrument is sending the "line feed" character on successful
        # connection
        self.read()

    def setSPDT(self, port=1):
        """Set the SPDT switch position.

        Integer value of a byte that represents the switch states. Each
        bit in the byte represents the state of an individual switch
        with value:
        0 = Connect Com port to port 1 (SPDT)
                Connect J1 <> J3 and J2 <> J4 (transfer switch)
        1 = Connect Com port to port 2
                Connect J1 <> J2 and J3 <> J4 (transfer switch)
        The least significant bit (LSB) represents switch A and the most
        significant bit (MSB) represents switch H (if applicable).

        Parameters
        ----------
        port : int, optional
            The port to connect to (1 or 2), defaults to 1.

        Returns
        -------
        str
            Response from the device.

        """
        if port == 1:
            cmd = "SETP=00"
        elif port == 2:
            cmd = "SETP=11"
        else:
            raise ValueError(f"Invalid port value: {port}. Must be 1 or 2.")
        return self.query(cmd)
