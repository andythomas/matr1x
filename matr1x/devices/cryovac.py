# This file is part of a software collection for data aquisition (matr1x).
# Copyright (C) 2024 matr1x developers
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

import logging

from wrapt import synchronized

from .visadevice import VisaDevice

logger = logging.getLogger(__name__)


class TIC500(VisaDevice):
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
        """routine to query a float including error checking"""
        ret = self.query(msg)
        try:
            return float(ret)
        except ValueError:
            logger.info(
                f"{self.name}.query_float: float conversion error ('{msg}', {ret})")

    # High level functions
    def get_temp(self, channel):
        """ Returns the temperature of `channel` """
        return self.query_float(f"{channel}?")

    @synchronized
    def set_setpoint(self, setpoint, channel):
        """ Sets the setpoint of `channel` """
        try:
            setpoint = float(setpoint)
            if 0 > setpoint or self.setlimit < setpoint:
                return
            self.write(f"{channel}.PID.Setpoint {setpoint:3f}")
        except ValueError:
            return

    @synchronized
    def get_setpoint(self, channel):
        """ Returns the current internal setpoint of `channel` """
        # return self.query_float(f"{channel}.PID.Setpoint?")
        # above is the line to return the actual/final setpoint
        return self.query_float(f"{channel}.PID.RampT?")

    @synchronized
    def get_power(self, channel):
        """ Returns the power on `channel` """
        return self.query_float(f"{channel}?")

    @synchronized
    def set_power(self, power, channel):
        """ sets the power on `channel` """
        try:
            power = float(power)
            if power >= 0 and power < 50:
                self.write(f"{channel}.value = {power}")
        except ValueError:
            return

    @synchronized
    def get_pid(self, channel):
        """ returns the pid parameters (tuple with length 3) on `channel` """
        return (self.query_float(f"{channel}.PID.P?"),
                self.query_float(f"{channel}.PID.I?"),
                self.query_float(f"{channel}.PID.D?"))

    @synchronized
    def set_pid(self, pid, channel):
        """ sets the pid parameters (tuple with length 3) on `channel` """
        pid = list(pid)
        self.write(f"{channel}.PID.P {pid[0]}"),
        self.write(f"{channel}.PID.I {pid[1]}"),
        self.write(f"{channel}.PID.D {pid[2]}")

    @synchronized
    def set_ramp(self, rate, channel):
        """ sets the ramp rate on `channel` """
        rate = float(rate)
        self.write(f"{channel}.PID.Ramp {rate}")

    @synchronized
    def get_ramp(self, channel):
        """ returns the ramp rate on `channel` """
        return self.query_float(f"{channel}.PID.Ramp?")

    @synchronized
    def get_state(self, channel):
        """ returns the state of the PID control on `channel` """
        ret = self.query(f"{channel}.PID.Mode?")
        return True if ret == "On" else False

    @synchronized
    def set_state(self, state, channel):
        """ enables/disables the PID control on `channel` """
        state = "On" if state is True else "Off"
        self.write(f"{channel}.PID.Mode {state}")

    @synchronized
    def set_output_enabled(self, state):
        """ sets the global output state """
        state = "On" if state is True else "Off"
        self.write(f"OutputEnable {state}")

    @synchronized
    def get_output_enabled(self):
        """ returns the global output state """
        ret = self.query("OutputEnable?")
        return True if ret == "On" else False

    @synchronized
    def disable_channel(self, channel):
        """
        turns off heater on channel (only works for output channels)
        can be reenabled by turning on PID control using set_state
        """
        self.write(f"{channel}.Off")
