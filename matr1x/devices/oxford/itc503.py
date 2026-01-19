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
"""Module for interfacing with Oxford Instruments ITC503 temperature controller."""

from pyvisa import constants
from wrapt import synchronized

from .isobus import IsobusDevice


class ITC503(IsobusDevice):
    """Oxford Instruments ITC503 temperature controller interface."""

    config_params = {"AutoHeater": "getAutoHeater", "PID": "getPID"}

    def __init__(self, interface, isobus_addr=None, **kwargs):
        """
        Initialize the ITC503 controller.

        Parameters
        ----------
        interface : str or visa.resources.Resource
            Communication interface to the device.
        isobus_addr : int, optional
            Address of the device on the ISObus.
        **kwargs : dict
            Additional keyword arguments to pass to the IsobusDevice constructor.
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
        if "query_delay" not in kwargs:
            kwargs["query_delay"] = 0.1
        super().__init__(interface, **kwargs)
        self.query("C3")

    def setTVTI(self, temp):
        """
        Set the temperature set point.

        Parameters
        ----------
        temp : float
            Target temperature value in Kelvin.
        """
        self.write(f"$T{temp:.2f}")

    @synchronized
    def getTVTI(self, setp=False, channel=1):
        """
        Get the temperature reading.

        Parameters
        ----------
        setp : bool, optional
            If True, return both temperature reading and set point, by default False.
        channel : int, optional
            The channel to read temperature from, by default 1.

        Returns
        -------
        float or list
            Temperature reading in Kelvin, or [temperature, setpoint] if setp=True.
        """
        temp = self.query_float(f"R{channel:d}")
        if setp is False:
            return temp
        else:
            temps = self.query_float("R0")
            return [temp, temps]

    def setHeater(self, htr):
        """
        Set the heater output level.

        Parameters
        ----------
        htr : float
            Heater output level in percent (0-100).
        """
        self.write(f"$O{float(htr):.1f}")

    def getHeater(self):
        """
        Get the current heater output level.

        Returns
        -------
        float
            Heater output level in percent.
        """
        return self.query_float("R5")

    def setAutoHeater(self, ahtr):
        """
        Enable or disable automatic heater control.

        Parameters
        ----------
        ahtr : bool
            True to enable automatic heater control, False to disable.
        """
        ahtr = int(bool(ahtr))
        self.write(f"$A{ahtr:d}")

    def getAutoHeater(self) -> bool:
        """
        Get the status of automatic heater control.

        Returns
        -------
        bool
            True if automatic heater control is enabled, False otherwise.
        """
        astat = self.get_status_value(max_depth=11, index=3, default_value=0)
        return astat in (1, 3)

    def setNV(self, nv):
        """
        Set the needle valve position.

        Parameters
        ----------
        nv : float
            Needle valve position in percent (0-99.9).
            Values outside this range will be clipped.
        """
        nv = float(nv)
        if nv > 99.9:
            nv = 99.9
        elif nv < 0:
            nv = 0
        self.write(f"$G{nv:.1f}")

    def getNV(self):
        """
        Get the current needle valve position.

        Returns
        -------
        float
            Needle valve position in percent.
        """
        return self.query_float("R7")

    def getPID(self):
        """
        Get the current PID parameters.

        Returns
        -------
        list
            List of [P, I, D] values.
        """
        ret = []
        for rnum in (8, 9, 10):
            ret.append(self.query_float(f"R{rnum:d}"))
        return ret

    def setPID(self, pid):
        """
        Set the PID parameters.

        Parameters
        ----------
        pid : list
            List of [P, I, D] values.
        """
        for cmd, val, digits in zip(("P", "I", "D"), pid, (3, 1, 1)):
            self.query(f"{cmd}{str(round(val, digits))}")

    def setAutoPID(self, aPID):
        """
        Enable or disable automatic PID control.

        Parameters
        ----------
        aPID : bool
            True to enable automatic PID, False to disable.
        """
        aPID = int(bool(aPID))
        self.write(f"$L{aPID:d}")

    def getAutoPID(self) -> bool:
        """
        Get the status of automatic PID control.

        Returns
        -------
        bool
            True if automatic PID is enabled, False otherwise.
        """
        astat = self.get_status_value(max_depth=6, index=12, default_value=0)
        return astat in (1, 3)

    def getSweepMode(self) -> bool:
        """
        Get the status of temperature sweep mode.

        Returns
        -------
        bool
            True if sweep mode is active, False otherwise.
        """
        sweepstat = self.get_status_value(max_depth=6, index=slice(7, 9), default_value=0)
        return sweepstat != 0

    @synchronized
    def setSweepMode(self, flag):
        """
        Set the temperature sweep mode.

        Configures the controller into sweep mode. When enabled, sweep is started
        according to the previously defined parameters and made to start at the
        current temperature.

        Parameters
        ----------
        flag : bool
            True to enable sweep mode, False to disable.
        """
        if flag:
            current_temp = self.getTVTI()
            self.query("x001")
            self.query("y001")
            self.query(f"s{current_temp:.2f}")
            self.query("x000")
            self.query("y000")
            self.query("S1")
        else:
            self.query("S0")

    @synchronized
    def getSweepTime(self):
        """
        Get the sweep time in minutes.

        Returns
        -------
        float
            Sweep time in minutes.
        """
        self.query("x002")
        self.query("y002")
        ret = self.query_float("r", max_depth=3)
        self.query("x000")
        self.query("y000")
        return ret

    @synchronized
    def setSweepTime(self, time):
        """
        Set the sweep time in minutes.

        Parameters
        ----------
        time : float
            Sweep time in minutes.
        """
        self.query("x002")
        self.query("y002")
        self.query(f"s{time:.1f}")
        self.query("x000")
        self.query("y000")

    @synchronized
    def setSweepTarget(self, temp):
        """
        Set the target temperature for the sweep.

        Parameters
        ----------
        temp : float
            Target temperature in Kelvin.
        """
        self.query("x002")
        self.query("y001")
        self.query(f"s{temp:.1f}")
        self.query("x016")  # repeat at last step so that heater stays on at the end
        self.query(f"s{temp:.1f}")
        self.query("x000")
        self.query("y000")
