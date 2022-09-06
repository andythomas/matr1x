# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
from struct import unpack

import numpy as np
from wrapt import synchronized

from .visadevice import VisaDevice


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
          Keyword arguments passed to the VISAdevice constructor.
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
