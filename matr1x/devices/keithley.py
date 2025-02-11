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

import time

from numpy import asarray, ceil
from wrapt import synchronized

from .visadevice import VisaDevice


class Keithley2400(VisaDevice):
    config_params = {"sourceMode": "sourceMode", "senseMode": "senseMode"}

    def __init__(self, interface, **kwargs):
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n"
        super().__init__(interface, **kwargs)
        # after initialization get the source function to determine
        # whether voltage or current is the sourced
        self.write(":SOUR:FUNC?")
        self.sourceMode = self.read()
        self.write(":SENS:FUNC?")
        self.senseMode = self.read()
        self.write(":OUTP?")
        self.outputState = bool(int(self.read()))

    def read(self):
        return super().read().replace("\x13", "")

    # high level functions
    def configure(
        self,
        sourceMode=None,
        senseMode=None,
        fourWire=None,
        senseAutoRange=None,
        senseRange=None,
        sourceAutoRange=None,
        sourceRange=None,
        senseLimit=None,
        output=None,
        delayAuto=None,
        delay=None,
        reset=False,
    ):
        """
        Configure the Keithley 2400

        Arguments
        -----
        sourceMode : str
          "VOLT" or "CURR", predefined physical parameter
        senseMode : str
          "VOLT" or "CURR", measured parameter
        fourWire : bool
          Four wire measurement? Default: None (use current configuration)
        senseAutoRange : bool
          Autodetect the sense range? Default: None
        senseRange : float
          Largest expected measurement value, device will
          pick the next inclusive range. Default: None
        sourceAutoRange : bool
          Autodetect the source range? Default: None
        sourceRange : float
          Largest expected source current, device will
          pick the next inclusive range. Default: None
        senseLimit : float
          Voltage limit. Default: 10V
        output : bool
          Turn the output on? Default: None
        delayAuto : bool
          Automatically choose the delay for stabilizing
          the output? Default: None
        delay : float
          Delay in seconds for stabilizing the output before
          doing an internal measurement. WON'T AFFECT/DELAY
          OTHER DEVICES! Default: 0.1(s)
        reset : bool
          If true, reset the device

        Example
        -----
        .. code-block:: python

           .configure(sourceMode = "CURR", senseMode = "VOLT",
                      fourWire=True, senseAutoRange=True,
                      sourceRange=0.001, output=True)

        The output will initially be turned off during configuration.
        This will configure the Keithley to be in 4W sense mode,
        detect the sense range automatically. The range is chosen to
        include 1mA and the output is turned on.
        """
        # do nothing if source/sensemode is not defined
        if sourceMode is None or senseMode is None:
            return
        # assert source and sense mode are correct
        assert (sourceMode == "VOLT" and senseMode == "CURR") or (sourceMode == "CURR" and senseMode == "VOLT"), (
            'source ("' + sourceMode + '") and/or sense ("' +
            senseMode + '") mode are incorrect'
        )
        # add get output here to reset the device to the previous state
        # if none is given
        # if self.outputState != bool(output):
        self.output(False)
        # sourceMode will now be current
        self.sourceMode = sourceMode
        self.senseMode = senseMode

        if reset is True:
            cmdlist = ["*RST"]
        else:
            cmdlist = []
        # we want sourceIsenseV
        cmdlist.append(f":SOUR:FUNC {sourceMode}")
        cmdlist.append(f':SENS:FUNC "{senseMode}"')

        # check vs manual
        if delayAuto is True:
            cmdlist.append(":SOUR:" + sourceMode + ":DEL:AUTO ON")
        elif delay is not None:
            cmdlist.append(":SOUR:" + sourceMode + ":DEL:AUTO OFF")
            cmdlist.append(":SOUR:" + sourceMode + ":DEL " + str(float(delay)))

        if fourWire is True:
            cmdlist.append(":SYST:RSEN ON")  # Model 2400: SYST:RSEN ON/OFF
        elif fourWire is False:
            cmdlist.append(":SYST:RSEN OFF")

        if senseAutoRange is True:
            cmdlist.append(":SENS:" + senseMode + ":RANG:AUTO ON")
        elif senseRange is not None:
            cmdlist.append(":SENS:" + senseMode + ":RANG:AUTO OFF")
            cmdlist.append(":SENS:" + senseMode +
                           ":RANG " + str(float(senseRange)))

        if sourceAutoRange is True:
            cmdlist.append(":SOUR:" + sourceMode + ":RANG:AUTO ON")
        elif sourceRange is not None:
            cmdlist.append(":SOUR:" + sourceMode + ":RANG:AUTO OFF")
            cmdlist.append(":SOUR:" + sourceMode +
                           ":RANG " + str(float(sourceRange)))

        if senseLimit is not None:
            cmdlist.append(":SENS:" + senseMode +
                           ":PROT:LEV " + str(float(senseLimit)))

        for cmd in cmdlist:
            self.write(cmd)
        # if self.outputState != bool(output):
        self.output(output)

    def output(self, state=False):
        if bool(state) is True:
            self.write(":OUTP:STAT ON")
            self.outputState = True
        elif bool(state) is False:
            self.write(":OUTP:STAT OFF")
            self.outputState = False

    def setSource(self, current):
        cmd = ":SOUR:" + self.sourceMode + ":LEV " + str(current)
        self.write(cmd)

    def getSource(self):
        self.write("READ?")
        return float(self.read().split(",")[1])

    def getSense(self):
        self.write("READ?")
        res = self.read().split(",")[0]
        return float(res)


