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
Base class for Modbus based device drivers in this package.

In this module the base class for all Modbus based device drivers in this package is
defined. It is itself based on the minimalmodbus library which handles all the low
level communication.
"""
import minimalmodbus
import serial
from wrapt import synchronized

from matr1x.devices.visadevice import output_name_on_error


class ModbusDevice(minimalmodbus.Instrument):
    """A class for communicating with Modbus devices using the minimalmodbus library.

    This class extends minimalmodbus.Instrument to provide thread-safe register read/write
    operations with error handling.

    Note that devices implemented based on this class will likely be deprecated in the future.

    Parameters
    ----------
    portname : str
        Name of the serial port
    slaveaddress : int
        Slave address of the Modbus device
    baudrate : int
        Communication speed in baud (bits/s)
    parity : str, optional
        Parity setting for serial communication (default serial.PARITY_NONE)
    """

    @output_name_on_error
    def __init__(self, portname, slaveaddress, baudrate, parity=serial.PARITY_NONE):
        self.name = f"{type(self).__name__}@{portname}({slaveaddress})"
        super().__init__(portname, slaveaddress)
        self.serial.baudrate = baudrate
        self.serial.parity = parity
        # next line added to potentially prevent problems (no proof this is neeed!)
        # the drawbacks (lower speed) seem however minor!Add commentMore actions
        self.serial.close_port_after_each_call = True

    @synchronized
    @output_name_on_error
    def read_register(self, *args, **kwargs):
        """Read a Modbus register.

        Thread-safe wrapper for minimalmodbus register read operation.

        Parameters
        ----------
        *args : tuple
            Variable length argument list passed to superclass
        **kwargs : dict
            Arbitrary keyword arguments passed to superclass

        Returns
        -------
        int
            Value read from register
        """
        return super().read_register(*args, **kwargs)

    @synchronized
    @output_name_on_error
    def write_register(self, *args, **kwargs) -> None:
        """Write to a Modbus register.

        Thread-safe wrapper for minimalmodbus register write operation.

        Parameters
        ----------
        *args
            Variable length argument list passed to superclass
        **kwargs : dict
            Arbitrary keyword arguments passed to superclass

        Returns
        -------
        None
        """
        return super().write_register(*args, **kwargs)
