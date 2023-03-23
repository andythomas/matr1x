# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2023 matr1x developers. All rights reserved.
# ---
import logging

from .visadevice import VisaDevice

logger = logging.getLogger(__name__)


class Danfysik9100(VisaDevice):
    # danfysik power supply driver

    def __init__(self, interface, **kwargs):
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r\n"
        if "baud_rate" not in kwargs:
            kwargs["baud_rate"] = 115200
        if "timeout" not in kwargs:
            kwargs["timeout"] = 500
        if "cmdpers" not in kwargs:
            kwargs["cmdpers"] = 10
        super().__init__(interface, **kwargs)

    # high level functions
    def getCurrent(self):
        """
        displays the actual current at the device output in A
        input:
           no input
        output:
           float
        """
        return float(self.query("AD 8"))/100

    def getVoltage(self):
        '''
        displays the actual voltage at the device output in V
        input:
          no input
        output:
          float
        '''
        return float(self.query("AD 2"))/10

    def getCurrentSetting(self):
        '''
        displays the output current setting value
        input:
          no input
        output:
          float
        '''
        a = self.query("DA 0")[2:]
        return float(a)/1000

    def setCurrent(self, setpoint):
        '''
        sets the output current in mA (integer)
        input:
          setpoint: integer
        output:
          no output
        '''
        self.write("DA 0 {:d}".format(int(1000*setpoint)))

    """
    def getVoltageSetting(self):
        # displays the output voltage setting value
        # input:
        #   no input
        # output:
        #   float
        self.write("AD 7")
        return self.read()

    def setVoltage(self, setpoint):
        # sets the output voltage in ppm
        # input:
        #   setpoint: integer
        # output:
        #   no output
        self.write("DA 4 {:d}".format(setpoint))
    """

    def getRampStatus(self):
        '''
        returns the current ramping status
        input:
         no input
        output:
         boolean True if ramping, False if stopped
        '''
        q = self.query("RR")
        if q == "S":
            return False
        else:
            return True

    def setOutput(self, output=None):
        '''
        sets the output current on or off
        input:
           boolean (true for on, false for off)
        output:
           no output
        '''
        if (output is True):
            self.write("N")
        elif (output is False):
            self.write("F")

    def id(self):
        '''
        # displays the device ID
        # input:
        #   no input
        # output:
        #   string
        '''
        return self.query("ID")

    def setRemote(self):
        '''
        # displays the device ID
        # input:
        #   no input
        # output:
        #   no output
        '''
        self.write("REM")
        self.read()

    def resetInterlocks(self):
        '''
        # resets the interlock state
        # input:
        #   no input
        # output:
        #   no output
        '''
        self.write("RS")
        self.read()

    def fetchStatus(self):
        '''
        # displays the device status
        # input:
        #   no input
        # output:
        #   status: dictionary  Example: "! . ! . ! ! . . . ! . . . . ! . . . . . . . ! ."
        #1   . . . . .     MAIN POWER OFF (!=OFF .=ON)
        #2   . . . . .     POLARITY NORMAL (!=Polarity Normal)
        #3   . . . . .     POLARITY REVERSED (!=Polarity REVERSED)
        #4   . . . . .     NOT USED
        #5   . . . . .     CROWBAR ON (!=ON .=OFF)
        #6   . . . . .     I-MODE (!=I-mode  .=V-mode)
        #7   . . . . .     != % ,  . = AMPS and VOLTS
        #8   . . . . .     EXTERNAL INTERLOCK 0  (!=Interlock  .=No interlock)
        #9   . . . . .     NOT USED.
        #10   . . . . .   SUM – INTERLOCK  (!=Sum interlock  .=No sum interlock)
        #11   . . . . .   OVER VOLTAGE (OVP) (!=over voltage  .=No over voltage)
        #12   . . . . .   DC OVER CURRENT (OCP) (!=over current
                                                 .=No over current)
        #13   . . . . .   DC UNDERVOLTAGE  (!=Fault  .=OK)
        #14   . . . . .   NOT USED
        #15   . . . . .   PHASE FAILURE (AC LINE OK) (!=Fault  .=OK)
        #16   . . . . .   NOT USED
        #17   . . . . .   EARTH LEAKAGE (!=Fault  .=OK)
        #18   . . . . .   FAN (!=Fault  .=OK)
        #19   . . . . .   MPS OVERTEMPERATURE (!=Fault  .=OK)
        #20   . . . . .   EXTERNAL INTERLOCK 1  (!=Interlock  .=No interlock)
        #21   . . . . .   EXTERNAL INTERLOCK 2  (!=Interlock  .=No interlock)
        #22   . . . . .   EXTERNAL INTERLOCK 3  (!=Interlock  .=No interlock)
        #23   . . . . .   MPS NOT READY (!=Not ready  .=Ready)
        #24   . . . . .   NOT USED
        '''
        self.write("S1")
        a = self.read()
        status = {"Main Power off": True, "polarity normal": True,
                  "polarity reversed": True, "not used": "",
                  "crowbar on": True, "I-Mode": True, "units": True,
                  "External Interlock": True, "not used": "",
                  "SUM-Interlock": True, "Over Voltage": True,
                  "DC Over current": "", "DC under voltage": True,
                  "not used": "", "Phase failure": True,
                  "not used": "", "Earth leakage": True, "Fan": True,
                  "MPS Over temperature": True, "External interlock 1": True,
                  "External interlock 2": True, "External interlock 3": True,
                  "MPS not ready": True, "not used": ""}
        count = 0
        for i in status:
            if a[count] == '!':
                status[i] = True
            elif a[count] == '.':
                status[i] = False
            count += 1
        return status
