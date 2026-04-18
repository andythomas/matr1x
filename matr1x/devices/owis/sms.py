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
"""
OWIS SMS motor controller interface module for stepper motor control.

This module provides the SMS class which interfaces with OWIS motor
controllers.
"""

import time

from matr1x.devices.visadevice import VisaDevice


class SMS(VisaDevice):
    r"""
    OWIS SMS motor controller class for stepper motor control.

    This class provides an interface to the SM INT controller with two
    SMK 02-Z stepper motor drivers. By default, it is configured for a
    rotary stepper motor with 200 steps per motor revolution and a
    1400:1 gear ratio, converting steps to degrees for angular
    positioning.

    The class allows control of up to 4 axes (X, Y, Z, R) and supports
    both absolute and relative movement commands.

    Parameters
    ----------
    interface : str
        VISA address, e.g. ASRL/dev/ttyUSB0::INSTR
    steps_per_revolution : int, optional
        Number of steps per motor revolution, default is 200
    gear_ratio : float, optional
        The gear ratio of the motor, default is 1400
    angle_ratio : float, optional
        The angle ratio for conversion, default is 540 (1.5 revolutions)
    limits : dict, optional
        Dictionary specifying the position limits for each axis.
        Format: {axis_number: {"lo": lower_limit, "hi": upper_limit}}
    **kwargs
        Additional parameters passed to VisaDevice:

        write_termination : str
            Line termination for write commands, default is "\r"
        read_termination : str
            Line termination for read commands, default is "\r"
        cmdpers : int
            Commands per second, default is 50
        timeout : float
            Timeout in milliseconds, default is 80000
        baud_rate : int
            Serial baud rate, default is 2400

    Notes
    -----
    To use a different unit system (e.g., linear positioning in mm instead of degrees),
    you can adjust the steps_per_revolution, gear_ratio, and angle_ratio parameters
    to match your mechanical setup.
    """

    _axes = {0: "X", 1: "Y", 2: "Z", 3: "R"}

    def __init__(
        self,
        interface,
        steps_per_revolution=200,
        gear_ratio=1400,
        angle_ratio=540,
        limits=None,
        **kwargs,
    ):
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
        self._steps_per_deg = steps_per_revolution * gear_ratio / angle_ratio
        self._settings = {ax: {} for ax, it in self._axes.items()}

        # Set default limits if none provided
        default_limits = {ax: {"lo": -40, "hi": 400} for ax in self._axes}
        if limits is not None:
            for ax, limit_values in limits.items():
                if ax in default_limits:
                    default_limits[ax].update(limit_values)

        self._limits = default_limits

    # high level functions
    def id(self):
        """
        Get the device identification string.

        Returns
        -------
        str
            The device ID string.
        """
        ret = self.query("VD")
        # read additional bits from interface (\n\x00)
        self.read_very_eager()
        return ret

    def configure_drive(self, stepfreq, ramp, startfreq, ax=0):
        """
        Configure the drive settings for an axis.

        Configures the parameters used by move_abs and move_rel. If drive/axis
        settings are not configured, device internal defaults are used.

        Parameters
        ----------
        stepfreq : int
            Step frequency in Hz. Maximum frequency is 15 kHz.
        ramp : int
            Ramp time in ms.
        startfreq : int
            Start frequency in Hz at the beginning of the ramp.
        ax : int, optional
            Axis to be configured (0-3), default is 0.

        Notes
        -----
        (stepfreq-startfreq)/ramp must be >= 100 Hz/s (watch units).
        For more details, refer to the device manual.
        """
        # cast to int
        stepfreq = int(stepfreq)
        startfreq = int(startfreq)
        ramp = int(ramp)
        # check validity:
        if (stepfreq - startfreq) / (ramp / 1000) < 100:
            # >= 100 Hz/s is required
            return
        self._settings[ax]["stepfreq"] = stepfreq
        self._settings[ax]["ramp"] = ramp
        self._settings[ax]["startfreq"] = startfreq

    def initialize(self, ax=0):
        """
        Initialize the axis and drive the stage to position 0.

        MOTION STARTS IMMEDIATELY if the axis is not at zero position!

        Parameters
        ----------
        ax : int, optional
            Axis to be initialized (0-3), default is 0.
        """
        self.write(f"I{self._axes[ax]}")

    def move_abs(self, pos, ax=0):
        """
        Move to absolute position and block until position is reached.

        Adjust the timeout for very long strides to ensure the function
        waits until the target position is reached.

        Parameters
        ----------
        pos : float
            Desired absolute position in units defined by _steps_per_deg.
        ax : int, optional
            Axis to move (0-3), default is 0.

        Returns
        -------
        None
            Function returns silently if the position is outside the
            configured limits or if the motor is already moving.
        """
        if pos > self._limits[ax]["hi"] or pos < self._limits[ax]["lo"]:
            # only allows rotations within limits
            return
        pos *= self._steps_per_deg
        if self.get_moving():
            # ignore command if still moving
            return
        if self._settings[ax] != {}:
            self.query(
                "GA{}{:d},{:d},{:d},{:d};S;".format(
                    self._axes[ax],
                    int(pos),
                    self._settings[ax]["stepfreq"],
                    self._settings[ax]["ramp"],
                    self._settings[ax]["startfreq"],
                )
            )
        else:
            self.query(f"GA{self._axes[ax]}{int(pos):d};S;")

    def move_rel(self, pos, ax=0):
        """
        Move relative to current position and block until complete.

        Adjust the timeout for very long strides to ensure the function
        waits until the target position is reached.

        Parameters
        ----------
        pos : float
            Desired relative position in units defined by _steps_per_deg.
        ax : int, optional
            Axis to move (0-3), default is 0.

        Returns
        -------
        None
            Function returns silently if the movement would exceed limits
            or if the motor is already moving.
        """
        if abs(pos) > abs(self._limits[ax]["hi"] - self._limits[ax]["lo"]):
            # ignore rotations that are guaranteed to exceed the limit
            return
        pos *= self._steps_per_deg
        if self.get_moving():
            # ignore command if still moving
            return
        if self._settings[ax] != {}:
            self.query(
                "GP{}{:d},{:d},{:d},{:d};S;".format(
                    self._axes[ax],
                    int(pos),
                    self._settings[ax]["stepfreq"],
                    self._settings[ax]["ramp"],
                    self._settings[ax]["startfreq"],
                )
            )
        else:
            self.query(f"GP{self._axes[ax]}{int(pos):d};S;")

    def move_abs_nonblocking(self, pos, ax=0):
        """
        Move to absolute position without blocking.

        Initiates a movement to the specified position and returns immediately,
        without waiting for the motion to complete.

        Parameters
        ----------
        pos : float
            Desired absolute position in units defined by _steps_per_deg.
        ax : int, optional
            Axis to move (0-3), default is 0.

        Returns
        -------
        None
            Function returns silently if the position is outside the
            configured limits or if the motor is already moving.
        """
        if pos > self._limits[ax]["hi"] or pos < self._limits[ax]["lo"]:
            # only allows rotations within limits
            return
        pos *= self._steps_per_deg
        if self.get_moving():
            # ignore command if still moving
            return
        if self._settings[ax] != {}:
            self.write(
                "A{}{:d},{:d},{:d},{:d}".format(
                    self._axes[ax],
                    int(pos),
                    self._settings[ax]["stepfreq"],
                    self._settings[ax]["ramp"],
                    self._settings[ax]["startfreq"],
                )
            )
        else:
            self.write(f"A{self._axes[ax]}{int(pos):d}")
        # wait to make reasonably sure command reaches the driver
        time.sleep(0.25)
        self.write("S")

    def move_rel_nonblocking(self, pos, ax=0):
        """
        Move relative to current position without blocking.

        Initiates a relative movement and returns immediately,
        without waiting for the motion to complete.

        Parameters
        ----------
        pos : float
            Desired relative position in units defined by _steps_per_deg.
        ax : int, optional
            Axis to move (0-3), default is 0.

        Returns
        -------
        None
            Function returns silently if the movement would exceed limits
            or if the motor is already moving.
        """
        if abs(pos) > abs(self._limits[ax]["hi"] - self._limits[ax]["lo"]):
            # ignore rotations that are guaranteed to exceed the limit
            return
        pos *= self._steps_per_deg
        if self.get_moving():
            # ignore command if still moving
            return
        if self._settings[ax] != {}:
            self.write(
                "P{}{:d},{:d},{:d},{:d}".format(
                    self._axes[ax],
                    int(pos),
                    self._settings[ax]["stepfreq"],
                    self._settings[ax]["ramp"],
                    self._settings[ax]["startfreq"],
                )
            )
        else:
            self.write(f"P{self._axes[ax]}{int(pos):d}")
        # wait to make reasonably sure command reaches the driver
        time.sleep(0.25)
        self.write("S")

    def get_moving(self, ax=0):
        """
        Check if the specified axis is currently moving.

        Parameters
        ----------
        ax : int, optional
            Axis to check (0-3), default is 0.

        Returns
        -------
        bool
            True if the axis is moving, False otherwise.
        """
        ret = self.query("B")
        return ret[3 + 3 * ax] == "j"

    def get_pos(self, ax=0):
        """
        Get the current position of an axis.

        Parameters
        ----------
        ax : int, optional
            Axis to query (0-3), default is 0.

        Returns
        -------
        float
            Current position in units defined by _steps_per_deg.
        """
        return float(self.query(f"C{self._axes[ax]}").replace("CX", "")) / self._steps_per_deg

    def stop(self, ax=0):
        """
        Stop the motion of an axis immediately.

        Parameters
        ----------
        ax : int, optional
            Axis to stop (0-3), default is 0.
        """
        self.write(f"E{self._axes[ax]}")
