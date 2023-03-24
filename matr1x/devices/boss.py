# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2023 matr1x developers. All rights reserved.
# ---
import logging
import time

from pyvisa import VisaIOError

from .visadevice import VisaDevice

logger = logging.getLogger(__name__)


class BOSS(VisaDevice):

    def __init__(self, interface, **kwargs):
        # take care, all values are transferred as integers although being
        # floats with one decimal place
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 2000
        if "query_delay" not in kwargs:
            kwargs["query_delay"] = 0.05
        if "cmdpers" not in kwargs:
            kwargs["cmdpers"] = 30
        super().__init__(interface, **kwargs)
        self.read_very_eager()  # clear leftovers of old communication
        # set talkback off
        self.query("SB0")
        # set device to remote
        self.query("SR")
        time.sleep(0.5)
        self.read_very_eager()

    def id(self):
        # Power supply seems to support no version or identifier command
        return "Electronics Measurement Inc. BOSS-20-5"

    def read_very_eager(self, attempts=0):
        # ignore non-ascii characters in reply which sometimes seem to appear
        try:
            return super().read_very_eager()
        except UnicodeDecodeError:
            logger.info(f"repeating read_very_eager (attempts: {attempts})")
            if attempts > 4:
                raise VisaIOError(f"too many attempts to read eagerly")
            return self.read_very_eager(attempts=attempts+1)

    def query(self, msg, attempts=0):
        try:
            ret = super().query(msg)
        except UnicodeDecodeError:
            logger.info(f"repeating query {msg} (attempts: {attempts})")
            if attempts > 4:
                raise VisaIOError(-1073807298)
            return self.query(msg, attempts=attempts+1)
        ret = ret.replace("Command>", "")
        return ret

    # high level functions
    def set_local(self):
        self.query("SL")

    def setControl(self, mode):
        """
        mode 0 - current
        mode 1 - voltage
        """
        if 0 == mode:
            self.query("SI")
        elif 1 == mode:
            self.query("SV")

    def getControl(self):
        ret = self.query("?C")
        if "V" in ret:
            return 1
        else:
            return 0

    def setSource(self, source):
        self.query("PC{:.3f}".format(float(source)))

    def getVoltage(self):
        ret = self.query("MV")
        ret = ret.replace("Voltage = ", "")
        ret = ret.replace(" Volts", "")
        return float(ret)

    def getCurrent(self):
        ret = self.query("MI")
        ret = ret.replace("Current = ", "")
        ret = ret.replace(" Amps", "")
        return float(ret)
