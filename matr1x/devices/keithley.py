import time

from wrapt import synchronized

from .visadevice import VisaDevice


class Keithley2400(VisaDevice):
    config_params = {"sourceMode": "sourceMode",
                     "senseMode": "senseMode"}

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
        self.outputState = bool(self.read())

    def read(self):
        return super().read().replace("\x13", "")

    # high level functions
    def configure(self, sourceMode=None, senseMode=None, fourWire=None,
                  senseAutoRange=None, senseRange=None, sourceAutoRange=None,
                  sourceRange=None, senseLimit=None, output=None,
                  delayAuto=None, delay=None, reset=False):
        """
        Configure the Keithley 2400

        Arguments
        -----
        sourceMode : str
          "VOLT" or "CURR", predefined physical parameter
        senseMode : str
          "VOLT" or "CURR", measured parameter
        fourWire : boolean
          Four wire measurement? Default: None (use current configuration)
        senseAutoRange : boolean
          Autodetect the sense range? Default: None
        senseRange : float
          Largest expected measurement value, device will
          pick the next inclusive range. Default: None
        sourceAutoRange : boolean
          Autodetect the source range? Default: None
        sourceRange : float
          Largest expected source current, device will
          pick the next inclusive range. Default: None
        senseLimit : float
          Voltage limit. Default: 10V
        output : boolean
          Turn the output on? Default: None
        delayAuto : boolean
          Automatically choose the delay for stabilizing
          the output? Default: None
        delay : float
          Delay in seconds for stabilizing the output before
          doing an internal measurement. WON'T AFFECT/DELAY
          OTHER DEVICES! Default: 0.1(s)
        reset : boolean
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
        assert ((sourceMode == "VOLT" and senseMode == "CURR") or
                (sourceMode == "CURR" and senseMode == "VOLT")), \
               ("source (\"" + sourceMode + "\") and/or sense (\"" +
                senseMode + "\") mode are incorrect")
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
        cmdlist.append(":SOUR:FUNC "+sourceMode)
        cmdlist.append(":SENS:FUNC \""+senseMode+"\"")

        # check vs manual
        if delayAuto is True:
            cmdlist.append(":SOUR:"+sourceMode+":DEL:AUTO ON")
        elif delay is not None:
            cmdlist.append(":SOUR:"+sourceMode+":DEL:AUTO OFF")
            cmdlist.append(":SOUR:"+sourceMode+":DEL " + str(float(delay)))

        if fourWire is True:
            cmdlist.append(":SYST:RSEN ON")  # Model 2400: SYST:RSEN ON/OFF
        elif fourWire is False:
            cmdlist.append(":SYST:RSEN OFF")

        if senseAutoRange is True:
            cmdlist.append(":SENS:"+senseMode+":RANG:AUTO ON")
        elif senseRange is not None:
            cmdlist.append(":SENS:"+senseMode+":RANG:AUTO OFF")
            cmdlist.append(":SENS:"+senseMode+":RANG " +
                           str(float(senseRange)))

        if sourceAutoRange is True:
            cmdlist.append(":SOUR:"+sourceMode+":RANG:AUTO ON")
        elif sourceRange is not None:
            cmdlist.append(":SOUR:"+sourceMode+":RANG:AUTO OFF")
            cmdlist.append(":SOUR:"+sourceMode+":RANG " +
                           str(float(sourceRange)))

        if senseLimit is not None:
            cmdlist.append(":SENS:"+senseMode+":PROT:LEV " +
                           str(float(senseLimit)))

        for cmd in cmdlist:
            self.write(cmd)
        # if self.outputState != bool(output):
        self.output(output)

    def output(self, state=False):
        if bool(state) is True:
            self.write(":OUTP:STAT ON")
        elif bool(state) is False:
            self.write(":OUTP:STAT OFF")

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
    config_params = {"sourceMode": "sourceMode",
                     "senseMode": "senseMode"}

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
        self.outputState = bool(self.read())

    # high level functions
    @synchronized
    def configure(self, sourceMode=None, senseMode=None, fourWire=None,
                  senseAutoRange=None, senseRange=None, sourceAutoRange=None,
                  sourceRange=None, senseLimit=None, output=None,
                  delayAuto=None, delay=None, reset=False):
        """
        Configure the Keithley 2450 to source current and sense voltage

        Arguments
        ------
        sourceMode: "VOLT" or "CURR" -- predefined physical parameter
        senseMode: "VOLT" or "CURR" -- measured parameter
        fourWire:boolean -- Four wire measurement? Default: None (use
                                current configuration)
        senseAutoRange:boolean -- Autodetect the sense range? Default: None
        senseRange:float -- Largest expected measurement value, device will
                                pick the next inclusive range. Default: None
        sourceAutoRange:boolean -- Autodetect the source range? Default:
                                       None
        sourceRange:float -- Largest expected source current, device will
                                 pick the next inclusive range. Default: None
        senseLimit:float -- Voltage/Current limit.
        output:boolean -- Turn the output on? Default: None
        delayAuto:boolean -- Automatically choose the delay for stabilizing
                                 the output? Default: None
        delay:float -- Delay in seconds for stabilizing the output before
                           doing an internal measurement. WON'T AFFECT/DELAY
                           OTHER DEVICES! Default: 0.1(s)
        reset:boolean -- If true, reset the device

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
        assert ((sourceMode == "VOLT" and senseMode == "CURR") or
                (sourceMode == "CURR" and senseMode == "VOLT")), \
               ("source (\"" + sourceMode + "\") and/or sense (\"" +
                senseMode + "\") mode are incorrect")
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
        cmdlist.append(":SENS:FUNC \"{}\"".format(self.senseMode))
        # turn on the readback so we get the actual value and not the setpoint
        cmdlist.append(":SOUR:{}:READ:BACK ON".format(self.sourceMode))

        if senseLimit is not None:
            cmdlist.append(":SOUR:{}:{}LIM {}".format(self.sourceMode,
                                                      limDef[self.senseMode],
                                                      float(senseLimit)))
        if delayAuto is True:
            cmdlist.append(":SOUR:{}:DEL:AUTO ON".format(self.sourceMode))
        elif delay is not None:
            cmdlist.append(":SOUR:{}:DEL:AUTO OFF".format(self.sourceMode))
            cmdlist.append(":SOUR:{}:DEL {}".format(self.sourceMode,
                                                    float(delay)))

        if fourWire is True:
            cmdlist.append(":SENS:{}:RSEN ON".format(self.senseMode))
        elif fourWire is False:
            cmdlist.append(":SENS:{}:RSEN OFF".format(self.senseMode))

        if senseAutoRange is True:
            cmdlist.append(":SENS:{}:RANG:AUTO ON".format(self.senseMode))
        elif senseRange is not None:
            cmdlist.append(":SENS:{}:RANG:AUTO OFF".format(self.senseMode))
            cmdlist.append(":SENS:{}:RANG {}".format(self.senseMode,
                                                     float(senseRange)))

        if sourceAutoRange is True:
            cmdlist.append(":SOUR:{}:RANG:AUTO ON".format(self.sourceMode))
        elif sourceRange is not None:
            cmdlist.append(":SOUR:{}:RANG:AUTO OFF".format(self.sourceMode))
            cmdlist.append(":SOUR:{}:RANG {}".format(self.sourceMode,
                                                     float(sourceRange)))

        for cmd in cmdlist:
            self.write(cmd)
        self.output(output)

    def output(self, state=False):
        if state is True:
            self.write(":OUTP ON")
        elif state is False:
            self.write(":OUTP OFF")

    def setSource(self, current):
        cmd = ":SOUR:" + self.sourceMode + " " + str(current)
        self.write(cmd)

    def getSource(self):
        return float(self.query("READ? \"defbuffer1\", SOUR"))

    def getSense(self):
        return float(self.query("READ?"))


