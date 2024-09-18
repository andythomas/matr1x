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

import re
import time

from numpy import clip, sign
from wrapt import synchronized

from .visadevice import VisaDevice


class NanotecPD4(VisaDevice):
    """
    Nanotec PD4 stepper motor with integrated controller
    """

    def __init__(
        self,
        interface,
        steps_per_deg=1,
        zero_offset=-150,  # internal zero offset
        steps_lower_limit=-150,
        steps_upper_limit=-21900,
        pos_mode="abs",
        status_enable=False,
        **kwargs,
    ):

        if "timeout" not in kwargs.keys():
            kwargs["timeout"] = 2e3
        self.timeout = kwargs["timeout"]
        super().__init__(interface, write_termination="\r",
                         read_termination="\r", query_delay=0.02, **kwargs)
        self.steps_per_deg = steps_per_deg
        self.zero_offset = zero_offset
        # lower limit defines the step number with the smallest distance to the reference point (e.g. the reference point)
        self.steps_lower_limit = steps_lower_limit
        # upper limit defines the step number with the greatest distance to the reference point
        self.steps_upper_limit = steps_upper_limit
        self.pos_mode = pos_mode

        # read to kill first open error (reason unknown)
        time.sleep(0.1)
        self.read_very_eager()

        if status_enable is True:
            self.query("#1J1")
            self.status_enable = True
        else:
            self.query("#1J0")
            self.status_enable = False
        self.rot_dir = 0
        self.last_reference_run = "Not yet referenced"
        self.setPosMode(pos_mode)

    def id(self):
        return self.query("#1v")

    # high level functions
    def referenceRun(self, wait=600e3):
        """
        performs a reference run and sets the positioning mode to absolute ("abs").
        Recommended to use when the position of the magnet isn't defined.
        input: None
        output: None
        """
        self.query("#1y2")  # loads reference run record
        self.startRecord()
        if self.status_enable is True:  # and waits
            self.connection.timeout = wait
            self.read()
            self.connection.timeout = self.timeout
        else:
            while self.getMovingStatus() is True:
                time.sleep(0.1)
        # store time of last reference run in a string formatted as "YYYY-MM-DD hh:mm:ss"
        timeStamp = time.localtime()
        formattedTime = time.strftime("%Y-%m-%d %H:%M:%S", timeStamp)
        print(formattedTime)
        self.last_reference_run = formattedTime
        self.query("#1y4")  # loads moving record
        self.setPosMode("abs")  # sets positioning mode to absolute
        self.moveClip(0.0, "deg")  # moves to 0.0° which is the oop direction

    def resetPosError(self):
        """
        resets the position error e.g. needed when running into limits
        input: None
        output: None
        """
        self.query("#1D")

    def stopRecord(self):
        """
        stops motor
        input: None
        output: None
        """
        self.query("#1S")

    def startRecord(self):
        """
        starts the active record / starts the motor
        input: None
        output: None
        """
        self.query("#1A")

    def setPosition(self, moves):
        """
        sets the position to a given number of steps
        input: moves (int)
        output: None
        """
        self.query("#1s" + str(int(moves)))

    def setRotDir(self, direction):
        """
        sets the rotation direction based on the sign of direction
        input: direction (int) (-1 -> 0 -> Left; 1 -> 1 -> Right)
        output: None
        """
        if direction == -1:
            self.rot_dir = 0
            self.query("#1d0")
        else:
            self.rot_dir = 1
            self.query("#1d1")

    def setRotDirBin(self, direction):
        if direction == 0:
            self.rot_dir = 0
            self.query("#1d0")
        else:
            self.rot_dir = 1
            self.query("#1d1")

    def setPosMode(self, mode):
        """
        sets the positioning mode to either relative "rel" or absolute "abs".
        input: mode (String) ("rel","abs")
        output: None
        """
        print("setting pos mode")
        if mode == "rel":
            self.pos_mode = mode
            self.query("#1p1")
        elif mode == "abs":
            self.pos_mode = mode
            self.query("#1p2")

    @synchronized
    def move(self, moves, position, speed):
        """
        Halbach funtions!

        moves the motor by a given amount of steps (rel) or to a given position (abs) depending on the current positioning mode.
        In relative positioning mode moves has to be a positive integer.
        input: moves (int) (positive in rel pos mode)
        output: None
        """
        if self.status_enable is True:
            # status will be returned on ending, so always block or
            # communication will be confused.
            self.moving = True
            self.connection.timeout = int(
                1.5 * abs(1e3 * (int(moves) - position) / speed) + 1e3)
            while self.moving:
                try:
                    returnStatement = self.read()
                    if returnStatement == "001j161":
                        self.moving = False
                except:
                    self.moving = True
        else:
            self.query("#1s" + str(int(moves)))  # sets moves
            self.startRecord()

    @synchronized
    def moveWait(self, moves, position, speed):
        """
        Halbach functions!
        """
        if self.status_enable is True:
            self.move(moves, position, speed)
        else:
            self.move(moves, position, speed)
            moving = True
            while moving is True:
                time.sleep(0.01)
                moving = self.isMoving()

    @synchronized
    def moveClip(self, pos, unit):
        """
        move the motor by a given distance (rel) or to a given position (abs)
        in the specified unit, depending on active positioning mode.
        Suitable for absolute and relative movement as well as degrees (if calibrated) or steps.
        input:  posDeg (float)
                unit ("deg", "steps")
        output: None
        """
        position = self.readMoves()
        self.readInitSpeed()
        if unit == "deg":
            moves = int(float(self.zero_offset) + float(pos)
                        * float(self.steps_per_deg))
        else:
            moves = int(pos)
        mode = self.pos_mode
        rotDir = sign(moves)
        if mode == "rel":  # in rel pos mode no negative values are allowed
            moves = clip(moves, int(self.steps_upper_limit) -
                         int(position), int(self.steps_lower_limit) - int(position))
            moves = int(abs(moves))
            self.setRotDir(rotDir)
        else:
            moves = clip(moves, int(self.steps_upper_limit),
                         int(self.steps_lower_limit))
        self.query("#1s" + str(int(moves)))  # sets moves
        self.startRecord()

    @synchronized
    def moveClipWait(self, posDeg, unit):
        """
        move the motor by a given distance (rel) or to a given position (abs)
        in the specified unit, depending on active positioning mode.
        Wait for move to finish.
        Suitable for absolute and relative movement as well as degrees (if calibrated) or steps.
        input:  posDeg (float)
                unit ("deg", "steps")
        output: None
        """
        initRotDir = self.rot_dir
        self.moveClip(posDeg, unit)
        if not self.status_enable:
            isMoving = True
            while isMoving:
                isMoving = self.getMovingStatus()
                time.sleep(0.1)
        else:
            while self.moving:
                try:
                    returnStatement = self.read()
                    if returnStatement == "001j161":
                        self.moving = False
                except:  # TODO : not write bare except
                    self.moving = True
        self.setRotDir(initRotDir)

    @synchronized
    def readMoves(self):
        """
        reads the current position in steps.
        input: None
        output: position (int) (steps)
        """
        pos = self.query("#1C")
        return int(pos.strip().replace("1C", ""))

    def getPosDeg(self):
        """
        returns current position in degrees
        input: None
        output: position (int) (deg)
        """
        pos = float(self.zero_offset) - float(self.readMoves())
        posDeg = -1 * pos / float(self.steps_per_deg)
        return posDeg

    def getPosMode(self):
        """
        returns active positioning mode
        input: None
        output: posMode (String) ("rel","abs")
        """
        posMode = self.getCurrentRecordParams("p")
        if posMode == 1:
            return "rel"
        elif posMode == 2:
            return "abs"
        else:
            return "error"

    def readInitSpeed(self):
        """
        reads the current minimum step frequency
        input: None
        output: minFreq (int) (steps/s)
        """
        return int(self.query("#1Zu").strip().replace("1Zu", ""))

    def getLastReferenceTime(self):
        """
        returns the time of the last reference run in local time
        input: None
        output: timeOfRun (String) (formatted as "YYYY-MM-DD hh:mm:ss")
        """
        return self.last_reference_run

    def getMovingStatus(self):
        """
        read if the motor is still moving.
        input: None
        output: moving (bool)
        """
        answer = self.query("#1$")
        status = answer.replace("001$", "")
        isMoving = (int(status) & 0b00000001) == False
        self.moving = isMoving
        return isMoving

    def getRotDir(self):
        """
        get the rotation direction.
        input: None
        output: rot_dir (int)
        """
        return self.rot_dir

    def getCurrentRecordParams(self, param):
        """
        readout the current record write parameter set in dictionary

        input:  param (String) see list below
                    # most important
                    p: Position mode
                    s: Travel distance
                    u: Initial step frequency
                    o: Maximum step frequency
                    # additional parameters
                    n: Second maximum step frequency
                    b: Acceleration and braking ramp
                    d: direction of rotation
                    t: Reversal in direction of rotation for repeat records
                    w: repetitions
                    P: Pause between repetitions and continuation records
                    N: Record number of continuation record
        output: associated value stored in record (int)
        """
        record = self.query("#1Z|")
        pattern = r"[Z]*(\w)[+]*([-]*\d+)"
        mask = re.compile(pattern)
        result = mask.findall(record)
        resultDict = {key: int(value) for key, value in result}
        value = resultDict[param]
        return value

    def resetMoves(self):
        """
        resets the position of the motor to 0
        input: None
        output: None
        """
        self.query("#1c")
