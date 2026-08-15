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
"""Module for controlling Kepco BOP power supplies."""

import numpy as np

from matr1x.devices.visadevice import VisaDevice


class BOP5020mg(VisaDevice):
    """
    The device class for the Kepco BOP 50-20MG power supply.

    It can possibly be used with different models with little changes.
    """

    def __init__(self, interface, **kwargs):
        """
        Initialize the BOP5020mg device.

        Parameters
        ----------
        interface : str
            VISA resource name for the device
        **kwargs : dict
            Additional keyword arguments to pass to the VISA device
        """
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r\n"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 1e3
        super().__init__(interface, **kwargs)

    def setRemote(self):
        """Set the device to remote mode."""
        self.query("SYST:REM ON")

    def setOutput(self, output=None):
        """
        Set the output current ON or OFF.

        Parameters
        ----------
        output : bool
            True for ON, False for OFF
        """
        if output is True:
            self.query("OUTP ON")
        elif output is False:
            self.query("OUTP OFF")

    def setMode(self, mode):
        """
        Set the output mode to current or voltage.

        Parameters
        ----------
        mode : str
            Takes "current" or "voltage" as input
        """
        if mode == "current":
            self.query("FUNC:MODE CURR")
            return
        if mode == "voltage":
            self.query("FUNC:MODE VOLT")
            return

    def setCurrent(self, current):
        """
        Set the output current in A.

        Parameters
        ----------
        current : float
            Output current in A
        """
        self.query(f"CURR {current}")

    def setCurrentWait(self, current, tolerance=0.4):
        """
        Set the output current in A so that the actual current is within tolerance.

        Adjusts the current incrementally until the desired value is reached.

        Parameters
        ----------
        current : float
            Output current in A
        tolerance : float, optional
            Tolerance for the actual current in A, default is 0.4
        """
        self.setVoltageProtection(current)
        if np.abs(current) > 20:
            print("Warning, attempting to set current exceeding 20A, returning")  # noqa: T201
            return
        current_now = self.getCurrent()
        while np.abs(current - current_now) > tolerance:
            if current_now < current:
                self.setCurrent(np.round(current_now + tolerance, 4))
                current_now = current_now + tolerance
            elif current_now > current:
                self.setCurrent(np.round(current_now - tolerance, 4))
                current_now = current_now - tolerance
        else:
            self.setCurrent(np.round(current, 4))

    def setVoltage(self, voltage):
        """
        Set the output voltage in V.

        Parameters
        ----------
        voltage : float
            Output voltage in V
        """
        self.query(f"VOLT {voltage}")

    def setVoltageProtection(self, current, resistance=0.8):
        """
        Set the output protection voltage in V.

        Calculates the voltage from the applied current and the total
        resistance of the electromagnet.

        Parameters
        ----------
        current : float
            Output current in A
        resistance : float, optional
            Total resistance of the electromagnet in Ohm, default is 0.8
        """
        max_voltage = 50  # V
        voltage = min(np.round(resistance * current * 2, 4), max_voltage)
        self.query(f"VOLT {voltage}")

    def setCurrentProtection(self, voltage, resistance=0.8):
        """
        Set the output protection current in A.

        Calculates the current from the applied voltage and the total
        resistance of the electromagnet.

        Parameters
        ----------
        voltage : float
            Output voltage in V
        resistance : float, optional
            Total resistance of the electromagnet in Ohm, default is 0.8
        """
        max_current = 20  # A
        current = min(np.round(voltage / resistance * 2, 4), max_current)
        self.query(f"CURR {current}")

    def getCurrent(self):
        """
        Get the actual current at the device output.

        Returns
        -------
        float
            Actual current in A
        """
        current = self.query("MEAS:CURR:DC?").replace("\x11\x13", "")
        return float(current)

    def getCurrentSetting(self):
        """
        Get the programmed value of current at the device output.

        Returns
        -------
        float
            Set current in A
        """
        current = self.query("CURR?").replace("\x11\x13", "")
        return float(current)

    def getVoltage(self):
        """
        Get the actual voltage at the device output.

        Returns
        -------
        float
            Actual voltage in V
        """
        voltage = self.query("MEAS:VOLT:DC?").replace("\x11\x13", "")
        return float(voltage)
