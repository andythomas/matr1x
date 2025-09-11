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
"""Module with device drivers for a PI stepper motor controller."""

from wrapt import synchronized

from matr1x.devices.visadevice import VisaDevice


class MercuryC663(VisaDevice):
    """
    Driver for PI stepper motor @ Rote Zora.

    This class provides control for the PI stepper motor with ItemID of
    the axis used for communication being 1.
    """

    def __init__(self, interface, **kwargs):
        """
        Initialize the Mercury C663 device.

        Parameters
        ----------
        interface : str
            VISA resource name or interface identifier
        """
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 1000
        if "encoding" not in kwargs:
            kwargs["encoding"] = "iso-8859-1"
        if "cmdpers" not in kwargs:
            kwargs["cmdpers"] = 20
        super().__init__(interface, **kwargs)
        try:  # first read attempt after opening usually fails
            self.getMotorState()
        except Exception:  # catch all possible Errors here
            pass

    @synchronized
    def getMotorState(self):
        """
        Get the motor state for the axis.

        Returns
        -------
        int
            Motor state: 1 for on, 0 for off
        """
        self.write("SVO?")
        return int(self.read()[2])

    def setMotorON(self):
        """
        Turn on the motor for the axis.

        This needs to be done after connecting to the motor.
        """
        self.write("SVO 1 1")

    def setMotorOFF(self):
        """Turn off the motor for the axis."""
        self.write("SVO 1 0")

    @synchronized
    def getReference(self):
        """
        Check reference state of the motor.

        Returns
        -------
        int
            Reference state: 1 if successfully referenced, 0 if not
        """
        self.write("FRF?")
        return int(self.read()[2])

    def setReference(self):
        """
        Move the motor to reference position (6deg).

        Note: Motor must be switched on!
        """
        self.write("FRF")

    def gotohome(self):
        """
        Move the motor to home position (0deg).

        Note: Motor must be switched on!
        """
        self.write("GOH")

    def setAngleAbs(self, angle):
        """
        Move to absolute angle defined from home position.

        Parameters
        ----------
        angle : float
            Target absolute angle in degrees
        """
        self.write(f"MOV 1 {float(angle):f}")

    def setAngleRel(self, angle):
        """
        Move to angle relative to current position.

        The sum of the provided angle and the last commanded target position
        is set as the new target position.

        Parameters
        ----------
        angle : float
            Relative angle change in degrees
        """
        self.write(f"MVR 1 {float(angle):f}")

    @synchronized
    def getAngle(self):
        """
        Read current target angle.

        Returns
        -------
        float
            Current target angle in degrees
        """
        self.write("MOV? 1")
        return float(self.read()[2:])

    @synchronized
    def getOnTarget(self):
        """
        Read on-target status of axis 1.

        Returns
        -------
        int
            1 if the axis is on target, 0 if not
        """
        self.write("ONT? 1")
        return int(self.read()[2:])

    def stop(self):
        """Stop all axis movement with system deceleration."""
        self.write("HLT")
