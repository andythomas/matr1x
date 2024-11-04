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

from .visadevice import VisaDevice


class RC_2SPDT_A18(VisaDevice):
    """
    Mini-Circuits RF Switch Matrix, DC - 18000 MHz, 50Ω
    USB & Ethernet Controlled
    """

    def __init__(self, interface, **kwargs):
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r\n"
        super().__init__(interface, **kwargs)
        # Instrument is sending the "line feed" character on successful
        # connection
        self.read()

    def setSPDT(self, port=1):
        """
        Integer value of a byte that represents the switch states. Each
        bit in the byte represents the state of an individual switch
        with value:
        0 = Connect Com port to port 1 (SPDT)
                Connect J1 <> J3 and J2 <> J4 (transfer switch)
        1 = Connect Com port to port 2
                Connect J1 <> J2 and J3 <> J4 (transfer switch)
        The least significant bit (LSB) represents switch A and the most
        significant bit (MSB) represents switch H (if applicable).
        """
        if port == 1:
            cmd = "SETP=00"
        if port == 2:
            cmd = "SETP=11"
        self.query(cmd)
