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
"""Module for controlling Oxford Instruments IPS120 power supplies and related devices."""

import math
import time

from pyvisa import constants
from wrapt import synchronized

from .isobus import IsobusDevice


class IPS120_switchheater(IsobusDevice):
    """Driver for IPS120 with switch heater control for persistent mode operations."""

    config_params = {
        "Rate": "getMagneticFieldRate",
        "MagnetStatus": "getMagnetStatus",
        "SwitchHeater": "getSwitchHeater",
    }

    def __init__(
        self,
        interface,
        isobus_addr=None,
        legacy=True,
        fieldlimits=(0, 1),
        max_rate=0.5,
        switch_wait_time=5,
        **kwargs,
    ):
        """
        Initialize the IPS120 switch heater driver.

        Parameters
        ----------
        interface : str
            VISA resource name or device path
        isobus_addr : int, optional
            ISOBUS address for the device
        legacy : bool, optional
            If True, use legacy mode without floating point commands
        fieldlimits : tuple, optional
            Min and max field limits in Tesla (default: (0, 1))
        max_rate : float, optional
            Maximum allowed field ramp rate in T/min (default: 0.5)
        switch_wait_time : float, optional
            Wait time in seconds after switching heater state (default: 5)
        **kwargs : dict
            Additional arguments passed to the IsobusDevice constructor
        """
        self.persistentField = None
        self.legacy = legacy
        self.fieldlimits = fieldlimits
        self.switch_wait_time = switch_wait_time
        self.max_rate = max_rate
        self.statusmsg = ""
        kwargs["isobus_addr"] = isobus_addr
        kwargs["open"] = open
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 2000
        if "cmdpers" not in kwargs:
            kwargs["cmdpers"] = 20
        if "stop_bits" not in kwargs:
            kwargs["stop_bits"] = constants.StopBits.two
        if "query_delay" not in kwargs:
            kwargs["query_delay"] = 0.08
        super().__init__(interface, **kwargs)
        self.query("C3")
        self.persistentField = self.getPersistentField()

    def _update_sleep(self, sec, msg=None, interval=0.5):
        """
        Wait for specified time while updating status message.

        Parameters
        ----------
        sec : float
            Sleep duration in seconds
        msg : str, optional
            Status message template with '{}' placeholder for remaining time
        interval : float, optional
            Update interval for status message in seconds (default: 0.5)
        """
        t0 = time.time()
        if msg is None:
            msg = "waiting {:2.0f} s"
        while (time.time() - t0) < sec:
            stillwaiting = sec - (time.time() - t0)
            if stillwaiting > interval * 1.1:
                self.statusmsg = msg.format(stillwaiting)
                time.sleep(interval)
            else:
                time.sleep(stillwaiting)
                break
            self.statusmsg = ""

    def setMagneticField(self, xval):
        """
        Set the magnetic field to the specified value.

        Parameters
        ----------
        xval : float
            Magnetic field value in Tesla

        Notes
        -----
        Automatically checks that the value is within the configured field limits.
        """
        # check xval <= fieldlimits
        if self.fieldlimits[1] < xval:
            xval = self.fieldlimits[1]
        elif self.fieldlimits[0] > xval:
            xval = self.fieldlimits[0]
        if self.legacy:
            self.query(f"J{int(1000 * xval):d}")
        else:
            self.query(f"J{xval:.4f}")

    def getMagneticField(self, setp=False):
        """
        Get the current magnetic field value.

        Parameters
        ----------
        setp : bool, optional
            If True, also returns the setpoint value

        Returns
        -------
        float or tuple
            Current field value in Tesla, or a tuple of (current, setpoint) if setp=True
        """
        if self.legacy:
            fval = self.query_float("R7") / 1000
            if setp is True:
                return (fval, self.query_float("R8") / 1000)
        else:
            fval = self.query_float("R7")
            if setp is True:
                return (fval, self.query_float("R8"))
        return fval

    def getPersistentField(self):
        """
        Get the persistent field value trapped in the magnet.

        Returns
        -------
        float or None
            Persistent field value in Tesla, or None if switch heater is on

        Notes
        -----
        Only returns a valid value if switch heater is off.
        """
        if self.getSwitchHeater() in (0, 2):
            self.persistentField = self.query_float("R18")
            if self.legacy:
                self.persistentField /= 1000
        else:
            self.persistentField = None
        return self.persistentField

    @synchronized
    def setMagneticFieldNonPersistent(self, field, block=False):
        """
        Set the field in non-persistent mode (with switch heater on).

        Parameters
        ----------
        field : float
            Target field value in Tesla
        block : bool, optional
            If True, blocks until field has reached target value
        """
        # verify magnet is in non persistent mode first
        swhtr = self.getSwitchHeater()
        if 2 == swhtr:
            # magnet is persistent with field inside, first remove field
            # set magnet on hold
            self.setMagnetStatus(0)
            time.sleep(0.1)
            # set setpoint to persistent field value
            self.setMagneticField(self.getPersistentField())
            time.sleep(0.1)
            # set magnet to go to setpoint
            self.setMagnetStatus(1)
            while self.persistentField != self.getMagneticField():
                time.sleep(1)
            time.sleep(1)
            # now magnet is ready to be switched to non persistent mode
            # turn on switch heater
            self.setSwitchHeater(True)
            # now magnet is in non persistent mode
        elif 0 == swhtr:
            # switch heater is off but no field in magnet
            # turn on switch heater
            self.setSwitchHeater(True)
            # now magnet is in non persistent mode
        else:
            # switch heater is on anyway
            pass
        # set magnet to hold
        self.setMagnetStatus(0)
        time.sleep(0.1)
        # apply setpoint
        self.setMagneticField(field)
        time.sleep(0.1)
        # set to go to setpoint and remain there
        self.setMagnetStatus(1)
        # switch heater stays on
        self.statusmsg = f"Ramping to {field} T"
        if block:
            while True:
                current_field = self.getMagneticField()
                # wait for magnet to reach setpoint
                if math.isclose(field, current_field, abs_tol=0.0001):
                    # # wait for magnet hold mode after reaching setpoint
                    # if self.getMagnetStatus() == 0:
                    break
                time.sleep(1)
            self.statusmsg = ""

    @synchronized
    def setMagneticFieldPersistent(self, field):
        """
        Set the field and switch to persistent mode.

        Parameters
        ----------
        field : float
            Target field value in Tesla

        Notes
        -----
        This method sets the field, turns off the switch heater, and then
        ramps the power supply to zero while keeping the field trapped in the magnet.
        """
        self.setMagneticFieldNonPersistent(field, block=True)
        # wait to be certain all field is gone
        time.sleep(1)
        # turn off switch heater
        self.setSwitchHeater(False)
        # set non persistent field to 0
        self.setMagnetStatus(2)
        # update persistent field in local memory
        self.getPersistentField()

    def setMagneticFieldRate(self, rate):
        """
        Set magnetic field ramp rate.

        Parameters
        ----------
        rate : float
            Field ramp rate in T/min (between 0 and max_rate)
        """
        if 0 > rate:
            rate = 0
        elif self.max_rate < rate:
            rate = self.max_rate
        if self.legacy:
            self.query(f"T{int(rate * 1000):04d}")
        else:
            self.query(f"T{rate:.4f}")

    def getMagneticFieldRate(self, setp=False):
        """
        Get the magnetic field ramp rate.

        Parameters
        ----------
        setp : bool, optional
            If True, also returns the setpoint rate

        Returns
        -------
        float or tuple
            Current ramp rate in T/min, or (current, setpoint) if setp=True
        """
        if self.legacy:
            val = self.query_float("R9") / 1000
            if setp is True:
                val = (val, self.query_float("R9") / 1000)
        else:
            val = self.query_float("R9")
            if setp is True:
                val = (val, self.query_float("R9"))
        return val

    def getVersion(self):
        """
        Get the controller firmware version.

        Returns
        -------
        str
            Firmware version string
        """
        return self.query("V")

    def getVoltage(self):
        """
        Get the power supply output voltage.

        Returns
        -------
        float
            Output voltage in Volts
        """
        if self.legacy:
            return self.query_float("R1") / 100
        else:
            return self.query_float("R1")

    @synchronized
    def setMagnetStatus(self, state):
        """
        Set operational state of the magnet.

        Parameters
        ----------
        state : int
            Operational state code:
                0 - HOLD
                1 - RTOS (Ramp to setpoint)
                2 - RTOZ (Ramp to zero)
                3 - CLMP (Clamped, when current is 0) - disallowed
        """
        statedict = {0: "Hold", 1: "Ramp to Setpoint", 2: "Ramp to Zero"}
        try:
            state = int(state)
            if 2 < state:
                # do NOT set to 3, opens door to breaking magnet!
                return
            elif 0 > state:
                return
        except ValueError:
            return
        self.query(f"A{state:d}")
        self.statusmsg = f"Status {statedict.get(state, 'unknown')}"

    def getMagnetStatus(self) -> int | None:
        """
        Get the operational state of the magnet.

        Returns
        -------
        int | None
            State of the magnet:
                0 - HOLD
                1 - RTOS (Ramp to setpoint)
                2 - RTOZ (Ramp to zero)
                3 - CLMP (Clamped, when current is 0)
                4 - Warming up
                8 - Fault
            None if status could not be read
        """
        return self.get_status_value(max_depth=11, index=4, default_value=None)

    def setSwitchHeater(self, output):
        """
        Control the switch heater state.

        Parameters
        ----------
        output : bool
            True to turn on the switch heater, False to turn it off

        Notes
        -----
        The switch heater is used to control persistent mode operation.
        When on, the magnet follows the power supply current.
        When off, the field is trapped in the magnet.
        """
        if output is True:
            self.query("H1")
            self._update_sleep(self.switch_wait_time, "warming the switch ({:2.0f} s)")
        else:
            self.query("H0")
            self._update_sleep(self.switch_wait_time, "cooling the switch ({:2.0f} s)")

    def getSwitchHeater(self) -> int | None:
        """
        Get the state of the switch heater.

        Returns
        -------
        int | None
            Switch heater state:
            0 - Off with no field in the magnet
            1 - On
            2 - Off with persistent field inside
            5 - Heater fault
            8 - No switch fitted
            None if status could not be read
        """
        return self.get_status_value(max_depth=11, index=8, default_value=None)