class Keithley2450(VisaDevice):
    config_params = {"sourceMode": "sourceMode", "senseMode": "senseMode"}

    def __init__(self, interface, **kwargs):
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n"
        super().__init__(interface, **kwargs)
        # ignore telnet commands sent by the instrument
        try:
            self.read(9)
        except Exception:
            pass
        # after initialization get the source function to determine
        # whether voltage or current is the sourced
        self.write(":SOUR:FUNC?")
        self.sourceMode = self.read()
        self.write(":SENS:FUNC?")
        self.senseMode = self.read()
        self.write(":OUTP?")
        self.outputState = bool(int(self.read()))

    # high level functions
    @synchronized
    def configure(
        self,
        sourceMode=None,
        senseMode=None,
        fourWire=None,
        senseAutoRange=None,
        senseRange=None,
        sourceAutoRange=None,
        sourceRange=None,
        senseLimit=None,
        output=None,
        delayAuto=None,
        delay=None,
        resetUnits=True,
        reset=False,
    ):
        """
        Configure the Keithley 2450 to source current and sense voltage

        Arguments
        -----
        sourceMode : str
          "VOLT" or "CURR", predefined physical parameter
        senseMode : str
          "VOLT" or "CURR", measured parameter
        fourWire : bool
          Four wire measurement? Default: None (use current configuration)
        senseAutoRange : bool
          Autodetect the sense range? Default: None
        senseRange : float
          Largest expected measurement value, device will
          pick the next inclusive range. Default: None
        sourceAutoRange : bool
          Autodetect the source range? Default: None
        sourceRange : float
          Largest expected source current, device will
          pick the next inclusive range. Default: None
        senseLimit : float
          Voltage limit. Default: None
        output : bool
          Turn the output on? Default: None
        delayAuto : bool
          Automatically choose the delay for stabilizing
          the output? Default: None
        delay : float
          Delay in seconds for stabilizing the output before
          doing an internal measurement. WON'T AFFECT/DELAY
          OTHER DEVICES! Default: 0.1(s)
        resetUnits: bool
          If true, Ampere and Volt are restored as default unit for
          current and voltage measurements.
        reset : bool
          If true, reset the device

        Example
        -----
        .. code-block:: python

           .configureSourceISenseV(fourWire=True, senseAutoRange=True,
                                   sourceRange=0.001, output=True)

        The output will initially be turned off during configuration.
        This will configure the Keithley to be in 4W sense mode,
        detect the sense range automatically. The range is chosen to
        include 1mA and the output is turned on.
        """
        # do nothing if source/sensemode is not defined
        if sourceMode is None or senseMode is None:
            return
        # assert source and sense mode are correct
        assert (sourceMode == "VOLT" and senseMode == "CURR") or (sourceMode == "CURR" and senseMode == "VOLT"), (
            'source ("' + sourceMode + '") and/or sense ("' +
            senseMode + '") mode are incorrect'
        )
        limDef = {"CURR": "I", "VOLT": "V"}
        # add get output here to reset the device to the previous state
        # if none is given
        self.output(False)
        # sourceMode will now be sourceMode
        self.sourceMode = sourceMode
        self.senseMode = senseMode
        if reset is True:
            cmdlist = ["*RST"]
        else:
            cmdlist = []
        # we want sourceIsenseV
        cmdlist.append(":SOUR:FUNC {}".format(self.sourceMode))
        cmdlist.append(':SENS:FUNC "{}"'.format(self.senseMode))
        # reset units to amp/volt to avoid unintentional reading of\
        # resistance
        if resetUnits:
            cmdlist.append(":SENS:CURR:UNIT AMP")
            cmdlist.append(":SENS:VOLT:UNIT VOLT")
        # turn on the readback so we get the actual value and not the setpoint
        cmdlist.append(":SOUR:{}:READ:BACK ON".format(self.sourceMode))

        if senseLimit is not None:
            cmdlist.append(":SOUR:{}:{}LIM {}".format(
                self.sourceMode, limDef[self.senseMode], float(senseLimit)))
        if delayAuto is True:
            cmdlist.append(":SOUR:{}:DEL:AUTO ON".format(self.sourceMode))
        elif delay is not None:
            cmdlist.append(":SOUR:{}:DEL:AUTO OFF".format(self.sourceMode))
            cmdlist.append(":SOUR:{}:DEL {}".format(
                self.sourceMode, float(delay)))

        if fourWire is True:
            cmdlist.append(":SENS:{}:RSEN ON".format(self.senseMode))
        elif fourWire is False:
            cmdlist.append(":SENS:{}:RSEN OFF".format(self.senseMode))

        if senseAutoRange is True:
            cmdlist.append(":SENS:{}:RANG:AUTO ON".format(self.senseMode))
        elif senseRange is not None:
            cmdlist.append(":SENS:{}:RANG:AUTO OFF".format(self.senseMode))
            cmdlist.append(":SENS:{}:RANG {}".format(
                self.senseMode, float(senseRange)))

        if sourceAutoRange is True:
            cmdlist.append(":SOUR:{}:RANG:AUTO ON".format(self.sourceMode))
        elif sourceRange is not None:
            cmdlist.append(":SOUR:{}:RANG:AUTO OFF".format(self.sourceMode))
            cmdlist.append(":SOUR:{}:RANG {}".format(
                self.sourceMode, float(sourceRange)))

        for cmd in cmdlist:
            self.write(cmd)
        self.output(output)

    def output(self, state=False):
        if state is True:
            self.write(":OUTP ON")
            self.outputState = True
        elif state is False:
            self.write(":OUTP OFF")
            self.outputState = False

    def setSource(self, current):
        cmd = ":SOUR:" + self.sourceMode + " " + str(current)
        self.write(cmd)

    def getSource(self):
        return float(self.query('READ? "defbuffer1", SOUR'))

    def getSense(self):
        return float(self.query("READ?"))


