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
Module for controlling Magnet Physik FH55 Hall probe.

This module provides a driver class for interfacing with the FH55 Hall
probe from Magnet Physik via VISA communication protocols. It enables
control and reading of magnetic field measurements, temperature
readings, and various device settings such as range, filter, and
operation mode.
"""

import time

from pyvisa import VisaIOError

from matr1x.devices.visadevice import VisaDevice


class FH55(VisaDevice):
    """Driver for Hall probe FH55 from Magnet Physik."""

    def __init__(self, interface, timeout=1e3, **kwargs):
        """
        Initialize FH55.

        Parameters
        ----------
        interface : str
          The ip andress and port where the device is located.
          e.g. TCPIP::192.98.143.1::5025::SOCKET
        timeout : int
          (Default = 1e3 ms)
          The timeout of the ethernet connection.
        **kwargs :
          Keyword arguments passed to the VISAdevice constructor.
        """
        super().__init__(
            interface,
            timeout=timeout,
            write_termination="\r",
            read_termination="\r\n",
            **kwargs,
        )
        # Instrument is sending some character on successful connection
        try:
            self.read()
        except VisaIOError:
            pass
        self.query("#AUTO 1")  # sets autorange OFF
        self.query("#UNIT 0")  # sets unit to Tesla
        self.query("#TEMP 1")  # sets temp unit to Celsius

    def reset(self):
        """
        Reset the FH55 using the RESET command.

        This resets all peak (max/min) settings. RESET returns a "OK".
        """
        self.query("#AUTO 1")  # sets autorange
        self.query("#RESET")

    # high level functions
    def getField(self):
        """
        Return magnetic field in T.

        units = ["mT","T"].
        """
        try:
            field, unit = self.query("?MEAS").split(" ")
        except ValueError:
            time.sleep(0.5)
            field, unit = self.query("?MEAS").split(" ")
        field = float(field)

        if unit == "mT":
            return float(field) * 1e-3
        else:
            return float(field)

    def setRange(self):
        """
        Set the measurement range based on the current field strength.

        Automatically selects the appropriate range for the Hall probe based on
        the measured field magnitude. Range selection criteria:
        - Range 1: < 30 µT
        - Range 2: < 300 µT
        - Range 3: < 3 mT
        - Range 4: < 30 mT
        - Range 5: < 300 mT
        - Range 6: < 3 T

        Prints an error message if the field is outside of valid ranges.
        """
        field = self.getField()
        field_abs = abs(field)
        if field_abs < 30e-6:
            self.query("#RANGE 1")
        elif field_abs < 300e-6:
            self.query("#RANGE 2")
        elif field_abs < 3e-3:
            self.query("#RANGE 3")
        elif field_abs < 30e-3:
            self.query("#RANGE 4")
        elif field_abs < 300e-3:
            self.query("#RANGE 5")
        elif field_abs < 3:
            self.query("#RANGE 6")
        else:
            print(f"Field {field} T is not within a valid range!")

    def getTemp(self):
        """Return temp in degree celsius."""
        temp = self.query("?TEMP")
        return float(temp.strip(" C"))

    def setFilter(self, filter_status):
        """
        Set the filter on or off.

        Parameters
        ----------
        filter_status : str
            Status of the filter, either "ON" or "OFF".
            Corresponds to 1=ON, 0=OFF in the device commands.
        """
        if filter_status == "ON":
            self.query("#FILTER 1")
        elif filter_status == "OFF":
            self.query("#FILTER 0")
        else:
            print(f"Please choose a valid filter status (ON/OFF)! Your input was: {filter_status}")

    def getMode(self):
        """Return the AC/DC mode."""
        mode = self.query("?MODE")
        mode = float(mode.strip("MODE "))
        if mode == 0:
            return "DC"
        elif mode == 1:
            return "AC"
        else:
            return print(f"Please choose a valid mode (0/1)! Your input was: {mode}")

    def setMode(self, mode):
        """
        Set the operation mode.

        Parameters
        ----------
        mode : int
            The operation mode:
            0 = DC mode
            1 = AC mode
        """
        self.write(f"#MODE {int(mode)}")
