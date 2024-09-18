# This file is part of a software collection for data aquisition (matr1x).
# Copyright (C) 2024 matr1x developers
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
import time

from wrapt import synchronized

from .visadevice import VisaDevice

logger = logging.getLogger(__name__)


class SMS(VisaDevice):
    # SM INT controller with two SMK 02 - Z stepper motor drivers
    # currently attached motor seems to have 200 steps/motor revolution
    # 1400:1 gear ratio, recalculate to single degree
    _axes = {0: "X", 1: "Y", 2: "Z", 3: "R"}

    def __init__(self, interface, **kwargs):
        """
        OWIS SMS motor controller class

        As programmed here for a rotary stepper motor. To go to any other unit,
        replace _steps_per_deg with what ever unit conversion (e.g. steps/mm) and
        all units will be in mm consequently.

        Parameters
        --------
        stepfreq: string
            VISA address, e.g. ASRL/dev/ttyUSB0::INSTR
        all kwargs are passed on to VisaDevice
        """
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r"
        if "cmdpers" not in kwargs:
            kwargs["cmdpers"] = 50
        if "timeout" not in kwargs:
            kwargs["timeout"] = 80e3
        if "baud_rate" not in kwargs:
            kwargs["baud_rate"] = 2400

        super().__init__(interface, **kwargs)

        # define class variables
        self._steps_per_deg = 200*1400/360
        self._settings = {ax: {} for ax, it in self._axes.items()}
        self._limits = {
            ax: {"lo": -40, "hi": 400} for ax, it in self._axes.items()}

    # high level functions
    def id(self):
        """
        Returns the device ID
        """
        ret = self.query("VD")
        # read additional bits from interface (\n\x00)
        self.read_very_eager()
        return ret

    def configure_drive(self, stepfreq, ramp, startfreq, ax=0):
        """
        Utility function to configure the drive settings used by move_abs
        and move_rel. If drive/axis settings are not configured, device internal
        defaults are used.

        maximum frequency is 15 kHz.
        (stepfreq-startfreq)/ramp must be >= 100 Hz/s (watch units).
        for details refer to the manual

        Parameters
        --------
        stepfreq: int
            Step frequency in Hz
        ramp: int
            Ramp time in ms
        startfreq: int
            Start frequency in Hz at the beginning of the Ramp
        ax: int <= 3
            axis to be configured
        """
        # cast to int
        stepfreq = int(stepfreq)
        startfreq = int(startfreq)
        ramp = int(ramp)
        # check validity:
        if (stepfreq - startfreq)/(ramp/1000) < 100:
            # >= 100 Hz/s is required
            return
        self._settings[ax]["stepfreq"] = stepfreq
        self._settings[ax]["ramp"] = ramp
        self._settings[ax]["startfreq"] = startfreq

    def initialize(self, ax=0):
        """
        initializes the axis and drives the stage to position 0.
        MOTION STARTS IMMEDIATELY, if axis is not at zero!

        Parameters
        --------
        ax: int <= 3
            axis to be configured
        """
        self.write(f"I{self._axes[ax]}")

    def move_abs(self, pos, ax=0):
        """
        moves to new position and blocks until position is reached.
        Adjust the timeout for very long strides.

        Parameters
        --------
        pos: float
            Desired absolute position (in units defined by _steps_per_deg
        ax: int <= 3
            axis to be configured
        """
        if pos > self._limits[ax]["hi"] or pos < self._limits[ax]["lo"]:
            # only allows rotations within limits
            return
        pos *= self._steps_per_deg
        if self.get_moving():
            # ignore command if still moving
            return
        if self._settings[ax] != {}:
            self.query("GA{}{:d},{:d},{:d},{:d};S;".format(
                self._axes[ax],
                int(pos),
                self._settings[ax]["stepfreq"],
                self._settings[ax]["ramp"],
                self._settings[ax]["startfreq"]))
        else:
            self.query(f"GA{self._axes[ax]}{int(pos):d};S;")

    def move_rel(self, pos, ax=0):
        """
        Moves relative to current position by pos and blocks until position is
        reached. Adjust the timeout for very long strides.

        Parameters
        --------
        pos: float
            Desired relative position (in units defined by _steps_per_deg
        ax: int <= 3
            axis to be configured
        """
        if abs(pos) > abs(self._limits[ax]["hi"]-self._limits[ax]["lo"]):
            # ignore rotations that are guaranteed to exceed the limit
            return
        pos *= self._steps_per_deg
        if self.get_moving():
            # ignore command if still moving
            return
        if self._settings[ax] != {}:
            self.query("GP{}{:d},{:d},{:d},{:d};S;".format(
                self._axes[ax],
                int(pos),
                self._settings[ax]["stepfreq"],
                self._settings[ax]["ramp"],
                self._settings[ax]["startfreq"]))
        else:
            self.query(f"GP{self._axes[ax]}{int(pos):d};S;")

    def move_abs_nonblocking(self, pos, ax=0):
        """
        moves to new position.

        Parameters
        --------
        pos: float
            Desired absolute position (in units defined by _steps_per_deg
        ax: int <= 3
            axis to be configured
        """
        if pos > self._limits[ax]["hi"] or pos < self._limits[ax]["lo"]:
            # only allows rotations within limits
            return
        pos *= self._steps_per_deg
        if self.get_moving():
            # ignore command if still moving
            return
        if self._settings[ax] != {}:
            self.write("A{}{:d},{:d},{:d},{:d}".format(
                self._axes[ax],
                int(pos),
                self._settings[ax]["stepfreq"],
                self._settings[ax]["ramp"],
                self._settings[ax]["startfreq"]))
        else:
            self.write(f"A{self._axes[ax]}{int(pos):d}")
        # wait to make reasonably sure command reaches the driver
        time.sleep(0.25)
        self.write("S")

    def move_rel_nonblocking(self, pos, ax=0):
        """
        Moves relative to current position by pos.

        Parameters
        --------
        pos: float
            Desired relative position (in units defined by _steps_per_deg
        ax: int <= 3
            axis to be configured
        """
        if abs(pos) > abs(self._limits[ax]["hi"]-self._limits[ax]["lo"]):
            # ignore rotations that are guaranteed to exceed the limit
            return
        pos *= self._steps_per_deg
        if self.get_moving():
            # ignore command if still moving
            return
        if self._settings[ax] != {}:
            self.write("P{}{:d},{:d},{:d},{:d}".format(
                self._axes[ax],
                int(pos),
                self._settings[ax]["stepfreq"],
                self._settings[ax]["ramp"],
                self._settings[ax]["startfreq"]))
        else:
            self.write(f"P{self._axes[ax]}{int(pos):d}")
        # wait to make reasonably sure command reaches the driver
        time.sleep(0.25)
        self.write("S")

    def get_moving(self, ax=0):
        """
        Checks the speed of axis one and verifies wether it turns to 0

        Parameters
        --------
        ax: int <= 3
            axis to be configured
        """
        ret = self.query("B")
        return "j" == ret[3+3*ax]

    def get_pos(self, ax=0):
        """
        Returns the position of an axis. Units are defined by _step_per_deg

        Parameters
        --------
        ax: int <= 3
            axis to be configured
        """
        return float(
            self.query(
                f"C{self._axes[ax]}").replace("CX", ""))/self._steps_per_deg

    def stop(self, ax=0):
        """
        Stops the motion of axis

        Parameters
        --------
        ax: int <= 3
            axis to be configured
        """
        self.write("E{self._axes[ax]}")


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
