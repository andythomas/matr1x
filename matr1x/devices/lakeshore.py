# This file is part of a software collection for data aquisition (matr1x).
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

import logging
import math
import time

from pyvisa import constants
from wrapt import synchronized

from .util import listToStr, strToList
from .visadevice import VisaDevice

logger = logging.getLogger(__name__)


class Lakeshore3xx(VisaDevice):
    config_params = {"CurveName": "getActiveCurveName",
                     "PID": "getPID",
                     "Ramp mode and rate": "getRamp"}

    def __init__(self, interface, **kwargs):
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
    def query(self, command, depth=0):
        if depth > 5:
            logger.info(f"{self.name}.query: maximal depth exceeded ('{command}')")
            if command.startswith("PID?") or command.startswith("RAMP?"):
                return "0,0,0"
            else:
                return "0"
        self.write(command)
        ret = self.read()
        if ret == "":
            logger.info(
                f"{self.name}.query: empty reply, reopening interface ('{command}', {ret})"
            )
            self.close()
            self.open()
            return self.query(command, depth=depth + 1)
        return ret

    @synchronized
    def query_float(self, msg, depth=0):
        """routine to query a float including error checking"""
        ret = self.query(msg, depth)
        try:
            return float(ret)
        except ValueError:
            logger.info(
                f"{self.name}.query_float: float conversion error ('{msg}', {ret})")
            # retry query
            return self.query_float(msg, depth+1)

    @synchronized
    def query_int(self, msg, depth=0):
        """routine to query an integer including error checking"""
        ret = self.query(msg, depth)
        try:
            return int(ret)
        except ValueError:
            logger.info(
                f"{self.name}.query_int: integer conversion error ('{msg}', {ret})")
            # retry query
            return self.query_int(msg, depth+1)

    # High level functions
    def getTemp(self, channel=None):
        return float(self.query("KRDG? " + str(channel if channel else
                                               self.channel)))

    def getRes(self, channel=None):
        return float(self.query("SRDG? " + str(channel if channel else
                                               self.channel)))

    def setSetpoint(self, setpoint, loop=1):
        try:
            setpoint = float(setpoint)
            if 0 > setpoint or self.setlimit < setpoint:
                return
            self.write("SETP " + str(loop) + ",{:.5f}".format(setpoint))
        except ValueError:
            return

    def setManualOutput(self, setpoint, loop=1):
        try:
            setpoint = float(setpoint)
            if 0 > setpoint or 100 < setpoint:
                return
            self.write("MOUT " + str(loop) + ",{:.5f}".format(setpoint))
        except ValueError:
            return

    def getSetpoint(self, loop=1):
        return self.query_float("SETP? " + str(loop))

    def getManualOutput(self, loop=1):
        return self.query_float("MOUT? " + str(loop))

    def getHeater(self, loop: int = 1) -> float:
        """
        Get heater value.

        Parameters
        ----------
        loop : int
            Heater loop to query.
        """
        return self.query_float(f"HTR? {loop}")

    def getControlMode(self, loop=1):
        return self.query_int("CMODE? " + str(loop)) - 1

    def setControlMode(self, mode, loop=1):
        try:
            mode = int(mode) + 1
            if 1 > mode or 7 < mode:
                return
            self.write("CMODE " + str(loop) + "," + str(mode))
        except ValueError:
            return

    def getPID(self, loop=1):
        dummy = self.query("PID? " + str(loop))
        return strToList(dummy)

    def setPID(self, pid, loop=1):
        pid = list(pid)
        self.write("PID " + str(loop) + "," + listToStr(pid))

    def setRamp(self, args, loop=1):
        state, rate = args
        state = int(bool(state))
        rate = float(rate)
        self.write(f"RAMP {loop:d},{state:d},{rate:.1f}")

    def getRamp(self, loop=1):
        dummy = self.query("RAMP? " + str(loop)).split(",")
        return bool(int(dummy[0])), float(dummy[1])

    def getCurveName(self, curve):
        try:
            curve = int(curve)
            if 0 > curve and 60 < curve:
                return
        except ValueError:
            return
        ret = self.query("CRVHDR? " + str(curve))
        return ret.split(",")[0]

    def getCurveNumber(self, channel=None):
        return self.query_int("INCRV? " + str(channel if channel else
                                              self.channel))

    def getActiveCurveName(self, channel=None):
        return self.getCurveName(self.getCurveNumber(channel=channel))

    @synchronized
    def setCurveNumber(self, curve, channel=None):
        try:
            curve = int(curve)
            if 0 > curve and 60 < curve:
                return
        except ValueError:
            return
        self.write("INCRV " + str(channel if channel else
                                  self.channel) + "," + str(curve))
        # wait to activate the change
        time.sleep(3)

    @synchronized
    def writeCurveToIndex(self, index, name, sn, rList, tList):
        """
        writes tList and rList as calibration curve into curve
        name with serial number sn
        max length of tList and rList is 199
        max length of name is 15, of sn 10 digits
        only supports cernox sensors currently
        """
        index = int(index)
        assert (len(rList) == len(tList) and 20 < index and
                index < 61 and len(name) < 16 and len(sn) < 10)
        self.write(f"CRVHDR {index},{name},{sn},4,{self.setlimit:.1f},1")
        time.sleep(0.1)
        for i, (res, temp) in enumerate(zip(rList, tList)):
            self.write(
                f"CRVPT {index},{i+1},{math.log10(res):.5f},{temp:.5f},N")
            time.sleep(0.1)


