# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
import logging
import time

from wrapt import synchronized

from .visadevice import VisaDevice

logger = logging.getLogger(__name__)


class Ps10(VisaDevice):
    # DMT100 has 50 microsteps, 200 steps/motor revolution
    # 180:1 gear ratio, recalculate to single degree
    DMT100_deg = 50*200*180/360
    config_params = {"Mode": "getMode"}

    def __init__(self, interface, **kwargs):
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r"
        if "cmdpers" not in kwargs:
            kwargs["cmdpers"] = 20
        if "baud_rate" not in kwargs:
            kwargs["baud_rate"] = 115200
        super().__init__(interface, **kwargs)

    @synchronized
    def query(self, msg, depth=0):
        if depth > 5:
            return "0"
        self.write(msg)
        ret = self.read()
        if ret == "":
            logger.info(
                f"{self.name}.query: empty reply ('{msg}', {ret})")
            return self.query(msg, depth=depth+1)
        return ret

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

    # high level functions
    def id(self):
        return self.query("?VERSION")

    def init(self):
        """
        initializes axis, needs to be done after connecting to the motor
        """
        self.write("INIT1")

    def getReferenced(self):
        """
        Check referenced state, returns 1 or 0
        """
        return self.query_int("?REFST1")

    def startReferenceDrive(self):
        """
        Start reference drive in mode 4 (goes to reference position and sets
        position counter to 0)
        """
        self.write("REF1=4")

    def setMode(self, mode):
        """
        set movement mode

        Parameters:
            mode - string, can be ABSOL or RELAT
        """
        # first read out was ABSOL
        assert ("ABSOL" == mode or "RELAT" == mode)
        self.write(mode + "1")

    def getMode(self):
        """
        Read movement mode (returns absol or relat)
        """
        return self.query("?MODE1")

    @synchronized
    def moveSteps(self, steps):
        """
        Move to steps (or by steps if mode is relative)

        Parameters:
            steps - int
        """
        if -100000000 < int(steps) and 100000000 > int(steps):
            dummy = "PSET1={:d}".format(int(steps))
            self.write(dummy)
            # start movement
            self.write("PGO1")

    def moveAngle(self, angle):
        """
        Move to angle (or by angle if mode is relative)

        Parameters:
            angle - float
        """
        self.moveSteps(angle*self.DMT100_deg)

    def waitUntilMoved(self):
        """
        Check whether motor is still moving and delay
        """
        while self.getMoving():
            time.sleep(0.05)

    def getMoving(self):
        """
        Checks the speed of axis one and verifies wether it turns to 0
        """
        ret = self.query_int("?VACT1")
        if 0 == ret:
            return False
        return True

    def readAngle(self):
        """
        Read current angle
        """
        return self.readSteps()/self.DMT100_deg

    def readSteps(self):
        """
        Read current steps
        """
        return self.query_int("?CNT1")

    def stop(self):
        """
        Stops all movement
        """
        self.write("STOP1")

    def setMotorState(self, state):
        """
        Set the motor state on or off

        Parameters:
            state - bool
        """
        if state is True:
            self.write("MON1")
        else:
            self.write("MOFF1")