class Keithley2611A(VisaDevice):
    config_params = {
        "sourceMode": "print(smua.source.func)",
        "senseMode": "print(smua.sense)",
        "voltageLimit": "print(smua.source.limitv)",
        "currentLimit": "print(smua.source.limiti)",
        "Model-identifing": "*IDN?",
    }
    mode_int = {"VOLT": 1, "CURR": 0}
    mode_char = {"VOLT": "v", "CURR": "i"}

    def __init__(self, interface, **kwargs):
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\n\r"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n\r"
        super().__init__(interface, **kwargs)
        # ignore telnet commands sent by the instrument
        try:
            self.read(9)
        except Exception:
            pass
        # after initialization get the source function to determine
        # whether voltage or current is the sourced
        # get the sourceMode 0 -> OUTPUT_DCAMPS (sourceCurrent)
        # 1 -> OUTPUT_DCAMPS (sourceVoltage)
        self.write("print(smua.source.func)")
        # can't directly pars the value to int
        self.sourceModeInt = int(float(self.read()))
        # get fourWire 0 -> senseMode local (2wire)
        # 1 -> senseMode remote (4wire)
        self.write("print(smua.sense)")
        # can't directly pars the output to bool
        self.fourWire = bool(float(self.read()))
        # get output status
        self.write("print(smua.source.func)")
        # can't directly pars the value to int
        self.outputState = int(float(self.read()))

    # high level functions
    @synchronized
    def configure(
        self,
        sourceMode=None,
        senseMode=None,
        fourWire=None,
        senseAutoRange=None,
        senseRange=None,
        sourceAutoRange=None,
        sourceRange=None,
        senseLimit=None,
        output=None,
        delayAuto=None,
        delay=None,
        reset=False,
    ):
        """
        Configure the Keithley 2611A to source current and sense voltage

        Arguments
        -----
        sourceMode: "VOLT" or "CURR" -- predefined physical parameter
        senseMode: "VOLT" or "CURR" -- measured parameter
        fourWire:bool -- Four wire measurement? Default: None (use
                                current configuration)
        senseAutoRange:bool -- Autodetect the sense range? Default: None
        senseRange:float -- Largest expected measurement value, device will
                                pick the next inclusive range. Default: None
        sourceAutoRange:bool -- Autodetect the source range? Default:
                                       None
        sourceRange:float -- Largest expected source current, device will
                                 pick the next inclusive range. Default: None
        senseLimit:float -- Voltage/Current limit.
        output:bool -- Turn the output on? Default: None
        delayAuto:bool -- Automatically choose the delay for stabilizing
                                 the output? Default: None
        delay:float -- Delay in seconds for stabilizing the output before
                           doing an internal measurement. WON'T AFFECT/DELAY
                           OTHER DEVICES! Default: 0.1(s)
        reset:bool -- If true, reset the device

        Example
        -----
        .. code-block:: python

           .configure(sourceMode="CURR", senseMode="VOLT",
                      fourWire=True, senseAutoRange=True,
                      sourceRange=0.001, output=True)

        The output will initially be turned off during configuration.
        This will configure the Keithley to be in 4W sense mode,
        detect the sense range automatically. The range is chosen to
        include 1mA and the output is turned on.
        """
        # do nothing if source/sensemode is not defined
        if sourceMode is None or senseMode is None:
            return
        # assert source and sense mode are correct
        assert (sourceMode == "VOLT" and senseMode == "CURR") or (sourceMode == "CURR" and senseMode == "VOLT"), (
            'source ("' + sourceMode + '") and/or sense ("' +
            senseMode + '") mode are incorrect'
        )
        # add get output here to reset the device to the previous state
        # if none is given
        self.output(False)
        # sourceMode will now be sourceMode
        self.sourceMode = sourceMode
        self.senseMode = senseMode

        if reset is True:
            cmdlist = ["smua.reset()"]
        else:
            cmdlist = []
        # we want sourceIsenseV
        cmdlist.append(f"smua.source.func={self.mode_int[self.sourceMode]}")
        # cmdlist.append(":SENS:FUNC \"{}\"".format(self.senseMode))
        # check if the last line is necessary for the new smu
        # turn on the readback so we get the actual value and not the setpoint
        # cmdlist.append(":SOUR:{}:READ:BACK ON".format(self.sourceMode))

        if senseLimit is not None:
            cmdlist.append(
                f"smua.source.limit{self.mode_char[self.senseMode]}={float(senseLimit)}")

        if fourWire is True:
            cmdlist.append("smua.sense=smua.SENSE_REMOTE")
        elif fourWire is False:
            cmdlist.append("smua.sense=smua.SENSE_LOCAL")

        if senseAutoRange is True:
            cmdlist.append(
                f"smua.measure.autorange{self.mode_char[self.senseMode]}=smua.AUTORANGE_ON")
        elif senseRange is not None:
            cmdlist.append(
                f"smua.measure.autorange{self.mode_char[self.senseMode]}=smua.AUTORANGE_OFF")
            cmdlist.append(
                f"smua.measure.range{self.mode_char[self.senseMode]}={float(senseRange)}")

        if sourceAutoRange is True:
            cmdlist.append(
                f"smua.source.autorange{self.mode_char[self.sourceMode]}=smua.AUTORANGE_ON")
        elif sourceRange is not None:
            cmdlist.append(
                f"smua.source.autorange{self.mode_char[self.sourceMode]}=smua.AUTORANGE_OFF")
            cmdlist.append(
                f"smua.source.range{self.mode_char[self.sourceMode]}={float(sourceRange)}")

        if delayAuto is True:
            cmdlist.append("smua.source.delay = smua.DELAY_AUTO")
        elif delay is not None:
            cmdlist.append(f"smua.source.delay = {float(delay)}")
        elif delay is False:
            cmdlist.append("smua.source.delay = smua.DELAY_OFF")

        for cmd in cmdlist:
            self.write(cmd)
        self.output(output)

    def output(self, state=False):
        if state is True:
            self.write("smua.source.output=smua.OUTPUT_ON")
        elif state is False:
            self.write("smua.source.output=smua.OUTPUT_OFF")

    def setSource(self, current):
        cmd = f"smua.source.level{self.mode_char[self.sourceMode]}={float(current)}"
        self.write(cmd)

    def getSource(self):
        return float(self.query(f"print(smua.measure.{self.mode_char[self.sourceMode]}(smua.nvbuffer1))"))

    def getSense(self):
        return float(self.query(f"print(smua.measure.{self.mode_char[self.senseMode]}(smua.nvbuffer1))"))


