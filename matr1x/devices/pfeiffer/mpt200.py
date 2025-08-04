# This file is part of a software collection for data acquisition (matr1x).
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
"""Pfeiffer pressure gauge device drivers."""

from matr1x.devices.visadevice import VisaDevice


class MPT200(VisaDevice):
    """
    MPT200 pressure gauge interface.

    This class provides methods to interact with a MPT200 pressure gauge
    through a VISA interface.
    """

    def __init__(self, interface) -> None:
        """
        Initialize the MPT200 device.

        Parameters
        ----------
        interface : str
            VISA resource name or interface identifier.
        """
        super().__init__(interface, write_termination="\r", read_termination="\r", timeout=0.5)

    def query(self, msg: str) -> str:
        """
        Send a query to the device with calculated checksum.

        Parameters
        ----------
        msg : str
            The message to be sent.

        Returns
        -------
        str
            The response from the device.
        """
        return super().query(f"{msg}{self.checksum(msg):03d}")

    def id(self) -> str:
        """
        Get the identification information of the device.

        Returns
        -------
        str
            The device identification string.
        """
        return self.query("0010034902=?") + " " + self.query("0010031202=?")

    def checksum(self, var: str) -> int:
        """
        Calculate the checksum for a command string.

        Parameters
        ----------
        var : str
            The string to calculate checksum for.

        Returns
        -------
        int
            The calculated checksum (0-255).
        """
        csum = 0
        for i in var:
            csum += ord(i)
        return csum % 256

    def resolvePressureValue(self, reading: str) -> float:
        """
        Convert the device pressure reading to a float value.

        Parameters
        ----------
        reading : str
            The raw pressure reading from the device.

        Returns
        -------
        float
            The pressure value in appropriate units.
        """
        mant = float(reading[10:14]) * 1e-3
        exp = int(reading[14:16]) - 20
        # return the correct float
        return mant * 10**exp

    def setFilamentState(self, state: int) -> None:
        """
        Set the filament state.

        Parameters
        ----------
        state : int
            The desired filament state (0=off, 1=on).
        """
        if 0 == int(state):
            # sets register 041 to 0/False
            self.query("00110041010")
        elif 1 == int(state):
            # sets register 041 to 1/True
            self.query("00110041011")

    def getFilamentState(self) -> int:
        """
        Get the current filament state.

        Returns
        -------
        int
            The current filament state (0=off, 1=on).
        """
        # sets register 041 to 1/True
        return int(self.query("0010004102=?")[10:11])

    def getPressure(self) -> float:
        """
        Get the current pressure reading.

        Returns
        -------
        float
            The current pressure value.
        """
        return self.resolvePressureValue(self.query("0010074002=?"))
