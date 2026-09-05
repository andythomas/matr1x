# This file is part of a software collection for data aquisition (matr1x).
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
"""AMI level meter AMI1700 module."""

from matr1x.core.visadevice import VisaDevice


class AMI1700(VisaDevice):
    """AMI 1700 Level Meter."""

    def __init__(self, interface, **kwargs):
        """
        Initialize device.

        In case no termination is specified, add default termination.
        """
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r\n"
        super().__init__(interface, **kwargs)

    def get_helium_level(self) -> tuple[float, str]:
        """Read liquid helium level.

        Returns
        -------
        unit : str
            The unit of the level, i.e. '%', 'in' or 'cm'.
        level : float
            The reading of the level.
        """
        unit = self.query(":HE:UNIT?")
        level = self.query("MEAS:HE:LEV?")
        return level, unit

    def get_nitrogen_level(self) -> tuple[float, str]:
        """
        Read liquid nitrogen level.

        Returns
        -------
        unit : str
            The unit of the level, i.e. '%', 'in' or 'cm'.
        level : float
            The reading of the level.
        """
        unit = self.query(":N2:UNIT?")
        level = self.query(":MEAS:N2:LEV?")
        return level, unit