class Lakeshore335(Lakeshore3xx):
    def __init__(self, interface, **kwargs):
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
        loop : int
            Heater loop to query.

        Returns
        -------
        int
            The selected range of the heater loop.
        """
        return self.query_int(f"RANGE? {loop}")

    def setHeaterRange(self, heaterRange: int, loop: int = 1) -> None:
        """
        Set the heater range.

        The function tests, if the range would be correctly set, i.e. 1, 2 or 3.

        Parameters
        ----------
        heaterRange : int
            The range to set (1, 2 or 3).
        """
        try:
            int(heaterRange)
            if 0 > heaterRange or 3 < heaterRange:
                return
            self.write(f"RANGE {loop},{heaterRange}")
        except ValueError:
            return

    def getControlMode(self, loop: int = 1) -> int:
        """
        Get the control mode of the heater loop.

        Parameters
        ----------
        loop : int
            Heater loop to query.

        Returns
        -------
        int
            The control mode of the heater loop (0 = Off, 1 = Closed Loop PID, 2 = Zone, 3 = Open Loop,
            4 = Monitor out, 5 = Warmup Supply).
        """
        ret = self.query(f"OUTMODE? {loop}")
        try:
            return int(ret.split(",")[0])
        except ValueError:
            return

    def setControlMode(self, mode: int, loop: int = 1, channel: str = "A") -> None:
        """
        Set the control mode of the heater loop.

        Parameters
        ----------
        mode : int
            The control mode to set (0 = Off, 1 = Closed Loop PID, 2 = Zone, 3 = Open Loop,
            4 = Monitor out, 5 = Warmup Supply).
        loop : int
            Heater loop to set the control mode for.
        channel : str
            Channel to set the control mode for (A or B).

        Returns
        -------
        None
        """

        channel_num = 0
        if channel == "A":
            channel_num = 1
        elif channel == "B":
            channel_num = 2
        try:
            mode = int(mode)
            if 0 > mode or 5 < mode:
                return
            self.write(f"OUTMODE {loop},{mode},{channel_num},1")
        except ValueError:
            return

    def setManOutput(self, power: float, loop: int = 1) -> None:
        """
        Set the manual output of the heater loop.

        Parameters
        ----------
        power : float
            The manual output power to set (0 to 100 %).
        loop : int
            Heater loop to set the manual output for.

        Returns
        -------
        None
        """
        try:
            power = float(power)
            if power < 0 or power > 100:
                return
            self.write(f"MOUT {loop},{power}")
        except ValueError:
            return

    def initiateAutotune(self, mode: int, loop: int = 1) -> None:
        """
        Initiate autotune on the specified heater loop.

        Parameters
        ----------
        mode : int
            The autotune mode to use (0 = P Only, 1 = PI, 2 = PID).
        loop : int
            The heater loop to initiate autotune on.

        Returns
        -------
        None
        """

        try:
            mode = int(mode)
            if mode < 0 or mode > 2:
                return
            self.write(f"ATUNE {loop},{mode}")
        except ValueError:
            return

    def getTuningStatus(self) -> list[str]:
        """
        Get the current autotune status.

        Returns
        -------
        list[str]
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
        channel : str
            The channel to set the temperature limit for (A or B).

        Returns
        -------
        None
        """
        try:
            limit = int(limit)
            self.write(f"TLIMIT {channel},{limit}")
        except ValueError:
            return


class Lakeshore340(Lakeshore3xx):
    def __init__(self, interface, **kwargs):
        if "baud_rate" not in kwargs:
            kwargs["baud_rate"] = 19200
        super().__init__(interface, **kwargs)

    def getHeaterRange(self):
        return self.query_int("RANGE?")

    def setHeaterRange(self, heaterRange):
        try:
            int(heaterRange)
            if 0 > heaterRange or 6 < heaterRange:
                return
            self.write("RANGE " + str(heaterRange))
        except ValueError:
            return

    @synchronized
    def writeCurveToIndex(self, index, name, sn, rList, tList):
        """
        writes tList and rList as calibration curve into curve
        name with serial number sn
        max length of tList and rList is 199
        max length of name is 15, of sn 10 digits
        only supports cernox sensors currently
        """
        index = int(index)
        assert (len(rList) == len(tList) and 20 < index and
                index < 61)
        self.write(f"CRVHDR {index},{name},{sn},3,{self.setlimit:.1f},1")
        time.sleep(0.3)
        for i, (res, temp) in enumerate(zip(rList, tList)):
            self.write(f"CRVPT {index},{i+1},{res:.5f},{temp:.5f}")
            time.sleep(0.3)
        self.write("CRVSAV")

    @synchronized
    def writeZonePID(self, templist, plist, ilist, dlist, rangelist, loop=1):
        """
        writes Zone PID settings into the controller to allow for automatic
        adjustment of the PID parameters upon a setpoint change. All lists can
        have maximally 10 entries.

        Parameters
        ----------
         templist: list
            upper temperatures for each zone (must be sorted! from small to
            big)
         plist, ilist, dlist: list
            P, I, D parameters for each temperature zone.
         rangelist: list
            heater range setting for each temperature zone.
            valid entries are 0 .. 5
        """
        assert (len(templist) == len(plist) and len(plist) == len(ilist) and
                len(plist) == len(dlist) and len(plist) == len(rangelist))

        for j, (t, p, i, d, r) in enumerate(zip(templist, plist, ilist, dlist,
                                                rangelist)):
            self.write(f"ZONE {loop}, {j+1}, {t}, {p}, {i}, {d}, , {r}")
            time.sleep(0.3)


class Lakeshore475(VisaDevice):

    def __init__(self, interface, **kwargs):
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 2000
        if "cmdpers" not in kwargs:
            kwargs["cmdpers"] = 20
        super().__init__(interface, **kwargs)

    # high level functions
    def getField(self):
        return float(self.query("RDGFIELD?"))

    def getTemp(self):
        return float(self.query("RDGTEMP?"))

    def setSetpoint(self, setpoint):
        self.write("CSETP " + "{:.5f}".format(float(setpoint)))

    def readSetpoint(self):
        return float(self.query("CSETP?"))

    def zeroProbe(self, clear=False):
        """
        zeros the Hall probe

        Arguments
        -----
        clear:bool
          If true, instead clears the zero probe command
        """
        if clear is False:
            self.write("ZPROBE")
        elif clear is True:
            self.write("ZCLEAR")

    def configureAnalogOut(self, voltlimit, lowfield, highfield, bipolar=2, mode=4,
                           manualOut=0):
        """
        function not tested

        Configure analog output of LS475

        Arguments
        -----
        voltlimit:int
          maximum voltage (1 to 10V)
        lowfield:float
          field value at which the analog output reaches -100% (0%)
        highfield:float
          field value at which the analog output reaches +100%
        bipolar:int
          can be 1 (unipolar) or 2 (bipolar)
        mode:int
          can be 0 (off), 1 (default), 2 (user defined), 3 (manual),
          4 (control)
        """

        self.write(f"ANALOG {str(mode)}, {str(bipolar)}, {str(lowfield)}, " +
                   f"{str(highfield)}, {manualOut:.4f}, {str(voltlimit)}")

    def configureControl(self, pValue, iValue, rampRate, maxVSlope, on=False):
        """
        function not tested

        Configure control mode

        Arguments
        -----
        on:bool
          if True, configures and turns on the control, otherwise just
          configures
        pValue:float
          proportional gain 0.01 to 1000
        iValue:float
          integral gain 0.0001 to 1000
        rampRate:float
          ramp rate in units/minute (unit is given by measurement unit
          setting)
        maxVSlope:float
          maximum rate of voltage output change 0.01 to 1000 V/min
        """
        if on is False:
            self.write("CMODE 0")
        self.write(f"CPARAM {str(pValue)}, {str(iValue)}, {str(rampRate)}, " +
                   f"{str(maxVSlope)}")
        if on is True:
            self.write("CMODE 1")

    def configure(
        self, reset=False, autoRange=True, range_val=None, dcRes=None, fUnit=None
    ):
        """
        Configure LS475 measurement parameters.

        Arguments
        -----
        reset:boolean
          If True reset the instrument
        autoRange:bool
          switches auto range on
        range_val:int
          has to be between 1 and 5, where 1 is the smallest
          range and 5 the largest, probe dependent
        dcRes:int
          has to be between 1 and 3, where 1 is 3 digits
          and 3 is 5 digits
        fUnit:int
          has to be between 1 and 4, where 1 is Gauss, 2 is
          Tesla, 3 is Oersted and 4 Amp/meter
        """
        if reset is True:
            self.write("*RST")
        if autoRange is True:
            self.write("AUTO 1")
        elif range_val is not None and 0 < range_val and 6 > range_val:
            self.write("AUTO 0")
            self.write("RANGE " + str(range_val))
        if dcRes is not None and 0 < dcRes and 4 > dcRes:
            self.write("RDGMODE 1," + str(dcRes) + ",1,1,1")
        if fUnit is not None and 0 < fUnit and 5 > fUnit:
            self.write("UNIT " + str(fUnit))
