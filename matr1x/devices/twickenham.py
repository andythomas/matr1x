# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2024 matr1x developers. All rights reserved.
# --- 
from matr1x.devices.visadevice import VisaDevice


class HDI(VisaDevice):
    def __init__(self, interface, **kwargs):
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r\n"
        if "baud_rate" not in kwargs:
            kwargs["baud_rate"] = 9600
        
        super().__init__(interface, **kwargs)

    def getDisplayReading(self):
        res = self.query('G')
        try:
            return int(res[-6:-2])
        except:
            return -1
