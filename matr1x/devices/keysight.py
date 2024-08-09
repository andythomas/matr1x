# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2024 matr1x developers. All rights reserved.
# ---
from struct import unpack

import numpy as np
from wrapt import synchronized

from .util import strToList
from .visadevice import VisaDevice


class PNA5225b(VisaDevice):
    """
    The device class for the Keysight VNA 5225b.
    It can possibly be used with different models from
    Keysight with little changes.
    """

    config_params = {
        "n_points": "SENS1:SWE:POIN?",
        "ifbw": "SENS1:BWID?",
        "average": "SENS1:AVER?",
        "n_average": "SENS1:AVER:COUN?",
        "format": "CALC1:FORM?",
    }
    maxAverage = 1
    """
    The maximum average setting of all configured channels.
    The VNA will trigger that many sweeps, so the averaging
    requirement for each channel is satisfied.
    """

    def __init__(self, interface, reset=True, timeout=10e3, **kwargs):
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
          (Default = 10e3 ms)
          The timeout of the ethernet connection.
        **kwargs :
          Keyword arguments passed to the VisaDevice constructor.
        """
        super().__init__(
            interface,
            write_termination="\n",
            read_termination="\n",
            timeout=timeout,
            **kwargs,
        )
        self.timeout = timeout

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

    def selectTrace(self, channel, trace):
        self.write("CALC%i:PAR:MNUM %i" % (channel, trace))

    @synchronized
    def createParam(self, channel, param, name=None, scale="lin", createTrace=True):
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
            name = "ch%i_%s" % (channel, param)

        # CALCulate<cnum>:PARameter[:DEFine]:EXTended <Mname>,<param>
        self.write("CALC%i:PAR:EXT '%s', '%s'" % (channel, name, param))
        # CALCulate<cnum>:PARameter:SELect <Mname>[,fast]
        self.write("CALC%i:PAR:SEL '%s'" % (channel, name))

        if scale == "lin":
            # CALCulate<cnum>:FORMat <char>
            self.write("CALC%i:FORM MLIN" % channel)
        elif scale == "log":
            self.write("CALC%i:FORM MLOG" % channel)
        else:
            print("Please choose a valid scale! Your input was: %s" % scale)

        if createTrace:
            self.createTrace(name, param)

    @synchronized
    def configureVNA(self, channel, fPoints, if_bw, average=None):
        """
        Change the sweep settings in the given channel.
        Frequency units are in Hz.
        'MIN'/'MAX' arguments can be used insted of actual numbers,
        and use the highest/lowest setting the VNA is cappable of.

        Parameters
        ----------
        channel : int
            The desired channel.
        fPoints : int or 'MIN'/'MAX'
            The number of points per sweep.
        if_bw : int
            The bandwidth of the digital IF filter.
            A lower value usually means a slower, but more accurate mesurement.
        average : int
             (Default = None)
            The number of averages which make up the final values.
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

        # SENSe<cnum>:SWEep:POINts <num>
        self.write("SENS%i:SWE:POIN %s" % (channel, str(fPoints)))
        # SENSe<cnum>:BWIDth
        self.write("SENS%i:BWID %s" % (channel, str(if_bw)))

    @synchronized
    def configureSweep(self, channel, fStart, fStop, getData=False):
        """
        Change the sweep settings in the given channel.
        Frequency units are in Hz.
        'MIN'/'MAX' arguments can be used insted of actual numbers,
        and use the highest/lowest setting the VNA is cappable of.

        Parameters
        ----------
        channel : int
            The desired channel.
        fStart : int
            The frequency on which the sweep starts.
        fEnd : int
            The frequency on which the sweep end.
        getData : bool
             (Default =  False)
            If true, trigger a sweep and return the results directly.
        Returns
        -------
        data : npArray
            The sweep data (if getData is true).
        """
        # SENSe<cnum>:FREQuency:STARt <num>
        self.write("SENS%i:FREQ:STAR %s" % (channel, str(fStart)))
        # SENSe<cnum>:FREQuency:STOP <num>
        self.write("SENS%i:FREQ:STOP %s" % (channel, str(fStop)))

        if getData:
            return self.getSweepData(channel)

    @synchronized
    def configureCW(self, channel, freq, activate=True):
        """
        Configure the VNA to output a wave with a constant frequency.

        Parameters
        ----------
        channel : int
            The desired channel.
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
            The desired channel.
        power : int
            Power in dbm.
        """
        self.write("SOUR%i:POW %i" % (channel, power))

    def getSourcePower(self, channel=1):
        """
        Configure the VNA output power (setpoint between +30 and -30dbm)

        Parameters
        ----------
        channel : int
            The desired channel.
        power : int
            Power in dbm.
        """
        power = self.query(f"SOUR{channel}:POW?")
        return float(power)

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
    def stopSweep(self):
        """
        Turns the VNA output off
        """
        # OUTPut[:STATe] <ON | OFF>
        self.write("OUTP OFF")

    @synchronized
    def trigger(self, channel=1):
        """
        Trigger the sweep(s).

        Parameters
        ----------
        channel : int
            The desired channel.
        """
        # get number of points and sweep time for timeout estimation
        n_points = float(self.query(f"SENS{channel}:SWE:POIN?"))
        sweep_time = float(self.query(f"SENS{channel}:SWE:TIME?"))

        # Clears & restart averaging of the measurement
        self.write(f"SENS{channel}:AVER:CLE")  # SENSe<cnum>:AVERage_CLEar
        for i in range(self.maxAverage):
            # estimate of sweep time by VNA + 1ms for frequency change
            self.interface.timeout = 1e3 * sweep_time + n_points + 10e3
            self.write("INIT:IMM")
            self.query("*OPC?")
            # reset timeout to default
            self.interface.timeout = self.timeout

    @synchronized
    def getData(self, channel, precision="single"):
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
        precdict = {
            "single": ("REAL,32", 4, ">f", "float32"),
            "double": ("REAL,64", 8, ">d", "float64"),
            "ascii": ("ASC,0", None, None),
        }

        try:
            self.write("FORM %s" % precdict[precision][0])
        except KeyError:
            print("%s is not a valid precision" % str(precision))
            return

        if precision == "ascii":
            data = self.query("CALC%i:DATA? FDATA" % channel)
            return np.fromstring(data, sep=",").transpose()

        byte_width = precdict[precision][1]
        self.write("CALC%i:DATA? FDATA" % channel)
        header1 = self.read(2)
        n_header_bytes = int(chr(header1[1]))
        header2 = self.read(n_header_bytes)
        n_data_bytes = 0
        for i, hbyte in enumerate(header2):
            n_data_bytes += 10 ** (n_header_bytes - i - 1) * int(chr(hbyte))
        data = self.read(n_data_bytes)
        self.read(1)

        values = []
        for i in range(int(len(data) / byte_width)):
            data_bit = data[i * byte_width: (i + 1) * byte_width]
            values.append(unpack(precdict[precision][2], data_bit))
        # add ravel to remove unnecessary dimensions of the array
        return np.array(values, dtype=precdict[precision][3]).ravel()

    @synchronized
    def getComplexData(self, channel, precision="single"):
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

        precdict = {
            "single": ("REAL,32", 4, ">f", "float32"),
            "double": ("REAL,64", 8, ">d", "float64"),
            "ascii": ("ASC,0", None, None),
        }

        try:
            self.write("FORM %s" % precdict[precision][0])
        except KeyError:
            print("%s is not a valid precision" % str(precision))
            return

        if precision == "ascii":
            data = self.query("CALC%i:DATA? FDATA" % channel)
            return np.fromstring(data, sep=",").transpose().ravel()

        byte_width = precdict[precision][1]
        self.write("CALC%i:DATA? SDATA" % channel)
        header1 = self.read(2)
        n_header_bytes = int(chr(header1[1]))
        header2 = self.read(n_header_bytes)
        n_data_bytes = 0
        for i, hbyte in enumerate(header2):
            n_data_bytes += 10 ** (n_header_bytes - i - 1) * int(chr(hbyte))
        data = self.read(n_data_bytes)
        self.read(1)

        values = []
        for i in range(int(len(data) / byte_width)):
            data_bit = data[i * byte_width: (i + 1) * byte_width]
            values.append(unpack(precdict[precision][2], data_bit))
        # add ravel to remove unnecessary dimensions of the array
        return np.array(values, dtype=precdict[precision][3]).reshape((-1, 2)).transpose()

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
        winNum = 1 if ("1" in param) ^ ("2" in param) else 2
        # DISPlay:WINDow<wnum>[:STATe] <ON | OFF>
        self.write("DISP:WIND%i:STAT ON" % winNum)
        self.write("DISP:WIND%i:TRAC%i:FEED '%s'" %
                   (winNum, int(param[1]), name))

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


