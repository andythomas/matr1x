# This file is part of a software collection for data aquisition (matr1x).
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

from wrapt import synchronized

from .visadevice import VisaDevice


class MercuryC663(VisaDevice):
    """
    Driver for PI stepper motor @ Rote Zora, ItemID of the
    axis used for communication is 1
    """

    def __init__(self, interface, **kwargs):
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
        gets the motor state for given axes (on=1/ off=0)
        """
        self.write("SVO?")
        return int(self.read()[2])

    def setMotorON(self):
        """
        sets the motor state for given axes (on=1/ off=0),
        needs to be done after connecting to the motor
        """
        self.write("SVO 1 1")

    def setMotorOFF(self):
        """
        sets the motor state for given axes (on=1/ off=0)
        """
        self.write("SVO 1 0")

    @synchronized
    def getReference(self):
        """
        checks reference state, returns 1 (successfully referenced)
        or 0 (not successfully referenced)
        """
        self.write("FRF?")
        return int(self.read()[2])

    def setReference(self):
        """
        moves the motor to reference position (6deg),
        motor must be switched on!
        """
        self.write("FRF")

    def gotohome(self):
        """
        moves the motor to home position (0deg), motor must be switched on!
        """
        self.write("GOH")

    def setAngleAbs(self, angle):
        """
        Move to absolute angle defined from home position

        Parameters:
            angle - float
        """
        self.write("MOV 1 {:f}".format(float(angle)))

    def setAngleRel(self, angle):
        """
        Move to angle relative to current position
        (the sum of the angle and the last commanded target position
        is is set as new target position)

        Parameters:
            angle - float
        """
        self.write("MVR 1 {:f}".format(float(angle)))

    @synchronized
    def getAngle(self):
        """
        Read current angle
        """
        self.write("MOV? 1")
        return float(self.read()[2:])

    @synchronized
    def getOnTarget(self):
        """
        Read on target status of axis 1
        """
        self.write("ONT? 1")
        return int(self.read()[2:])

    def stop(self):
        """
        Stops all axis movement with given system deceleration
        """
        self.write("HLT")