class Keithley2182A(VisaDevice):
    config_params = {
        "Mode": ":SENS:FUNC?",
        "VOLT:RANGE": ":SENS:VOLT:RANG?",
        "VOLT:NPLC": ":SENS:VOLT:NPLC?",
        "VOLT:DFIL:COUNT": ":SENS:VOLT:DFIL:COUN?",
    }

    def __init__(self, interface, **kwargs):
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 50000
        super().__init__(interface, **kwargs)
        self.triggered = False

        tstore = self.connection.timeout
        self.connection.timeout = 1
        time.sleep(1)
        try:
            self.read(20)
        except Exception:
            pass
        self.connection.timeout = tstore

    # high level functions
    @synchronized
    def configure(
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
        Configure the Keitley K2182 to detect voltages.

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
            If true, turn on the digital filter. If False, window and filter count are ignored
        voltage_range : float, optional
            Range of the voltage detection. Selected by the instrument to include the value
        rangeAuto : bool, optional
            Automatic detection of the measurement range. Takes additional time during measurements
        trigBus : bool, optional
            Sets trigger source to BUS if true
        repeatingFilter : bool, optional
            If true set the filter to repeating, if false to moving
        reset : bool, optional
            If true, the device is reset prior to configuration (default False)
        """
        cmdList = []
        if reset is True:
            self.write("*RST")
            time.sleep(0.05)
        # we want to measure volts
        cmdList.append(':SENS:FUNC "VOLT"')
        if NPLC is not None:
            cmdList.append(f":SENS:VOLT:NPLC {float(NPLC):f}")
        if digits is not None:
            cmdList.append(f":SENS:VOLT:DIG {int(digits):d}")
        if rangeAuto is True:
            cmdList.append(":SENS:VOLT:RANG:AUTO ON")
        elif voltage_range is not None:
            cmdList.append(":SENS:VOLT:RANG:AUTO OFF")
            cmdList.append(f":SENS:VOLT:RANG {float(voltage_range):f}")
        if dFil is True:
            cmdList.append(":SENS:VOLT:DFIL:STATE ON")
            if window is not None:
                cmdList.append(f":SENS:VOLT:DFIL:WIND {float(window):f}")
            if count is not None:
                cmdList.append(f":SENS:VOLT:DFIL:COUN {int(count):d}")
            if repeatingFilter is True:
                cmdList.append(":SENS:VOLT:DFIL:TCON REP")
            elif repeatingFilter is False:
                cmdList.append(":SENS:VOLT:DFIL:TCON MOV")
        elif dFil is False:
            cmdList.append(":SENS:VOLT:DFIL:STATE OFF")
        if trigBus is True:
            cmdList.append(":ABOR")
            # Only triggered reading
            cmdList.append(":INIT:CONT OFF")
            cmdList.append(":TRIG:SOUR BUS")
            cmdList.append(":TRIG:COUN INF")
            cmdList.append(":INIT")
        for cmd in cmdList:
            self.write(cmd)
        time.sleep(0.2)

    def triggerReading(self):
        if self.triggered is False:
            self.write("*TRG")
            self.triggered = True

    def getReading(self):
        if self.triggered is True:
            result = self.query(":SENS:DATA:FRES?")
            self.triggered = False
            return float(result)


class Keithley2701(VisaDevice):
    config_params = {"Mode": ":SENS:FUNC?", "VOLT:RANGE": ":SENS:VOLT:RANG?",
                     "VOLT:NPLC": ":SENS:VOLT:NPLC?", "Model-identifing": "*IDN?"}

    def __init__(self, interface, **kwargs):
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
        """Configure the Keithley 2701 to detect 4-wire resistance.

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
        """Configure the Keitley 2701 to detect 2-wire resistance.

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
            If true, turn on the digital filter. If False window and filter count are ignored
        resistance_range : float, optional
            Range of the voltage detection. Selected by the instrument to include the value
        rangeAuto : bool, optional
            Automatic detection of the measurement range. Takes additional time during measurements
        trigBus : bool, optional
            Sets trigger source to BUS if true
        repeatingFilter : bool, optional
            If true set the filter to repeating, if false to moving
        reset : bool, optional
            If true, the device is reset prior to configuration (default False)
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
        Configure the Keitley 2701 to detect voltages.

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
            If true, turn on the digital filter. If False window and filter count are ignored
        voltage_range : float, optional
            Range of the voltage detection. Selected by the instrument to include the value
        rangeAuto : bool, optional
            Automatic detection of the measurement range. Takes additional time during measurements
        trigBus : bool, optional
            Sets trigger source to BUS if true
        repeatingFilter : bool, optional
            If true set the filter to repeating, if false to moving
        reset : bool, optional
            If true, the device is reset prior to configuration (default False)
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
        self.write("*TRG")
        self.triggered = True

    def getReading(self):
        if self.triggered is True:
            self.write(":SENS:DATA:FRES?")
            result = self.read().replace("\x13", "")
            self.triggered = False
            return float(result)


class Keithley2000(VisaDevice):
    config_params = {"Mode": ":SENS:FUNC?", "VOLT:RANGE": ":SENS:VOLT:RANG?",
                     "VOLT:NPLC": ":SENS:VOLT:NPLC?", "Model-identifing": "*IDN?"}

    def __init__(self, interface, **kwargs):
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 10000
        super().__init__(interface, **kwargs)
        self.triggered = False

        try:  # First query after open usually does not work
            self.query(":SENS:FUNC?")
        except UnicodeDecodeError:
            try:
                # to be sure that all in the input buffer is gone, with
                # the individual RS232-Ethernet adapter it happend that
                # some leftover of old communication messed up things.
                self.read_very_eager()
            except Exception:
                pass

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
        """Configure the Keithley 2000 to detect 4-wire resistance.

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
            If True, turn on the digital filter. If False, window and
            filter count are ignored
        resistance_range : float, optional
            Range of the voltage detection. Selected by the instrument
            to include the value of range
        rangeAuto : bool, optional
            Automatic detection of the measurement range. Takes additional
            time during measurements
        trigBus : bool, optional
            Sets trigger source to BUS if True
        repeatingFilter : bool, optional
            If True set the filter to repeating, if False to moving
        reset : bool, optional
            If True, the device is reset prior to configuration (default False)
        """
        if reset is True:
            cmdList = ["*RST"]
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
        """Configure the Keitley 2000 to detect 2-wire resistance.

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
            If true, turn on the digital filter. If False window and filter count are ignored
        resistance_range : float, optional
            Range of the voltage detection. Selected by the instrument to include the value
        rangeAuto : bool, optional
            Automatic detection of the measurement range. Takes additional time during measurements
        trigBus : bool, optional
            Sets trigger source to BUS if true
        repeatingFilter : bool, optional
            If true set the filter to repeating, if false to moving
        reset : bool, optional
            If true, the device is reset prior to configuration (default False)
        """
        if reset is True:
            cmdList = ["*RST"]
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
        """Configure the Keithley 2000 to detect voltages.

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
            If True, turn on the digital filter. If False, window and filter count are ignored.
        voltage_range : float, optional
            Range of the voltage detection. Selected by the instrument to include the value.
        rangeAuto : bool, optional
            Automatic detection of the measurement range. Takes additional time during measurements.
        trigBus : bool, optional
            Sets trigger source to BUS if True.
        repeatingFilter : bool, optional
            If True set the filter to repeating, if False to moving.
        reset : bool, optional
            If True, the device is reset prior to configuration. Defaults to False.
        """
        cmdList = []
        if reset is True:
            self.write("*RST")
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
        self.write("*TRG")
        self.triggered = True

    def getReading(self):
        if self.triggered is True:
            result = self.query(":SENS:DATA:FRES?")
            result = result.replace("\x13", "")
            self.triggered = False
            return float(result)


class Keithley6221(VisaDevice):
    config_params = {"Model-identifing": "*IDN?"}

    def __init__(self, interface, **kwargs):
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
        Generates a waveform signal and launches it

        Arguments
        -----
        function:[sinusoid,square,ramp]
          select the type of the wavelet: sinusoid, square, ramp
        dutyCycle:float[0:100]
          choose how much (percent, 0-100) of the amplitude is going
          to be high line (the other percent are going to be low)
        amplitude:float[2e-12:0.105]
          set the amplitude (amps) of the wavelet
        offset:float[-0.105:0,105]
          set the offset (amps) of the wavelet
        frequency:float[0:1e5]
          set the frequency (Hz) of the wavelet
        rangingMode:[best,fixed]
          best: automatically choose the best
            measurement range for the given wavelet
          fixed: do not change measurement range
            when generating the wavelet
        durationTime:float[100e-9:999999.999,-1]
          defines how long (seconds) the wavelet is going to be
          emitted. -1 = infinity
        durationCycles:float[0.001:99999999900]
          sets the number of cycles how long the wavelet is
          going to be emitted. -1=infinity
        compliance:float[0.1:105]
          sets the compliance in volts
        reset:bool
          should the device be resetted before waving?
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
        !!function not tested!!

        Generates a arbitrary waveform and launch it

        Arguments
        -----
        points: float array
          list of points that the current source should set (-1 to 1,
          maximum length is 65535)
        amplitude:float[2e-12:0.105]
          set the amplitude (amps) of the wavelet
        offset:float[-0.105:0,105]
          set the offset (amps) of the wavelet
        frequency:float[0:1e5]
          set the frequency (Hz) of the wavelet
        rangingMode:[best,fixed]
          best: automatically choose the best measurement range
            for the given wavelet
          fixed: do not change measurement range when generating the
            wavelet
        durationTime:float[100e-9:999999.999,-1]
          defines how long (seconds) the wavelet is going to be
          emitted. -1 = infinity
        durationCycles:float[0.001:99999999900]
          sets the number of cycles how long the wavelet is
          going to be emitted. -1=infinity
        compliance:float[0.1:105]
          sets the compliance??? in volts
        reset:boolean
          should the device be reset before waving?
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
                        f"SOUR:WAVE:ARB:APP {','.join(points[i*100:(i+1)*100])}")
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
    def generateConstant(self, amplitude=None, autoRanging=None, sourceRange=None, compliance=None, reset=True):
        """
        Sets a constant current

        Arguments:
        -----
        amplitude:float[-0.105:0.105]
          set the amplitude (amps) of the wavelet
        autoRanging:boolean
          sets the auto ranging mode to on or off. On might
          change the measurement range while performing
        sourceRange:[-0.105:0.105]
          sets the measurement range. You can simply choose the
          output current that is going to be sourced.
        compliance:[0.1:105]
          sets the compliance level
        reset:boolean
          should the device be resetted before currenting?
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
    def generatePulseDelta(self, ihigh, ilow, width, sdel, count, rang, interval, compliance=10, sweep="OFF", lme=1, reset=False):
        """
        Initializes K6221 into pulse delta mode

        Arguments:
        -----
        ihigh:float[-0.105:0.105]
          peak pulse current in A
        ilow:float[-0.105:0.105]
          low current (i.e. outside of pulse) in A
        width:float
          pulse width (50us to 12ms) in s
        sdel:float
          source delay in s
        count:int
          count of pulses
        rang:str
          range ("BEST" or "FIX")
        interval:int
          cycle time (5 to 999999) in PLCs
        sweep:str
          "ON" or "OFF"
        compliance:float
          voltage compliance
        lme:int
          number of low measurements (0 to 2)
        reset:bool
          resets the device before configuring the sequence
        """
        if reset is True:
            cmdList = ["*RST"]
        else:
            cmdList = []
        cmdList.append("SOUR:PDEL:HIGH {}".format(ihigh))
        cmdList.append("SOUR:PDEL:LOW {}".format(ilow))
        cmdList.append("SOUR:PDEL:WIDT {}".format(width))
        cmdList.append("SOUR:PDEL:SDEL {}".format(sdel))
        cmdList.append("SOUR:PDEL:COUN {}".format(count))
        cmdList.append("SOUR:PDEL:RANG {}".format(rang))
        cmdList.append("SOUR:PDEL:INT {}".format(interval))
        cmdList.append("SOUR:PDEL:SWE {}".format(sweep))
        cmdList.append("SOUR:PDEL:LME {}".format(lme))
        cmdList.append("SOUR:CURR:COMP {}".format(compliance))
        cmdList.append("TRAC:POIN {}".format(count))
        for cmd in cmdList:
            self.write(cmd)

    @synchronized
    def generateDelta(self, i, nplc, sdel, count, rang,
                      compliance=10, comp_abort=True,
                      reset=False):
        """
        Initializes K6221 into pulse delta mode

        Arguments:
        -----
        i:float[-0.105:0.105]
          peak pulse current in A
        nplc:int
          resolution on 2182 (integer PLC)
        sdel:float
          source delay in s
        count:int
          count of delta measurements
        rang:str
          range of nanovoltmeter in V
        compliance:float
          voltage compliance
        comp_abort:bool
          abort on compliance triggered
        reset:bool
          resets the device before configuring the sequence
        """
        if reset is True:
            cmdList = ["*RST"]
        else:
            cmdList = []
        cmdList.append("SYST:COMM:SER:SEND \"VOLT:RANG {}\"".format(rang))
        cmdList.append("SYST:COMM:SER:SEND \"VOLT:NPLC {}\"".format(nplc))
        cmdList.append("SOUR:DELT:HIGH {}".format(i))
        cmdList.append("SOUR:DELT:DEL {}".format(sdel))
        cmdList.append("SOUR:DELT:COUN {}".format(count))
        cmdList.append(
            "SOUR:DELT:CAB {}".format("ON" if comp_abort else "OFF"))
        cmdList.append("SOUR:CURR:COMP {}".format(compliance))
        cmdList.append("TRAC:POIN {}".format(count))
        for cmd in cmdList:
            self.write(cmd)

    @synchronized
    def pulseGo(self):
        """
        arm pulse mode and run measurement, waiting for the result
        """
        if 0 == int(self.query("SOUR:PDEL:ARM?")):
            self.write("SOUR:PDEL:ARM")
        self.write("INIT:IMM")
        self.query("*OPC?")

    @synchronized
    def deltaGo(self):
        """
        arm pulse mode and run measurement, waiting for the result
        """
        if 0 == int(self.query("SOUR:DELT:ARM?")):
            self.write("SOUR:DELT:ARM")
            time.sleep(5)
        self.write("INIT:IMM")
        print(self.query("*OPC?"))

    def pulseStop(self):
        """abort pulse mode"""
        self.write("SOUR:SWE:ABOR")

    def deltaStop(self):
        """ abort delta mode """
        self.pulseStop()

    def fetchData(self, wait=True):
        """get data trace and return as array"""
        # if wait is True:
        # while(not self.queryDone()):
        # time.sleep(0.1)
        ret = self.query("TRAC:DATA?")
        return asarray(ret.split(","), dtype='float64').reshape(-1, 2).T

    @synchronized
    def waveGo(self):
        """initialize wave mode and turn on output"""
        self.write("SOUR:WAVE:ARM")
        self.write("SOUR:WAVE:INIT")

    def queryDone(self):
        """check measurement finished"""
        register = int(self.query("STAT:OPER?"))
        return bool(register & (1 << 7))

    def queryCompliance(self):
        """check compliance reached"""
        register = int(self.query("STAT:MEAS?"))
        return bool(register & (1 << 3))

    def constGo(self):
        """turn on output for constant current"""
        self.write("OUTP ON")

    def setConstCurrent(self, current):
        """set constant current"""
        self.write("CURR " + str(current))

    def getConstCurrent(self):
        """read current setting (no readback!)"""
        return float(self.query("CURR?"))

    @synchronized
    def abort(self):
        """
        aborts the emission of the wavelet
        """
        self.write("SOUR:WAVE:ABOR")
        self.write("OUTP OFF")
        self.write("ABOR")