class PSG8257D(VisaDevice):
    """
    The device class for the Keysight PSG 8257D-521, a microwave signal generator.
    """

    config_params = {
        "npoints": ":SOUR:SWE:POIN?",
        "modulation_output_status": ":OUTPUT:MOD?",
        "LFO_output_status": ":lfo:stat?",
        "LFO_source": ":SOUR:LFO:SOUR?",
        "LFO_amplitude": ":SOUR:LFO:AMPL?",
        "modulation_source": ":SOUR:AM:SOUR?",
        "modulation_frequency": ":SOUR:AM:INT:FREQ?",
        "modulation_shape": ":SOUR:AM:INT:FUNC:SHAP?",
        "modulation_amplitude_depth": ":SOUR:AM:DEPT?",
        "pulse_output_status": ":SOUR:PULM:STAT?",
        "pulse_source": ":SOUR:PULM:SOUR?",
        "pulse_input": ":SOUR:PULM:SOUR:INT?",
        "pulse_frequency": ":SOUR:PULM:INT:FREQ?",
    }

    def __init__(self, interface, reset=True, timeout=10e3, **kwargs):
        """
        Initialize a PSG8257D device.
        Parameters
        ----------
        interface : str
            The ip andress and port where the device is located.
            e.g. TCPIP::192.168.5.102::5025::SOCKET
        reset : bool
            (Default = True)
            If true, the VNA is reset on object creation using the reset method.
        timeout : int
            (Default = 10e3 ms)
            The timeout of the ethernet connection.
        **kwargs :
            Keyword arguments passed to the VISAdevice constructor.
        """
        super().__init__(
            interface,
            write_termination="\n",
            read_termination="\n",
            timeout=timeout,
            **kwargs,
        )
        self.timeout = timeout
        if reset:
            self.reset()

    def reset(self):
        """
        Disables the signal modulation and turns off the output of the PSG.
        """
        self.write(":OUTPUT:MOD OFF;")
        self.write(":lfo:stat off;")
        self.write(":OUTPUT OFF")

    @synchronized
    def setModulation(self, mod=False):
        """
        Enables the signal modulation.
        """
        if mod:
            self.write(":OUTPUT:MOD ON;")
            self.write(":lfo:stat on")
        else:
            self.write(":OUTPUT:MOD OFF;")
            self.write(":lfo:stat off")

    @synchronized
    def setLFO(self, LFO=True, source="INT", amplitude=3):
        """
        Configure the PSG low frequency output (LFO).

        Parameters
        ----------
        source : str
            The source of the low frequency output, which can take the values:
            internal:'INT', internal2:'INT2', function:'FUNC', function2:'FUNC2'
            internal & internal2: for the inernal source
            function & function2: for an internal function generator which can
            be configured.
        amplitude : int [0,3.5]
            Peak voltage (amplitude) of the low frequency output in volts,
            which can take values from 0-3.5V
        """
        if LFO is False:
            self.write(":SOUR:LFO:STAT OFF")
        else:
            self.write(":SOUR:LFO:STAT ON")
            self.write(":SOUR:LFO:SOUR %s" % (source))
            self.write(":SOUR:LFO:AMPL %g VP" % (amplitude))

    @synchronized
    def configureAmpMod(
        self,
        AmpMod=True,
        amMode="DEEP",
        ampSource="INT",
        intFreq=1e3,
        intShape="SINE",
        ampDepth=100,
    ):
        """
        Configure the PSG amplitude modulation (AmpMod).

        Parameters
        ----------
        ampSource : str
            The source of the amplitude modulation signal, which can take the values:
            internal:'INT', internal 2:'INT2',
            external:'EXT', external 2:'EXT2'
        intFreq : int [0.5,1e3]
            Frequency of the internal
            oscillator in Hertz, which can take values from 0.5 Hz to 1 MHz.
        intShape : str
            Shape of the internal oscillations, which can take the values:
            sine:'SINE', triangle:'TRI', square:'SQU', ramp:'RAMP',
            noise:'NOIS', dual-sine:'DUAL', swept-sine:'SWEP'
        ampDepth : int [0,100]
            Amplitude modulation in precent, which can take values from 0 to 100 %.
        ----------
        """
        if AmpMod is False:
            self.write(":SOUR:AM:STAT OFF")
        else:
            self.write(":SOUR:AM:STAT ON")
            self.write(f":AM:MODE {amMode}")  # NORM or DEEP
            self.write(":SOUR:AM:SOUR %s" % (ampSource))
            self.write(":SOUR:AM:INT:FREQ %g" % (intFreq))
            self.write(":SOUR:AM:INT:FUNC:SHAP %s" % (intShape))
            self.write(":SOUR:AM:DEPT %g" % (ampDepth))

    @synchronized
    def configurePulseMod(self, PulseMod=True, pulseSource="INT", pulseInput="SQU", frequency=1e3):
        """
        Configures the pulse modulation of the output signal.

        Parameters
        ----------
        pulseSource : str
            source of the pulse modulation signal, which can take the values:
            internal:'INT', external:'EXT', scalar:'SCAL'
        input : str
            Internally generated modulation input for the pulse modulation,
            which can take the values: square:'SQU', free-run:'FRUN',
            triggered:'TRIG', doublet:'DOUB', gated:'GATE'
        frequency : int [0.1,10e3]
            Pulse rate frequency in Hertz, which can take values from 0.1 Hz to 10 MHz.
        """
        if PulseMod is False:
            self.write(":SOUR:PULM:STAT OFF")
        else:
            self.write(":SOUR:PULM:STAT ON")
            self.write(":SOUR:PULM:SOUR %s" % (pulseSource))
            self.write(":SOUR:PULM:SOUR:INT %s" % (pulseInput))
            self.write(":SOUR:PULM:INT:FREQ %g" % (frequency))

    @synchronized
    def readFreq(self):
        """
        Read the parameters from the PSG.

        Returns
        -------
        freq : int
            The output frequency in Hz.
        power : int
            The output power in dBm.
        """
        self.write(":FREQ?")
        freq = float(self.read())
        return freq

    @synchronized
    def setSourcePower(self, power):
        """
        Configure the PSG output power (setpoint between +25 and -20 dBm)

        Parameters
        ----------
        power : int
            Power in dbm.
        """
        # :POWer <num> dBm
        self.write(f":POW {power} dBm")

    @synchronized
    def getSourcePower(self):
        """
        Configure the PSG output power (setpoint between +25 and -20 dBm)

        Parameters
        ----------
        power : int
            Power in dbm.
        """
        power = self.query(":POW?")
        return power

    @synchronized
    def trigger(self):
        """
        Trigger the sweep(s).

        Parameters
        ----------
        sync : bool
          (Default = True)
          If true, the function will wait for the sweep to comlete
          before returning.
        """
        # get number of points and sweep time for timeout estimation
        n_points = float(self.query(":SOUR:SWE:POIN?"))
        sweep_time = float(self.query(":SOUR:SWE:TIME?"))

        self.write(":ABOR")
        # estimate of sweep time by VNA + 1ms for frequency change
        self.interface.timeout = 1e3 * sweep_time + n_points + 10e3
        self.write("INIT:IMM")
        self.query("*OPC?")
        # reset timeout to default
        self.interface.timeout = self.timeout

    @synchronized
    def configureSweep(self, fStart, fStop, fPoints, stepDwell):
        """
        Change the sweep settings in the given channel.
        Frequency units are in Hz.
        'MIN'/'MAX' arguments can be used insted of actual numbers,
        and use the highest/lowest setting the VNA is cappable of.

        Parameters
        ----------
        fStart : int
            The frequency on which the sweep starts.
        fEnd : int
            The frequency on which the sweep end.
        fPoints : int or 'MIN'/'MAX'
            The number of points per sweep.
        stepDwell : int
            setting the dwell time for a step sweep.
        getData : bool
             (Default =  False)
            If true, trigger a sweep and return the results directly.
        Returns
        -------
        data : npArray
            The sweep data (if getData is true).
        """
        self.write(":SWE:GEN STEP")  # sweep type: ANALog or STEPped.
        # automatically sweep through frequency range
        self.write(":SWE:MODE AUTO")
        self.write(":SWE:TIME:AUTO ON")
        self.write(":FREQ:MODE SWE")  # FIXed|CW|SWEep|LIST
        self.write(":TRIG:OUTP:POL POS")
        self.write(":LIST:TRIG:SOUR IMM")
        self.write(f":FREQ:STAR {fStart}")
        self.write(f":FREQ:STOP {fStop}")
        self.write(f":SWE:POIN {fPoints}")
        self.write(f":SWE:DWEL {stepDwell}")

    @synchronized
    def configureCW(self, freq):
        """
        Configure the PDG to output a wave with a constant frequency.

        Parameters
        ----------
        channel : int
            The used channel.
        freq : int or 'MIN'/'MAX'
            The frequency in Hz.
        """
        self.write(":FREQ:MODE CW")  # set frequency mode
        self.write(f":FREQ {freq}Hz")
        self.write(":OUTPUT ON")

    @synchronized
    def output(self, state):
        """
        Set the output state of the PSG
        """
        # OUTPut[:STATe] <ON | OFF>
        if state is True:
            self.write(":OUTP ON")
            return
        self.write(":OUTP OFF")

    @synchronized
    def startSweep(self):
        """
        Prepare the PSG for triggering a sweep.
        The PSG activates the output, disables the continuous trigger and
        therefore enables manual triggering.
        Any currently running sweeps are aborted.
        """
        self.output(True)
        # INITiate:CONTinuous <boolean> Trigger source to manual
        self.write(":INIT:CONT OFF")
        self.write(":ABOR")

    @synchronized
    def stopSweep(self):
        """
        Turns the PSG output off
        """
        self.output(False)

    @synchronized
    def readSweepParams(self):
        """
        Read the sweep parameters from the VNA.
        Frequencies are returned in Hz.

        Returns
        -------
        fStart : int
            The frequency at which the sweep starts.
        fStop : int
            The frequency at which the sweep stops.
        fPoints : int
            The number of points in the sweep.
        """
        fStart = float(self.query(":FREQ:STAR?"))
        fStop = float(self.query(":FREQ:STOP?"))
        return fStart, fStop


