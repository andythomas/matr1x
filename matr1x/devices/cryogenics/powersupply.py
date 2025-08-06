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
Module for controlling Cryogenic power supplies over VISA interface.

This module provides classes to interact with Cryogenic power supplies,
including standard and bipolar models.
"""

import logging
import math
import re
import time

import pyvisa.errors
from wrapt import synchronized

from matr1x.devices.visadevice import VisaDevice

logger = logging.getLogger(__name__)


class CryogenicPS(VisaDevice):
    """
    Control interface for Cryogenic Power Supply.

    This class provides methods to control and monitor a Cryogenic Power Supply
    using VISA communication.

    Parameters
    ----------
    interface : str
        VISA resource name for the device
    gpib_addr : int, optional
        GPIB address, default is 4
    cmds_pers : int, optional
        Commands per second, default is 5
    field_limit : float, optional
        Maximum field limit in Tesla, default is 5
    **kwargs
        Additional parameters passed to VisaDevice

    Attributes
    ----------
    gpib_addr : int
        GPIB address of the device
    field_limit : float
        Maximum field limit in Tesla
    tpa : float
        Tesla per Ampere conversion factor
    """

    config_params = {"TeslePerAmpere": "tpa"}
    re_output = re.compile(r"OUTPUT: ([0-9\.\-]+) TESLA AT ([0-9\.\-]+) VOLTS")
    re_holding = re.compile(r"HOLDING ON [A-Z]+ AT ([0-9\.\-]+) TESLA")
    re_ramping = re.compile(r"RAMPING FROM [0-9\.\-]+ TO ([0-9\.\-]+) TESLA AT")

    def __init__(self, interface, gpib_addr=4, cmds_pers=5, field_limit=5, **kwargs):
        self.gpib_addr = gpib_addr
        self.field_limit = field_limit
        self.tpa = None
        kwargs["cmds_pers"] = cmds_pers
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r\n"
        if "query_delay" not in kwargs:
            kwargs["query_delay"] = 0.25
        if "timeout" not in kwargs:
            kwargs["timeout"] = 5000
        super().__init__(interface, **kwargs)
        self.write("++addr %d" % self.gpib_addr)
        self.write("++read_tmo_ms 3000")
        self.write("++eoi 0")
        self.write("++eos 0")
        self.write("++auto 0")
        time.sleep(1)
        self.write("++ifc")
        time.sleep(1)
        self.write("++read")
        time.sleep(5)
        self.write("++read")
        time.sleep(5)
        self.write("++read")
        time.sleep(3)
        msg = self.read_very_eager()
        logger.info(f"{self.name}.open: '{msg}'")
        self._id = msg.split("........")[0].strip()
        time.sleep(1)
        self.query("LOCK OFF")
        self.read_very_eager()
        self.query("T ON")
        self.tpa = float(msg[msg.find("FIELD CONSTANT:") :].split()[2])
        self.setMax(self.field_limit)

    def id(self):
        """
        Get the device identifier.

        Returns
        -------
        str
            The device identifier string
        """
        return self._id

    @synchronized
    def query(self, command):
        """
        Send a query command to the device and get the response.

        Parameters
        ----------
        command : str
            Command string to send to the device

        Returns
        -------
        str
            The response from the device
        """
        self.read_very_eager()
        self.write(command)
        time.sleep(self.connection.query_delay)
        return super().query("++read 10")

    @synchronized
    def getUpdate(self):
        """
        Get an update of the device status.

        Returns
        -------
        str
            Status information from the device
        """
        self.read_very_eager()
        self.write("U")
        time.sleep(self.connection.query_delay)
        self.write("++read")
        time.sleep(self.connection.query_delay)
        ret = self.read()
        ret += self.read_very_eager()
        return ret

    @synchronized
    def getStatus(self, depth=0):
        """
        Return field, rate, voltage, and ramp-status.

        Parameters
        ----------
        depth : int, optional
            Retry depth for error handling, default is 0

        Returns
        -------
        tuple
            (field, setpoint, rate, voltage, status)
            where status is either 'HOLDING' or 'RAMPING'
        """
        if depth > 4:
            return -99, 0, 0, 0, 0
        time.sleep(3 * depth)
        try:
            up = self.getUpdate()
        except Exception as e:  # (pyvisa.errors.VisaIOError, UnicodeDecodeError)
            # log incident and retry
            logger.info(f"getStatus: '{type(e).__name__}: {e}'")
            logger.info(f"getStatus: retrying to get update ({depth})")
            return self.getStatus(depth + 1)

        try:
            match = self.re_output.findall(up)[0]
            field = float(match[0])
            setp = float(up[up.find("MID SETTING:") :].split()[2])
            rate = self._as2tmin(float(up[up.find("RAMP RATE:") :].split()[2]))
            voltage = float(match[1])
            status = up[up.find("RAMP STATUS:") :].split()[2]
        except Exception as e:
            # log incident and retry
            logger.info(f"getStatus: '{type(e).__name__}: {e}'")
            logger.info(f"getStatus: retrying to analyze update ({depth})")
            return self.getStatus(depth + 1)
        return field, setp, rate, voltage, status

    @synchronized
    def getOutput(self, depth=0):
        """
        Get the current output field and voltage.

        Parameters
        ----------
        depth : int, optional
            Retry depth for error handling, default is 0

        Returns
        -------
        tuple
            (field, voltage) - current field in Tesla and voltage
            or (math.nan, math.nan) if failed
        """
        if depth > 4:
            return math.nan, math.nan
        time.sleep(3 * depth)
        try:
            ret = self.query("G O")
        except Exception as e:  # (pyvisa.errors.VisaIOError, UnicodeDecodeError)
            # log incident and retry
            logger.info(f"getOutput: '{type(e).__name__}: {e}'")
            logger.info(f"getOutput: retrying to get update ({depth})")
            return self.getOutput(depth + 1)

        match = self.re_output.findall(ret)
        if len(match) >= 1:
            # power supply at stable output, return field and voltage
            return float(match[0][0]), float(match[0][1])
        else:  # something wrong?
            return math.nan, math.nan

    def _tmin2as(self, value):
        """
        Convert Tesla/minute to Amps/second.

        Parameters
        ----------
        value : float
            Rate in Tesla per minute

        Returns
        -------
        float
            Rate in Amps per second
        """
        return value / 60 / self.tpa

    def _as2tmin(self, value):
        """
        Convert Amps/second to Tesla/minute.

        Parameters
        ----------
        value : float
            Rate in Amps per second

        Returns
        -------
        float
            Rate in Tesla per minute
        """
        return value * 60 * self.tpa

    @synchronized
    def get_ramp_status(self, depth=0):
        """
        Get the current ramping status and target field.

        Parameters
        ----------
        depth : int, optional
            Retry depth for error handling, default is 0

        Returns
        -------
        tuple
            (status, field) where status is one of:
            'HOLDING', 'RAMPING', or 'unknown'
        """
        if depth > 4:
            return "unknown", math.nan
        time.sleep(3 * depth)
        try:
            self.write("R S")
            time.sleep(self.connection.query_delay)
            self.write("++read")
            time.sleep(self.connection.query_delay)
            ret = self.read()
            ret += self.read_very_eager()
        except Exception as e:  # (pyvisa.errors.VisaIOError, UnicodeDecodeError)
            # since we are desperate we ignore all other Exceptions as well
            logger.info(f"get_ramp_status: '{type(e).__name__}: {e}'")
            logger.info(f"get_ramp_status: retrying to get update ({depth})")
            return self.get_ramp_status(depth + 1)

        mhold = self.re_holding.findall(ret)
        mramp = self.re_ramping.findall(ret)

        if len(mhold) >= 1:
            # power supply at stable output, return status and setpoint
            return "HOLDING", float(mhold[0])
        elif len(mramp) >= 1:
            # power supply ramping
            return "RAMPING", float(mramp[0])
        else:  # something wrong
            return "unknown", math.nan

    def getRate(self):
        """
        Get the current ramp rate.

        Returns
        -------
        float
            Current ramp rate in Tesla per minute
        """
        up = self.getUpdate()
        return self._as2tmin(float(up[up.find("RAMP RATE:") :].split()[2]))

    def setRate(self, value):
        """
        Set the output ramp rate in Tesla per minute.

        Parameters
        ----------
        value : float
            Desired ramp rate in Tesla per minute

        Returns
        -------
        float
            Actual ramp rate that was set
        """
        if value > 0.52:
            rate = self._tmin2as(0.5)
        else:
            rate = self._tmin2as(value)
        self.write("S R" + str(rate))
        return rate

    @synchronized
    def setOutput(self, value):
        """
        Set the output field using MID value as setpoint.

        Parameters
        ----------
        value : float
            Target field in Tesla
        """
        self.write("S %" + str(value))
        self.write("R MID")

    def setMax(self, value):
        """
        Set the maximum field limit.

        Parameters
        ----------
        value : float
            Maximum field limit in Tesla
        """
        self.query("S !" + str(value))  # ! or MAX is valid

    def setMid(self, value):
        """
        Set the MID field value.

        Parameters
        ----------
        value : float
            Mid field value in Tesla
        """
        self.write("S %" + str(value))  # % or MID is valid

    def setZero(self):
        """Set the field to zero."""
        self.write("R 0")

    def setPause(self):
        """
        Pause the ramping operation.

        Note: Currently not implemented.
        """
        pass


class CryogenicBipolarPS(VisaDevice):
    """
    Control interface for Cryogenic Bipolar Power Supply.

    This class provides methods to control and monitor a Cryogenic Bipolar Power
    Supply using VISA communication. It supports both positive and negative fields.

    Parameters
    ----------
    interface : str
        VISA resource name for the device
    cmds_pers : int, optional
        Commands per second, default is 5
    field_limit : float, optional
        Maximum field limit in Tesla, default is 5
    **kwargs
        Additional parameters passed to VisaDevice

    Attributes
    ----------
    field_limit : float
        Maximum field limit in Tesla
    tpa : float
        Tesla per Ampere conversion factor
    """

    config_params = {"TeslePerAmpere": "tpa"}
    re_output = re.compile(r"OUTPUT: ([0-9\.\-]+) TESLA AT ([0-9\.\-]+) VOLTS")
    re_holding = re.compile(r"HOLDING ON [A-Z]+ AT ([0-9\.\-]+) TESLA")
    re_ramping = re.compile(r"RAMPING FROM [0-9\.\-]+ TO ([0-9\.\-]+) TESLA AT")
    re_mid = re.compile(r"MID SETTING: ([0-9\.\-]+) TESLA")

    def __init__(self, interface, cmds_pers=5, field_limit=5, **kwargs):
        self.field_limit = field_limit
        self.tpa = None
        kwargs["cmds_pers"] = cmds_pers
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r\n"
        if "query_delay" not in kwargs:
            kwargs["query_delay"] = 0.25
        if "timeout" not in kwargs:
            kwargs["timeout"] = 5000
        super().__init__(interface, **kwargs)
        self.query("LOCK OFF")
        self.query("T ON")
        time.sleep(1)
        msg = self.query("G T")
        self.tpa = float(msg[msg.find("FIELD CONSTANT:") :].split()[2])
        self.setMax(self.field_limit)

    def id(self):
        """
        Get the device identifier.

        Returns
        -------
        str
            The device identifier string
        """
        return "SMC120C"

    @synchronized
    def read_very_eager(self):
        """
        Read from device without blocking IO.

        This method sets a short timeout and reads as much data as available
        without blocking.

        Returns
        -------
        str
            The data read from the device
        """
        t = self.connection.timeout
        self.connection.timeout = 250
        ret = ""
        try:
            while True:
                ret += self.connection.read()
        except pyvisa.errors.VisaIOError:
            pass
        self.connection.timeout = t
        return ret

    @synchronized
    def query(self, command):
        """
        Send a query command to the device and get the response.

        Parameters
        ----------
        command : str
            Command string to send to the device

        Returns
        -------
        str
            The response from the device
        """
        self.read_very_eager()
        return super().query(command)

    @synchronized
    def getUpdate(self):
        """
        Get an update of the device status.

        Returns
        -------
        str
            Status information from the device
        """
        ret = self.query("U")
        ret += self.read_very_eager()
        return ret

    @synchronized
    def getStatus(self, depth=0):
        """
        Return field, rate, voltage, and ramp-status.

        Parameters
        ----------
        depth : int, optional
            Retry depth for error handling, default is 0

        Returns
        -------
        tuple
            (field, setpoint, rate, voltage, status)
            where status is either 'HOLDING' or 'RAMPING'
        """
        if depth > 4:
            return -99, 0, 0, 0, 0
        time.sleep(3 * depth)
        try:
            up = self.getUpdate()
        except Exception as e:  # (pyvisa.errors.VisaIOError, UnicodeDecodeError)
            # log incident and retry
            logger.info(f"getStatus: '{type(e).__name__}: {e}'")
            logger.info(f"getStatus: retrying to get update ({depth})")
            return self.getStatus(depth + 1)

        try:
            match = self.re_output.findall(up)[0]
            field = float(match[0])
            setp = float(up[up.find("MID SETTING:") :].split()[2])
            rate = self._as2tmin(float(up[up.find("RAMP RATE:") :].split()[2]))
            voltage = float(match[1])
            status = up[up.find("RAMP STATUS:") :].split()[2]
        except Exception as e:
            # log incident and retry
            logger.info(f"getStatus: '{type(e).__name__}: {e}'")
            logger.info(f"getStatus: retrying to analyze update ({depth})")
            return self.getStatus(depth + 1)
        return field, setp, rate, voltage, status

    @synchronized
    def getOutput(self, depth=0):
        """
        Get the current output field and voltage.

        Parameters
        ----------
        depth : int, optional
            Retry depth for error handling, default is 0

        Returns
        -------
        tuple
            (field, voltage) - current field in Tesla and voltage
            or (math.nan, math.nan) if failed
        """
        if depth > 4:
            return math.nan, math.nan
        time.sleep(3 * depth)
        try:
            ret = self.query("G O")
        except Exception as e:  # (pyvisa.errors.VisaIOError, UnicodeDecodeError)
            # log incident and retry
            logger.info(f"getOutput: '{type(e).__name__}: {e}'")
            logger.info(f"getOutput: retrying to get update ({depth})")
            return self.getOutput(depth + 1)

        match = self.re_output.findall(ret)
        if len(match) >= 1:
            # power supply at stable output, return field and voltage
            return float(match[0][0]), float(match[0][1])
        else:  # something wrong?
            return math.nan, math.nan

    def _tmin2as(self, value):
        """
        Convert Tesla/minute to Amps/second.

        Parameters
        ----------
        value : float
            Rate in Tesla per minute

        Returns
        -------
        float
            Rate in Amps per second
        """
        return value / 60 / self.tpa

    def _as2tmin(self, value):
        """
        Convert Amps/second to Tesla/minute.

        Parameters
        ----------
        value : float
            Rate in Amps per second

        Returns
        -------
        float
            Rate in Tesla per minute
        """
        return value * 60 * self.tpa

    @synchronized
    def get_ramp_status(self, depth=0):
        """
        Get the current ramping status and target field.

        Parameters
        ----------
        depth : int, optional
            Retry depth for error handling, default is 0

        Returns
        -------
        tuple
            (status, field) where status is one of:
            'HOLDING', 'RAMPING', or 'unknown'
        """
        if depth > 4:
            return "unknown", math.nan
        time.sleep(3 * depth)
        try:
            ret = self.query("R S")
            ret += self.read_very_eager()
        except Exception as e:  # (pyvisa.errors.VisaIOError, UnicodeDecodeError)
            # since we are desperate we ignore all other Exceptions as well
            logger.info(f"get_ramp_status: '{type(e).__name__}: {e}'")
            logger.info(f"get_ramp_status: retrying to get update ({depth})")
            return self.get_ramp_status(depth + 1)

        mhold = self.re_holding.findall(ret)
        mramp = self.re_ramping.findall(ret)

        if len(mhold) >= 1:
            # power supply at stable output, return status and setpoint
            return "HOLDING", float(mhold[0])
        elif len(mramp) >= 1:
            # power supply ramping
            return "RAMPING", float(mramp[0])
        else:  # something wrong
            return "unknown", math.nan

    def getRate(self):
        """
        Get the current ramp rate.

        Returns
        -------
        float
            Current ramp rate in Tesla per minute
        """
        up = self.getUpdate()
        return self._as2tmin(float(up[up.find("RAMP RATE:") :].split()[2]))

    def setRate(self, value):
        """
        Set the output ramp rate in Tesla per minute.

        Parameters
        ----------
        value : float
            Desired ramp rate in Tesla per minute

        Returns
        -------
        float
            Actual ramp rate that was set
        """
        if value > 0.52:
            rate = self._tmin2as(0.5)
        else:
            rate = self._tmin2as(value)
        self.write("S R" + str(rate))
        return rate

    @synchronized
    def setOutput(self, value):
        """
        Set the output field using MID value as setpoint.

        Automatically sets the direction (+ or -) based on the sign of the value.

        Parameters
        ----------
        value : float
            Target field in Tesla
        """
        self.write("S %" + str(value))
        self.write("R MID")
        if value >= 0:
            self.write("D +")
        else:
            self.write("D -")
        time.sleep(1)  # here one needs to wait to ensure the sign changed

    def setMax(self, value):
        """
        Set the maximum field limit.

        This also ensures the mid value is within the field limit.

        Parameters
        ----------
        value : float
            Maximum field limit in Tesla
        """
        m = self.query("G %")
        mid = float(self.re_mid.findall(m)[0])
        if abs(mid) > value:
            self.setMid(math.copysign(value, mid))
        self.query("S !" + str(value))  # ! or MAX is valid

    def setMid(self, value):
        """
        Set the MID field value.

        Parameters
        ----------
        value : float
            Mid field value in Tesla
        """
        self.write("S %" + str(value))  # % or MID is valid

    def setZero(self):
        """Set the field to zero."""
        self.write("R 0")

    def setPause(self):
        """
        Pause the ramping operation.

        Note: Currently not implemented.
        """
        pass
