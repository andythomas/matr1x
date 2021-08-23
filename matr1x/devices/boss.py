from .visadevice import VisaDevice


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
        self.write("SB0")
        try:
            self.read()
        except UnicodeDecodeError:
            self.read_very_eager()
        # set device to remote
        # ignore non-ascii characters in reply which sometimes seem to appear
        try:
            self.query("SR")
        except UnicodeDecodeError:
            self.read_very_eager()

    def id(self):
        # Power supply seems to support no version or identifier command
        return "Electronics Measurement Inc. BOSS-20-5"

    def query(self, msg):
        ret = super().query(msg)
        ret = ret.replace("Command>", "")
        return ret

    # high level functions
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
