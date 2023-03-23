# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
from struct import unpack

import numpy as np
from wrapt import synchronized

from .util import strToList
from .visadevice import VisaDevice


class KeysightB2961(VisaDevice):
    """
    Keysight B2961 DC (and low frequency AC) power supply

    Typically connected via TCPIP::<IP-address>:5025::SOCKET
    """
    config_params = {"sourceMode": "sourceMode",
                     "senseMode": "senseMode",
                     "VOLT:RANGE": "VOLT:RANG?",
                     "CURR:RANGE": "CURR:RANG?",
                     "VOLT:NPLC": ":SENS:VOLT:NPLC?",
                     "CURR:NPLC": ":SENS:CURR:NPLC?",
                     "Output": "outputState",
                     }

    def __init__(self, interface, **kwargs):
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n"
        super().__init__(interface, **kwargs)
        # after initialization get the source function to determine
        # whether voltage or current is the sourced
        self.write(":SOUR:FUNC:MODE?")
        self.sourceMode = self.read()
        self.write(":SENS:FUNC?")
        self.senseMode = self.read()
        self.write(":OUTP?")
        self.outputState = bool(self.read())
        # set the SMU to always only return the three typ. interesting values
        self.write(':FORM:ELEM:SENS VOLT,CURR,SOUR')

    def configure(self, sourceMode=None, senseMode=None, fourWire=None,
                  sourceAutoRange=None, sourceRange=None, senseLimit=None,
                  output=None, delayAuto=None, delay=None, nplc=None,
                  reset=False):
        """
        Configure the Keysight B2961A to source current/voltage and sense
        voltage/current

        Arguments:
            sourceMode: "VOLT" or "CURR" -- predefined physical parameter
            senseMode: "VOLT" or "CURR" -- measured parameter
            fourWire:boolean -- Four wire measurement? Default: None (use
                                current configuration)
            sourceAutoRange:boolean -- Autodetect the source range? Default:
                                       None
            sourceRange:float -- Largest expected source current, device will
                                 pick the next inclusive range. Default: None
            senseLimit:float -- source compliance level
            output:boolean -- Turn the output on? Default: None
            delayAuto:boolean -- Automatically choose the delay for stabilizing
                                 the output? Default: None
            delay:float -- Delay in seconds for stabilizing the output before
                           doing an internal measurement. WON'T AFFECT/DELAY
                           OTHER DEVICES! Default: 0.1(s)
            nplc:float -- number of power line cycles to average (4e-4 to 100)
            reset:boolean -- If true, reset the device

            Example:
                .configure(fourWire=True, senseAutoRange=True,
                           sourceRange=0.001, output=True)
                The output will initially be turned off during configuration.
                This will configure the Keithley 2450a to be in 4W sense mode,
                detect the sense range automatically. The range is chosen to
                include 1mA and the output is turned on.
        """
        # do nothing if sourcemode is not defined
        if sourceMode is None:
            return
        # assert source and sense mode are correct
        assert ((sourceMode == "VOLT") or (sourceMode == "CURR")), \
               ("source (\"" + sourceMode + "\") and/or sense (\"" +
                senseMode + "\") mode are incorrect")
        # add get output here to reset the device to the previous state
        self.output(False)
        # sourceMode will now be sourceMode
        self.sourceMode = sourceMode
        if reset is True:
            cmdlist = ["*RST"]
        else:
            cmdlist = []
        # we want sourceIsenseV
        cmdlist.append(":SOUR:FUNC:MODE {}".format(self.sourceMode))
        if senseMode is not None:
            self.senseMode = senseMode
            cmdlist.append(":SENS:FUNC \"{}\"".format(self.senseMode))

        if senseLimit is not None:
            cmdlist.append(":SOUR:{}:PROT {}".format(self.sourceMode,
                                                     float(senseLimit)))

        if nplc is not None:
            cmdlist.append(":SENS:{}:NPLC {}".format(self.sourceMode,
                                                     float(nplc)))
        if delayAuto is True:
            cmdlist.append(":SENS:WAIT:AUTO ON")
        elif delay is not None:
            cmdlist.append(":SENS:WAIT:AUTO OFF")
            cmdlist.append(":SENS:WAIT:OFFS {}".format(float(delay)))
        if fourWire is True:
            cmdlist.append(":SENS:REM ON")
        elif fourWire is False:
            cmdlist.append(":SENS:REM OFF")

        if sourceAutoRange is True:
            cmdlist.append(":SOUR:{}:RANG:AUTO ON".format(self.sourceMode))
        elif sourceRange is not None:
            cmdlist.append(":SOUR:{}:RANG:AUTO OFF".format(self.sourceMode))
            cmdlist.append(":SOUR:{}:RANG {}".format(self.sourceMode,
                                                     float(sourceRange)))

        cmdlist.append(':FORM:ELEM:SENS VOLT,CURR,SOUR')

        for cmd in cmdlist:
            self.write(cmd)
        self.output(output)

    def output(self, state=False):
        """
        turn output on if state is True, off with when state is False,
        otherwise do nothing
        """
        if state is True:
            self.write(":OUTP ON")
        elif state is False:
            self.write(":OUTP OFF")

    def setSource(self, value):
        """
        set the output value of the source to the defined value. This happens
        immediately without changing the source output status!
        """
        cmd = ":SOUR:{} {}".format(self.sourceMode, float(value))
        self.write(cmd)

    def getMeas(self):
        """perform a self triggered measurement and return the values"""
        self.write("MEAS?")
        return strToList(self.read())

    def getSource(self):
        self.write("MEAS:{}?".format(self.sourceMode))
        return float(self.read())

    def getSense(self):
        self.write("MEAS:{}?".format(self.senseMode))
        return float(self.read())

    def setAcquisitionTriggerMode(self, mode='BUS', count=None):
        """
        set up the SMU for triggered aquisition of the measurement system.

        Note: the source still has another independent trigger system which is
        not changed by this function!

        Arguments:
            mode: trigger mode: AINT (=Automatic), BUS (for use with
                  triggerReading), TIMER (for time trace recording)
            count: amount of triggers (typically 1 for BUS), allowed are: None,
                   integer, or inf
        """
        self.write(':TRIG:ACQ:SOUR {}'.format(mode))
        if count:
            self.write(':TRIG:ACQ:COUN {}'.format(count))

    def triggerReading(self):
        """sent a trigger to trigger a reading when trigger is set to BUS"""
        self.write(':ABOR:ACQ')
        self.write(':INIT:ACQ')
        self.write(':ARM:ACQ')
        self.write('*TRG')

    def getReading(self):
        """fetch measured data after a trigger was sent"""
        self.write("FETCH?")
        return strToList(self.read())

    def configure_sine(self, amp, freq, offset=0, count='INF',
                       onlysetamp=False):
        """
        configure for generation of a sign wave. use configure first to set up
        the sourceMode!  use run_wave after this command to actually start the
        output!

        note: this function also sets up the phase marker output (mapped to
        EXT1) which can be used as a sync signal for a lockin.

        Arguments:
            amp: amplitude of the sine wave
            freq: frequency of the sine wave
            offset: vertical offset of the sine wave (default 0)
            count: number of sine wave to output. (default: INF)
            onlyssetamp: flag to only set a new amplitude and leave the rest
                         unchanged -> keeps the output on!
        """
        cmdlist = [':ABOR']

        if onlysetamp:
            cmdlist.append(':SOUR:ARB:{}:SIN:AMPL {}'.format(self.sourceMode,
                                                             amp))
            cmdlist.append(':INIT')
        else:
            cmdlist.append(':OUTP OFF')
            # set sin mode
            cmdlist.append(':SOUR:{}:MODE ARB'.format(self.sourceMode))
            cmdlist.append(':SOUR:ARB:FUNC SIN')
            cmdlist.append(':SOUR:ARB:{}:SIN:AMPL {}'.format(self.sourceMode,
                                                             float(amp)))
            cmdlist.append(':SOUR:ARB:{}:SIN:FREQ {}'.format(self.sourceMode,
                                                             float(freq)))
            cmdlist.append(':SOUR:ARB:{}:SIN:OFFS {}'.format(self.sourceMode,
                                                             float(offset)))
            # set number of repetitions
            cmdlist.append(':SOUR:ARB:COUN {}'.format(count))
            # set phase marker (trigger/sync) output
            cmdlist.append(
                ':SOUR:ARB:{}:SIN:PMAR:PHAS 0'.format(self.sourceMode))
            cmdlist.append(
                ':SOUR:ARB:{}:SIN:PMAR:STAT 1'.format(self.sourceMode))
            cmdlist.append(
                ':SOUR:ARB:{}:SIN:PMAR:SIGN ext1'.format(self.sourceMode))
            cmdlist.append(':SOUR:DIG:EXT1:FUNC TOUT')
            cmdlist.append(':SOUR:DIG:EXT1:POL POS')
            cmdlist.append(':SOUR:DIG:EXT1:TOUT:WIDT 100e-6')

            # generate triggers for source internally
            cmdlist.append(':TRIG:TRAN:COUN 1')
            cmdlist.append(':TRIG:TRAN:SOUR TIMER')

        for cmd in cmdlist:
            self.write(cmd)

    def run_wave(self):
        self.write(':INIT')
        self.output(True)

    def visualize_trace(self, dt=1e-3, points=1000):
        self.setAcquisitionTriggerMode(mode='TIMER', count=points)
        self.write(':TRIG:ACQ:TIM {}'.format(dt))


