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
"""Module for interfacing with Oxford Instruments devices via Isobus protocol."""

import logging
import time

from pyvisa import errors
from wrapt import synchronized

from matr1x.devices.visadevice import VisaDevice

logger = logging.getLogger(__name__)


class IsobusDevice(VisaDevice):
    """Base class for Oxford Instruments devices using the ISOBUS protocol.

    This class extends VisaDevice to handle the specific communication requirements
    of Oxford Instruments devices connected via ISOBUS.
    """

    def __init__(self, interface, **kwargs):
        """Initialize an ISOBUS device.

        Parameters
        ----------
        interface : str
            VISA resource name of the interface
        **kwargs : dict
            Additional keyword arguments

            - isobus_addr : str, optional
                ISOBUS address for the device
            - query_delay : float, optional
                Delay between queries, defaults to 0.05 seconds
        """
        self.isobus_addr = kwargs.pop("isobus_addr", None)
        if "query_delay" not in kwargs:
            kwargs["query_delay"] = 0.05
        super().__init__(interface, **kwargs)

    def id(self):
        """Get the device identification.

        Returns
        -------
        str
            Device identification string
        """
        return self.query("V")

    @synchronized
    def write(self, msg):
        """Write a message to the device with ISOBUS address prepended.

        Parameters
        ----------
        msg : str
            Message to send to the device
        """
        if self.isobus_addr is not None:
            if msg.startswith("$"):
                cmd = f"$@{self.isobus_addr}{msg[1:]}"
            else:
                cmd = f"@{self.isobus_addr}{msg}"
        else:
            cmd = msg
        super().write(cmd)

    @synchronized
    def query(self, msg, depth=0, max_depth=2):
        """Send a query to the device and get the response with error handling.

        Includes automatic retries with progressive delay for error recovery.

        Parameters
        ----------
        msg : str
            Query message to send
        depth : int, optional
            Current retry depth, by default 0
        max_depth : int, optional
            Maximum number of retries, by default 2

        Returns
        -------
        str
            Response from the device
        """
        with self.sharedlock:
            if depth > 0:
                time.sleep(3 + depth)  # add progressive delay on repeated failure
            self.read_very_eager()

            if self.isobus_addr is not None:
                cmd = f"@{self.isobus_addr}{msg}"
            else:
                cmd = msg

            if depth > max_depth:
                logger.info(f"{self.name}.query: maximum depth exeeded ('{msg}')")
                ret = super().query(cmd)

            try:
                # call unwrapped instance here since we do our own error handling
                ret = super().query.__wrapped__(cmd)
            except UnicodeDecodeError:
                logger.info(f"{self.name}.query: UnicodeDecodeError, {msg}, {depth}")
                return self.query(msg, depth + 1, max_depth=max_depth)
            except errors.VisaIOError:
                logger.info(f"{self.name}.query: VisaIOError, {msg}, {depth}")
                return self.query(msg, depth + 1, max_depth=max_depth)

            if ret is None:
                logger.info(f"{self.name}.query: None, {msg}, {depth}")
                ret = self.query(msg, depth + 1, max_depth=max_depth)
            if "?" in ret:
                logger.info(f"{self.name}.query: reply '?', {msg}, {depth}")
                ret = self.query(msg, depth + 1, max_depth=max_depth)
            elif "" == ret:
                logger.info(f"{self.name}.query: empty reply, {msg}, {depth}")
                ret = self.query(msg, depth + 1, max_depth=max_depth)
            elif msg[0] not in ret:
                logger.info(
                    f"{self.name}.query: wrong reply character, {msg}, {depth}, {ret}"
                )
                try:
                    self.read_very_eager()
                except UnicodeDecodeError:
                    pass
                ret = self.query(msg, depth + 1, max_depth=max_depth)
            return ret

    @synchronized
    def query_float(self, msg, depth=0, max_depth=4):
        """Query a floating point value from the device with error handling.

        Parameters
        ----------
        msg : str
            Query message to send
        depth : int, optional
            Current retry depth, by default 0
        max_depth : int, optional
            Maximum number of retries, by default 4

        Returns
        -------
        float
            Floating point response from the device
        """
        with self.sharedlock:
            ret = self.query(msg, depth=depth, max_depth=max_depth)
            try:
                return float(ret[1:])
            except ValueError:
                logger.info(
                    f"{self.name}.query_float: float conversion error ('{msg}', {ret})"
                )
                # retry query
                return self.query_float(msg, depth + 1)