class Keithley2611A(VisaDevice):
    config_params = {"sourceMode": "print(smua.source.func)",
                     "senseMode": "print(smua.sense)",
                     "voltageLimit": "print(smua.source.limitv)",
                     "currentLimit": "print(smua.source.limiti)",
                     "Model-identifing": "*IDN?"}
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
    def configure(self, sourceMode=None, senseMode=None, fourWire=None,
                  senseAutoRange=None, senseRange=None, sourceAutoRange=None,
                  sourceRange=None, senseLimit=None, output=None,
                  delayAuto=None, delay=None, reset=False):
        """
        Configure the Keithley 2611A to source current and sense voltage

        Arguments
        -----
        sourceMode: "VOLT" or "CURR" -- predefined physical parameter
        senseMode: "VOLT" or "CURR" -- measured parameter
        fourWire:boolean -- Four wire measurement? Default: None (use
                                current configuration)
        senseAutoRange:boolean -- Autodetect the sense range? Default: None
        senseRange:float -- Largest expected measurement value, device will
                                pick the next inclusive range. Default: None
        sourceAutoRange:boolean -- Autodetect the source range? Default:
                                       None
        sourceRange:float -- Largest expected source current, device will
                                 pick the next inclusive range. Default: None
        senseLimit:float -- Voltage/Current limit.
        output:boolean -- Turn the output on? Default: None
        delayAuto:boolean -- Automatically choose the delay for stabilizing
                                 the output? Default: None
        delay:float -- Delay in seconds for stabilizing the output before
                           doing an internal measurement. WON'T AFFECT/DELAY
                           OTHER DEVICES! Default: 0.1(s)
        reset:boolean -- If true, reset the device

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
        assert ((sourceMode == "VOLT" and senseMode == "CURR") or
                (sourceMode == "CURR" and senseMode == "VOLT")), \
               ("source (\"" + sourceMode + "\") and/or sense (\"" +
                senseMode + "\") mode are incorrect")
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
    config_params = {"Mode": ":SENS:FUNC?",
                     "VOLT:RANGE": ":SENS:VOLT:RANG?",
                     "VOLT:NPLC": ":SENS:VOLT:NPLC?",
                     "VOLT:DFIL:COUNT": ":SENS:VOLT:DFIL:COUN?"}

    def __init__(self, interface, **kwargs):
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 10000
        super().__init__(interface, **kwargs)
        self.triggered = False

        tstore = self.VISAdev.timeout
        self.VISAdev.timeout = 1
        time.sleep(1)
        try:
            self.read(20)
        except Exception:
            pass
        self.VISAdev.timeout = tstore

    # high level functions
    @synchronized
    def configure(self, digits=None, count=None, window=None, NPLC=None,
                  dFil=None, range=None, rangeAuto=None, trigBus=None,
                  repeatingFilter=None, reset=False):
        """
        Configure the Keitley K2182 to detect voltages

        Arguments:
            digits:int -- number of digits to display (4-8). default: None
            count:int -- filter count for the digital filter. default: None
            window:float -- filter window for the digital filter, default: None
            NPLC:int -- Number of power line cycles to integrate over.
                        default: None
            dFil:boolean -- If true, turn on the digital filter. If False
                            window and filter count are ignored- default: None
            repeatingFilter:boolean -- If true set the filter to repeating,
                                       If false to moving - default: None
            range:float -- Range of the voltage detection. Selected by the
                           instrument to include the value of range.
                           default: None
            rangeAuto:boolean -- Automatic detection of the measurement range
                                 Take care, takes additional time during
                                 measurements! default: None
            trigBus:boolean -- sets trigger source to BUS if true
            reset:boolean -- if true, the device is reset prior to
                             configuration, default: False
        """
        cmdList = []
        if reset is True:
            self.write("*RST")
            time.sleep(0.05)
        # we want to measure volts
        cmdList.append(":SENS:FUNC \"VOLT\"")
        if NPLC is not None:
            cmdList.append(":SENS:VOLT:NPLC " + str(float(NPLC)))
        if digits is not None:
            cmdList.append(":SENS:VOLT:DIG " + str(int(digits)))
        if rangeAuto is True:
            cmdList.append(":SENS:VOLT:RANG:AUTO ON")
        elif range is not None:
            cmdList.append(":SENS:VOLT:RANG:AUTO OFF")
            cmdList.append(":SENS:VOLT:RANG " + str(float(range)))
        if dFil is True:
            cmdList.append(":SENS:VOLT:DFIL:STATE ON")
            if window is not None:
                cmdList.append(":SENS:VOLT:DFIL:WIND " + str(float(window)))
            if count is not None:
                cmdList.append(":SENS:VOLT:DFIL:COUN " + str(int(count)))
            if repeatingFilter is True:
                cmdList.append(":SENS:VOLT:DFIL:TCON REP")
            elif repeatingFilter is False:
                cmdList.append(":SENS:VOLT:DFIL:TCON MOV")
        elif dFil is False:
            cmdList.append(":SENS:VOLT:DFIL:STATE OFF")
        if trigBus is True:
            cmdList.append(":ABOR")
            cmdList.append(":INIT:CONT OFF")  # Only triggered reading
            cmdList.append(":TRIG:SOUR BUS")
            cmdList.append(":TRIG:COUN INF")
            cmdList.append(":INIT")
        for cmd in cmdList:
            self.write(cmd)
        time.sleep(1)

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
    config_params = {"Mode": ":SENS:FUNC?",
                     "VOLT:RANGE": ":SENS:VOLT:RANG?",
                     "VOLT:NPLC": ":SENS:VOLT:NPLC?",
                     "Model-identifing": "*IDN?"}

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
    def configure4WireOhm(self, digits=None, count=None, window=None,
                          NPLC=None, dFil=None, range=None, rangeAuto=None,
                          trigBus=None, repeatingFilter=None, reset=False):
        """
        Configure the Keitley 2701 to detect 4wire resistance

        Arguments:
            digits:int -- number of digits to display (4-8). default: None
            count:int -- filter count for the digital filter. default: None
            window:float -- filter window for the digital filter, default: None
            NPLC:int -- Number of power line cycles to integrate over.
                        default: None
            dFil:boolean -- If true, turn on the digital filter. If False
                            window and filter count are ignored- default: None
            repeatingFilter:boolean -- If true set the filter to repeating,
                                       If false to moving - default: None
            range:float -- Range of the voltage detection. Selected by the
                           instrument to include the value of range.
                           default: None
            rangeAuto:boolean -- Automatic detection of the measurement range
                                 Take care, takes additional time during
                                 measurements! default: None
            trigBus:boolean -- sets trigger source to BUS if true
            reset:boolean -- if true, the device is reset prior to
                             configuration, default: False
        """
        if reset is True:
            cmdList = ["*RST"]
            cmdList.append(":FORM:ELEM READ")
        else:
            cmdList = []
        # we want to measure volts
        cmdList.append(":SENS:FUNC \"FRES\"")
        if NPLC is not None:
            cmdList.append(":SENS:FRES:NPLC " + str(int(NPLC)))
        if digits is not None:
            cmdList.append(":SENS:FRES:DIG " + str(int(digits)))
        if rangeAuto is True:
            cmdList.append(":SENS:FRES:RANG:AUTO ON")
        elif range is not None:
            cmdList.append(":SENS:FRES:RANG:AUTO OFF")
            cmdList.append(":SENS:FRES:RANG " + str(float(range)))
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
    def configure2WireOhm(self, digits=None, count=None, window=None,
                          NPLC=None, dFil=None, range=None, rangeAuto=None,
                          trigBus=None, repeatingFilter=None, reset=False):
        """
        Configure the Keitley 2701 to detect 2wire resistance

        Arguments:
            digits:int -- number of digits to display (4-8). default: None
            count:int -- filter count for the digital filter. default: None
            window:float -- filter window for the digital filter, default: None
            NPLC:int -- Number of power line cycles to integrate over.
                        default: None
            dFil:boolean -- If true, turn on the digital filter. If False
                            window and filter count are ignored- default: None
            repeatingFilter:boolean -- If true set the filter to repeating,
                                       If false to moving - default: None
            range:float -- Range of the voltage detection. Selected by the
                           instrument to include the value of range.
                           default: None
            rangeAuto:boolean -- Automatic detection of the measurement range
                                 Take care, takes additional time during
                                 measurements! default: None
            trigBus:boolean -- sets trigger source to BUS if true
            reset:boolean -- if true, the device is reset prior to
                             configuration
                             default: False
        """
        if reset is True:
            cmdList = ["*RST"]
            cmdList.append(":FORM:ELEM READ")
        else:
            cmdList = []
        # we want to measure volts
        cmdList.append(":SENS:FUNC \"RES\"")
        if NPLC is not None:
            cmdList.append(":SENS:RES:NPLC " + str(int(NPLC)))
        if digits is not None:
            cmdList.append(":SENS:RES:DIG " + str(int(digits)))
        if rangeAuto is True:
            cmdList.append(":SENS:RES:RANG:AUTO ON")
        elif range is not None:
            cmdList.append(":SENS:RES:RANG:AUTO OFF")
            cmdList.append(":SENS:RES:RANG " + str(float(range)))
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
    def configureVolt(self, digits=None, count=None, window=None, NPLC=None,
                      dFil=None, range=None, rangeAuto=None, trigBus=None,
                      repeatingFilter=None, reset=False):
        """
        Configure the Keitley 2701 to detect voltages

        Arguments:
            digits:int -- number of digits to display (4-8). default: None
            count:int -- filter count for the digital filter. default: None
            window:float -- filter window for the digital filter, default: None
            NPLC:int -- Number of power line cycles to integrate over.
                        default: None
            dFil:boolean -- If true, turn on the digital filter. If False
                            window and filter count are ignored- default: None
            repeatingFilter:boolean -- If true set the filter to repeating,
                                       If false to moving - default: None
            range:float -- Range of the voltage detection. Selected by the
                           instrument to include the value of range.
                           default: None
            rangeAuto:boolean -- Automatic detection of the measurement range
                                 Take care, takes additional time during
                                 measurements! default: None
            trigBus:boolean -- sets trigger source to BUS if true
            reset:boolean -- if true, the device is reset prior to
                             configuration, default: False
        """
        cmdList = []
        if reset is True:
            self.write("*RST")
            cmdList.append(":FORM:ELEM READ")
            time.sleep(0.05)
        # we want to measure volts
        cmdList.append(":SENS:FUNC \"VOLT:DC\"")
        if NPLC is not None:
            cmdList.append(":SENS:VOLT:NPLC " + str(float(NPLC)))
        if digits is not None:
            cmdList.append(":SENS:VOLT:DIG " + str(int(digits)))
        if rangeAuto is True:
            cmdList.append(":SENS:VOLT:RANG:AUTO ON")
        elif range is not None:
            cmdList.append(":SENS:VOLT:RANG:AUTO OFF")
            cmdList.append(":SENS:VOLT:RANG " + str(float(range)))
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
            result = self.read().replace('\x13', '')
            self.triggered = False
            return float(result)


class Keithley2000(VisaDevice):
    config_params = {"Mode": ":SENS:FUNC?",
                     "VOLT:RANGE": ":SENS:VOLT:RANG?",
                     "VOLT:NPLC": ":SENS:VOLT:NPLC?",
                     "Model-identifing": "*IDN?"}

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
            pass

    @synchronized
    def configure4WireOhm(self, digits=None, count=None, window=None,
                          NPLC=None, dFil=None, range=None, rangeAuto=None,
                          trigBus=None, repeatingFilter=None, reset=False):
        """
        Configure the Keitley 2000 to detect 4wire resistance

        Arguments:
            digits:int -- number of digits to display (4-8). default: None
            count:int -- filter count for the digital filter. default: None
            window:float -- filter window for the digital filter, default: None
            NPLC:int -- Number of power line cycles to integrate over.
                        default: None
            dFil:boolean -- If true, turn on the digital filter. If False
                            window and filter count are ignored- default: None
            repeatingFilter:boolean -- If true set the filter to repeating,
                                       If false to moving - default: None
            range:float -- Range of the voltage detection. Selected by the
                           instrument to include the value of range.
                           default: None
            rangeAuto:boolean -- Automatic detection of the measurement range
                                 Take care, takes additional time during
                                 measurements! default: None
            trigBus:boolean -- sets trigger source to BUS if true
            reset:boolean -- if true, the device is reset prior to
                             configuration, default: False
        """
        if reset is True:
            cmdList = ["*RST"]
        else:
            cmdList = []
        # we want to measure volts
        cmdList.append(":SENS:FUNC \"FRES\"")
        if NPLC is not None:
            cmdList.append(":SENS:FRES:NPLC " + str(int(NPLC)))
        if digits is not None:
            cmdList.append(":SENS:FRES:DIG " + str(int(digits)))
        if rangeAuto is True:
            cmdList.append(":SENS:FRES:RANG:AUTO ON")
        elif range is not None:
            cmdList.append(":SENS:FRES:RANG:AUTO OFF")
            cmdList.append(":SENS:FRES:RANG " + str(float(range)))
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
    def configure2WireOhm(self, digits=None, count=None, window=None,
                          NPLC=None, dFil=None, range=None, rangeAuto=None,
                          trigBus=None, repeatingFilter=None, reset=False):
        """
        Configure the Keitley 2000 to detect 2wire resistance

        Arguments:
            digits:int -- number of digits to display (4-8). default: None
            count:int -- filter count for the digital filter. default: None
            window:float -- filter window for the digital filter, default: None
            NPLC:int -- Number of power line cycles to integrate over.
                        default: None
            dFil:boolean -- If true, turn on the digital filter. If False
                            window and filter count are ignored- default: None
            repeatingFilter:boolean -- If true set the filter to repeating,
                                       If false to moving - default: None
            range:float -- Range of the voltage detection. Selected by the
                           instrument to include the value of range.
                           default: None
            rangeAuto:boolean -- Automatic detection of the measurement range
                                 Take care, takes additional time during
                                 measurements! default: None
            trigBus:boolean -- sets trigger source to BUS if true
            reset:boolean -- if true, the device is reset prior to
                             configuration
                             default: False
        """
        if reset is True:
            cmdList = ["*RST"]
        else:
            cmdList = []
        # we want to measure volts
        cmdList.append(":SENS:FUNC \"RES\"")
        if NPLC is not None:
            cmdList.append(":SENS:RES:NPLC " + str(int(NPLC)))
        if digits is not None:
            cmdList.append(":SENS:RES:DIG " + str(int(digits)))
        if rangeAuto is True:
            cmdList.append(":SENS:RES:RANG:AUTO ON")
        elif range is not None:
            cmdList.append(":SENS:RES:RANG:AUTO OFF")
            cmdList.append(":SENS:RES:RANG " + str(float(range)))
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
    def configureVolt(self, digits=None, count=None, window=None, NPLC=None,
                      dFil=None, range=None, rangeAuto=None, trigBus=None,
                      repeatingFilter=None, reset=False):
        """
        Configure the Keitley 2000 to detect voltages

        Arguments:
            digits:int -- number of digits to display (4-8). default: None
            count:int -- filter count for the digital filter. default: None
            window:float -- filter window for the digital filter, default: None
            NPLC:int -- Number of power line cycles to integrate over.
                        default: None
            dFil:boolean -- If true, turn on the digital filter. If False
                            window and filter count are ignored- default: None
            repeatingFilter:boolean -- If true set the filter to repeating,
                                       If false to moving - default: None
            range:float -- Range of the voltage detection. Selected by the
                           instrument to include the value of range.
                           default: None
            rangeAuto:boolean -- Automatic detection of the measurement range
                                 Take care, takes additional time during
                                 measurements! default: None
            trigBus:boolean -- sets trigger source to BUS if true
            reset:boolean -- if true, the device is reset prior to
                             configuration, default: False
        """
        cmdList = []
        if reset is True:
            self.write("*RST")
            time.sleep(0.05)
        # we want to measure volts
        cmdList.append(":SENS:FUNC \"VOLT:DC\"")
        if NPLC is not None:
            cmdList.append(":SENS:VOLT:NPLC " + str(float(NPLC)))
        if digits is not None:
            cmdList.append(":SENS:VOLT:DIG " + str(int(digits)))
        if rangeAuto is True:
            cmdList.append(":SENS:VOLT:RANG:AUTO ON")
        elif range is not None:
            cmdList.append(":SENS:VOLT:RANG:AUTO OFF")
            cmdList.append(":SENS:VOLT:RANG " + str(float(range)))
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
            result = result.replace('\x13', '')
            self.triggered = False
            return float(result)
