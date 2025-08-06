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
"""
Matr1x data acquisition control module.

This module provides control thread classes for PID control.
"""

import threading
import time
import warnings

import numpy as np


class ControlThread(threading.Thread):
    """
    Control thread class, needs to be reimplemented to function properly.

    This class provides a framework for implementing control threads with PID control.
    Child classes should reimplement specific methods to customize functionality.

    Notes
    -----
    Reimplement the _initializeReadout() and _initializeOutput() functions for
    initialization of output devices. Make sure to set outLimit, bipolar,
    outdim and maxOut in these functions.

    Reimplement _getReading() for readout value and _setOutput() for setting
    of output values.

    Internally uses the PIDcontroller class for the PID control.

    Attributes
    ----------
    outLimit : float
        Current maximum output value.
    bipolar : bool
        Whether output range is bipolar (True) or unipolar (False).
    maxOut : float
        Absolute maximum output value allowed.
    rateLimit : float or None
        Maximum rate of change for control values (control units/s).
    """

    outLimit = None
    bipolar = None
    maxOut = None

    rateLimit = None

    def __init__(self, parent=None, lock=None, ndim=1):
        """
        Initialize the control thread.

        Parameters
        ----------
        parent : object, optional
            Parent class for accessing functions
        lock : threading.Lock, optional
            Multithreading lock, by default None which creates a new lock
        ndim : int, optional
            Number of dimensions for control, by default 1
        """
        warnings.warn(
            "The class ControlThread is deprecated and will be removed in a future release. "
            "Please use https://simple-pid.readthedocs.io/.",
            category=DeprecationWarning,
            stacklevel=2,
        )
        threading.Thread.__init__(self)
        # parent class necessary if functions should be acessed
        self.parent = parent
        # parent window, necessary for acquisition of multithreading lock if no
        # lock is required, pass None as parameter, then a new lock is
        # initialized
        if lock is not None:
            self.lock = lock
        else:
            self.lock = threading.Lock()

        self.controlMode = 0
        self.ndim = ndim
        self.terminate = False

        self._initializeReadout()
        self._initializeOutput()

        assert self.bipolar is not None and self.outLimit is not None and self.maxOut is not None

        self.pidController = PIDcontroller(ndim)
        self.pidController.outLimit = self.outLimit
        self.pidController.bipolar = self.bipolar

        self.analogOut = np.zeros(self.ndim)
        self.currentOutput = np.zeros(self.ndim)

    # device specific driver functions
    def _initializeReadout(self):
        """
        Initialize the readout stage of the PID controller.

        This method should be reimplemented by child classes if
        necessary.
        """
        pass

    def _initializeOutput(self):
        """
        Initialize the output stage of the PID controller.

        This method needs to be reimplemented for other devices than the Waveshare DAC.

        Notes
        -----
        Make sure to set:
            self.maxOut (absolute maximum output value)
            self.outLimit (current maximum output value) in this function!
            self.bipolar (bool determining bipolar or unipolar output)
        """
        pass

    def _getReading(self):
        """
        Get the readout value from the device.

        This method should be reimplemented by child classes if necessary.

        Returns
        -------
        numpy.ndarray
            Vector of length ndim with current readings
        """
        pass

    def _setOutput(self, output):
        """
        Write the output value to the respective device.

        This method should be reimplemented by child classes if necessary.

        Parameters
        ----------
        output : numpy.ndarray
            Vector of length ndim with output values

        Notes
        -----
        Should take a vector of length ndim. If output dimension
        is different, handle this in this function (i.e. read dimension is
        three and output dimension only 2).

        Important: For proper function of the rate limiting, self.currentOutput has to
        be set here, so the current output values can be compared.
        """
        pass

    # driver functions
    def setOutput(self, output, ax=0):
        """
        Set the analog output voltage.

        Parameters
        ----------
        output : float or numpy.ndarray
            Output value(s) to set
        ax : int, optional
            Axis to set output for, by default 0. Use -1 for all axes.
        """
        if ax > self.ndim or ax < -1:
            return
        if -1 == ax:
            if len(output) != self.ndim:
                return
            for i in range(self.ndim):
                if np.absolute(output[i]) > self.outLimit:
                    output[i] = np.sign(output[i]) * self.outLimit
                elif self.bipolar is False and 0 > output[i]:
                    output[i] = 0
            self.analogOut = output
        else:
            if np.absolute(output) > self.outLimit:
                output = np.sign(output) * self.outLimit
            elif self.bipolar is False and 0 > output:
                output = 0
            self.analogOut[ax] = output

    def getOutput(self, ax=0):
        """
        Get the current analog output value.

        Parameters
        ----------
        ax : int, optional
            Axis to get output for, by default 0. Use -1 for all axes.

        Returns
        -------
        float or numpy.ndarray
            Current output value(s)
        """
        if ax > self.ndim or ax < -1:
            return
        if -1 == ax:
            return self.currentOutput
        else:
            return self.currentOutput[ax]

    def setMode(self, mode):
        """
        Set the control mode.

        Parameters
        ----------
        mode : int
            Control mode (0: inactive, 1: PID control, 2: manual)
        """
        if mode > 2:
            return
        elif mode < 0:
            return
        self.controlMode = int(mode)

    def getMode(self):
        """
        Get the current control mode.

        Returns
        -------
        int
            Current control mode (0: inactive, 1: PID control, 2: manual)
        """
        return self.controlMode

    def setParameter(self, param):
        """
        Set the controlling parameters of the PID controller.

        Parameters
        ----------
        param : tuple
            Tuple of length three with p, i, d parameters
        """
        if len(param) != 3:
            return
        self.pidController.parameters = param

    def getParameters(self):
        """
        Get the current controlling parameters.

        Returns
        -------
        numpy.ndarray
            Array with current [P, I, D] parameters
        """
        return self.pidController.parameters

    def setSetPoint(self, setpoint):
        """
        Set the controlling setpoint.

        Parameters
        ----------
        setpoint : tuple or list
            Setpoint values of length ndim (e.g., with Bx, By, Bz for 3D)
        """
        if self.ndim != len(setpoint):
            return
        self.pidController.setpoint = np.array(setpoint)

    def getSetPoint(self):
        """
        Get the current controlling setpoint.

        Returns
        -------
        list
            Current setpoint values
        """
        return list(self.pidController.setpoint)

    def setRateLimit(self, limit):
        """
        Set the rate limit for maximum control change.

        Parameters
        ----------
        limit : float
            Maximum rate of change in control units/s
        """
        self.rateLimit = abs(float(limit))

    def getRateLimit(self):
        """
        Get the rate limit for maximum control change.

        Returns
        -------
        float
            Current rate limit in control units/s
        """
        return self.rateLimit

    def setOutLimit(self, limit):
        """
        Set the maximum output value.

        Parameters
        ----------
        limit : float
            Maximum output value (must be positive, applied to both positive and negative)
        """
        if np.absolute(limit) > self.maxOut:
            limit = self.maxOut
        self.outLimit = np.absolute(limit)
        self.pidController.outLimit = self.outLimit

    def getOutLimit(self):
        """
        Get the current maximum output voltage.

        Returns
        -------
        float
            Current maximum output value
        """
        return self.outLimit

    def run(self):
        """
        Execute the control loop.

        This method handles the control based on the selected mode. May
        need to be reimplemented for different devices.
        """
        outp = np.zeros(self.ndim)
        lastcontrol = time.time()
        while self.terminate is False:
            currentcontrol = time.time()
            if self.controlMode == 0:
                time.sleep(1)
            else:
                if self.controlMode == 1:
                    # get time for rate limiting
                    # do the PID control
                    np.copyto(outp, self.pidController.control(self._getReading()))
                    # delay to limit speed
                    # best rate is limited by reading fresh rate, could be changed
                    time.sleep(0.02)
                if self.controlMode == 2:
                    if any(self.analogOut != self.currentOutput):
                        np.copyto(outp, self.analogOut)
                    else:
                        # if no change needs to be done, store the last time
                        # and reset to beginning of while loop
                        lastcontrol = currentcontrol
                        time.sleep(0.01)
                        continue
                if self.rateLimit is not None and 0 != self.rateLimit:
                    #
                    dt = lastcontrol - currentcontrol
                    changeRate = (outp - self.currentOutput) / dt
                    mask = abs(changeRate) > self.rateLimit
                    if any(mask):
                        outp[mask] = (
                            self.currentOutput[mask]
                            + np.sign(changeRate[mask]) * self.rateLimit * dt
                        )
                self._setOutput(outp)
            lastcontrol = currentcontrol

    def stop(self):
        """
        Request the controlling thread to terminate.

        Sets the terminate flag to stop the control loop.
        """
        self.terminate = True


