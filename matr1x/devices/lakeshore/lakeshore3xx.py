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
Interface implementation for Lakeshore temperature controllers.

This module provides classes to interact with various Lakeshore
temperature controllers of the 3xx series.
"""

import logging
import math
import time

from pyvisa import constants
from wrapt import synchronized

from matr1x.devices.util import listToStr, strToList
from matr1x.devices.visadevice import VisaDevice

logger = logging.getLogger(__name__)


class Lakeshore3xx(VisaDevice):
    """
    Base class for Lakeshore 3xx series temperature controllers.

    This class provides common functionality for all Lakeshore 3xx series
    temperature controllers.

    Attributes
    ----------
    config_params : dict
        Dictionary containing configuration parameters.
    channel : str
        Default channel to use for measurements.
    setlimit : float
        Upper temperature limit for setpoints.
    """

    config_params = {
        "CurveName": "getActiveCurveName",
        "PID": "getPID",
        "Ramp mode and rate": "getRamp",
    }

    def __init__(self, interface, **kwargs):
        """
        Initialize the Lakeshore controller.

        Parameters
        ----------
        interface : str
            VISA resource string for the instrument.
        **kwargs : dict
            Additional keyword arguments.
            - channel: Default channel to use (default: "B")
            - setlimit: Maximum allowed setpoint temperature (default: 321)
            - write_termination: Command termination character (default: LF)
            - read_termination: Response termination character (default: LF)
            - timeout: Connection timeout in milliseconds (default: 2000)
            - cmdpers: Commands per second limit (default: 20)
        """
        self.channel = kwargs.pop("channel", "B")
        self.setlimit = kwargs.pop("setlimit", 321)
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 2000
        if "cmdpers" not in kwargs:
            kwargs["cmdpers"] = 20
        super().__init__(interface, **kwargs)

    @synchronized
    def query(self, command: str, depth: int = 0) -> str:
        """
        Send a query to the device and return the response.

        This method includes automatic retry logic and error handling.

        Parameters
        ----------
        command : str
            The command to send to the device.
        depth : int, optional
            Current retry depth, by default 0.

        Returns
        -------
        str
            The response from the device.
        """
        if depth > 5:
            logger.info("%s.query: maximal depth exceeded ('%s')", self.name, command)
            if command.startswith("PID?") or command.startswith("RAMP?"):
                return "0,0,0"
            else:
                return "0"
        self.write(command)
        ret = self.read()
        if ret == "":
            logger.info(
                "%s.query: empty reply, reopening interface ('%s', '%s')", self.name, command, ret
            )
            self.close()
            self.open()
            return self.query(command, depth=depth + 1)
        return ret

    @synchronized
    def query_float(self, msg: str, depth: int = 0) -> float:
        """
        Query a float value from the device with error checking.

        Parameters
        ----------
        msg : str
            The query message to send.
        depth : int, optional
            Current retry depth, by default 0.

        Returns
        -------
        float
            The float value returned by the device.
        """
        ret = self.query(msg, depth)
        try:
            return float(ret)
        except ValueError:
            logger.info("%s.query_float: float conversion error ('%s', %s)", self.name, msg, ret)
            # retry query
            return self.query_float(msg, depth + 1)

    @synchronized
    def query_int(self, msg: str, depth: int = 0) -> int:
        """
        Query an integer value from the device with error checking.

        Parameters
        ----------
        msg : str
            The query message to send.
        depth : int, optional
            Current retry depth, by default 0.

        Returns
        -------
        int
            The integer value returned by the device.
        """
        ret = self.query(msg, depth)
        try:
            return int(ret)
        except ValueError:
            logger.info("%s.query_int: integer conversion error ('%s', %s)", self.name, msg, ret)
            # retry query
            return self.query_int(msg, depth + 1)

    # High level functions
    def getTemp(self, channel: str | None = None) -> float:
        """
        Get the temperature reading from the specified channel.

        Parameters
        ----------
        channel : str, optional
            Channel to read temperature from, by default None which uses the default channel.

        Returns
        -------
        float
            Temperature in Kelvin.
        """
        return float(self.query("KRDG? " + str(channel if channel else self.channel)))

    def getRes(self, channel: str | None = None) -> float:
        """
        Get the resistance reading from the specified channel.

        Parameters
        ----------
        channel : str, optional
            Channel to read resistance from, by default None which uses the default channel.

        Returns
        -------
        float
            Resistance in Ohms.
        """
        return float(self.query("SRDG? " + str(channel if channel else self.channel)))

    def setSetpoint(self, setpoint: float, loop: int = 1) -> None:
        """
        Set the temperature setpoint for the specified control loop.

        Parameters
        ----------
        setpoint : float
            Temperature setpoint value in Kelvin.
        loop : int, optional
            Control loop number, by default 1.
        """
        try:
            setpoint = float(setpoint)
            if 0 > setpoint or self.setlimit < setpoint:
                return
            self.write("SETP " + str(loop) + f",{setpoint:.5f}")
        except ValueError:
            return

    def setManualOutput(self, setpoint: float, loop: int = 1) -> None:
        """
        Set the manual output power for the specified control loop.

        Parameters
        ----------
        setpoint : float
            Manual output power in percent (0-100).
        loop : int, optional
            Control loop number, by default 1.
        """
        try:
            setpoint = float(setpoint)
            if 0 > setpoint or 100 < setpoint:
                return
            self.write("MOUT " + str(loop) + f",{setpoint:.5f}")
        except ValueError:
            return

    def getSetpoint(self, loop: int = 1) -> float:
        """
        Get the temperature setpoint for the specified control loop.

        Parameters
        ----------
        loop : int, optional
            Control loop number, by default 1.

        Returns
        -------
        float
            Temperature setpoint in Kelvin.
        """
        return self.query_float("SETP? " + str(loop))

    def getManualOutput(self, loop: int = 1) -> float:
        """
        Get the manual output power for the specified control loop.

        Parameters
        ----------
        loop : int, optional
            Control loop number, by default 1.

        Returns
        -------
        float
            Manual output power in percent (0-100).
        """
        return self.query_float("MOUT? " + str(loop))

    def getHeater(self, loop: int = 1) -> float:
        """
        Get heater output power value.

        Parameters
        ----------
        loop : int, optional
            Heater loop to query, by default 1.

        Returns
        -------
        float
            Heater output power in percent (0-100).
        """
        return self.query_float(f"HTR? {loop}")

    def getControlMode(self, loop: int = 1) -> int:
        """
        Get the control mode for the specified loop.

        Parameters
        ----------
        loop : int, optional
            Control loop number, by default 1.

        Returns
        -------
        int
            Control mode index.
        """
        return self.query_int("CMODE? " + str(loop)) - 1

    def setControlMode(self, mode: int, loop: int = 1) -> None:
        """
        Set the control mode for the specified loop.

        Parameters
        ----------
        mode : int
            Control mode to set.
        loop : int, optional
            Control loop number, by default 1.
        """
        try:
            mode = int(mode) + 1
            if 1 > mode or 7 < mode:
                return
            self.write("CMODE " + str(loop) + "," + str(mode))
        except ValueError:
            return

    def getPID(self, loop: int = 1) -> list[float]:
        """
        Get the PID parameters for the specified loop.

        Parameters
        ----------
        loop : int, optional
            Control loop number, by default 1.

        Returns
        -------
        List[float]
            List of PID parameters [P, I, D].
        """
        dummy = self.query("PID? " + str(loop))
        return strToList(dummy)

    def setPID(self, pid: list[float], loop: int = 1) -> None:
        """
        Set the PID parameters for the specified loop.

        Parameters
        ----------
        pid : List[float]
            List of PID parameters [P, I, D].
        loop : int, optional
            Control loop number, by default 1.
        """
        pid = list(pid)
        self.write("PID " + str(loop) + "," + listToStr(pid))

    def setRamp(self, args: tuple[bool, float], loop: int = 1) -> None:
        """
        Set the temperature ramp parameters for the specified loop.

        Parameters
        ----------
        args : Tuple[bool, float]
            Tuple containing (ramp_enabled, ramp_rate).
        loop : int, optional
            Control loop number, by default 1.
        """
        state, rate = args
        state = int(bool(state))
        rate = float(rate)
        self.write(f"RAMP {loop:d},{state:d},{rate:.1f}")

    def getRamp(self, loop: int = 1) -> tuple[bool, float]:
        """
        Get the temperature ramp parameters for the specified loop.

        Parameters
        ----------
        loop : int, optional
            Control loop number, by default 1.

        Returns
        -------
        Tuple[bool, float]
            Tuple containing (ramp_enabled, ramp_rate).
        """
        dummy = self.query("RAMP? " + str(loop)).split(",")
        return bool(int(dummy[0])), float(dummy[1])

    def getCurveName(self, curve: int) -> str | None:
        """
        Get the name of the specified temperature calibration curve.

        Parameters
        ----------
        curve : int
            Curve number to query.

        Returns
        -------
        str
            Curve name.
        """
        try:
            curve = int(curve)
            if 0 > curve and 60 < curve:
                return
        except ValueError:
            return
        ret = self.query("CRVHDR? " + str(curve))
        return ret.split(",")[0]

    def getCurveNumber(self, channel: str | None = None) -> int:
        """
        Get the currently active curve number for the specified channel.

        Parameters
        ----------
        channel : str, optional
            Channel to query, by default None which uses the default channel.

        Returns
        -------
        int
            Active curve number.
        """
        return self.query_int("INCRV? " + str(channel if channel else self.channel))

    def getActiveCurveName(self, channel: str | None = None) -> str:
        """
        Get the name of the currently active calibration curve for the specified channel.

        Parameters
        ----------
        channel : str, optional
            Channel to query, by default None which uses the default channel.

        Returns
        -------
        str
            Active curve name.
        """
        return self.getCurveName(self.getCurveNumber(channel=channel))

    @synchronized
    def setCurveNumber(self, curve: int, channel: str | None = None) -> None:
        """
        Set the active calibration curve for the specified channel.

        Parameters
        ----------
        curve : int
            Curve number to set as active.
        channel : str, optional
            Channel to set curve for, by default None which uses the default channel.
        """
        try:
            curve = int(curve)
            if 0 > curve and 60 < curve:
                return
        except ValueError:
            return
        self.write("INCRV " + str(channel if channel else self.channel) + "," + str(curve))
        # wait to activate the change
        time.sleep(3)

    @synchronized
    def writeCurveToIndex(
        self, index: int, name: str, sn: str, rList: list[float], tList: list[float]
    ) -> None:
        """
        Write a calibration curve to the device.

        Parameters
        ----------
        index : int
            Index to store the curve at (21-60).
        name : str
            Name of the curve (max 15 characters).
        sn : str
            Serial number of the sensor (max 10 characters).
        rList : List[float]
            List of resistance values (max 199 points).
        tList : List[float]
            List of temperature values (max 199 points).

        Notes
        -----
        This method only supports Cernox sensors currently.
        """
        index = int(index)
        assert (
            len(rList) == len(tList)
            and 20 < index
            and index < 61
            and len(name) < 16
            and len(sn) < 10
        )
        self.write(f"CRVHDR {index},{name},{sn},4,{self.setlimit:.1f},1")
        time.sleep(0.1)
        for i, (res, temp) in enumerate(zip(rList, tList)):
            self.write(f"CRVPT {index},{i + 1},{math.log10(res):.5f},{temp:.5f},N")
            time.sleep(0.1)


class Lakeshore335(Lakeshore3xx):
    """
    Interface for Lakeshore 335 temperature controller.

    This class extends the base Lakeshore3xx class with specific
    features for the Lakeshore 335 model.
    """

    def __init__(self, interface, **kwargs):
        """
        Initialize Lakeshore 335 temperature controller.

        Parameters
        ----------
        interface : str
            VISA resource string for the instrument.
        **kwargs : dict
            Additional keyword arguments.
            - channel: Default channel to use (default: "A")
            - baud_rate: Serial communication baud rate (default: 57600)
            - data_bits: Number of data bits (default: 7)
            - read_termination: Response termination character (default: CRLF)
            - parity: Parity bit configuration (default: odd)
        """
        if "channel" not in kwargs:
            kwargs["channel"] = "A"
        if "baud_rate" not in kwargs:
            kwargs["baud_rate"] = 57600
        if "data_bits" not in kwargs:
            kwargs["data_bits"] = 7
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r\n"
        if "parity" not in kwargs:
            kwargs["parity"] = constants.Parity.odd
        super().__init__(interface, **kwargs)

    def getHeaterRange(self, loop: int = 1) -> int:
        """
        Get the heater range.

        Parameters
        ----------
        loop : int, optional
            Heater loop to query, by default 1.

        Returns
        -------
        int
            The selected range of the heater loop.
        """
        return self.query_int(f"RANGE? {loop}")

    def setHeaterRange(self, heaterRange: int, loop: int = 1) -> None:
        """
        Set the heater range.

        Parameters
        ----------
        heaterRange : int
            The range to set (0-3, where 0=Off, 1=Low, 2=Med, 3=High).
        loop : int, optional
            Heater loop to set, by default 1.

        Notes
        -----
        The function tests if the range would be correctly set, i.e. 0-3.
        """
        heaterRange = int(heaterRange)
        if 0 > heaterRange or 3 < heaterRange:
            return
        self.write(f"RANGE {loop},{heaterRange}")

    def getControlMode(self, loop: int = 1) -> int:
        """
        Get the control mode of the heater loop.

        Parameters
        ----------
        loop : int, optional
            Heater loop to query, by default 1.

        Returns
        -------
        int
            The control mode of the heater loop
            (0 = Off, 1 = Closed Loop PID, 2 = Zone, 3 = Open Loop,
            4 = Monitor out, 5 = Warmup Supply).
        """
        ret = self.query(f"OUTMODE? {loop}")
        return int(ret.split(",")[0])

    def setControlMode(self, mode: int, loop: int = 1, channel: str = "A") -> None:
        """
        Set the control mode of the heater loop.

        Parameters
        ----------
        mode : int
            The control mode to set (0 = Off, 1 = Closed Loop PID, 2 = Zone, 3 = Open Loop,
            4 = Monitor out, 5 = Warmup Supply).
        loop : int, optional
            Heater loop to set the control mode for, by default 1.
        channel : str, optional
            Channel to set the control mode for (A or B), by default "A".
        """
        channel_num = 0
        if channel == "A":
            channel_num = 1
        elif channel == "B":
            channel_num = 2

        mode = int(mode)
        if 0 > mode or 5 < mode:
            return
        self.write(f"OUTMODE {loop},{mode},{channel_num},1")

    def setManOutput(self, power: float, loop: int = 1) -> None:
        """
        Set the manual output of the heater loop.

        Parameters
        ----------
        power : float
            The manual output power to set (0 to 100 %).
        loop : int, optional
            Heater loop to set the manual output for, by default 1.
        """
        power = float(power)
        if power < 0 or power > 100:
            return
        self.write(f"MOUT {loop},{power}")

    def initiateAutotune(self, mode: int, loop: int = 1) -> None:
        """
        Initiate autotune on the specified heater loop.

        Parameters
        ----------
        mode : int
            The autotune mode to use (0 = P Only, 1 = PI, 2 = PID).
        loop : int, optional
            The heater loop to initiate autotune on, by default 1.
        """
        mode = int(mode)
        if mode < 0 or mode > 2:
            return
        self.write(f"ATUNE {loop},{mode}")

    def getTuningStatus(self) -> list[str]:
        """
        Get the current autotune status.

        Returns
        -------
        List[str]
            A list of strings:
            [0]: 0 = no active tuning, 1 = active tuning.
            [1]: 1 = Output 1, 2 = Output 2
            [2]: 0 = no tuning error, 1 = tuning error
            [3]: stage status
        """
        return self.query("TUNEST?").split(",")

    def setTLimit(self, limit: int, channel: str = "A") -> None:
        """
        Set the temperature limit of the specified channel.

        Parameters
        ----------
        limit : int
            The temperature limit to set (in Kelvin).
        channel : str, optional
            The channel to set the temperature limit for (A or B), by default "A".
        """
        limit = int(limit)
        self.write(f"TLIMIT {channel},{limit}")


class Lakeshore340(Lakeshore3xx):
    """
    Interface for Lakeshore 340 temperature controller.

    This class extends the base Lakeshore3xx class with specific
    features for the Lakeshore 340 model.
    """

    def __init__(self, interface, **kwargs):
        """
        Initialize Lakeshore 340 temperature controller.

        Parameters
        ----------
        interface : str
            VISA resource string for the instrument.
        **kwargs : dict
            Additional keyword arguments.
            - baud_rate: Serial communication baud rate (default: 19200)
        """
        if "baud_rate" not in kwargs:
            kwargs["baud_rate"] = 19200
        super().__init__(interface, **kwargs)

    def getHeaterRange(self) -> int:
        """
        Get the heater range setting.

        Returns
        -------
        int
            Current heater range setting (0-5).
        """
        return self.query_int("RANGE?")

    def setHeaterRange(self, heaterRange: int) -> None:
        """
        Set the heater range.

        Parameters
        ----------
        heaterRange : int
            Heater range to set (0-5).
            0: Off, 1: Low, 2: Medium, 3: High, etc.
        """
        try:
            int(heaterRange)
            if 0 > heaterRange or 6 < heaterRange:
                return
            self.write("RANGE " + str(heaterRange))
        except ValueError:
            return

    @synchronized
    def writeCurveToIndex(
        self, index: int, name: str, sn: str, rList: list[float], tList: list[float]
    ) -> None:
        """
        Write a calibration curve to the device.

        Parameters
        ----------
        index : int
            Index to store the curve at (21-60).
        name : str
            Name of the curve.
        sn : str
            Serial number of the sensor.
        rList : List[float]
            List of resistance values.
        tList : List[float]
            List of temperature values.

        Notes
        -----
        Only supports Cernox sensors currently.
        Maximum length of tList and rList is 199.
        """
        index = int(index)
        assert len(rList) == len(tList) and 20 < index and index < 61
        self.write(f"CRVHDR {index},{name},{sn},3,{self.setlimit:.1f},1")
        time.sleep(0.3)
        for i, (res, temp) in enumerate(zip(rList, tList)):
            self.write(f"CRVPT {index},{i + 1},{res:.5f},{temp:.5f}")
            time.sleep(0.3)
        self.write("CRVSAV")

    @synchronized
    def writeZonePID(
        self,
        templist: list[float],
        plist: list[float],
        ilist: list[float],
        dlist: list[float],
        rangelist: list[int],
        loop: int = 1,
    ) -> None:
        """
        Write Zone PID settings to the controller.

        Parameters
        ----------
        templist : List[float]
            Upper temperature limits for each zone (must be sorted from low to high).
        plist : List[float]
            P (proportional) parameters for each temperature zone.
        ilist : List[float]
            I (integral) parameters for each temperature zone.
        dlist : List[float]
            D (derivative) parameters for each temperature zone.
        rangelist : List[int]
            Heater range settings for each temperature zone (0-5).
        loop : int, optional
            Control loop number, by default 1.

        Notes
        -----
        All lists can have at most 10 entries.
        Enables automatic adjustment of PID parameters based on temperature.
        """
        assert (
            len(templist) == len(plist)
            and len(plist) == len(ilist)
            and len(plist) == len(dlist)
            and len(plist) == len(rangelist)
        )

        for j, (t, p, i, d, r) in enumerate(zip(templist, plist, ilist, dlist, rangelist)):
            self.write(f"ZONE {loop}, {j + 1}, {t}, {p}, {i}, {d}, , {r}")
            time.sleep(0.3)
