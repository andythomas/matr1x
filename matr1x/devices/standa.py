# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
import ctypes
import os.path
import sys


class Standa8SMC4():
    config_params = {}

    def __init__(self):
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
                "package.")
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
        return "StandaMotor"

    def query(self, msg):
        """ not implemented, return call """
        return msg

    # high level functions
    def getSpeed(self):
        """
        Reads speed from motor
        """
        mvst = self.pyximc.move_settings_t()
        result = self.lib.get_move_settings(self._device_id,
                                            ctypes.byref(mvst))
        return mvst.Speed

    def setSpeed(self, speed):
        """
        Sets the motor speed
        """

    def getPosition(self, speed):
        """
        returns position of motor
        """
        x_pos = self.pyximc.get_position_t()
        result = self.lib.get_position(self._device_id, ctypes.byref(x_pos))
        return float(x_pos.Position) + float(x_pos.uPosition)/256.

    def move(self, distance):
        """
        Moves by distance (in steps)
        """
        udistance = int((distance - int(distance))*256)
        distance = int(distance)
        result = self.lib.command_move(self._device_id, distance, udistance)
        print(result)

    def waitForStop(self):
        """
        Delays until motor is stopped
        """
        result = self.lib.command_wait_for_stop(self._device_id, 100)
        print(result)

    def getStatus(self):
        """
        Returns the status
        """
        x_status = self.pyximc.status_t()
        result = self.lib.get_status(self._device_id, ctypes.byref(x_status))
        print("Result " + repr(result))


class Standa8SMC1():
    config_params = {}

    def __init__(self):
        self.speed = 0
        # add path to folder to pythonpath, should contain the pyximc.py
        # wrapper file (not included in this package)
        # software can be obtained from:
        # https://files.xisupport.com/Software.en.html
        try:
            import PyUSMC
        except ImportError:
            raise ImportError("Standa8SMC1 driver was loaded without the "
                              "required PyUSMC library installed on the "
                              "system. Please install missing package.")
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
        return "StandaMotor-8SMC1"

    def query(self, msg):
        """ not implemented, return call """
        return msg

    # high level functions
    def getSpeed(self):
        """
        Reads speed from motor
        """
        return self.speed

    def setSpeed(self, speed):
        """
        Sets the motor speed
        """
        speed = abs(speed)
        if speed < 10:
            self.speed = speed

    def setMotorPower(self, state):
        """
        Turns the motor on or off depending on state
        """
        if state is True:
            self._device_id.mode.PowerOn()
        elif state is False:
            self._device_id.mode.PowerOff()

    def setPosition(self, position):
        """
        Sets the current position to position (in degree)
        """
        self._device_id.SetCurrentPosition(position)

    def getPosition(self):
        """
        returns position of motor in degree
        """
        pos = self._device_id.GetPos()
        return pos

    def move(self, position):
        """
        Moves to position (in degree)
        """
        self._device_id.Start(position, self.speed)

    def waitForStop(self):
        """
        Delays until motor is stopped
        """
        self._device_id.WaitToStop()
