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
"""Module for Horst HTMC11 bakeout controller."""

import enum

import serial
from wrapt import synchronized

from matr1x.devices.modbusdevice import ModbusDevice


class HorstManualMode(enum.Enum):
    """Manual mode setting for the Horst HTMC11."""

    OFF = 0
    AUTO = 1
    MANUAL = 2


class HTMC11(ModbusDevice):
    """
    Instrument class for the Horst HTMC11 bakeout controller.

    connection is made via a RS485 serial line which uses the Modbus RTU
    protocol.
    """

    def __init__(self, portname, slaveaddress, baudrate=115200):
        """
        Initialize Horst HTMC11 bakeout controller.

        Parameters
        ----------
        portname : str
            Name of the serial port to connect to
        slaveaddress : int
            Modbus slave address of the device
        baudrate : int, optional
            Serial communication speed in baud. Default is 115200
        """
        super().__init__(portname, slaveaddress, baudrate, parity=serial.PARITY_NONE)
        self._number_of_decimals = int(self.read_register(0x1D00)) + 1

    @synchronized
    def write_register(self, *args, **kwargs) -> None:
        """
        Write to a Modbus register using functioncode 6.

        Parameters
        ----------
        *args : tuple
            Variable length argument list passed to superclass
        **kwargs : dict
            Arbitrary keyword arguments passed to superclass

        Returns
        -------
        None
        """
        kwargs["functioncode"] = 6
        super().write_register(*args, **kwargs)

    @property
    def temperature(self) -> float:
        """
        Get the current temperature.

        Returns
        -------
        float
            The current temperature reading.
        """
        return self.read_register(0x1000, self._number_of_decimals)

    @property
    def temperature2(self) -> int:
        """
        Get the second temperature reading.

        Returns
        -------
        int
            The second temperature reading.
        """
        return self.read_register(0x1400, 1)

    @property
    def current_setpoint(self) -> int:
        """
        Get the current setpoint.

        Returns
        -------
        int
            The current setpoint value.
        """
        return self.read_register(0x2000)

    @property
    def heater_current(self) -> float:
        """
        Get the heater current.

        Returns
        -------
        float
            The heater current reading.
        """
        return self.read_register(0x1100, self._number_of_decimals)

    @property
    def actual_output_ratio(self) -> int:
        """
        Get the actual output ratio.

        Returns
        -------
        int
            The actual output ratio value.
        """
        return self.read_register(0x6000)

    @property
    def setpoint1(self) -> int:
        """
        Get the first setpoint.

        Returns
        -------
        int
            The first setpoint value.
        """
        return self.read_register(0x2100)

    @setpoint1.setter
    def setpoint1(self, value: int) -> None:
        """
        Set the first setpoint.

        Parameters
        ----------
        value : int
            The setpoint value to set.
        """
        self.write_register(0x2100, value)

    @property
    def manual_output_ratio(self) -> int:
        """
        Get the manual output ratio.

        Returns
        -------
        int
            The manual output ratio value.
        """
        return self.read_register(0x6200)

    @manual_output_ratio.setter
    def manual_output_ratio(self, value: int) -> None:
        """
        Set the manual output ratio.

        Parameters
        ----------
        value : int
            The manual output ratio value to set (0-100).
        """
        value = max(0, min(100, value))
        self.write_register(0x6200, value)

    @property
    def manual_mode(self) -> HorstManualMode:
        """
        Get the manual mode.

        Returns
        -------
        HorstManualMode
            The current manual mode.
        """
        mode = self.read_register(0x8B00)
        return HorstManualMode(mode)

    @manual_mode.setter
    def manual_mode(self, mode: HorstManualMode) -> None:
        """
        Set the manual mode.

        Parameters
        ----------
        mode : HorstManualMode
            The manual mode to set.

        Raises
        ------
        ValueError
            If an unknown mode is set.
        """
        if isinstance(mode, HorstManualMode):
            self.write_register(0x8B00, mode.value)
        else:
            raise ValueError("unknown mode to set")

    @property
    def proportional_band(self) -> float:
        """
        Get the proportional band.

        Returns
        -------
        int
            The proportional band value.
        """
        return self.read_register(0x4000, 1)

    @proportional_band.setter
    def proportional_band(self, value: int) -> None:
        """
        Set the proportional band.

        Parameters
        ----------
        value : int
            The proportional band value to set.
        """
        self.write_register(0x4000, value * 10)

    @property
    def integral_time(self) -> int:
        """
        Get the integral time.

        Returns
        -------
        int
            The integral time value.
        """
        return self.read_register(0x4200)

    @integral_time.setter
    def integral_time(self, value: int) -> None:
        """
        Set the integral time.

        Parameters
        ----------
        value : int
            The integral time value to set.
        """
        self.write_register(0x4200, value)

    @property
    def derivative_time(self) -> int:
        """
        Get the derivative time.

        Returns
        -------
        int
            The derivative time value.
        """
        return self.read_register(0x4100)

    @derivative_time.setter
    def derivative_time(self, value: int) -> None:
        """
        Set the derivative time.

        Parameters
        ----------
        value : int
            The derivative time value to set.
        """
        self.write_register(0x4100, value)

    @property
    def cycle_time(self) -> float:
        """
        Get the cycle time.

        Returns
        -------
        int
            The cycle time value.
        """
        return self.read_register(0x4300, 1)

    @cycle_time.setter
    def cycle_time(self, value: int) -> None:
        """
        Set the cycle time.

        Parameters
        ----------
        value : int
            The cycle time value to set.
        """
        self.write_register(0x4300, value * 10)