class PNA5225b(VisaDevice):
    """
    The device class for the Keysight VNA 5225b.
    It can possibly be used with different models from
    Keysight with little changes.
    """
    config_params = {"npoints": "SENS1:SWE:POIN?",
                     "ifbw": "SENS1:BWID?",
                     "average": "SENS1:AVER?",
                     "naverage": "SENS1:AVER:COUN?",
                     "power": "SOUR1:POW?",
                     "format": "CALC1:FORM?",
                     }
    maxAverage = 1
    """
    The maximum average setting of all configured channels.
    The VNA will trigger that many sweeps, so the averaging
    requirement for each channel is satisfied.
    """

    def __init__(self, interface, reset=True, timeout=60e3, **kwargs):
        """
        Initialize a PNA5225b device.

        Parameters
        ----------
        interface : str
          The ip andress and port where the device is located.
          e.g. TCPIP::192.98.143.1::5025::SOCKET
        open : bool
          (Default = True)
          If true, the connection to the VNA is opened on object creation.
        reset : bool
          (Default = True)
          If true, the VNA is reset on object creation using the reset method.
        timeout : int
          (Default = 60e3)
          The timeout of the ethernet connection.
        **kwargs :
          Keyword arguments passed to the VisaDevice constructor.
        """
        super().__init__(interface, write_termination="\n",
                         read_termination="\n", timeout=timeout,
                         **kwargs)
        if reset:
            self.reset()

    def reset(self):
        r"""
        Reset the VNA using the SYST:FPRESET command.
        Note that this does not reset the data transfer format!
        Use \*RST for this
        """
        self.write("SYST:FPRESET")  # system:fpreset
        self.maxAverage = 1

    @synchronized
    def createParam(self, channel, param, name=None,
                    scale='lin', createTrace=True):
        """
        Create a new mesurement parameter.

        Parameters
        ----------
        channel : int
          The Channel on which the parameter is created.
        param : str
          The name of the parameter to be measured.
          e.g S12
        name : str
          (Default = None)
          The name the parameter will be assigned.
          If None, a name will be automatically generated from
          the selected arameter and the channel.
          e.g. channel=1, param=S12 => name=ch1_S12
        scale : str
          (Default = 'lin')
          The display format of the mesurement.
          Currently implemented are 'lin': linear and 'log' :
          logarithmic scale.
        createTrace : bool
          (Default = True)
          If true, a trace of the parameter is created using
          the createTrace method.
        """
        channel = int(channel)
        if not name:
            name = 'ch%i_%s' % (channel, param)

        # CALCulate<cnum>:PARameter[:DEFine]:EXTended <Mname>,<param>
        self.write("CALC%i:PAR:EXT '%s', '%s'" % (channel,
                                                  name,
                                                  param))
        # CALCulate<cnum>:PARameter:SELect <Mname>[,fast]
        self.write("CALC%i:PAR:SEL '%s'" % (channel,
                                            name))

        if scale == 'lin':
            # CALCulate<cnum>:FORMat <char>
            self.write("CALC%i:FORM MLIN" % channel)
        elif scale == 'log':
            self.write("CALC%i:FORM MLOG" % channel)
        else:
            print('Please choose a valid scale! Your input was: %s' % scale)

        if createTrace:
            self.createTrace(name, param)

    @synchronized
    def configureSweep(self, channel, fStart, fEnd, fPoints,
                       if_bw, average=None, getData=False):
        """
        Change the sweep settings in the given channel.
        Frequency units are in Hz.
        'MIN'/'MAX' arguments can be used insted of actual numbers,
        and use the highest/lowest setting the VNA is cappable of.

        Parameters
        ----------
        channel : int
            The used channel.
        fStart : int
            The frequency on which the sweep starts.
        fEnd : int
            The frequency on which the sweep end.
        fPoints : int or 'MIN'/'MAX'
            The number of points per sweep.
        if_bw : int
            The bandwidth of the digital IF filter.
            A lower value usually means a slower, but more accurate mesurement.
        average : int
             (Default = None)
            The number of averages which make up the final values.
        getData : bool
             (Default =  False)
            If true, trigger a sweep and return the results directly.
        Returns
        -------
        data : npArray
            The sweep data (if getData is true).
        """

        if average:
            # SENSe<cnum>:AVERage
            self.write("SENS%i:AVER ON" % channel)
            # SENSe<cnum>:AVERage:COUNt <num>
            self.write("SENS%i:AVER:COUN %i" % (channel, average))
            self.maxAverage = max(average, self.maxAverage)
        else:
            self.write("SENS%i:AVER OFF" % channel)

        # SENSe<cnum>:FREQuency:STARt <num>
        self.write("SENS%i:FREQ:STAR %s" % (channel, str(fStart)))
        # SENSe<cnum>:FREQuency:STOP <num>
        self.write("SENS%i:FREQ:STOP %s" % (channel, str(fEnd)))
        # SENSe<cnum>:SWEep:POINts <num>
        self.write("SENS%i:SWE:POIN %s" % (channel, str(fPoints)))
        # SENSe<cnum>:BWIDth
        self.write("SENS%i:BWID %s" % (channel, str(if_bw)))

        if getData:
            return self.getSweepData(channel)

    @synchronized
    def configureCW(self, channel, freq, activate=True):
        """
        Configure the VNA to output a wave with a constant frequency.

        Parameters
        ----------
        channel : int
            The used channel.
        freq : int or 'MIN'/'MAX'
            The frequency in Hz.
        activate : bool
             (Default = True)
            If true, activate the output after configuration.
        """

        self.write("SENS%i:FREQ:CW %i" % (channel, freq))
        if activate:
            self.write("SENS%i:SWE:TYPE CW" % channel)
            self.write("OUTP ON")

    def setSourcePower(self, power, channel=1):
        """
        Configure the VNA output power (setpoint between +30 and -30dbm)

        Parameters
        ----------
        channel : int
            The used channel.
        power : int
            Power in dbm.
        """
        self.write("SOUR%i:POW %i" % (channel, power))

    @synchronized
    def startSweep(self):
        """
        Prepare the VNA for triggering a sweep.
        The VNA activates the output, disables the continuous trigger and
        therefore enables manual triggering.
        Any currently running sweeps are aborted.
        """
        # OUTPut[:STATe] <ON | OFF>
        self.write("OUTP ON")
        # INITiate:CONTinuous <boolean> Trigger source to manual
        self.write("INIT:CONT OFF")
        self.write("ABOR")

    @synchronized
    def trigger(self, sync=True):
        """
        Trigger the sweep(s).

        Parameters
        ----------
        sync : bool
          (Default = True)
          If true, the function will wait for the sweep to comlete
          before returning.
        """

        for i in range(self.maxAverage):
            self.write("INIT:IMM")
            if sync:
                self.query("*OPC?")

    @synchronized
    def getData(self, channel, precision='single'):
        """
        Transfer mesurement data from the VNA.

        Parameters
        ----------
        channel : int
          The desired channel
        precision : str
          (Default = 'single')
          One of {'single', 'double', 'ascii'}
          'single' and 'double' precisions are transferd as binary data,
          and achive much faster transfer speeds.
          'ascii' is only implemented as a fallback method, as it is
          much easier to debug.
        Returns
        -------
        data : np.array
            The mesured data from the specified channel.
        """
        precdict = {'single': ('REAL,32', 4, '>f', 'float32'),
                    'double': ('REAL,64', 8, '>d', 'float64'),
                    'ascii': ('ASC,0', None, None)}

        try:
            self.write('FORM %s' % precdict[precision][0])
        except KeyError:
            print('%s is not a valid precision' % str(precision))
            return

        if precision == 'ascii':
            data = self.query("CALC%i:DATA? FDATA" % channel)
            return np.fromstring(data, sep=',').transpose()

        byte_width = precdict[precision][1]
        self.write("CALC%i:DATA? FDATA" % channel)
        header1 = self.read(2)
        n_header_bytes = int(chr(header1[1]))
        header2 = self.read(n_header_bytes)
        n_data_bytes = 0
        for i, hbyte in enumerate(header2):
            n_data_bytes += 10**(n_header_bytes - i - 1) * int(chr(hbyte))
        data = self.read(n_data_bytes)
        self.read(1)

        values = []
        for i in range(int(len(data)/byte_width)):
            data_bit = data[i*byte_width:(i+1)*byte_width]
            values.append(unpack(precdict[precision][2], data_bit))
        # add ravel to remove unnecessary dimensions of the array
        return (np.array(values, dtype=precdict[precision][3]).ravel())

    @synchronized
    def getComplexData(self, channel, precision='single'):
        """
        Transfer mesurement data from the VNA.

        Parameters
        ----------
        channel : int
          The desired channel
        precision : str
          (Default = 'single')
          One of {'single', 'double', 'ascii'}
          'single' and 'double' precisions are transferd as binary data,
          and achive much faster transfer speeds.
          'ascii' is only implemented as a fallback method, as it
          is much easier to debug.
        Returns
        -------
        data : np.array
          The mesured data from the specified channel.
        """

        precdict = {'single': ('REAL,32', 4, '>f', 'float32'),
                    'double': ('REAL,64', 8, '>d', 'float64'),
                    'ascii': ('ASC,0', None, None)}

        try:
            self.write('FORM %s' % precdict[precision][0])
        except KeyError:
            print('%s is not a valid precision' % str(precision))
            return

        if precision == 'ascii':
            data = self.query("CALC%i:DATA? FDATA" % channel)
            return np.fromstring(data, sep=',').transpose().ravel()

        byte_width = precdict[precision][1]
        self.write("CALC%i:DATA? SDATA" % channel)
        header1 = self.read(2)
        n_header_bytes = int(chr(header1[1]))
        header2 = self.read(n_header_bytes)
        n_data_bytes = 0
        for i, hbyte in enumerate(header2):
            n_data_bytes += 10**(n_header_bytes - i - 1) * int(chr(hbyte))
        data = self.read(n_data_bytes)
        self.read(1)

        values = []
        for i in range(int(len(data)/byte_width)):
            data_bit = data[i*byte_width:(i+1)*byte_width]
            values.append(unpack(precdict[precision][2], data_bit))
        # add ravel to remove unnecessary dimensions of the array
        return (np.array(values,
                         dtype=precdict[
                             precision][3]).reshape((-1, 2)).transpose())

    @synchronized
    def getSweepData(self, channel):
        """
        Convenience method to prepare and trigger the sweep and transfer
        the data afterwards.

        Parameters
        ----------
        channel : int
            The used channel.
        Returns
        -------
        data : np.array
            The mesured data from the specified channel.
        """

        self.startSweep()
        self.trigger()
        return self.getData(channel)

    @synchronized
    def readSweepParams(self, channel):
        """
        Read the sweep parameters from the VNA.
        Frequencies are returned in Hz.

        Parameters
        ----------
        channel : int
            The channel for which the sweep parameters should be returned
        Returns
        -------
        fStart : int
            The frequency at which the sweep starts.
        fStop : int
            The frequency at which the sweep stops.
        fPoints : int
            The number of points in the sweep.
        """

        self.write("SENS%i:FREQ:STAR?" % channel)
        fStart = float(self.read())
        self.write("SENS%i:FREQ:STOP?" % channel)
        fStop = float(self.read())
        self.write("SENS%i:SWE:POIN?" % channel)
        fPoints = int(self.read())
        return fStart, fStop, fPoints

    @synchronized
    def createTrace(self, name, param):
        """
        Create a trace on the VNA display.
        Currently, the method will display the reflexion paramters
        in window 1 and the transmission parameters in window 2.
        At the moment it has no defined behavior for mesurment of
        parameters other than the Sij.

        Parameters
        ----------
        name : str
            The name of the mesurement parameter,
                by default ch<channel>_<parameter>
        param : str
            The mesured parameter
        """
        # 1: Reflexion, 2: Transmission
        winNum = 1 if ('1' in param) ^ ('2' in param) else 2
        # DISPlay:WINDow<wnum>[:STATe] <ON | OFF>
        self.write("DISP:WIND%i:STAT ON" % winNum)
        self.write("DISP:WIND%i:TRAC%i:FEED '%s'" % (winNum,
                                                     int(param[1]), name))

    def deleteTrace(self, winNum, tracNum):
        """
        Delete a trace from the VNA display.

        Parameters
        ----------
        winNum : int
            The window number in which the trace is displayed.
        tracNum : int
            The number of the trace.
        """
        self.write("DISP:WIND%i:TRAC%i:DEL" % (winNum, tracNum))