class PSA_E4440A(VisaDevice):
    """
    The device class for the Agilent PSA E4440A - Spectrum Analyzer.
    It can possibly be used with different models with little changes.
    """

    config_params = {
        "vidBW": "BAND:VID?",
        "resBW": "BAND?",
        "average": "AVER:STAT?",
        "naverage": "AVERage:COUNt?",
    }
    maxAverage = 1
    """
    The maximum average setting of all configured channels.
    The VNA will trigger that many sweeps, so the averaging
    requirement for each channel is satisfied.
    """

    def __init__(self, interface, reset=True, timeout=10e3, **kwargs):
        """
        Initialize the device.

        Parameters
        ----------
        interface : str
          The ip andress and port where the device is located.
          e.g. TCPIP::192.168.5.52::5025::SOCKET
        open : bool
          (Default = True)
          If true, the connection to the PSA is opened on object creation.
        reset : bool
          (Default = True)
          If true, the PSA is reset on object creation using the reset method.
        timeout : int
          (Default = 10e3 ms)
          The timeout of the ethernet connection.
        **kwargs :
          Keyword arguments passed to the VISAdevice constructor.
        """
        super().__init__(
            interface,
            write_termination="\n",
            read_termination="\n",
            timeout=timeout,
            **kwargs,
        )
        self.timeout = timeout
        self.write("SYST:PRES:TYPE MODE")
        self.write("SYST:PRES")  # SYSTem:PRESet

        self.write("TRIG:SOUR IMM")
        self.write("SWE:TIME:AUTO ON")
        self.write("POW:RF:GAIN:STAT ON")  # turns on internal preamp
        self.write("POW:RF:GAIN 30")  # set gain of preamp to 30 dB
        self.write("POW:RF:ATT:AUTO OFF")  # turns on automatic attenuation
        self.write("POWer:ATT 0")  # set attenuation to 0 dB
        self.write("CAL:AUTO OFF")

        if reset:
            self.reset()

    def reset(self):
        """
        Reset the VNA using the SYST:FPRESET command.
        Note that this does not reset the data transfer format!
        Use *RST for this
        """
        self.write("SYST:PRES:TYPE MODE")
        self.write("SYST:PRES")  # SYSTem:PRESet
        self.write("CAL:AUTO ON")
        self.maxAverage = 1

    @synchronized
    def configureSweep(
        self,
        fCent,
        fSpan,
        fPoints,
        refLev,
        resBW,
        vidBW,
        average=None,
        avgType="rms",
        scale="log",
        getData=False,
    ):
        """
        Change the sweep settings in the given channel.
        Frequency units are in Hz.
        'MIN'/'MAX' arguments can be used insted of actual numbers,
        and use the highest/lowest setting the VNA is cappable of.

        Parameters
        ----------
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
        avgType : str
                        (Default = 'rms')
                        The average typ of the mesurement.
                        Currently implemented are 'rms': Power (RMS) averaging,
                        'log' : Log-Power (video) averaging and 'scalar' : Voltage
                        averaging.
        scale : str
          (Default = 'log')
          The display format of the mesurement.
          Currently implemented are 'lin': linear and 'log' :
          logarithmic scale.
        getData : bool
             (Default =  False)
            If true, trigger a sweep and return the results directly.

        Returns
        -------
        data : npArray
            The sweep data (if getData is true).
        """
        fStop = fCent + (fSpan / 2)
        if fStop > 8e9:
            print("Warning, attempting to set Frequency exceeding 8GHz, returning")
            return

        if average:
            if avgType == "rms":
                self.write("AVERage:TYPE:RMS")
            elif avgType == "log":
                self.write("AVERage:TYPE:LOG")
            elif avgType == "scalar":
                self.write("AVERage:TYPE:SCAL")
            else:
                print("Please choose a valid average type! Your input was: {}".format(
                    str(avgType)))
            self.write("AVER:STAT ON")
            self.write("AVERage:COUNt {}".format(average))
            self.maxAverage = max(average, self.maxAverage)
        else:
            self.write("AVER:STAT OFF")

        self.write("FREQ:CENT {} HZ".format(str(fCent)))
        self.write("FREQ:SPAN {} HZ".format(str(fSpan)))
        self.write("SWE:POIN {}".format(str(fPoints)))
        self.write("BAND:VID {} Hz".format(str(vidBW)))
        self.write("BAND {} Hz".format(str(resBW)))
        self.write("DISP:WIND:TRAC:Y:RLEV {} dbm".format(str(refLev)))

        if scale == "lin":
            self.write("DISP:WIND:TRAC:Y:SCAL:SPAC LIN")
        elif scale == "log":
            self.write("DISP:WIND:TRAC:Y:SCAL:SPAC LOG")
        else:
            print("Please choose a valid scale! Your input was: {}".format(str(scale)))

        # selects the sweep type automatic mode
        self.write("SWEep:TYPE AUTO")
        # sets the rules for the sweep type auto mode to dynamic range
        self.write("SWE:TYPE:AUTO:RUL DRAN")

        if getData:
            return self.getSweepData()

    @synchronized
    def startSweep(self):
        """
        Prepare the PSA for triggering a sweep.
        The PSA disables the continuous trigger and therefore enables
        manual triggering. Any currently running sweeps are aborted.
        """
        self.write(":ABORT")
        # INITiate:CONTinuous <boolean> Trigger source to manual
        self.write(":INIT:CONT OFF")

    @synchronized
    def trigger(self):
        """
        Trigger the sweep(s).

        Parameters
        ----------
        sync : bool
          (Default = True)
          If true, the function will wait for the sweep to comlete
          before returning.
        """
        # get number of points and sweep time for timeout estimation
        n_points = float(self.query(":SOUR:SWE:POIN?"))
        sweep_time = float(self.query(":SOUR:SWE:TIME?"))

        for i in range(self.maxAverage):
            # estimate of sweep time by VNA + 1ms for frequency change
            self.interface.timeout = 1e3 * sweep_time + n_points + 10e3
            self.write("INIT:IMM")
            self.query("*OPC?")
            # reset timeout to default
            self.interface.timeout = self.timeout

    @synchronized
    def getData(self, precision="single"):
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
        precdict = {
            "single": ("REAL,32", 4, ">f", "float32"),
            "double": ("REAL,64", 8, ">d", "float64"),
            "ascii": ("ASC,0", None, None),
        }

        try:
            self.write("FORM {}".format(precdict[precision][0]))
        except KeyError:
            print("{} is not a valid precision".format(str(precision)))
            # return
        if precision == "ascii":
            data = self.query("TRAC:DATA? TRACE1")
            return np.fromstring(data, sep=",").transpose()

        byte_width = precdict[precision][1]
        self.write("TRAC:DATA? TRACE1")
        header1 = self.read(2)
        n_header_bytes = int(chr(header1[1]))
        header2 = self.read(n_header_bytes)
        n_data_bytes = 0
        for i, hbyte in enumerate(header2):
            n_data_bytes += 10 ** (n_header_bytes - i - 1) * int(chr(hbyte))
        data = self.read(n_data_bytes)
        self.read(1)

        values = []
        for i in range(int(len(data) / byte_width)):
            data_bit = data[i * byte_width: (i + 1) * byte_width]
            values.append(unpack(precdict[precision][2], data_bit))
        # add ravel to remove unnecessary dimensions of the array
        return np.array(values, dtype=precdict[precision][3]).ravel()

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
        return self.getData()

    @synchronized
    def readSweepParams(self):
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
        self.write("FREQ:CENT?")
        fCent = float(self.read())
        self.write("FREQ:SPAN?")
        fSpan = float(self.read())
        self.write("SWE:POIN?")
        fPoints = int(self.read())
        return fCent - fSpan, fCent + fSpan, fPoints


