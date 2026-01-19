# This file is part of a software collection for data acquisition (matr1x).
# Copyright (C) 2006-2026 matr1x developers
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
"""Module for interfacing with Nanotec stepper motor controllers."""

import re
import time

from numpy import clip, sign
from pyvisa.errors import VisaIOError
from wrapt import synchronized

from matr1x.devices.visadevice import VisaDevice


class NanotecPD4(VisaDevice):
    """Nanotec PD4 stepper motor with integrated controller."""

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
        """
        Initialize the Nanotec PD4 controller.

        Parameters
        ----------
        interface : str
            Communication interface identifier
        steps_per_deg : int, optional
            Steps per degree of rotation, by default 1
        zero_offset : int, optional
            Internal zero offset in steps, by default -150
        steps_lower_limit : int, optional
            Lower limit in steps, defined as the smallest distance to
            the reference point, by default -150
        steps_upper_limit : int, optional
            Upper limit in steps, defined as the greatest distance to
            the reference point, by default -21900
        pos_mode : str, optional
            Initial positioning mode, either "abs" or "rel", by
            default "abs"
        status_enable : bool, optional
            Enable status responses, by default False
        **kwargs
            Additional arguments passed to VisaDevice
        """
        if "timeout" not in kwargs.keys():
            kwargs["timeout"] = 2e3
        self.timeout = kwargs["timeout"]
        super().__init__(
            interface,
            write_termination="\r",
            read_termination="\r",
            query_delay=0.02,
            **kwargs,
        )
        self.steps_per_deg = steps_per_deg
        self.zero_offset = zero_offset
        # lower limit defines the step number with the smallest
        # distance to the reference point (e.g. the reference point)
        self.steps_lower_limit = steps_lower_limit
        # upper limit defines the step number with the greatest
        # distance to the reference point
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
        """
        Get the device identifier.

        Returns
        -------
        str
            Device identifier string
        """
        return self.query("#1v")

    # high level functions
    def referenceRun(self, wait=600e3):
        """
        Perform a reference run and set positioning mode to absolute.

        Recommended to use when the position of the magnet isn't defined.

        Parameters
        ----------
        wait : float, optional
            Timeout value for the reference run in milliseconds, by default 600e3

        Returns
        -------
        None
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
        Reset the position error.

        Useful when running into limits.

        Returns
        -------
        None
        """
        self.query("#1D")

    def stopRecord(self):
        """
        Stop the motor.

        Returns
        -------
        None
        """
        self.query("#1S")

    def startRecord(self):
        """
        Start the active record / start the motor.

        Returns
        -------
        None
        """
        self.query("#1A")

    def setPosition(self, moves):
        """
        Set the position to a given number of steps.

        Parameters
        ----------
        moves : int
            Number of steps to set as the position

        Returns
        -------
        None
        """
        self.query("#1s" + str(int(moves)))

    def setRotDir(self, direction):
        """
        Set the rotation direction based on the sign of direction.

        Parameters
        ----------
        direction : int
            Direction value (-1 -> 0 -> Left; 1 -> 1 -> Right)

        Returns
        -------
        None
        """
        if direction == -1:
            self.rot_dir = 0
            self.query("#1d0")
        else:
            self.rot_dir = 1
            self.query("#1d1")

    def setRotDirBin(self, direction):
        """
        Set the rotation direction using binary values.

        Parameters
        ----------
        direction : int
            Direction value (0 -> Left; 1 -> Right)

        Returns
        -------
        None
        """
        if direction == 0:
            self.rot_dir = 0
            self.query("#1d0")
        else:
            self.rot_dir = 1
            self.query("#1d1")

    def setPosMode(self, mode):
        """
        Set the positioning mode to either relative or absolute.

        Parameters
        ----------
        mode : str
            Positioning mode ("rel" or "abs")

        Returns
        -------
        None
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
        Halbach function to move the motor.

        Moves the motor by a given amount of steps (rel) or to a given position (abs)
        depending on the current positioning mode. In relative positioning mode,
        moves has to be a positive integer.

        Parameters
        ----------
        moves : int
            Number of steps to move or target position (positive in rel pos mode)
        position : int
            Current position
        speed : float
            Movement speed

        Returns
        -------
        None
        """
        if self.status_enable is True:
            # status will be returned on ending, so always block or
            # communication will be confused.
            self.moving = True
            self.connection.timeout = int(1.5 * abs(1e3 * (int(moves) - position) / speed) + 1e3)
            while self.moving:
                try:
                    returnStatement = self.read()
                    if returnStatement == "001j161":
                        self.moving = False
                except VisaIOError:
                    self.moving = True
        else:
            self.query("#1s" + str(int(moves)))  # sets moves
            self.startRecord()

    @synchronized
    def moveWait(self, moves, position, speed):
        """
        Halbach function to move the motor and wait for completion.

        Parameters
        ----------
        moves : int
            Number of steps to move or target position
        position : int
            Current position
        speed : float
            Movement speed

        Returns
        -------
        None
        """
        if self.status_enable is True:
            self.move(moves, position, speed)
        else:
            self.move(moves, position, speed)
            moving = True
            while moving is True:
                time.sleep(0.01)
                moving = self.getMovingStatus()

    @synchronized
    def moveClip(self, pos, unit):
        """
        Move the motor with position clipping.

        Move the motor by a given distance (rel) or to a given position (abs)
        in the specified unit, depending on active positioning mode.
        Suitable for absolute and relative movement as well as degrees (if calibrated) or steps.

        Parameters
        ----------
        pos : float
            Position or distance to move
        unit : str
            Unit of position ("deg" or "steps")

        Returns
        -------
        None
        """
        position = self.readMoves()
        self.readInitSpeed()
        if unit == "deg":
            moves = int(float(self.zero_offset) + float(pos) * float(self.steps_per_deg))
        else:
            moves = int(pos)
        mode = self.pos_mode
        rotDir = sign(moves)
        if mode == "rel":  # in rel pos mode no negative values are allowed
            moves = clip(
                moves,
                int(self.steps_upper_limit) - int(position),
                int(self.steps_lower_limit) - int(position),
            )
            moves = int(abs(moves))
            self.setRotDir(rotDir)
        else:
            moves = clip(moves, int(self.steps_upper_limit), int(self.steps_lower_limit))
        self.query("#1s" + str(int(moves)))  # sets moves
        self.startRecord()

    @synchronized
    def moveClipWait(self, posDeg, unit):
        """
        Move the motor with position clipping and wait for completion.

        Move the motor by a given distance (rel) or to a given position (abs)
        in the specified unit, depending on active positioning mode.
        Wait for move to finish.
        Suitable for absolute and relative movement as well as degrees (if calibrated) or steps.

        Parameters
        ----------
        posDeg : float
            Position or distance to move
        unit : str
            Unit of position ("deg" or "steps")

        Returns
        -------
        None
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
                except VisaIOError:
                    # why is this required at all?
                    # TODO: Test on device
                    self.moving = True
        self.setRotDir(initRotDir)

    @synchronized
    def readMoves(self):
        """
        Read the current position in steps.

        Parameters
        ----------
        None

        Returns
        -------
        int
            Current position in steps
        """
        pos = self.query("#1C")
        return int(pos.strip().replace("1C", ""))

    def getPosDeg(self):
        """
        Get current position in degrees.

        Parameters
        ----------
        None

        Returns
        -------
        float
            Current position in degrees
        """
        pos = float(self.zero_offset) - float(self.readMoves())
        posDeg = -1 * pos / float(self.steps_per_deg)
        return posDeg

    def getPosMode(self):
        """
        Get active positioning mode.

        Parameters
        ----------
        None

        Returns
        -------
        str
            Positioning mode ("rel", "abs", or "error")
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
        Read the current minimum step frequency.

        Parameters
        ----------
        None

        Returns
        -------
        int
            Minimum step frequency in steps/s
        """
        return int(self.query("#1Zu").strip().replace("1Zu", ""))

    def getLastReferenceTime(self):
        """
        Get the time of the last reference run in local time.

        Parameters
        ----------
        None

        Returns
        -------
        str
            Time of run formatted as "YYYY-MM-DD hh:mm:ss"
        """
        return self.last_reference_run

    def getMovingStatus(self):
        """
        Read if the motor is still moving.

        Parameters
        ----------
        None

        Returns
        -------
        bool
            True if the motor is moving, False otherwise
        """
        answer = self.query("#1$")
        status = answer.replace("001$", "")
        isMoving = 0 == (int(status) & 0b1)
        self.moving = isMoving
        return isMoving

    def getErrorStatus(self):
        """
        Read if the motor has a position error.

        Parameters
        ----------
        None

        Returns
        -------
        bool
            True if there is a position error, False otherwise
        """
        answer = self.query("#1$")
        status = answer.replace("001$", "")
        print(status)
        isPosError = 0 != (int(status) & 0b100)
        self.poserror = isPosError
        return isPosError

    def getRotDir(self):
        """
        Get the rotation direction.

        Parameters
        ----------
        None

        Returns
        -------
        int
            Rotation direction (0: Left, 1: Right)
        """
        return self.rot_dir

    def getCurrentRecordParams(self, param):
        """
        Readout the current record write parameter set in dictionary.

        Parameters
        ----------
        param : str
            Parameter to retrieve, options include:
            - p: Position mode
            - s: Travel distance
            - u: Initial step frequency
            - o: Maximum step frequency
            - n: Second maximum step frequency
            - b: Acceleration and braking ramp
            - d: Direction of rotation
            - t: Reversal in direction of rotation for repeat records
            - w: Repetitions
            - P: Pause between repetitions and continuation records
            - N: Record number of continuation record

        Returns
        -------
        int
            Value of the requested parameter
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
        Reset the position of the motor to 0.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        self.query("#1c")
