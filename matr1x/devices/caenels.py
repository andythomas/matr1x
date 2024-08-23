# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2024 matr1x developers. All rights reserved.
# ---
from .visadevice import VisaDevice


class CAENelsEasyDriver(VisaDevice):

    def __init__(self, interface, **kwargs):
        super().__init__(
            interface,
            write_termination="\r",
            read_termination="\r",
            **kwargs,
        )

    def setCurrent(self, current):
        # sets the output current (abruptly, no ramp)
        # input:
        #   current: float
        # output:
        #   no output
        self.query("MWI:" + str(current))

    def setOff(self):
        # sets the output off
        # input:
        #   no input
        # output:
        #   no output
        self.query("MOFF")

    def setOn(self):
        # sets the output on
        # input:
        #   no input
        # output:
        #   no output
        self.query("MON")

    def setOutput(self, output=None):
        # sets the output current on or off
        # input:
        #   output: boolean (True for on, False for off)
        # output:
        #   no output
        if output:
            self.setOn()
        else:
            self.setOff()

    def resetModule(self):
        # resets the module (after fault (short circuit))
        # input:
        #   no input
        # output:
        #   no output
        self.query("MRESET")

    def getCurrent(self):
        # displays the output current
        # input:
        #   no input
        # output:
        #   float
        a = self.query("MRI")
        return float(a[5:])

    def getID(self):
        # gets the module ID
        # input:
        #   no input
        # output:
        #   string
        a = self.query("MRID")
        return a[6:]

    def setRampCurrent(self, current):
        # sets the output current (linear ramp to setpoint)
        # input:
        #   current: float
        # output:
        #   no output
        self.query("MRM:" + str(current))

    def getRampSlewRate(self):
        # displays the ramp slew rate
        # input:
        #   no input
        # output:
        #   float
        a = self.query("MRSR")
        return float(a[6:])

    def setRampSlewRate(self, slewrate):
        # sets the ramp slew rate
        # input:
        #   slewrate: float
        # output:
        #   no output
        self.query("MWSR:" + str(slewrate))

    def getDCVoltage(self):
        # displays the bulk DC voltage
        # input:
        #   no input
        # output:
        #   float
        a = self.query("MRP")
        return float(a[5:])

    def getVoltage(self):
        # displays the output voltage
        # input:
        #   no input
        # output:
        #   float
        a = self.query("MRV")
        return float(a[5:])

    def fetchStatus(self):
        # displays the device status
        # input:
        #   no input
        # output:
        #   8-bit binary number
        #     bit 0: ouput 1=on, 0=off
        #     bit 1: fault 1=yes, 0=no
        #     bit 2: DC link undervoltage
        #     bit 3: mosfet temperature
        #     bit 4: shunt temperature
        #     bit 5: external interlock flag
        #     bit 6: reserved
        #     bit 7: reserved
        #   float:
        #     output current
        a = self.query("FDB:80:0")
        a = a.split(":")
        return bin(int(a[1], 16)), float(a[2])

    def getFault(self):
        # displays whether module is in fault mode (short circuit)
        # input:
        #   no input
        # output:
        #   boolean: 1=fault, 0=no fault
        return bool(self.fetchStatus()[0] & 0b10)

    def getOutputState(self):
        # displays whether output is on or off
        # input:
        #   no input
        # output:
        #   boolean: 1=on, 0=off
        return bool(self.fetchStatus()[0] & 0b1)

    def getCurrentSetpoint(self):
        # displays current setpoint
        # input:
        #   no input
        # output:
        #   float
        return self.fetchStatus()[1]
