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
"""Module for interfacing with Oxford ILM200 level meter instruments."""

import logging

from pyvisa import constants

from .isobus import IsobusDevice

logger = logging.getLogger(__name__)


class ILM200(IsobusDevice):
    """Driver for Oxford ILM200 series level meter."""

    config_params = {"LHe": "getLHe", "LN2": "getLN2"}

    def __init__(self, interface, isobus_addr=None, **kwargs):
        """
        Initialize the Oxford ILM200 level meter.

        Parameters
        ----------
        interface : str
            Communication interface to use with the device.
        isobus_addr : int, optional
            ISOBUS address of the device.
        **kwargs : dict
            Additional parameters to pass to the underlying VISA resource.
        """
        kwargs["isobus_addr"] = isobus_addr
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 2000
        if "cmdpers" not in kwargs:
            kwargs["cmdpers"] = 10
        if "stop_bits" not in kwargs:
            kwargs["stop_bits"] = constants.StopBits.two
        super().__init__(interface, **kwargs)
        self.query("C3")

    def getLHe(self):
        """
        Get the liquid helium level reading.

        Returns
        -------
        float
            Liquid helium level in percentage.
        """
        return self.query_float("R1") / 10

    def getLN2(self):
        """
        Get the liquid nitrogen level reading.

        Returns
        -------
        float
            Liquid nitrogen level in percentage.
        """
        return self.query_float("R2") / 10

    def setRate(self, fast):
        """
        Set the rate to fast or slow mode.

        Parameters
        ----------
        fast : bool
            If True, set rate to fast mode. If False, set rate to slow mode.
        """
        if fast is True:
            self.query("T1")
        else:
            self.query("S1")

    def getRate(self) -> bool:
        """
        Get the current rate setting.

        Returns
        -------
        bool
            True if rate is set to fast mode, False if slow mode.
        """
        hex_char = self.get_status_value(
            max_depth=11, index=6, default_value="0", conversion_func=str
        )

        try:
            return bool(int(hex_char, 16) & 0b10)
        except ValueError:
            logger.debug("Could not convert hex value: %s", hex_char)
            return False
