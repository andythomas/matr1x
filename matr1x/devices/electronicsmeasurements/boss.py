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
"""
Module for Electronics Measurement Inc.

BOSS-20-5 power supply.
"""

import logging
import time

from matr1x.devices.visadevice import VisaDevice

logger = logging.getLogger(__name__)


class BOSS(VisaDevice):
    """
    Class for controlling the Electronics Measurement Inc.

    BOSS-20-5 power supply.
    """

    def __init__(self, interface, **kwargs):
        """
        Initialize BOSS device.

        Parameters
        ----------
        interface : str
            VISA resource name.
        **kwargs : dict
            Additional keyword arguments for VisaDevice.
        """
        # take care, all values are transferred as integers although being
        # floats with one decimal place
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 2000
        if "query_delay" not in kwargs:
            kwargs["query_delay"] = 0.05
        if "cmdpers" not in kwargs:
            kwargs["cmdpers"] = 30
        super().__init__(interface, **kwargs)
        self.read_very_eager()  # clear leftovers of old communication
        # set talkback off
        self.query("SB0")
        # set device to remote
        self.query("SR")
        time.sleep(0.5)
        self.read_very_eager()

    def id(self):
        """
        Get device identifier.

        Returns
        -------
        str
            Device identifier.
        """
        # Power supply seems to support no version or identifier command
        return "Electronics Measurement Inc. BOSS-20-5"

    def read_very_eager(self, attempts=0):
        """
        Read all available data from device buffer.

        Parameters
        ----------
        attempts : int, optional
            Number of retry attempts.

        Returns
        -------
        str
            Data read from device buffer.

        Raises
        ------
        OSError
            If too many attempts to read eagerly.
        """
        # ignore non-ascii characters in reply which sometimes seem to appear
        try:
            return super().read_very_eager()
        except UnicodeDecodeError:
            logger.info("repeating read_very_eager (attempts: %d)", attempts)
            if attempts > 4:
                raise OSError("too many attempts to read eagerly")
            return self.read_very_eager(attempts=attempts + 1)

    def query(self, msg, attempts=0):
        """
        Send a command to the device and get the response.

        Parameters
        ----------
        msg : str
            Command to send.
        attempts : int, optional
            Number of retry attempts.

        Returns
        -------
        str
            Device response.

        Raises
        ------
        OSError
            If too many attempts to query.
        """
        try:
            ret = super().query(msg)
        except UnicodeDecodeError:
            logger.info("repeating query %s (attempts: %d)", msg, attempts)
            if attempts > 4:
                raise OSError("Query failed after too many attempts.")
            return self.query(msg, attempts=attempts + 1)
        ret = ret.replace("Command>", "")
        return ret

    # high level functions
    def set_local(self):
        """Set device to local mode."""
        self.query("SL")

    def setControl(self, mode):
        """
        Set control mode.

        Parameters
        ----------
        mode : int
            0 for current mode, 1 for voltage mode.
        """
        if mode == 0:
            self.query("SI")
        elif mode == 1:
            self.query("SV")

    def getControl(self):
        """
        Get current control mode.

        Returns
        -------
        int
            0 for current mode, 1 for voltage mode.
        """
        ret = self.query("?C")
        if "V" in ret:
            return 1
        else:
            return 0

    def setSource(self, source):
        """
        Set source value.

        Parameters
        ----------
        source : float
            Source value to set.
        """
        self.query(f"PC{float(source):.3f}")

    def getVoltage(self):
        """
        Get current voltage.

        Returns
        -------
        float
            Current voltage in Volts.
        """
        ret = self.query("MV")
        ret = ret.replace("Voltage = ", "")
        ret = ret.replace(" Volts", "")
        return float(ret)

    def getCurrent(self):
        """
        Get current amperage.

        Returns
        -------
        float
            Current amperage in Amps.
        """
        ret = self.query("MI")
        ret = ret.replace("Current = ", "")
        ret = ret.replace(" Amps", "")
        return float(ret)
