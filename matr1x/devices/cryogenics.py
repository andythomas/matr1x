import logging
import math
import re
import time

import pyvisa.errors
from wrapt import synchronized

from .visadevice import VisaDevice

logger = logging.getLogger(__name__)


class CryogenicPS(VisaDevice):
    config_params = {"TeslePerAmpere": "tpa"}
    re_output = re.compile(r"OUTPUT: ([0-9\.\-]+) TESLA AT ([0-9\.\-]+) VOLTS")
    re_holding = re.compile(r"HOLDING ON [A-Z]+ AT ([0-9\.\-]+) TESLA")
    re_ramping = re.compile(
        r"RAMPING FROM [0-9\.\-]+ TO ([0-9\.\-]+) TESLA AT")

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
        self.tpa = float(msg[msg.find("FIELD CONSTANT:"):].split()[2])
        self.setMax(self.field_limit)

    def id(self):
        return self._id

    @synchronized
    def query(self, command):
        self.read_very_eager()
        self.write(command)
        time.sleep(self.VISAdev.query_delay)
        return super().query("++read 10")

    @synchronized
    def getUpdate(self):
        self.read_very_eager()
        self.write("U")
        time.sleep(self.VISAdev.query_delay)
        self.write("++read")
        time.sleep(self.VISAdev.query_delay)
        ret = self.read()
        ret += self.read_very_eager()
        return ret

    @synchronized
    def getStatus(self, depth=0):
        """return field, rate, voltage, ramp-status

        ramp status is either 'HOLDING' or 'RAMPING'
        """
        if depth > 4:
            return -99, 0, 0, 0, 0
        time.sleep(3*depth)
        try:
            up = self.getUpdate()
        except Exception as e:  # (pyvisa.errors.VisaIOError, UnicodeDecodeError)
            # log incident and retry
            logger.info(f"getStatus: '{type(e).__name__}: {e}'")
            logger.info(f"getStatus: retrying to get update ({depth})")
            return self.getStatus(depth+1)

        try:
            match = self.re_output.findall(up)[0]
            field = float(match[0])
            setp = float(up[up.find("MID SETTING:"):].split()[2])
            rate = self._as2tmin(float(up[up.find("RAMP RATE:"):].split()[2]))
            voltage = float(match[1])
            status = up[up.find("RAMP STATUS:"):].split()[2]
        except Exception as e:
            # log incident and retry
            logger.info(f"getStatus: '{type(e).__name__}: {e}'")
            logger.info(f"getStatus: retrying to analyze update ({depth})")
            return self.getStatus(depth+1)
        return field, setp, rate, voltage, status

    @synchronized
    def getOutput(self, depth=0):
        if depth > 4:
            return math.nan, math.nan
        time.sleep(3*depth)
        try:
            ret = self.query("G O")
        except Exception as e:  # (pyvisa.errors.VisaIOError, UnicodeDecodeError)
            # log incident and retry
            logger.info(f"getOutput: '{type(e).__name__}: {e}'")
            logger.info(f"getOutput: retrying to get update ({depth})")
            return self.getOutput(depth+1)

        match = self.re_output.findall(ret)
        if len(match) >= 1:
            # power supply at stable output, return field and voltage
            return float(match[0][0]), float(match[0][1])
        else:  # something wrong?
            return math.nan, math.nan

    def _tmin2as(self, value):
        return value/60/self.tpa

    def _as2tmin(self, value):
        return value*60*self.tpa

    @synchronized
    def get_ramp_status(self, depth=0):
        if depth > 4:
            return "unknown", math.nan
        time.sleep(3*depth)
        try:
            self.write("R S")
            time.sleep(self.VISAdev.query_delay)
            self.write("++read")
            time.sleep(self.VISAdev.query_delay)
            ret = self.read()
            ret += self.read_very_eager()
        except Exception as e:  # (pyvisa.errors.VisaIOError, UnicodeDecodeError)
            # since we are desperate we ignore all other Exceptions as well
            logger.info(f"get_ramp_status: '{type(e).__name__}: {e}'")
            logger.info(f"get_ramp_status: retrying to get update ({depth})")
            return self.get_ramp_status(depth+1)

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
        up = self.getUpdate()
        return self._as2tmin(float(up[up.find("RAMP RATE:"):].split()[2]))

    # Set the output value in T/min.
    def setRate(self, value):
        if value > 0.52:
            rate = self._tmin2as(0.5)
        else:
            rate = self._tmin2as(value)
        self.write("S R" + str(rate))
        return rate

    @synchronized
    def setOutput(self, value):
        """use MID value as our setpoint"""
        self.write("S %" + str(value))
        self.write("R MID")

    def setMax(self, value):
        self.query("S !" + str(value))  # ! or MAX is valid

    def setMid(self, value):
        self.write("S %" + str(value))  # % or MID is valid

    def setZero(self):
        self.write("R 0")

    def setPause(self):
        pass


