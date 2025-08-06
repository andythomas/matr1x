# This file is part of a software collection for data acquisition (matr1x).
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
"""Module with device drivers for Standa stepper motor controllers."""

import ctypes
import os.path
import sys


class Standa8SMC4:
    """Control interface for Standa 8SMC4 stepper motor controller."""

    config_params = {}

    def __init__(self):
        """
        Initialize the Standa 8SMC4 motor controller.

        Connects to the motor controller and prepares it for operation.

        Raises
        ------
        ImportError
            If the required pyximc library is not installed.
        ValueError
            If no motor is discovered or more than one motor is connected.
        """
        # add path to folder to pythonpath, should contain the pyximc.py
        # wrapper file (not included in this package)
        # software can be obtained from:
        # https://files.xisupport.com/Software.en.html
        sys.path.append(os.path.dirname(__file__))
        try:
            import pyximc
        except ImportError:
            raise ImportError(
                "Standa8SMC4 driver was loaded without the required pyximc "
                "library installed on the system. Please install missing "
                "package."
            )
        self.pyximc = pyximc
        self.lib = pyximc.lib
        # open motor
        probe_flags = pyximc.EnumerateFlags.ENUMERATE_PROBE
        enum_hints = b"addr="
        devenum = self.lib.enumerate_devices(probe_flags, enum_hints)
        dev_count = self.lib.get_device_count(devenum)
        if dev_count == 0:
            raise ValueError("No motor discovered")
        elif dev_count > 1:
            raise ValueError("More than one motor connected")
        open_name = self.lib.get_device_name(devenum, 0)
        self._device_id = self.lib.open_device(open_name)

    def id(self):
        """
        Return the motor identifier.

        Returns
        -------
        str
            The motor identifier string.
        """
        return "StandaMotor"

    def query(self, msg):
        """
        Not implemented, return call.

        Parameters
        ----------
        msg : str
            The message to query.

        Returns
        -------
        str
            The input message.
        """
        return msg

    # high level functions
    def getSpeed(self):
        """
        Get the current motor speed.

        Returns
        -------
        int
            The current speed setting of the motor.
        """
        mvst = self.pyximc.move_settings_t()
        self.lib.get_move_settings(self._device_id, ctypes.byref(mvst))
        return mvst.Speed

    def setSpeed(self, speed):
        """
        Set the motor speed.

        Parameters
        ----------
        speed : int
            The speed to set for the motor.
        """

    def getPosition(self, speed):
        """
        Get the current position of the motor.

        Parameters
        ----------
        speed : int
            Speed parameter (unused).

        Returns
        -------
        float
            The current position of the motor.
        """
        x_pos = self.pyximc.get_position_t()
        self.lib.get_position(self._device_id, ctypes.byref(x_pos))
        return float(x_pos.Position) + float(x_pos.uPosition) / 256.0

    def move(self, distance):
        """
        Move the motor by the specified distance.

        Parameters
        ----------
        distance : float
            The distance to move in steps.

        Returns
        -------
        int
            Result code from the movement command.
        """
        udistance = int((distance - int(distance)) * 256)
        distance = int(distance)
        result = self.lib.command_move(self._device_id, distance, udistance)
        print(result)

    def waitForStop(self):
        """
        Wait for the motor to stop moving.

        Returns
        -------
        int
            Result code from the wait command.
        """
        result = self.lib.command_wait_for_stop(self._device_id, 100)
        print(result)

    def getStatus(self):
        """
        Get the current status of the motor.

        Returns
        -------
        status_t
            Status object containing current motor status.
        """
        x_status = self.pyximc.status_t()
        result = self.lib.get_status(self._device_id, ctypes.byref(x_status))
        print("Result " + repr(result))


class Standa8SMC1:
    """Control interface for Standa 8SMC1 stepper motor controller."""

    config_params = {}

    def __init__(self):
        """
        Initialize the Standa 8SMC1 motor controller.

        Connects to the motor controller and prepares it for operation.

        Raises
        ------
        ImportError
            If the required PyUSMC library is not installed.
        ValueError
            If no motor is discovered or more than one motor is connected.
        """
        self.speed = 0
        # add path to folder to pythonpath, should contain the pyximc.py
        # wrapper file (not included in this package)
        # software can be obtained from:
        # https://files.xisupport.com/Software.en.html
        try:
            import PyUSMC
        except ImportError:
            raise ImportError(
                "Standa8SMC1 driver was loaded without the "
                "required PyUSMC library installed on the "
                "system. Please install missing package."
            )
        self.controller = PyUSMC.StepperMotorController()
        # open motor
        self.controller.Init()
        # check device count
        dev_count = self.controller.N
        if dev_count == 0:
            raise ValueError("No motor discovered")
        elif dev_count > 1:
            raise ValueError("More than one motor connected")
        # move motor object into name space
        self._device_id = self.controller.motors[0]
        self._device_id.mode.PowerOn()

    def id(self):
        """
        Return the motor identifier.

        Returns
        -------
        str
            The motor identifier string.
        """
        return "StandaMotor-8SMC1"

    def query(self, msg):
        """
        Not implemented, return call.

        Parameters
        ----------
        msg : str
            The message to query.

        Returns
        -------
        str
            The input message.
        """
        return msg

    # high level functions
    def getSpeed(self):
        """
        Get the current motor speed.

        Returns
        -------
        float
            The current speed setting of the motor.
        """
        return self.speed

    def setSpeed(self, speed):
        """
        Set the motor speed.

        Parameters
        ----------
        speed : float
            The speed to set for the motor. Must be less than 10.
        """
        speed = abs(speed)
        if speed < 10:
            self.speed = speed

    def setMotorPower(self, state):
        """
        Set the power state of the motor.

        Parameters
        ----------
        state : bool
            True to power on, False to power off.
        """
        if state is True:
            self._device_id.mode.PowerOn()
        elif state is False:
            self._device_id.mode.PowerOff()

    def setPosition(self, position):
        """
        Set the current position of the motor.

        Parameters
        ----------
        position : float
            The position to set in degrees.
        """
        self._device_id.SetCurrentPosition(position)

    def getPosition(self):
        """
        Get the current position of the motor.

        Returns
        -------
        float
            The current position of the motor in degrees.
        """
        pos = self._device_id.GetPos()
        return pos

    def move(self, position):
        """
        Move the motor to the specified position.

        Parameters
        ----------
        position : float
            The target position in degrees.
        """
        self._device_id.Start(position, self.speed)

    def waitForStop(self):
        """
        Wait for the motor to stop moving.

        Blocks until the motor has stopped moving.
        """
        self._device_id.WaitToStop()
