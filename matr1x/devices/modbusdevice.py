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
Base class for Modbus based device drivers in this package.

In this module the base class for all Modbus based device drivers in
this package is defined. It is itself based on the minimalmodbus library
which handles all the low level communication.
"""

import logging

import minimalmodbus
import serial
from wrapt import synchronized

logger = logging.getLogger(__name__)


class ModbusDevice(minimalmodbus.Instrument):
    """
    A class for communicating with Modbus devices using the minimalmodbus library.

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

    def __init__(
        self,
        portname: str,
        slaveaddress: int,
        baudrate: int,
        parity: str = serial.PARITY_NONE,
    ):
        self.name: str = f"{type(self).__name__}@{portname}({slaveaddress})"
        try:
            super().__init__(portname, slaveaddress)
        except Exception:
            logger.exception("Exception occured inside %s during init.", self.name)
            raise
        if self.serial is None:
            raise ConnectionError(f"Could not open {self.name}.")  # Should never occur!
        self.serial.baudrate = baudrate
        self.serial.parity = parity
        # next line added to potentially prevent problems (no proof this is neeed!)
        # the drawbacks (lower speed) seem however minor!Add commentMore actions
        self.serial.close_port_after_each_call: bool = True
        # self.close_port_after_each_call = True # This would be the intended(?!) call.

    @synchronized
    def read_register(self, *args, **kwargs):
        """
        Read a Modbus register.

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
        try:
            ret = super().read_register(*args, **kwargs)
        except Exception:
            logger.exception(
                "Exception occured in % during read_register using %s and %s.",
                self.name,
                args,
                kwargs,
            )
            raise
        return ret

    @synchronized
    def write_register(self, *args, **kwargs) -> None:
        """
        Write to a Modbus register.

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
        try:
            super().write_register(*args, **kwargs)
        except Exception:
            logger.exception(
                "Exception occured in % during write_register using %s and %s.",
                self.name,
                args,
                kwargs,
            )
            raise
