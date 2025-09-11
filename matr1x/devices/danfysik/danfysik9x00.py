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
"""
Driver module for Danfysik power supplies.

This module provides classes to control and interact with Danfysik power
supply models 9100 and 9700.
"""

import time

from matr1x.devices.visadevice import VisaDevice


class Danfysik9100(VisaDevice):
    """
    Driver for Danfysik 9100 power supply.

    This class provides methods to control and monitor Danfysik 9100
    power supplies through a VISA interface.
    """

    def __init__(self, interface, **kwargs):
        """
        Initialize the Danfysik 9100 power supply.

        Parameters
        ----------
        interface : str
            VISA resource name for the device interface
        **kwargs : dict
            Optional parameters:
                write_termination : str
                    Character(s) to append to each write command
                read_termination : str
                    Character(s) that indicate end of read
                baud_rate : int
                    Serial communication baud rate
                timeout : float
                    Communication timeout in milliseconds
                cmdpers : int
                    Commands per second limitation
        """
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n\r"
        if "baud_rate" not in kwargs:
            kwargs["baud_rate"] = 115200
        if "timeout" not in kwargs:
            kwargs["timeout"] = 2e3
        if "cmdpers" not in kwargs:
            kwargs["cmdpers"] = 10
        super().__init__(interface, **kwargs)

    # high level functions
    def getCurrent(self):
        """
        Get the actual current at the device output.

        Returns
        -------
        float
            Output current in Amperes
        """
        current = self.query("AD 8")
        try:
            current_return = float(current) / 100
        except ValueError:
            time.sleep(2)
            current_return = float(current) / 100
        return current_return

    def getVoltage(self):
        """
        Get the actual voltage at the device output.

        Returns
        -------
        float
            Output voltage in Volts
        """
        voltage = self.query("AD 2")
        return float(voltage) / 10

    def getCurrentSetting(self):
        """
        Get the output current setting value.

        Returns
        -------
        float
            Current setting in Amperes
        """
        current = self.query("DA 0")[2:]
        return float(current) / 1000

    def setCurrent(self, setpoint):
        """
        Set the output current.

        Parameters
        ----------
        setpoint : float
            Current setpoint in Amperes
        """
        self.write(f"DA 0 {int(1000 * setpoint):d}")

    def getVoltageSetting(self):
        """
        Get the output voltage setting value.

        Returns
        -------
        float
            Voltage setting in Volts
        """
        voltage = self.query("AD 7")
        return float(voltage)

    def setVoltage(self, setpoint):
        """
        Set the output voltage in ppm.

        Parameters
        ----------
        setpoint : int
            Voltage setpoint in parts per million
        """
        self.write(f"DA 4 {setpoint:d}")

    def getRampStatus(self):
        """
        Get the current ramping status.

        Returns
        -------
        bool
            True if ramping, False if stopped
        """
        q = self.query("RR")
        if q == "S":
            return False
        else:
            return True

    def setOutput(self, output=None):
        """
        Set the output current on or off.

        Parameters
        ----------
        output : bool, optional
            True to turn output on, False to turn output off
        """
        if output is True:
            self.write("N")
        elif output is False:
            self.write("F")

    def id(self):
        """
        Get the device ID.

        Returns
        -------
        str
            Device identification string
        """
        return self.query("ID")

    def setRemote(self):
        """
        Change to remote control mode.

        This command switches the device to remote operation.
        """
        self.write("REM")

    def resetInterlocks(self):
        """
        Reset the interlock state.

        This command clears all active interlocks.
        """
        self.write("RS")

    def fetchStatus(self):
        """
        Get the device status.

        Returns
        -------
        dict
            Dictionary containing status information for various device states.
            Example output format: "! . ! . ! ! . . . ! . . . . ! . . . . . . . ! ."

        Notes
        -----
        Status bits:
            #1   . . . . .    MAIN POWER OFF (!=OFF .=ON)
            #2   . . . . .    POLARITY NORMAL (!=Polarity Normal)
            #3   . . . . .    POLARITY REVERSED (!=Polarity REVERSED)
            #4   . . . . .    NOT USED
            #5   . . . . .    CROWBAR ON (!=ON .=OFF)
            #6   . . . . .    I-MODE (!=I-mode  .=V-mode)
            #7   . . . . .    != % ,  . = AMPS and VOLTS
            #8   . . . . .    EXTERNAL INTERLOCK 0  (!=Interlock  .=No interlock)
            #9   . . . . .    NOT USED.
            #10  . . . . .    SUM – INTERLOCK  (!=Sum interlock  .=No sum interlock)
            #11  . . . . .    OVER VOLTAGE (OVP) (!=over voltage  .=No over voltage)
            #12  . . . . .    DC OVER CURRENT (OCP) (!=over current .=No over current)
            #13  . . . . .    DC UNDERVOLTAGE  (!=Fault  .=OK)
            #14  . . . . .    NOT USED
            #15  . . . . .    PHASE FAILURE (AC LINE OK) (!=Fault  .=OK)
            #16  . . . . .    NOT USED
            #17  . . . . .    EARTH LEAKAGE (!=Fault  .=OK)
            #18  . . . . .    FAN (!=Fault  .=OK)
            #19  . . . . .    MPS OVERTEMPERATURE (!=Fault  .=OK)
            #20  . . . . .    EXTERNAL INTERLOCK 1  (!=Interlock  .=No interlock)
            #21  . . . . .    EXTERNAL INTERLOCK 2  (!=Interlock  .=No interlock)
            #22  . . . . .    EXTERNAL INTERLOCK 3  (!=Interlock  .=No interlock)
            #23  . . . . .    MPS NOT READY (!=Not ready  .=Ready)
            #24  . . . . .    NOT USED.
        """
        self.write("S1")
        a = self.read()
        status = {
            "Main Power off": True,
            "polarity normal": True,
            "polarity reversed": True,
            "NU#4": "",
            "crowbar on": True,
            "I-Mode": True,
            "units": True,
            "External Interlock": True,
            "NU#9": "",
            "SUM-Interlock": True,
            "Over Voltage": True,
            "DC Over current": "",
            "DC under voltage": True,
            "NU#14": "",
            "Phase failure": True,
            "NU#16": "",
            "Earth leakage": True,
            "Fan": True,
            "MPS Over temperature": True,
            "External interlock 1": True,
            "External interlock 2": True,
            "External interlock 3": True,
            "MPS not ready": True,
            "NU#24": "",
        }
        count = 0
        for i in status:
            if a[count] == "!":
                status[i] = True
            elif a[count] == ".":
                status[i] = False
            count += 1
        return status

    def getPolarityStatus(self):
        """
        Get the current polarity status.

        Returns
        -------
        str
            "+" for positive polarity, "-" for negative polarity
        """
        return self.query("PO")

    def setPolarity(self, polarity):
        """
        Set the polarity of the power supply.

        Parameters
        ----------
        polarity : str
            "+" for positive polarity, "-" for negative polarity
        """
        if polarity != self.getPolarityStatus():
            self.write(f"PO {polarity}")
            time.sleep(3)
            while self.fetchStatus()["MPS not ready"] is not False:
                if self.fetchStatus()["Main Power off"] is True:
                    time.sleep(0.5)
                    return
                time.sleep(0.5)


class Danfysik9700(Danfysik9100):
    """
    Danfysik System 9700 power supply + polarity switch unit.

    This class extends the Danfysik9100 driver with additional functions
    for power supplies with polarity switch unit.
    """

    def getCurrent(self):
        """
        Get current based on polarity switch.

        Returns
        -------
        float
            Current value in Amperes with sign indicating polarity
        """
        current = super().getCurrent()
        polStat = super().getPolarityStatus()
        if polStat == "-":
            return -current
        else:
            return current

    def getCurrentSetting(self):
        """
        Get the current setting based on polarity switch.

        Returns
        -------
        float
            Current setting in Amperes with sign indicating polarity
        """
        current = super().getCurrentSetting()
        polStat = super().getPolarityStatus()
        if polStat == "-":
            return -current
        else:
            return current

    def getVoltage(self):
        """
        Get voltage based on polarity switch.

        Returns
        -------
        float
            Voltage value in Volts with sign indicating polarity
        """
        voltage = super().getVoltage()
        polStat = super().getPolarityStatus()
        if polStat == "-":
            return -voltage
        else:
            return voltage
