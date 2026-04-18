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
"""Module for Tempco 9300 temperature controller."""

import enum

import serial

from matr1x.devices.modbusdevice import ModbusDevice


class TempcoMode(enum.Enum):
    """
    Temperature controller operation modes.

    Parameters
    ----------
    PID : int
        PID control mode
    CALIBRATION : int
        Calibration mode
    AUTOTUNE : int
        Auto-tuning mode
    FAILURE : int
        Failure mode
    MANUAL : int
        Manual control mode
    SLEEP : int
        Sleep mode
    RAMP : int
        Temperature ramping mode
    """

    PID = 0
    CALIBRATION = 1
    AUTOTUNE = 2
    FAILURE = 3
    MANUAL = 4
    SLEEP = 5
    RAMP = 6


class Tempco9300(ModbusDevice):
    """
    Instrument class for the Tempco 9300 temperature controller.

    connection is made via a RS485 serial line which uses the Modbus RTU
    protocol.
    """

    def __init__(self, portname: str, slaveaddress: int, baudrate: int = 38400):
        """
        Initialize Tempco 9300 temperature controller.

        Parameters
        ----------
        portname : str
            Name of the serial port to connect to
        slaveaddress : int
            Modbus slave address of the device
        baudrate : int, optional
            Serial communication speed in baud. Default is 38400
        """
        super().__init__(portname, slaveaddress, baudrate, parity=serial.PARITY_EVEN)

    @staticmethod
    def value2int(temp: float) -> int:
        """
        Convert floating-point value to integer representation.

        Parameters
        ----------
        temp : float
            Floating-point value.

        Returns
        -------
        int
            Integer representation of the value.
        """
        return int(temp * 10 + 19999)

    @staticmethod
    def int2value(value: int) -> float:
        """
        Convert integer representation to floating-point value.

        Parameters
        ----------
        value : int
            Integer representation of the floating-point value.

        Returns
        -------
        float
            Floating-point representation of the value.
        """
        return (value - 19999) / 10

    @property
    def temperature(self) -> float:
        """
        Get the current temperature.

        Returns
        -------
        float
            The current temperature reading.
        """
        return self.int2value(self.read_register(128))

    @property
    def current_setpoint(self) -> float:
        """
        Get the current setpoint.

        Returns
        -------
        float
            The current setpoint value.
        """
        return self.int2value(self.read_register(129))

    @property
    def target_setpoint(self) -> float:
        """
        Get the target setpoint.

        Returns
        -------
        float
            The target setpoint value.
        """
        return self.int2value(self.read_register(148))

    @property
    def power(self) -> float:
        """
        Get the current power output.

        Returns
        -------
        float
            The current power output.
        """
        return self.read_register(130, number_of_decimals=2)

    @property
    def setpoint1(self) -> float:
        """
        Get the first setpoint.

        Returns
        -------
        float
            The first setpoint value.
        """
        return self.int2value(self.read_register(0))

    @setpoint1.setter
    def setpoint1(self, value: float) -> None:
        """
        Set the first setpoint.

        Parameters
        ----------
        value : float
            The setpoint value to set.
        """
        self.write_register(0, self.value2int(value))

    @property
    def ramp_rate(self) -> float:
        """
        Get the ramp rate.

        Returns
        -------
        float
            The ramp rate value.
        """
        return self.read_register(6) / 10

    @ramp_rate.setter
    def ramp_rate(self, value: float) -> None:
        """
        Set the ramp rate.

        Parameters
        ----------
        value : float
            The ramp rate value to set.
        """
        self.write_register(6, value * 10)

    @property
    def manual_power(self) -> float:
        """
        Get the manual power.

        Returns
        -------
        float
            The manual power value.
        """
        return self.int2value(self.read_register(52))

    @manual_power.setter
    def manual_power(self, value: float) -> None:
        """
        Set the manual power.

        Parameters
        ----------
        value : float
            The manual power value to set.
        """
        self.write_register(52, self.value2int(value))

    @property
    def control_mode(self) -> TempcoMode:
        """
        Get the control mode.

        Returns
        -------
        TempcoMode
            The current control mode.
        """
        mode = self.read_register(141)
        if mode == 0:
            setpoint_mode = self.read_register(68)
            if setpoint_mode == 1:
                return TempcoMode.RAMP
        elif mode > 5:
            raise ValueError("unknown mode value in register 141")
        return TempcoMode(mode)

    @control_mode.setter
    def control_mode(self, mode: TempcoMode) -> None:
        """
        Set the control mode.

        Parameters
        ----------
        mode : TempcoMode
            The control mode to set.

        Raises
        ------
        ValueError
            If an unknown mode is set.
        """
        if mode == TempcoMode.PID:
            self.write_register(142, 0x6825)
            self.write_register(68, 0)
        elif mode == TempcoMode.AUTOTUNE:
            self.write_register(142, 0x6828)
        elif mode == TempcoMode.MANUAL:
            self.write_register(68, 0)
            self.write_register(142, 0x6827)
        elif mode == TempcoMode.RAMP:
            self.write_register(142, 0x6825)
            self.write_register(68, 1)
        else:
            raise ValueError("unknown mode to set")

    @property
    def offset(self) -> float:
        """
        Get the offset.

        Returns
        -------
        float
            The offset value.
        """
        return self.read_register(7) / 10

    @offset.setter
    def offset(self, value: float) -> None:
        """
        Set the offset.

        Parameters
        ----------
        value : float
            The offset value to set.
        """
        self.write_register(7, int(value * 10))

    @property
    def power_limit(self) -> int:
        """
        Get the power limit.

        Returns
        -------
        int
            The power limit value.
        """
        return self.read_register(22)

    @power_limit.setter
    def power_limit(self, value: int) -> None:
        """
        Set the power limit.

        Parameters
        ----------
        value : int
            The power limit value to set.
        """
        self.write_register(22, value)

    @property
    def proportional_band1(self) -> float:
        """
        Get the proportional band 1.

        Returns
        -------
        float
            The proportional band 1 value.
        """
        return self.read_register(10) / 10

    @proportional_band1.setter
    def proportional_band1(self, value: float) -> None:
        """
        Set the proportional band 1.

        Parameters
        ----------
        value : float
            The proportional band 1 value to set.
        """
        self.write_register(10, value * 10)

    @property
    def integral_time1(self) -> int:
        """
        Get the integral time 1.

        Returns
        -------
        int
            The integral time 1 value.
        """
        return self.read_register(11)

    @integral_time1.setter
    def integral_time1(self, value: int) -> None:
        """
        Set the integral time 1.

        Parameters
        ----------
        value : int
            The integral time 1 value to set.
        """
        self.write_register(11, value)

    @property
    def derivative_time1(self) -> float:
        """
        Get the derivative time 1.

        Returns
        -------
        float
            The derivative time 1 value.
        """
        return self.read_register(12) / 10

    @derivative_time1.setter
    def derivative_time1(self, value: float) -> None:
        """
        Set the derivative time 1.

        Parameters
        ----------
        value : float
            The derivative time 1 value to set.
        """
        self.write_register(12, int(value * 10))

    @property
    def proportional_band2(self) -> float:
        """
        Get the proportional band 2.

        Returns
        -------
        float
            The proportional band 2 value.
        """
        return self.read_register(16) / 10

    @proportional_band2.setter
    def proportional_band2(self, value: float) -> None:
        """
        Set the proportional band 2.

        Parameters
        ----------
        value : float
            The proportional band 2 value to set.
        """
        self.write_register(16, int(value * 10))

    @property
    def integral_time2(self) -> int:
        """
        Get the integral time 2.

        Returns
        -------
        int
            The integral time 2 value.
        """
        return self.read_register(17)

    @integral_time2.setter
    def integral_time2(self, value: int) -> None:
        """
        Set the integral time 2.

        Parameters
        ----------
        value : int
            The integral time 2 value to set.
        """
        self.write_register(17, value)

    @property
    def derivative_time2(self) -> float:
        """
        Get the derivative time 2.

        Returns
        -------
        float
            The derivative time 2 value.
        """
        return self.read_register(18) / 10

    @derivative_time2.setter
    def derivative_time2(self, value: float) -> None:
        """
        Set the derivative time 2.

        Parameters
        ----------
        value : float
            The derivative time 2 value to set.
        """
        self.write_register(18, int(value * 10))
