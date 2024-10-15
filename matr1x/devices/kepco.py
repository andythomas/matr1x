# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2024 matr1x developers. All rights reserved.
# ---
import logging

import numpy as np

from .visadevice import VisaDevice

logger = logging.getLogger(__name__)


class BOP5020mg(VisaDevice):
    """
    The device class for the Kepco BOP 50-20MG power supply.
    It can possibly be used with different models with little changes.
    """

    def __init__(self, interface, **kwargs):
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r\n"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 1e3
        super().__init__(interface, **kwargs)

    def setRemote(self):
        """
        Sets the device to remote mode.
        """
        self.query("SYST:REM ON")

    def setOutput(self, output=None):
        """
        Sets the output current ON or OFF.

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
        Sets the output mode to current or voltage.

        Parameters
        ----------
        mode: string
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
        Sets the output current in A (float).

        Parameters
        ----------
        current: float
          Output current in A
        """
        self.query(f"CURR {current}")

    def setCurrentWait(self, current, tolerance=0.4):
        """
        Sets the output current in A (float) so that the actual
        current is within the tolerance of the set current.

        Parameters
        ----------
        current: float
          Output current in A
        tolerance: float
          Tolerance for the actual current in A
        """
        self.setVoltageProtection(current)
        if np.abs(current) > 20:
            print("Warning, attempting to set current exceeding 20A, returning")
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
        Sets the output voltage in V (float).

        Parameters
        ----------
        voltage: float
          Output voltage in V
        """
        self.query(f"VOLT {voltage}")

    def setVoltageProtection(self, current, resistance=0.8):
        """
        Sets the output protection voltage in V (float) by
        calculating the voltage from the applied current and
        the total resistance of the electromagnet.

        Parameters
        ----------
        current: float
          Output current in A
        resistance: float
          Total resistance of the electromagnet in Ohm
        """
        max_voltage = 50  # V
        voltage = min(np.round(resistance * current * 2, 4), max_voltage)
        self.query(f"VOLT {voltage}")

    def setCurrentProtection(self, voltage, resistance=0.8):
        """
        Sets the output protection current in A (float) by
        calculating the current from the applied voltage and
        the total resistance of the electromagnet.

        Parameters
        ----------
        voltage: float
          Output voltage in V
        resistance: float
          Total resistance of the electromagnet in Ohm
        """
        max_current = 20  # A
        current = min(np.round(voltage / resistance * 2, 4), max_current)
        self.query(f"CURR {current}")

    def getCurrent(self):
        """
        Displays the actual current at the device output in A.

        Returns
        -------
        current : float
          Actual current in A
        """
        current = self.query("MEAS:CURR:DC?").replace("\x11\x13", "")
        return float(current)

    def getCurrentSetting(self):
        """
        Displays the pogrammed value of current at the device output in A.

        Returns
        -------
        current : float
          Setted current in A
        """
        current = self.query("CURR?").replace("\x11\x13", "")
        return float(current)

    def getVoltage(self):
        """
        Displays the actual voltage at the device output in V.

        Returns
        -------
        voltage : float
          Actual voltage in V
        """
        voltage = self.query("MEAS:VOLT:DC?").replace("\x11\x13", "")
        return float(voltage)
