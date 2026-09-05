# This file is part of a software collection for data acquisition (matr1x).
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
Twickenham Helium Depth Indicator (HDI) interface module.

This module provides a class to interface with the Twickenham Helium
Depth Indicator device through a VISA connection.
"""

from matr1x.core.visadevice import VisaDevice


class HDI(VisaDevice):
    """
    Twickenham Helium Depth Indicator (HDI) interface.

    This class provides an interface to communicate with and control a
    Twickenham Helium Depth Indicator device through a VISA connection.

    Parameters
    ----------
    interface : str
        VISA resource identifier for the HDI device
    **kwargs : dict, optional
        Additional keyword arguments to pass to the VisaDevice parent class.
        Automatically sets appropriate communication parameters if not specified.
    """

    def __init__(self, interface, **kwargs):
        """
        Initialize the HDI device interface with appropriate communication parameters.

        Parameters
        ----------
        interface : str
            VISA resource identifier for the HDI device
        **kwargs : dict, optional
            Additional keyword arguments to pass to the VisaDevice parent class
        """
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r\n"
        if "baud_rate" not in kwargs:
            kwargs["baud_rate"] = 9600

        super().__init__(interface, **kwargs)

    def getDisplayReading(self):
        """
        Get the current helium level reading from the device display.

        Returns
        -------
        int
            The helium level reading as displayed on the device.
            Returns -1 if the reading cannot be parsed.
        """
        res = self.query("G")
        try:
            return int(res[-6:-2])
        except (IndexError, ValueError):
            return -1
