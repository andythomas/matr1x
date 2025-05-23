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
"""Interface module for the Keithley DMM6500 digital multimeter."""

import time

from wrapt import synchronized

from matr1x.devices.visadevice import VisaDevice


class KeithleyDMM6500(VisaDevice):
    """
    Class for controlling the Keithley DMM6500 multimeter.

    This class provides methods to configure and take measurements with the
    Keithley DMM6500 digital multimeter for voltage, 2-wire and 4-wire
    resistance measurements.

    Attributes
    ----------
    config_params : dict
        Dictionary of configuration parameters and their corresponding query commands.
    triggered : bool
        Flag indicating if a measurement has been triggered.
    """

    config_params = {
        "Mode": ":SENS:FUNC?",
        "VOLT:RANGE": "VOLT:RANG?",
        "VOLT:NPLC": ":SENS:VOLT:NPLC?",
        "Model-identifing": "*IDN?",
    }

    def __init__(self, interface, **kwargs):
        """
        Initialize the Keithley DMM6500 device.

        Parameters
        ----------
        interface : str
            VISA resource name for the instrument.
        **kwargs : dict
            Additional keyword arguments to pass to the VisaDevice constructor.
            If not specified, read_termination and write_termination are set to LF.
        """
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n"
        super().__init__(interface, **kwargs)
        self.triggered = False

    @synchronized
    def configure4WireOhm(
        self,
        digits=None,
        count=None,
        window=None,
        NPLC=None,
        dFil=None,
        rang=None,
        rangeAuto=None,
        trigBus=None,
        repeatingFilter=None,
        reset=False,
    ):
        """
        Configure the Keithley DMM6500 to measure 4-wire resistance.

        Parameters
        ----------
        digits : int, optional
            Number of digits to display (4-8).
        count : int, optional
            Filter count for the digital filter.
        window : float, optional
            Filter window for the digital filter.
        NPLC : int, optional
            Number of power line cycles to integrate over.
        dFil : bool, optional
            If True, turn on the digital filter. If False,
            window and filter count are ignored.
        rang : float, optional
            Range of the resistance measurement. Selected by the
            instrument to include the value of range.
        rangeAuto : bool, optional
            If True, enables automatic detection of the measurement range.
            Takes additional time during measurements.
        trigBus : bool, optional
            Does nothing. Kept for backward compatibility.
        repeatingFilter : bool, optional
            If True, set the filter to repeating. If False, set to moving.
        reset : bool, optional
            If True, the device is reset prior to configuration. Default is False.
        """
        if reset is True:
            cmdList = ["*RST"]
        else:
            cmdList = []
        # we want to measure 4-wire resistance
        cmdList.append(':SENS:FUNC "FRES"')
        if NPLC is not None:
            cmdList.append(":SENS:FRES:NPLC " + str(int(NPLC)))
        if digits is not None:
            cmdList.append(":SENS:FRES:DIG " + str(int(digits)))
        if rangeAuto is True:
            cmdList.append(":SENS:FRES:RANG:AUTO ON")
        elif rang is not None:
            cmdList.append(":SENS:FRES:RANG:AUTO OFF")
            cmdList.append(":SENS:FRES:RANG " + str(float(rang)))
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
        rang=None,
        rangeAuto=None,
        trigBus=None,
        repeatingFilter=None,
        reset=False,
    ):
        """
        Configure the Keithley DMM6500 to measure 2-wire resistance.

        Parameters
        ----------
        digits : int, optional
            Number of digits to display (4-8).
        count : int, optional
            Filter count for the digital filter.
        window : float, optional
            Filter window for the digital filter.
        NPLC : int, optional
            Number of power line cycles to integrate over.
        dFil : bool, optional
            If True, turn on the digital filter. If False,
            window and filter count are ignored.
        rang : float, optional
            Range of the resistance measurement. Selected by the
            instrument to include the value of range.
        rangeAuto : bool, optional
            If True, enables automatic detection of the measurement range.
            Takes additional time during measurements.
        trigBus : bool, optional
            Does nothing. Kept for backward compatibility.
        repeatingFilter : bool, optional
            If True, set the filter to repeating. If False, set to moving.
        reset : bool, optional
            If True, the device is reset prior to configuration. Default is False.
        """
        if reset is True:
            cmdList = ["*RST"]
        else:
            cmdList = []
        # we want to measure 2-wire resistance
        cmdList.append(':SENS:FUNC "RES"')
        if NPLC is not None:
            cmdList.append(":SENS:RES:NPLC " + str(int(NPLC)))
        if digits is not None:
            cmdList.append(":SENS:RES:DIG " + str(int(digits)))
        if rangeAuto is True:
            cmdList.append(":SENS:RES:RANG:AUTO ON")
        elif rang is not None:
            cmdList.append(":SENS:RES:RANG:AUTO OFF")
            cmdList.append(":SENS:RES:RANG " + str(float(rang)))
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
        rang=None,
        rangeAuto=None,
        trigBus=None,
        repeatingFilter=None,
        reset=False,
    ):
        """
        Configure the Keithley DMM6500 to measure DC voltage.

        Parameters
        ----------
        digits : int, optional
            Number of digits to display (4-8).
        count : int, optional
            Filter count for the digital filter.
        window : float, optional
            Filter window for the digital filter.
        NPLC : int, optional
            Number of power line cycles to integrate over.
        dFil : bool, optional
            If True, turn on the digital filter. If False,
            window and filter count are ignored.
        rang : float, optional
            Range of the voltage detection. Selected by the
            instrument to include the value of range.
        rangeAuto : bool, optional
            If True, enables automatic detection of the measurement range.
            Takes additional time during measurements.
        trigBus : bool, optional
            Does nothing. Kept for backward compatibility.
        repeatingFilter : bool, optional
            If True, set the filter to repeating. If False, set to moving.
        reset : bool, optional
            If True, the device is reset prior to configuration. Default is False.
        """
        cmdList = []
        if reset is True:
            self.write("*RST")
            time.sleep(0.05)
        # we want to measure DC volts
        cmdList.append(':SENS:FUNC "VOLT:DC"')
        if NPLC is not None:
            cmdList.append(":SENS:VOLT:NPLC " + str(float(NPLC)))
        if digits is not None:
            cmdList.append(":SENS:VOLT:DIG " + str(int(digits)))
        if rangeAuto is True:
            cmdList.append(":SENS:VOLT:RANG:AUTO ON")
        elif rang is not None:
            cmdList.append(":SENS:VOLT:RANG:AUTO OFF")
            cmdList.append(":SENS:VOLT:RANG " + str(float(rang)))
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
        for cmd in cmdList:
            self.write(cmd)

    def triggerReading(self):
        """
        Trigger a reading from the instrument.

        Sets the triggered flag to True to indicate a measurement is pending.
        """
        self.write("*TRG")
        self.triggered = True

    def getReading(self):
        """
        Get the reading from the instrument.

        Returns
        -------
        float
            The measured value if a reading has been triggered, otherwise None.

        Notes
        -----
        This method resets the triggered flag to False after reading.
        """
        if self.triggered is True:
            result = self.query(":READ?")
            self.triggered = False
            return float(result)
