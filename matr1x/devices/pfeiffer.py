from .visadevice import VisaDevice


class MPT200(VisaDevice):
    def __init__(self, interface):
        super().__init__(interface, write_termination="\r",
                         read_termination="\r", timeout=0.5)

    def query(self, msg):
        return super().query(f"{msg}{self.checksum(msg):03d}")

    def id(self):
        return self.query("0010034902=?") + " " + self.query("0010031202=?")

    def checksum(self, var):
        csum = 0
        for i in var:
            csum += ord(i)
        return csum % 256

    def resolvePressureValue(self, reading):
        mant = float(reading[10:14])*1e-3
        exp = int(reading[14:16]) - 20
        # return the correct float
        return mant*10**exp

    def setFilamentState(self, state):
        """
        state can be 0 or 1
        """
        if 0 == int(state):
            # sets register 041 to 0/False
            self.query("00110041010")
        elif 1 == int(state):
            # sets register 041 to 1/True
            self.query("00110041011")

    def getFilmantState(self):
        # sets register 041 to 1/True
        return int(self.query("0010004102=?")[10:11])

    def getPressure(self):
        return self.resolvePressureValue(self.query("0010074002=?"))
