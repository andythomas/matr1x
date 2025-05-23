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
Module for Keithley 2701 multimeter control.

This module provides an interface to the Keithley 2701 multimeter for precise measurements
of resistance, voltage, and other electrical parameters through VISA communication.
"""
import time

from wrapt import synchronized

from matr1x.devices.visadevice import VisaDevice


class Keithley2701(VisaDevice):
    """
    Interface for the Keithley 2701 multimeter.

    This class provides methods to configure and control the Keithley 2701
    for various measurement types including resistance and voltage.

    Attributes
    ----------
    config_params : dict
        Dictionary of configuration parameters and their corresponding commands
    triggered : bool
        Flag indicating if a measurement has been triggered
    """

    config_params = {
        "Mode": ":SENS:FUNC?",
        "VOLT:RANGE": ":SENS:VOLT:RANG?",
        "VOLT:NPLC": ":SENS:VOLT:NPLC?",
        "Model-identifing": "*IDN?",
    }

    def __init__(self, interface, **kwargs):
        """
        Initialize the Keithley 2701 device.

        Parameters
        ----------
        interface : str
            VISA resource name for the instrument
        **kwargs : dict
            Additional parameters for VISA communication

        Notes
        -----
        Default settings include:
        - write_termination = LF
        - read_termination = LF
        - timeout = 10000 ms
        """
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 10000
        super().__init__(interface, **kwargs)
        self.triggered = False
        self.write(":FORM:ELEM READ")

    # high level functions
    @synchronized
    def configure4WireOhm(
        self,
        digits=None,
        count=None,
        window=None,
        NPLC=None,
        dFil=None,
        resistance_range=None,
        rangeAuto=None,
        trigBus=None,
        repeatingFilter=None,
        reset=False,
    ):
        """
        Configure the Keithley 2701 to detect 4-wire resistance.

        Parameters
        ----------
        digits : int, optional
            Number of digits to display (4-8)
        count : int, optional
            Filter count for the digital filter
        window : float, optional
            Filter window for the digital filter
        NPLC : int, optional
            Number of power line cycles to integrate over
        dFil : bool, optional
            If True, turn on the digital filter. If False window and filter count are ignored
        resistance_range : float, optional
            Range of the resistance detection. Selected by the instrument to include the value
        rangeAuto : bool, optional
            Automatic detection of the measurement range. Takes additional time during measurements
        trigBus : bool, optional
            Sets trigger source to BUS if True
        repeatingFilter : bool, optional
            If True set the filter to repeating, if False to moving
        reset : bool, optional
            If True, the device is reset prior to configuration (default False)

        Returns
        -------
        None
        """
        if reset is True:
            cmdList = ["*RST"]
            cmdList.append(":FORM:ELEM READ")
        else:
            cmdList = []
        # we want to measure volts
        cmdList.append(':SENS:FUNC "FRES"')
        if NPLC is not None:
            cmdList.append(":SENS:FRES:NPLC " + str(int(NPLC)))
        if digits is not None:
            cmdList.append(":SENS:FRES:DIG " + str(int(digits)))
        if rangeAuto is True:
            cmdList.append(":SENS:FRES:RANG:AUTO ON")
        elif resistance_range is not None:
            cmdList.append(":SENS:FRES:RANG:AUTO OFF")
            cmdList.append(":SENS:FRES:RANG " + str(float(resistance_range)))
        if dFil is True:
            cmdList.append(":SENS:FRES:AVER:STATE ON")
            if count is not None:
                cmdList.append(":SENS:FRES:AVER:COUN " + str(int(count)))
            if repeatingFilter is True:
                cmdList.append(":SENS:FRES:AVER:TCON REP")
            elif repeatingFilter is False:
                cmdList.append(":SENS:FRES:AVER:TCON MOV")
        elif dFil is False:
            cmdList.append(":SENS:FRES:AVER:STATE OFF")
        cmdList.append(":INIT:CONT OFF")  # Only triggered reading
        if trigBus is True:
            cmdList.append(":ABOR")
            cmdList.append(":INIT:CONT OFF")  # Only triggered reading
            cmdList.append(":TRIG:SOUR BUS")
            cmdList.append(":TRIG:COUN INF")
            cmdList.append(":INIT")
        for cmd in cmdList:
            self.write(cmd)

    @synchronized
    def configure2WireOhm(
        self,
        digits=None,
        count=None,
        window=None,
        NPLC=None,
        dFil=None,
        resistance_range=None,
        rangeAuto=None,
        trigBus=None,
        repeatingFilter=None,
        reset=False,
    ):
        """
        Configure the Keithley 2701 to detect 2-wire resistance.

        Parameters
        ----------
        digits : int, optional
            Number of digits to display (4-8)
        count : int, optional
            Filter count for the digital filter
        window : float, optional
            Filter window for the digital filter
        NPLC : int, optional
            Number of power line cycles to integrate over
        dFil : bool, optional
            If True, turn on the digital filter. If False window and filter count are ignored
        resistance_range : float, optional
            Range of the resistance detection. Selected by the instrument to include the value
        rangeAuto : bool, optional
            Automatic detection of the measurement range. Takes additional time during measurements
        trigBus : bool, optional
            Sets trigger source to BUS if True
        repeatingFilter : bool, optional
            If True set the filter to repeating, if False to moving
        reset : bool, optional
            If True, the device is reset prior to configuration (default False)

        Returns
        -------
        None
        """
        if reset is True:
            cmdList = ["*RST"]
            cmdList.append(":FORM:ELEM READ")
        else:
            cmdList = []
        # we want to measure volts
        cmdList.append(':SENS:FUNC "RES"')
        if NPLC is not None:
            cmdList.append(":SENS:RES:NPLC " + str(int(NPLC)))
        if digits is not None:
            cmdList.append(":SENS:RES:DIG " + str(int(digits)))
        if rangeAuto is True:
            cmdList.append(":SENS:RES:RANG:AUTO ON")
        elif resistance_range is not None:
            cmdList.append(":SENS:RES:RANG:AUTO OFF")
            cmdList.append(":SENS:RES:RANG " + str(float(resistance_range)))
        if dFil is True:
            cmdList.append(":SENS:RES:AVER:STATE ON")
            if count is not None:
                cmdList.append(":SENS:RES:AVER:COUN " + str(int(count)))
            if repeatingFilter is True:
                cmdList.append(":SENS:RES:AVER:TCON REP")
            elif repeatingFilter is False:
                cmdList.append(":SENS:RES:AVER:TCON MOV")
        elif dFil is False:
            cmdList.append(":SENS:RES:AVER:STATE OFF")
        cmdList.append(":INIT:CONT OFF")  # Only triggered reading
        if trigBus is True:
            cmdList.append(":ABOR")
            cmdList.append(":INIT:CONT OFF")  # Only triggered reading
            cmdList.append(":TRIG:SOUR BUS")
            cmdList.append(":TRIG:COUN INF")
            cmdList.append(":INIT")
        for cmd in cmdList:
            self.write(cmd)

    @synchronized
    def configureVolt(
        self,
        digits=None,
        count=None,
        window=None,
        NPLC=None,
        dFil=None,
        voltage_range=None,
        rangeAuto=None,
        trigBus=None,
        repeatingFilter=None,
        reset=False,
    ):
        """
        Configure the Keithley 2701 to detect voltages.

        Parameters
        ----------
        digits : int, optional
            Number of digits to display (4-8)
        count : int, optional
            Filter count for the digital filter
        window : float, optional
            Filter window for the digital filter
        NPLC : int, optional
            Number of power line cycles to integrate over
        dFil : bool, optional
            If True, turn on the digital filter. If False window and filter count are ignored
        voltage_range : float, optional
            Range of the voltage detection. Selected by the instrument to include the value
        rangeAuto : bool, optional
            Automatic detection of the measurement range. Takes additional time during measurements
        trigBus : bool, optional
            Sets trigger source to BUS if True
        repeatingFilter : bool, optional
            If True set the filter to repeating, if False to moving
        reset : bool, optional
            If True, the device is reset prior to configuration (default False)

        Returns
        -------
        None
        """
        cmdList = []
        if reset is True:
            self.write("*RST")
            cmdList.append(":FORM:ELEM READ")
            time.sleep(0.05)
        # we want to measure volts
        cmdList.append(':SENS:FUNC "VOLT:DC"')
        if NPLC is not None:
            cmdList.append(":SENS:VOLT:NPLC " + str(float(NPLC)))
        if digits is not None:
            cmdList.append(":SENS:VOLT:DIG " + str(int(digits)))
        if rangeAuto is True:
            cmdList.append(":SENS:VOLT:RANG:AUTO ON")
        elif voltage_range is not None:
            cmdList.append(":SENS:VOLT:RANG:AUTO OFF")
            cmdList.append(":SENS:VOLT:RANG " + str(float(voltage_range)))
        if dFil is True:
            cmdList.append(":SENS:VOLT:AVER:STATE ON")
            if count is not None:
                cmdList.append(":SENS:VOLT:AVER:COUN " + str(int(count)))
            if repeatingFilter is True:
                cmdList.append(":SENS:VOLT:AVER:TCON REP")
            elif repeatingFilter is False:
                cmdList.append(":SENS:VOLT:AVER:TCON MOV")
        elif dFil is False:
            cmdList.append(":SENS:VOLT:AVER:STATE OFF")
        if trigBus is True:
            cmdList.append(":ABOR")
            cmdList.append(":INIT:CONT OFF")  # Only triggered reading
            cmdList.append(":TRIG:SOUR BUS")
            cmdList.append(":TRIG:COUN INF")
            cmdList.append(":INIT")
        for cmd in cmdList:
            self.write(cmd)

    def triggerReading(self):
        """
        Trigger a measurement reading from the device.

        This method sends the trigger command to the device and
        sets the triggered flag to True.

        Returns
        -------
        None
        """
        self.write("*TRG")
        self.triggered = True

    def getReading(self):
        """
        Get a reading from the device if it has been triggered.

        This method retrieves the measurement data from the device,
        clears the triggered flag, and returns the result as a float.

        Returns
        -------
        float
            The measured value from the device

        Notes
        -----
        This method only works if triggerReading() has been called previously.
        """
        if self.triggered is True:
            self.write(":SENS:DATA:FRES?")
            result = self.read().replace("\x13", "")
            self.triggered = False
            return float(result)