class KeysightB2961(VisaDevice):
    """
    Keysight B2961 DC (and low frequency AC) power supply

    Typically connected via TCPIP::<IP-address>:5025::SOCKET
    """

    config_params = {
        "sourceMode": "sourceMode",
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
        self.write(":FORM:ELEM:SENS VOLT,CURR,SOUR")

    def configure(
        self,
        sourceMode=None,
        senseMode=None,
        fourWire=None,
        sourceAutoRange=None,
        sourceRange=None,
        senseLimit=None,
        output=None,
        delayAuto=None,
        delay=None,
        nplc=None,
        reset=False,
    ):
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
        assert (sourceMode == "VOLT") or (sourceMode == "CURR"), 'source ("' + \
            sourceMode + '") and/or sense ("' + \
            senseMode + '") mode are incorrect'
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
            cmdlist.append(':SENS:FUNC "{}"'.format(self.senseMode))

        if senseLimit is not None:
            cmdlist.append(":SOUR:{}:PROT {}".format(
                self.sourceMode, float(senseLimit)))

        if nplc is not None:
            cmdlist.append(":SENS:{}:NPLC {}".format(
                self.sourceMode, float(nplc)))
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
            cmdlist.append(":SOUR:{}:RANG {}".format(
                self.sourceMode, float(sourceRange)))

        cmdlist.append(":FORM:ELEM:SENS VOLT,CURR,SOUR")

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

    def setAcquisitionTriggerMode(self, mode="BUS", count=None):
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
        self.write(":TRIG:ACQ:SOUR {}".format(mode))
        if count:
            self.write(":TRIG:ACQ:COUN {}".format(count))

    def triggerReading(self):
        """sent a trigger to trigger a reading when trigger is set to BUS"""
        self.write(":ABOR:ACQ")
        self.write(":INIT:ACQ")
        self.write(":ARM:ACQ")
        self.write("*TRG")

    def getReading(self):
        """fetch measured data after a trigger was sent"""
        self.write("FETCH?")
        return strToList(self.read())

    def configure_sine(self, amp, freq, offset=0, count="INF", onlysetamp=False):
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
        cmdlist = [":ABOR"]

        if onlysetamp:
            cmdlist.append(":SOUR:ARB:{}:SIN:AMPL {}".format(
                self.sourceMode, amp))
            cmdlist.append(":INIT")
        else:
            cmdlist.append(":OUTP OFF")
            # set sin mode
            cmdlist.append(":SOUR:{}:MODE ARB".format(self.sourceMode))
            cmdlist.append(":SOUR:ARB:FUNC SIN")
            cmdlist.append(":SOUR:ARB:{}:SIN:AMPL {}".format(
                self.sourceMode, float(amp)))
            cmdlist.append(":SOUR:ARB:{}:SIN:FREQ {}".format(
                self.sourceMode, float(freq)))
            cmdlist.append(":SOUR:ARB:{}:SIN:OFFS {}".format(
                self.sourceMode, float(offset)))
            # set number of repetitions
            cmdlist.append(":SOUR:ARB:COUN {}".format(count))
            # set phase marker (trigger/sync) output
            cmdlist.append(
                ":SOUR:ARB:{}:SIN:PMAR:PHAS 0".format(self.sourceMode))
            cmdlist.append(
                ":SOUR:ARB:{}:SIN:PMAR:STAT 1".format(self.sourceMode))
            cmdlist.append(
                ":SOUR:ARB:{}:SIN:PMAR:SIGN ext1".format(self.sourceMode))
            cmdlist.append(":SOUR:DIG:EXT1:FUNC TOUT")
            cmdlist.append(":SOUR:DIG:EXT1:POL POS")
            cmdlist.append(":SOUR:DIG:EXT1:TOUT:WIDT 100e-6")

            # generate triggers for source internally
            cmdlist.append(":TRIG:TRAN:COUN 1")
            cmdlist.append(":TRIG:TRAN:SOUR TIMER")

        for cmd in cmdlist:
            self.write(cmd)

    def run_wave(self):
        self.write(":INIT")
        self.output(True)

    def visualize_trace(self, dt=1e-3, points=1000):
        self.setAcquisitionTriggerMode(mode="TIMER", count=points)
        self.write(":TRIG:ACQ:TIM {}".format(dt))
