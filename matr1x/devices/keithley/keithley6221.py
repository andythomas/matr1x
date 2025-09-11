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
"""Module for controlling the Keithley 6221 Current Source."""

import time

from numpy import asarray, ceil
from wrapt import synchronized

from matr1x.devices.visadevice import VisaDevice


class Keithley6221(VisaDevice):
    """
    Keithley 6221 AC and DC Current Source interface.

    This class provides methods to control the Keithley 6221 current
    source for generating waveforms, arbitrary waveforms, constant
    currents, and performing delta and pulse delta measurements.
    """

    config_params = {"Model-identifing": "*IDN?"}

    def __init__(self, interface, **kwargs):
        """
        Initialize the Keithley 6221 device.

        Parameters
        ----------
        interface : str
            VISA resource name for the instrument
        **kwargs : dict
            Additional parameters to pass to the VISA driver.
            Defaults for write_termination, read_termination, and timeout
            are provided if not specified.
        """
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r\n"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 100000
        super().__init__(interface, **kwargs)

    @synchronized
    def generateWave(
        self,
        function="sinusoid",
        dutyCycle=None,
        amplitude=None,
        offset=None,
        frequency=None,
        rangingMode=None,
        durationTime=None,
        durationCycles=None,
        compliance=None,
        reset=True,
    ):
        """
        Generate a waveform signal and launch it.

        Parameters
        ----------
        function : str, optional
            Type of wavelet to generate: 'sinusoid', 'square', 'ramp'.
            Default is 'sinusoid'.
        dutyCycle : float, optional
            Percentage (0-100) of the amplitude that will be high.
            The remaining percentage will be low.
        amplitude : float, optional
            Amplitude of the wavelet in amps. Range: 2e-12 to 0.105.
        offset : float, optional
            Offset of the wavelet in amps. Range: -0.105 to 0.105.
        frequency : float, optional
            Frequency of the wavelet in Hz. Range: 0 to 1e5.
        rangingMode : str, optional
            Measurement range selection mode:
            'best': automatically select the best range for the wavelet
            'fixed': use the current range for the wavelet
        durationTime : float, optional
            Duration of wavelet emission in seconds.
            Range: 100e-9 to 999999.999, or -1 for infinity.
        durationCycles : float, optional
            Number of cycles to emit the wavelet.
            Range: 0.001 to 99999999900, or -1 for infinity.
        compliance : float, optional
            Compliance level in volts. Range: 0.1 to 105.
        reset : bool, optional
            Whether to reset the device before configuring the wave.
            Default is True.

        Returns
        -------
        None
        """
        # reset
        if reset is True:
            cmdlist = ["*RST"]
        else:
            cmdlist = []

        # compliance
        if compliance is not None:
            cmdlist.append("SOUR:CURR:COMP " + str(compliance))
        # waveform
        if function == "sinusoid":
            cmdlist.append("SOUR:WAVE:FUNC SIN")
        elif function == "square":
            cmdlist.append("SOUR:WAVE:FUNC SQU")
        elif function == "ramp":
            cmdlist.append("SOUR:WAVE:FUNC RAMP")
        # duty cycle
        if dutyCycle is not None:
            cmdlist.append("SOUR:WAVE:DCYC " + str(dutyCycle))
        # amplitude
        if amplitude is not None:
            cmdlist.append("SOUR:WAVE:AMPL " + str(amplitude))
        # offset
        if offset is not None:
            cmdlist.append("SOUR:WAVE:OFFS " + str(offset))
        # frequency
        if frequency is not None:
            cmdlist.append("SOUR:WAVE:FREQ " + str(frequency))
        # ranging mode
        if rangingMode == "best":
            cmdlist.append("SOUR:WAVE:RANG BEST")
        elif rangingMode == "fixed":
            cmdlist.append("SOUR:WAVE:RANG FIX")
        # duration
        if durationTime is not None:
            if durationTime == -1:
                cmdlist.append("SOUR:WAVE:DUR:TIME INF")
            else:
                cmdlist.append("SOUR:WAVE:DUR:TIME " + str(durationTime))
        if durationCycles is not None:
            if durationCycles == -1:
                cmdlist.append("SOUR:WAVE:DUR:CYCL INF")
            else:
                cmdlist.append("SOUR:WAVE:DUR:CYCL " + str(durationCycles))
        cmdlist.append("SOUR:WAVE:ARM")

        # output
        for cmd in cmdlist:
            self.write(cmd)

    @synchronized
    def generateArbWave(
        self,
        points=None,
        amplitude=None,
        frequency=None,
        offset=None,
        dutyCycle=None,
        rangingMode=None,
        durationTime=None,
        durationCycles=None,
        compliance=None,
        reset=True,
    ):
        """
        Generate an arbitrary waveform and launch it.

        Note: This function has not been fully tested.

        Parameters
        ----------
        points : array_like, optional
            List of points that the current source should set.
            Values must be between -1 and 1. Maximum length is 65535.
        amplitude : float, optional
            Amplitude of the wavelet in amps. Range: 2e-12 to 0.105.
        frequency : float, optional
            Frequency of the wavelet in Hz. Range: 0 to 1e5.
        offset : float, optional
            Offset of the wavelet in amps. Range: -0.105 to 0.105.
        dutyCycle : float, optional
            Duty cycle for the waveform (if applicable).
        rangingMode : str, optional
            Measurement range selection mode:
            'best': automatically select the best range for the wavelet
            'fixed': use the current range for the wavelet
        durationTime : float, optional
            Duration of wavelet emission in seconds.
            Range: 100e-9 to 999999.999, or -1 for infinity.
        durationCycles : float, optional
            Number of cycles to emit the wavelet.
            Range: 0.001 to 99999999900, or -1 for infinity.
        compliance : float, optional
            Compliance level in volts. Range: 0.1 to 105.
        reset : bool, optional
            Whether to reset the device before configuring the wave.
            Default is True.

        Returns
        -------
        None

        Raises
        ------
        ValueError
            If the points list has fewer than 2 elements or more than 65535 elements.
        """
        # reset
        if reset is True:
            cmdlist = ["*RST"]
        else:
            cmdlist = []

        # compliance
        if compliance is not None:
            cmdlist.append("SOUR:CURR:COMP " + str(compliance))
        # points
        if points is not None:
            if len(points) < 2:
                raise ValueError("List of points has insufficient length")
            elif len(points) > 65535:
                raise ValueError("List of points is too long")
            # convert floats to string
            points = [str(point) for point in points]
            cmdlist.append(f"SOUR:WAVE:ARB:DATA {', '.join(points[:100])}")
            nappend = ceil(len(points) / 100)
            if nappend > 1:
                for i in range(1, nappend):
                    cmdlist.append(
                        f"SOUR:WAVE:ARB:APP {','.join(points[i * 100 : (i + 1) * 100])}"
                    )
            # allows to save the wave in the persistent memory
            # cmdlist.append("SOUR:WAVE:ARB:COPY 1")
        cmdlist.append("SOUR:WAVE:FUNC ARB0")
        # amplitude
        if amplitude is not None:
            cmdlist.append("SOUR:WAVE:AMPL " + str(amplitude))
        # offset
        if offset is not None:
            cmdlist.append("SOUR:WAVE:OFFS " + str(offset))
        # frequency
        if frequency is not None:
            cmdlist.append("SOUR:WAVE:FREQ " + str(frequency))
        # ranging mode
        if rangingMode == "best":
            cmdlist.append("SOUR:WAVE:RANG BEST")
        elif rangingMode == "fixed":
            cmdlist.append("SOUR:WAVE:RANG FIX")
        # duration
        if durationTime is not None:
            cmdlist.append("SOUR:WAVE:DUR:TIME " + str(durationTime))
        elif durationTime == -1:
            cmdlist.append("SOUR:WAVE:DUR:TIME INF")
        if durationCycles is not None:
            cmdlist.append("SOUR:WAVE:DUR:CYCL " + str(durationCycles))
        elif durationCycles == -1:
            cmdlist.append("SOUR:WAVE:DUR:CYCL INF")

        # output
        for cmd in cmdlist:
            self.write(cmd)

    @synchronized
    def generateConstant(
        self,
        amplitude=None,
        autoRanging=None,
        sourceRange=None,
        compliance=None,
        reset=True,
    ):
        """
        Set a constant current output.

        Parameters
        ----------
        amplitude : float, optional
            Current amplitude in amps. Range: -0.105 to 0.105.
        autoRanging : bool, optional
            Whether to enable auto ranging. If True, the measurement range
            may change while performing measurements.
        sourceRange : float, optional
            The measurement range to use in amps. Range: -0.105 to 0.105.
            This determines the output current range that will be sourced.
        compliance : float, optional
            The compliance level in volts. Range: 0.1 to 105.
        reset : bool, optional
            Whether to reset the device before setting the current.
            Default is True.

        Returns
        -------
        None
        """
        # reset
        if reset is True:
            cmdlist = ["*RST"]
        else:
            cmdlist = []
        # amplitude
        if amplitude is not None:
            cmdlist.append("CURR " + str(amplitude))
        # range
        if sourceRange is not None:
            cmdlist.append("CURR:RANG " + str(sourceRange))
        # ranging mode
        if autoRanging is True:
            cmdlist.append("CURR:RANG:AUTO ON")
        elif autoRanging is False:
            cmdlist.append("CURR:RANG:AUTO OFF")
        # compliance
        if compliance is not None:
            cmdlist.append("CURR:COMP " + str(compliance))
        # output
        for cmd in cmdlist:
            self.write(cmd)

    @synchronized
    def generatePulseDelta(
        self,
        ihigh,
        ilow,
        width,
        sdel,
        count,
        rang,
        interval,
        compliance=10,
        sweep="OFF",
        lme=1,
        reset=False,
    ):
        """
        Initialize K6221 into pulse delta mode.

        Parameters
        ----------
        ihigh : float
            Peak pulse current in amps. Range: -0.105 to 0.105.
        ilow : float
            Low current (i.e., outside of pulse) in amps. Range: -0.105 to 0.105.
        width : float
            Pulse width in seconds. Range: 50us to 12ms.
        sdel : float
            Source delay in seconds.
        count : int
            Count of pulses.
        rang : str
            Range setting. Options are "BEST" or "FIX".
        interval : int
            Cycle time in PLCs. Range: 5 to 999999.
        sweep : str, optional
            Sweep mode. Options are "ON" or "OFF". Default is "OFF".
        compliance : float, optional
            Voltage compliance level in volts. Default is 10.
        lme : int, optional
            Number of low measurements (0 to 2). Default is 1.
        reset : bool, optional
            Whether to reset the device before configuring. Default is False.

        Returns
        -------
        None
        """
        if reset is True:
            cmdList = ["*RST"]
        else:
            cmdList = []
        cmdList.append(f"SOUR:PDEL:HIGH {ihigh}")
        cmdList.append(f"SOUR:PDEL:LOW {ilow}")
        cmdList.append(f"SOUR:PDEL:WIDT {width}")
        cmdList.append(f"SOUR:PDEL:SDEL {sdel}")
        cmdList.append(f"SOUR:PDEL:COUN {count}")
        cmdList.append(f"SOUR:PDEL:RANG {rang}")
        cmdList.append(f"SOUR:PDEL:INT {interval}")
        cmdList.append(f"SOUR:PDEL:SWE {sweep}")
        cmdList.append(f"SOUR:PDEL:LME {lme}")
        cmdList.append(f"SOUR:CURR:COMP {compliance}")
        cmdList.append(f"TRAC:POIN {count}")
        for cmd in cmdList:
            self.write(cmd)

    @synchronized
    def generateDelta(
        self, i, nplc, sdel, count, rang, compliance=10, comp_abort=True, reset=False
    ):
        """
        Initialize K6221 into delta mode.

        Parameters
        ----------
        i : float
            Peak pulse current in amps. Range: -0.105 to 0.105.
        nplc : int
            Resolution on 2182 (integer power line cycles).
        sdel : float
            Source delay in seconds.
        count : int
            Count of delta measurements.
        rang : str
            Range of nanovoltmeter in volts.
        compliance : float, optional
            Voltage compliance level in volts. Default is 10.
        comp_abort : bool, optional
            Whether to abort on compliance trigger. Default is True.
        reset : bool, optional
            Whether to reset the device before configuring. Default is False.

        Returns
        -------
        None
        """
        if reset is True:
            cmdList = ["*RST"]
        else:
            cmdList = []
        cmdList.append(f'SYST:COMM:SER:SEND "VOLT:RANG {rang}"')
        cmdList.append(f'SYST:COMM:SER:SEND "VOLT:NPLC {nplc}"')
        cmdList.append(f"SOUR:DELT:HIGH {i}")
        cmdList.append(f"SOUR:DELT:DEL {sdel}")
        cmdList.append(f"SOUR:DELT:COUN {count}")
        cmdList.append(f"SOUR:DELT:CAB {'ON' if comp_abort else 'OFF'}")
        cmdList.append(f"SOUR:CURR:COMP {compliance}")
        cmdList.append(f"TRAC:POIN {count}")
        for cmd in cmdList:
            self.write(cmd)

    @synchronized
    def pulseGo(self):
        """
        Arm pulse mode and run measurement, waiting for the result.

        Returns
        -------
        None
        """
        if 0 == int(self.query("SOUR:PDEL:ARM?")):
            self.write("SOUR:PDEL:ARM")
        self.write("INIT:IMM")
        self.query("*OPC?")

    @synchronized
    def deltaGo(self):
        """
        Arm delta mode and run measurement, waiting for the result.

        Returns
        -------
        None
        """
        if 0 == int(self.query("SOUR:DELT:ARM?")):
            self.write("SOUR:DELT:ARM")
            time.sleep(5)
        self.write("INIT:IMM")
        print(self.query("*OPC?"))

    def pulseStop(self):
        """
        Abort pulse mode.

        Returns
        -------
        None
        """
        self.write("SOUR:SWE:ABOR")

    def deltaStop(self):
        """
        Abort delta mode.

        Returns
        -------
        None
        """
        self.pulseStop()

    def fetchData(self, wait=True):
        """
        Get data trace and return as array.

        Parameters
        ----------
        wait : bool, optional
            Whether to wait for measurement completion. Default is True.

        Returns
        -------
        numpy.ndarray
            2D array containing the data trace.
        """
        # if wait is True:
        # while(not self.queryDone()):
        # time.sleep(0.1)
        ret = self.query("TRAC:DATA?")
        return asarray(ret.split(","), dtype="float64").reshape(-1, 2).T

    @synchronized
    def waveGo(self):
        """
        Initialize wave mode and turn on output.

        Returns
        -------
        None
        """
        self.write("SOUR:WAVE:ARM")
        self.write("SOUR:WAVE:INIT")

    def queryDone(self):
        """
        Check if measurement has finished.

        Returns
        -------
        bool
            True if measurement is complete, False otherwise.
        """
        register = int(self.query("STAT:OPER?"))
        return bool(register & (1 << 7))

    def queryCompliance(self):
        """
        Check if compliance limit has been reached.

        Returns
        -------
        bool
            True if compliance has been reached, False otherwise.
        """
        register = int(self.query("STAT:MEAS?"))
        return bool(register & (1 << 3))

    def constGo(self):
        """
        Turn on output for constant current.

        Returns
        -------
        None
        """
        self.write("OUTP ON")

    def setConstCurrent(self, current):
        """
        Set constant current output level.

        Parameters
        ----------
        current : float
            Current level in amps.

        Returns
        -------
        None
        """
        self.write("CURR " + str(current))

    def getConstCurrent(self):
        """
        Read current setting (no measurement readback).

        Returns
        -------
        float
            Current setting in amps.
        """
        return float(self.query("CURR?"))

    @synchronized
    def abort(self):
        """
        Abort the emission of the wavelet.

        Returns
        -------
        None
        """
        self.write("SOUR:WAVE:ABOR")
        self.write("OUTP OFF")
        self.write("ABOR")
