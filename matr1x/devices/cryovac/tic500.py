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
TIC500 temperature controller interface module.

This module provides an interface to control TIC500 temperature
controllers.
"""

import logging

from wrapt import synchronized

from matr1x.devices.visadevice import VisaDevice

logger = logging.getLogger(__name__)


class TIC500(VisaDevice):
    """
    TIC500 temperature controller interface.

    A class that provides an interface to communicate with and control
    TIC500 temperature controllers via VISA.

    Parameters
    ----------
    interface : str
        VISA resource name to connect to
    **kwargs : dict
        Additional keyword arguments:
        write_termination : str, optional
            The string to append to each write command (default: CRLF)
        read_termination : str, optional
            The string that marks the end of a read response (default: CRLF)
        timeout : int, optional
            Timeout in milliseconds (default: 2000)
        setlimit : int, optional
            Maximum temperature setpoint limit (default: 301)
    """

    def __init__(self, interface, **kwargs):
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r\n"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 2000
        if "setlimit" not in kwargs:
            self.setlimit = 301
        else:
            self.setlimit = kwargs["setlimit"]
        super().__init__(interface, **kwargs)

    @synchronized
    def query_float(self, msg):
        """
        Query device and convert response to float.

        Parameters
        ----------
        msg : str
            Command string to query

        Returns
        -------
        float or None
            The response as a float, or None if conversion fails
        """
        ret = self.query(msg)
        try:
            return float(ret)
        except ValueError:
            logger.info("%s.query_float: float conversion error ('%s', %s)", self.name, msg, ret)

    # High level functions
    def get_temp(self, channel):
        """
        Get the temperature of a channel.

        Parameters
        ----------
        channel : str
            The channel to query

        Returns
        -------
        float or None
            The temperature of the channel, or None if query fails
        """
        return self.query_float(f"{channel}?")

    @synchronized
    def set_setpoint(self, setpoint, channel):
        """
        Set the setpoint of a channel.

        Parameters
        ----------
        setpoint : float
            The temperature setpoint to set
        channel : str
            The channel to set the setpoint for

        Returns
        -------
        None
        """
        try:
            setpoint = float(setpoint)
            if 0 > setpoint or self.setlimit < setpoint:
                return
            self.write(f"{channel}.PID.Setpoint {setpoint:3f}")
        except ValueError:
            return

    @synchronized
    def get_setpoint(self, channel):
        """
        Get the current internal setpoint of a channel.

        Parameters
        ----------
        channel : str
            The channel to query

        Returns
        -------
        float or None
            The current setpoint, or None if query fails
        """
        # return self.query_float(f"{channel}.PID.Setpoint?")
        # above is the line to return the actual/final setpoint
        return self.query_float(f"{channel}.PID.RampT?")

    @synchronized
    def get_power(self, channel):
        """
        Get the power on a channel.

        Parameters
        ----------
        channel : str
            The channel to query

        Returns
        -------
        float or None
            The power level, or None if query fails
        """
        return self.query_float(f"{channel}?")

    @synchronized
    def set_power(self, power, channel):
        """
        Set the power on a channel.

        Parameters
        ----------
        power : float
            The power level to set (0-50)
        channel : str
            The channel to set the power for

        Returns
        -------
        None
        """
        try:
            power = float(power)
            if power >= 0 and power < 50:
                self.write(f"{channel}.value = {power}")
        except ValueError:
            return

    @synchronized
    def get_pid(self, channel):
        """
        Get the PID parameters for a channel.

        Parameters
        ----------
        channel : str
            The channel to query

        Returns
        -------
        tuple
            A tuple containing (P, I, D) parameters
        """
        return (
            self.query_float(f"{channel}.PID.P?"),
            self.query_float(f"{channel}.PID.I?"),
            self.query_float(f"{channel}.PID.D?"),
        )

    @synchronized
    def set_pid(self, pid, channel):
        """
        Set the PID parameters for a channel.

        Parameters
        ----------
        pid : tuple
            A tuple containing (P, I, D) parameters
        channel : str
            The channel to set the PID parameters for

        Returns
        -------
        None
        """
        pid = list(pid)
        self.write(f"{channel}.PID.P {pid[0]}")
        self.write(f"{channel}.PID.I {pid[1]}")
        self.write(f"{channel}.PID.D {pid[2]}")

    @synchronized
    def set_ramp(self, rate, channel):
        """
        Set the ramp rate for a channel.

        Parameters
        ----------
        rate : float
            The temperature ramp rate to set
        channel : str
            The channel to set the ramp rate for

        Returns
        -------
        None
        """
        rate = float(rate)
        self.write(f"{channel}.PID.Ramp {rate}")

    @synchronized
    def get_ramp(self, channel):
        """
        Get the ramp rate for a channel.

        Parameters
        ----------
        channel : str
            The channel to query

        Returns
        -------
        float or None
            The current ramp rate, or None if query fails
        """
        return self.query_float(f"{channel}.PID.Ramp?")

    @synchronized
    def get_state(self, channel):
        """
        Get the state of the PID control for a channel.

        Parameters
        ----------
        channel : str
            The channel to query

        Returns
        -------
        bool
            True if PID control is on, False otherwise
        """
        ret = self.query(f"{channel}.PID.Mode?")
        return True if ret == "On" else False

    @synchronized
    def set_state(self, state, channel):
        """
        Enable or disable the PID control for a channel.

        Parameters
        ----------
        state : bool
            True to enable PID control, False to disable
        channel : str
            The channel to set the state for

        Returns
        -------
        None
        """
        state = "On" if state is True else "Off"
        self.write(f"{channel}.PID.Mode {state}")

    @synchronized
    def set_output_enabled(self, state):
        """
        Set the global output state.

        Parameters
        ----------
        state : bool
            True to enable output, False to disable

        Returns
        -------
        None
        """
        state = "On" if state is True else "Off"
        self.write(f"OutputEnable {state}")

    @synchronized
    def get_output_enabled(self):
        """
        Get the global output state.

        Returns
        -------
        bool
            True if output is enabled, False otherwise
        """
        ret = self.query("OutputEnable?")
        return True if ret == "On" else False

    @synchronized
    def disable_channel(self, channel):
        """
        Turn off heater on a channel.

        Only works for output channels. The channel can be reenabled by
        turning on PID control using set_state.

        Parameters
        ----------
        channel : str
            The channel to disable

        Returns
        -------
        None
        """
        self.write(f"{channel}.Off")
