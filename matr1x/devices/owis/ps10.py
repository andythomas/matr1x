# This file is part of a software collection for data acquisition (matr4x).
# Copyright (C) 2006-2025 matr1x developers
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
"""Module for controlling OWIS PS10 motor controllers."""

import logging
import time

from wrapt import synchronized

from matr1x.devices.visadevice import VisaDevice

logger = logging.getLogger(__name__)


class Ps10(VisaDevice):
    r"""
    Owis PS10 motor controller class for stepper motor control.

    This class provides an interface to control Owis PS10 motor controllers,
    particularly for DMT100 stepper motors. It supports both absolute and
    relative movement modes.

    Parameters
    ----------
    interface : str
        VISA address, e.g. ASRL/dev/ttyUSB0::INSTR
    microsteps : int, optional
        Number of microsteps per full step, default is 50
    steps_per_rev : int, optional
        Number of full steps per motor revolution, default is 200
    gear_ratio : float, optional
        The gear ratio of the motor, default is 180
    angle_conv : float, optional
        The full angle for conversion (degrees), default is 360
    **kwargs
        Additional parameters passed to VisaDevice:

        write_termination : str
            Line termination for write commands, default is "\r"
        read_termination : str
            Line termination for read commands, default is "\r"
        cmdpers : int
            Commands per second, default is 20
        baud_rate : int
            Serial baud rate, default is 115200

    Notes
    -----
    The DMT100 motor configuration uses 50 microsteps, 200 steps per motor
    revolution, and a 180:1 gear ratio by default.
    """

    config_params = {"Mode": "getMode"}

    def __init__(
        self,
        interface,
        microsteps=50,
        steps_per_rev=200,
        gear_ratio=180,
        angle_conv=360,
        **kwargs,
    ):
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r"
        if "cmdpers" not in kwargs:
            kwargs["cmdpers"] = 20
        if "baud_rate" not in kwargs:
            kwargs["baud_rate"] = 115200

        super().__init__(interface, **kwargs)

        # Calculate steps per degree based on configurable parameters
        self.DMT100_deg = microsteps * steps_per_rev * gear_ratio / angle_conv

    @synchronized
    def query(self, msg, depth=0):
        """
        Query the device with automatic retry.

        Parameters
        ----------
        msg : str
            Command message to send to device
        depth : int, optional
            Current recursion depth for retries, by default 0

        Returns
        -------
        str
            Device response

        Notes
        -----
        Will retry up to 5 times if an empty response is received.
        """
        if depth > 5:
            return "0"
        self.write(msg)
        ret = self.read()
        if ret == "":
            logger.info(f"{self.name}.query: empty reply ('{msg}', {ret})")
            return self.query(msg, depth=depth + 1)
        return ret

    @synchronized
    def query_int(self, msg, depth=0):
        """
        Query an integer from the device with error checking.

        Parameters
        ----------
        msg : str
            Command message to send to device
        depth : int, optional
            Current recursion depth for retries, by default 0

        Returns
        -------
        int
            Integer value from device response

        Notes
        -----
        Will retry if value cannot be converted to an integer.
        """
        ret = self.query(msg, depth)
        try:
            return int(ret)
        except ValueError:
            logger.info(
                f"{self.name}.query_int: integer conversion error ('{msg}', {ret})"
            )
            # retry query
            return self.query_int(msg, depth + 1)

    # high level functions
    def id(self):
        """
        Get the device version identification.

        Returns
        -------
        str
            Version information from the device
        """
        return self.query("?VERSION")

    def init(self):
        """
        Initialize the motor axis.

        Must be called after connecting to the motor.
        """
        self.write("INIT1")

    def getReferenced(self):
        """
        Check if the motor is referenced.

        Returns
        -------
        int
            1 if referenced, 0 if not
        """
        return self.query_int("?REFST1")

    def startReferenceDrive(self):
        """
        Start the reference drive procedure.

        Goes to the reference position and sets position counter to 0 using
        reference mode 4.
        """
        self.write("REF1=4")

    def setMode(self, mode):
        """
        Set the movement mode.

        Parameters
        ----------
        mode : str
            Movement mode, must be either "ABSOL" or "RELAT"
        """
        # first read out was ABSOL
        assert "ABSOL" == mode or "RELAT" == mode
        self.write(mode + "1")

    def getMode(self):
        """
        Get the current movement mode.

        Returns
        -------
        str
            Current mode, either "ABSOL" or "RELAT"
        """
        return self.query("?MODE1")

    @synchronized
    def moveSteps(self, steps):
        """
        Move the motor by a specified number of steps.

        In absolute mode, moves to the absolute position.
        In relative mode, moves by the specified amount from current position.

        Parameters
        ----------
        steps : int
            Target position in steps
        """
        if -100000000 < int(steps) and 100000000 > int(steps):
            dummy = "PSET1={:d}".format(int(steps))
            self.write(dummy)
            # start movement
            self.write("PGO1")

    def moveAngle(self, angle):
        """
        Move the motor by a specified angle.

        In absolute mode, moves to the absolute angle.
        In relative mode, moves by the specified angle from current position.

        Parameters
        ----------
        angle : float
            Target angle in degrees
        """
        self.moveSteps(angle * self.DMT100_deg)

    def waitUntilMoved(self):
        """
        Wait until the motor has stopped moving.

        Polls the motor status and blocks until the movement is complete.
        """
        while self.getMoving():
            time.sleep(0.05)

    def getMoving(self):
        """
        Check if the motor is currently moving.

        Returns
        -------
        bool
            True if the motor is moving, False otherwise
        """
        ret = self.query_int("?VACT1")
        if 0 == ret:
            return False
        return True

    def readAngle(self):
        """
        Read the current motor angle.

        Returns
        -------
        float
            Current angle in degrees
        """
        return self.readSteps() / self.DMT100_deg

    def readSteps(self):
        """
        Read the current motor position in steps.

        Returns
        -------
        int
            Current position in steps
        """
        return self.query_int("?CNT1")

    def stop(self):
        """Stop all motor movement immediately."""
        self.write("STOP1")

    def setMotorState(self, state):
        """
        Set the motor power state.

        Parameters
        ----------
        state : bool
            True to turn motor on, False to turn motor off
        """
        if state is True:
            self.write("MON1")
        else:
            self.write("MOFF1")
