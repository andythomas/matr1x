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

import threading
import time

import numpy as np


class ControlThread (threading.Thread):
    """
    Control thread class, needs to be reimplemented to function properly.

    reimplement the _initializeReadout() and _initalizeOutput() functions for
    initialization of output devices. Make sure to set outLimit, bipolar,
    outdim and maxOut in these functions
    reimplement _getReading() for readout value
    reimplement _setOutput() for setting of output values

    Internally uses the PIDcontroller class for the PID control.
    """
    outLimit = None
    bipolar = None
    maxOut = None

    rateLimit = None

    def __init__(self, parent=None, lock=None, ndim=1):
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

        assert (self.bipolar is not None and self.outLimit is not None and
                self.maxOut is not None)

        self.pidController = PIDcontroller(ndim)
        self.pidController.outLimit = self.outLimit
        self.pidController.bipolar = self.bipolar

        self.analogOut = np.zeros(self.ndim)
        self.currentOutput = np.zeros(self.ndim)

    # device specific driver functions
    def _initializeReadout(self):
        """
        initializes the readout stage of the PID controller
        reimplement if necessary
        """

    def _initializeOutput(self):
        """
        initializes the output stage of the PID controller, needs to be
        reimplemented for other devices than the Waveshare DAC

        make sure to set:
            self.maxOut (absolut maximum output value)
            self.outLimit (current maximum output value) in this function!
            self.bipolar (bool determining bipolar or unipolar output
        """

    def _getReading(self):
        """
        function for obtaining the readout value, should return a vector of
        length ndim
        reimplement if necessary
        """

    def _setOutput(self, output):
        """
        function for writing the output value to the respective device
        reimplement if necessary
        should take a vector of length ndim, if output dimension
        is different, handle this in this function (i.e. read dimension is
        three and output dimension only 2)
        important sidenote:
            for proper function of the rate limiting, self.currentOutput has to
            be set here, so the current output values can be compared
        """

    # driver functions
    def setOutput(self, output, ax=0):
        """
        Sets the analog output voltage
        """
        if ax > self.ndim or ax < -1:
            return
        if -1 == ax:
            if len(output) != self.ndim:
                return
            for i in range(self.ndim):
                if np.absolute(output[i]) > self.outLimit:
                    output[i] = np.sign(output[i])*self.outLimit
                elif self.bipolar is False and 0 > output[i]:
                    output[i] = 0
            self.analogOut = output
        else:
            if np.absolute(output) > self.outLimit:
                output = np.sign(output)*self.outLimit
            elif self.bipolar is False and 0 > output:
                output = 0
            self.analogOut[ax] = output

    def getOutput(self, ax=0):
        """
        returns the current analog output value
        """
        if ax > self.ndim or ax < -1:
            return
        if -1 == ax:
            return self.currentOutput
        else:
            return self.currentOutput[ax]

    def setMode(self, mode):
        if mode > 2:
            return
        elif mode < 0:
            return
        self.controlMode = int(mode)

    def getMode(self):
        return self.controlMode

    def setParameter(self, param):
        """
        sets the controlling parameter of the pid
        param must be a tuple of length three with p,i,d-parameter
        """
        if len(param) != 3:
            return
        self.pidController.parameters = param

    def getParameters(self):
        """
        returns the current controlling parameter
        """
        return self.pidController.parameters

    def setSetPoint(self, setpoint):
        """
        sets the the controlling setpoint
        setpoint must be a tuple of length ndim with Bx,By,Bz
        """
        if self.ndim != len(setpoint):
            return
        self.pidController.setpoint = np.array(setpoint)

    def getSetPoint(self):
        """
        returns the current controlling setpoint
        """
        return list(self.pidController.setpoint)

    def setRateLimit(self, limit):
        """
        sets the rate limit for maximumum control change (control unit/s)
        """
        self.rateLimit = abs(float(limit))

    def getRateLimit(self):
        """
        returns the rate limit for maximumum control change
        """
        return self.rateLimit

    def setOutLimit(self, limit):
        """
        sets the maximum output value
        limit must be positive and is set also for negative values
        """
        if np.absolute(limit) > self.maxOut:
            limit = self.maxOut
        self.outLimit = np.absolute(limit)
        self.pidController.outLimit = self.outLimit

    def getOutLimit(self):
        """
        returns the current maximum output voltage
        """
        return self.outLimit

    def run(self):
        """
        probably needs to be reimplemented for different devices
        control function that really handles the control
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
                    np.copyto(outp,
                              self.pidController.control(self._getReading()))
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
                    changeRate = (outp - self.currentOutput)/dt
                    mask = abs(changeRate) > self.rateLimit
                    if any(mask):
                        outp[mask] = (self.currentOutput[mask] +
                                      np.sign(changeRate[mask]) *
                                      self.rateLimit*dt)
                self._setOutput(outp)
            lastcontrol = currentcontrol

    def stop(self):
        """
        request the controlling thread to determinate
        """
        self.terminate = True


class PIDcontroller():
    """
    PID controller class

    Access setpoint etc. by accessing class attributes

    Attributes
    ----
    setpoint : array of length ndim
      setpoint of PID controller
    outLimit : float
      the maximum allowed output value, this is in particular used for
      controlling integral windup
    parameters : array of length three
      contains the [KP, KI, KD] parameters
    bipolar : bool
      determines whether output is bipolar (True) or unipolar, this is only
      used for output limiting (between +-max or 0-max)

    The other parameters should not be accessed
    """

    def __init__(self, ndim):
        """
        initializes PID controller class with ndim dimensions
        make sure outFunc and readFunc take/return np.arrays of correct
        dimension
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
        Runs one step of the PID control for the given reading
        """
        t = time.time()
        dt = t - self._lasttime
        self._lasttime = t
        # add the error for averaging
        error = self.setpoint - reading
        # calculate integral, weighting is done here to
        # allow for easy mitigation of windup
        self._integral += self.parameters[1]*error*dt
        # windup supression
        ol = self.outLimit < np.absolute(self._integral)
        if any(ol):
            # set all values that are above/below self.outLimit to +-
            # self.outlimit
            self._integral[ol] = (self.ones[ol] *
                                  self.outLimit * np.sign(self._integral[ol]))
        if self.bipolar is False:
            ol = self._integral < 0
            if any(ol):
                # set all values that are below 0 to 0
                self._integral[ol] = self.ones[ol] * 0
        # calculate derivative and store previous error
        derivative = (error - self._previous_error)/dt
        self._previous_error = error
        # calculate output from parameters
        output = (self.parameters[0]*error +
                  self._integral +
                  self.parameters[2]*derivative)
        # limit control
        for i, elem in enumerate(output):
            if np.absolute(elem) > self.outLimit:
                output[i] = self.outLimit*np.sign(output[i])
            elif self.bipolar is False and elem < 0:
                output[i] = 0
        # return the new setpoint
        return output