class CryogenicBipolarPS(VisaDevice):
    config_params = {"TeslePerAmpere": "tpa"}
    re_output = re.compile(r"OUTPUT: ([0-9\.\-]+) TESLA AT ([0-9\.\-]+) VOLTS")
    re_holding = re.compile(r"HOLDING ON [A-Z]+ AT ([0-9\.\-]+) TESLA")
    re_ramping = re.compile(
        r"RAMPING FROM [0-9\.\-]+ TO ([0-9\.\-]+) TESLA AT")
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
        self.tpa = float(msg[msg.find("FIELD CONSTANT:"):].split()[2])
        self.setMax(self.field_limit)

    def id(self):
        return "SMC120C"

    @synchronized
    def read_very_eager(self):
        """read from device without blocking IO (timeout=0)"""
        t = self.VISAdev.timeout
        self.VISAdev.timeout = 250
        ret = ""
        try:
            while True:
                ret += self.VISAdev.read()
        except pyvisa.errors.VisaIOError:
            pass
        self.VISAdev.timeout = t
        return ret

    @synchronized
    def query(self, command):
        self.read_very_eager()
        return super().query(command)

    @synchronized
    def getUpdate(self):
        ret = self.query("U")
        ret += self.read_very_eager()
        return ret

    @synchronized
    def getStatus(self, depth=0):
        """return field, rate, voltage, ramp-status

        ramp status is either 'HOLDING' or 'RAMPING'
        """
        if depth > 4:
            return -99, 0, 0, 0, 0
        time.sleep(3*depth)
        try:
            up = self.getUpdate()
        except Exception as e:  # (pyvisa.errors.VisaIOError, UnicodeDecodeError)
            # log incident and retry
            logger.info(f"getStatus: '{type(e).__name__}: {e}'")
            logger.info(f"getStatus: retrying to get update ({depth})")
            return self.getStatus(depth+1)

        try:
            match = self.re_output.findall(up)[0]
            field = float(match[0])
            setp = float(up[up.find("MID SETTING:"):].split()[2])
            rate = self._as2tmin(float(up[up.find("RAMP RATE:"):].split()[2]))
            voltage = float(match[1])
            status = up[up.find("RAMP STATUS:"):].split()[2]
        except Exception as e:
            # log incident and retry
            logger.info(f"getStatus: '{type(e).__name__}: {e}'")
            logger.info(f"getStatus: retrying to analyze update ({depth})")
            return self.getStatus(depth+1)
        return field, setp, rate, voltage, status

    @synchronized
    def getOutput(self, depth=0):
        if depth > 4:
            return math.nan, math.nan
        time.sleep(3*depth)
        try:
            ret = self.query("G O")
        except Exception as e:  # (pyvisa.errors.VisaIOError, UnicodeDecodeError)
            # log incident and retry
            logger.info(f"getOutput: '{type(e).__name__}: {e}'")
            logger.info(f"getOutput: retrying to get update ({depth})")
            return self.getOutput(depth+1)

        match = self.re_output.findall(ret)
        if len(match) >= 1:
            # power supply at stable output, return field and voltage
            return float(match[0][0]), float(match[0][1])
        else:  # something wrong?
            return math.nan, math.nan

    def _tmin2as(self, value):
        return value/60/self.tpa

    def _as2tmin(self, value):
        return value*60*self.tpa

    @synchronized
    def get_ramp_status(self, depth=0):
        if depth > 4:
            return "unknown", math.nan
        time.sleep(3*depth)
        try:
            ret = self.query("R S")
            ret += self.read_very_eager()
        except Exception as e:  # (pyvisa.errors.VisaIOError, UnicodeDecodeError)
            # since we are desperate we ignore all other Exceptions as well
            logger.info(f"get_ramp_status: '{type(e).__name__}: {e}'")
            logger.info(f"get_ramp_status: retrying to get update ({depth})")
            return self.get_ramp_status(depth+1)

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
        up = self.getUpdate()
        return self._as2tmin(float(up[up.find("RAMP RATE:"):].split()[2]))

    # Set the output value in T/min.
    def setRate(self, value):
        if value > 0.52:
            rate = self._tmin2as(0.5)
        else:
            rate = self._tmin2as(value)
        self.write("S R" + str(rate))
        return rate

    @synchronized
    def setOutput(self, value):
        """use MID value as our setpoint"""
        self.write("S %" + str(value))
        self.write("R MID")
        if value >= 0:
            self.write("D +")
        else:
            self.write("D -")
        time.sleep(1)  # here one needs to wait to ensure the sign changed

    def setMax(self, value):
        m = self.query("G %")
        mid = float(self.re_mid.findall(m)[0])
        if abs(mid) > value:
            self.setMid(math.copysign(value, mid))
        self.query("S !" + str(value))  # ! or MAX is valid

    def setMid(self, value):
        self.write("S %" + str(value))  # % or MID is valid

    def setZero(self):
        self.write("R 0")

    def setPause(self):
        pass