class PIDcontroller:
    """
    PID controller class.

    This class implements a Proportional-Integral-Derivative controller
    for multiple dimensions.

    Attributes
    ----------
    setpoint : numpy.ndarray
        Setpoint of PID controller, array of length ndim
    outLimit : float
        The maximum allowed output value, used for controlling integral windup
    parameters : numpy.ndarray
        Contains the [KP, KI, KD] parameters
    bipolar : bool
        Determines whether output is bipolar (True) or unipolar, this is only
        used for output limiting (between +-max or 0-max)

    Notes
    -----
    The other parameters should not be accessed directly.
    """

    def __init__(self, ndim):
        """
        Initialize PID controller class with ndim dimensions.

        Parameters
        ----------
        ndim : int
            Number of dimensions for the controller

        Notes
        -----
        Make sure outFunc and readFunc take/return np.arrays of correct
        dimension.
        """
        self.parameters = np.zeros(3)
        self.outLimit = 0
        self._lasttime = 0

        self._ndim = ndim
        self.setpoint = np.zeros(ndim)
        self.bipolar = True
        self._integral = np.zeros(ndim)
        self._previous_error = np.zeros(ndim)
        self.ones = np.ones(ndim)

    def control(self, reading):
        """
        Run one step of the PID control for the given reading.

        Parameters
        ----------
        reading : numpy.ndarray
            Current reading values, array of length ndim

        Returns
        -------
        numpy.ndarray
            Output values after PID control calculation
        """
        t = time.time()
        dt = t - self._lasttime
        self._lasttime = t
        # add the error for averaging
        error = self.setpoint - reading
        # calculate integral, weighting is done here to
        # allow for easy mitigation of windup
        self._integral += self.parameters[1] * error * dt
        # windup supression
        ol = self.outLimit < np.absolute(self._integral)
        if any(ol):
            # set all values that are above/below self.outLimit to +-
            # self.outlimit
            self._integral[ol] = self.ones[ol] * self.outLimit * np.sign(self._integral[ol])
        if self.bipolar is False:
            ol = self._integral < 0
            if any(ol):
                # set all values that are below 0 to 0
                self._integral[ol] = self.ones[ol] * 0
        # calculate derivative and store previous error
        derivative = (error - self._previous_error) / dt
        self._previous_error = error
        # calculate output from parameters
        output = self.parameters[0] * error + self._integral + self.parameters[2] * derivative
        # limit control
        for i, elem in enumerate(output):
            if np.absolute(elem) > self.outLimit:
                output[i] = self.outLimit * np.sign(output[i])
            elif self.bipolar is False and elem < 0:
                output[i] = 0
        # return the new setpoint
        return output
