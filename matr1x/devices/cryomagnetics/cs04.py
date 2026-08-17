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
Interface for the Cryomagnetics CS04 magnet power supply.

This module provides control functions for Cryomagnetics CS04
superconducting magnet power supplies over VISA interface.
"""

import time

from matr1x.devices.visadevice import VisaDevice


class CS04(VisaDevice):
    """
    Cryomagnetics CS04 magnet power supply.

    Typically connected via GPIB::<address>::INSTR
    The user shall set `max_field` to a reasonable value upon initialization.

    Parameters
    ----------
    interface : str
        VISA resource name
    max_field : float, optional
        Maximum allowed field in Tesla, defaults to 0.1 T
    **kwargs
        Additional arguments passed to VisaDevice
    """

    config_params = {}

    def __init__(self, interface, **kwargs):
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n"
        self.max_field = kwargs.pop("max_field", 0.1)
        self._setpoint = 0
        super().__init__(interface, **kwargs)

    def ident(self):
        """
        Get the device identification string.

        Returns
        -------
        str
            Device identification string
        """
        return self.query("*IDN?")

    def reset(self):
        """
        Reset the magnet to zero field.

        Sets the upper and lower limits to zero and initiates a slow
        sweep to zero field.
        """
        self._setpoint = 0
        self.write("SWEEP PAUSE")
        self.write("ULIM 0")
        self.write("LLIM 0")
        self.write("SWEEP ZERO SLOW")

    def set_field(self, field):
        """
        Set the magnetic field to a specified value.

        Parameters
        ----------
        field : float
            Target magnetic field in Tesla

        Notes
        -----
        If field is zero, it will call reset().
        If field exceeds max_field, the command will be rejected.
        For positive fields, it sets upper limit and sweeps up.
        For negative fields, it sets lower limit and sweeps down.
        """
        if field == 0:
            self.reset()
            return
        if abs(field) > self.max_field:
            print(f"Request for too large field ({field} T). Max is {self.max_field} T")  # noqa: T201
            return
        self._setpoint = field
        if field > 0:
            self.write("SWEEP PAUSE")
            self.write("LLIM 0")
            self.write(f"ULIM {field}")
            self.write("SWEEP UP SLOW")
        else:
            self.write("SWEEP PAUSE")
            self.write("ULIM 0")
            self.write(f"LLIM {field}")
            self.write("SWEEP DOWN SLOW")

    def get_field(self):
        """
        Get the current magnetic field.

        Returns
        -------
        float
            Current magnetic field in Tesla
        """
        return float(self.query("IOUT?").strip(" T"))

    def wait_field(self, setpoint=None, delta=0.0002):
        """
        Wait until the magnet field reaches the specified setpoint.

        Parameters
        ----------
        setpoint : float, optional
            Target field in Tesla. If None, uses the internal setpoint.
        delta : float, optional
            Acceptable difference between current and target field, defaults to 0.0002 T

        Notes
        -----
        The method will wait until the field is within delta of the setpoint
        for at least two consecutive readings, then pause the sweep.
        """
        if not setpoint:
            setpoint = self._setpoint
        inrange = 0
        while True:
            if abs(self.get_field() - setpoint) < delta:
                inrange += 1
            if inrange >= 2:
                break
            time.sleep(1)
        time.sleep(1)
        self.write("SWEEP PAUSE")
