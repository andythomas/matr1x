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
"""CAEN ELS EasyDriver power supply interface module."""

from matr1x.devices.visadevice import VisaDevice


class CAENelsEasyDriver(VisaDevice):
    """
    Interface class for CAEN ELS EasyDriver power supply.

    This class provides methods to control and monitor CAEN ELS
    EasyDriver power supplies through a VISA interface.
    """

    def __init__(self, interface, **kwargs):
        """
        Initialize the CAEN ELS EasyDriver.

        Parameters
        ----------
        interface : str
            VISA resource name of the device
        **kwargs : dict
            Additional arguments passed to VisaDevice
        """
        super().__init__(
            interface,
            write_termination="\r",
            read_termination="\r",
            **kwargs,
        )

    def setCurrent(self, current):
        """
        Set the output current abruptly (no ramp).

        Parameters
        ----------
        current : float
            The current value to set in amps
        """
        self.query("MWI:" + str(current))

    def setOff(self):
        """Turn the output off."""
        self.query("MOFF")

    def setOn(self):
        """Turn the output on."""
        self.query("MON")

    def setOutput(self, output=None):
        """
        Set the output current on or off.

        Parameters
        ----------
        output : bool, optional
            True to turn output on, False to turn it off
        """
        if output:
            self.setOn()
        else:
            self.setOff()

    def resetModule(self):
        """Reset the module after a fault (short circuit)."""
        self.query("MRESET")

    def getCurrent(self):
        """
        Get the current output current value.

        Returns
        -------
        float
            The output current in amps
        """
        a = self.query("MRI")
        return float(a[5:])

    def getID(self):
        """
        Get the module ID.

        Returns
        -------
        str
            The module identification string
        """
        a = self.query("MRID")
        return a[6:]

    def setRampCurrent(self, current):
        """
        Set the output current with a linear ramp to setpoint.

        Parameters
        ----------
        current : float
            The target current value in amps
        """
        self.query("MRM:" + str(current))

    def getRampSlewRate(self):
        """
        Get the configured ramp slew rate.

        Returns
        -------
        float
            The ramp slew rate
        """
        a = self.query("MRSR")
        return float(a[6:])

    def setRampSlewRate(self, slewrate):
        """
        Set the ramp slew rate.

        Parameters
        ----------
        slewrate : float
            The slew rate value to set
        """
        self.query("MWSR:" + str(slewrate))

    def getDCVoltage(self):
        """
        Get the bulk DC voltage.

        Returns
        -------
        float
            The bulk DC voltage in volts
        """
        a = self.query("MRP")
        return float(a[5:])

    def getVoltage(self):
        """
        Get the output voltage.

        Returns
        -------
        float
            The output voltage in volts
        """
        a = self.query("MRV")
        return float(a[5:])

    def fetchStatus(self):
        """
        Get the device status.

        Returns
        -------
        tuple
            A tuple containing:
                - str: 8-bit binary number as a string where:
                  - bit 0: ouput (1=on, 0=off)
                  - bit 1: fault (1=yes, 0=no)
                  - bit 2: DC link undervoltage
                  - bit 3: mosfet temperature
                  - bit 4: shunt temperature
                  - bit 5: external interlock flag
                  - bit 6: reserved
                  - bit 7: reserved
                - float: output current
        """
        a = self.query("FDB:80:0")
        a = a.split(":")
        return bin(int(a[1], 16)), float(a[2])

    def getFault(self):
        """
        Check if the module is in fault mode (short circuit).

        Returns
        -------
        bool
            True if fault detected, False otherwise
        """
        status_bin_str = self.fetchStatus()[0]
        # Convert binary string to integer and check bit 1
        status_int = int(status_bin_str, 2)
        return bool(status_int & 0b10)

    def getOutputState(self):
        """
        Check if the output is on or off.

        Returns
        -------
        bool
            True if output is on, False if output is off
        """
        status_bin_str = self.fetchStatus()[0]
        # Convert binary string to integer and check bit 0
        status_int = int(status_bin_str, 2)
        return bool(status_int & 0b1)

    def getCurrentSetpoint(self):
        """
        Get the current setpoint.

        Returns
        -------
        float
            The current setpoint in amps
        """
        return self.fetchStatus()[1]
