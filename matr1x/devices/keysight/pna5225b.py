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
"""Module for controlling Keysight VNA 5225b device."""

from struct import unpack

import numpy as np
from wrapt import synchronized

from matr1x.devices.visadevice import VisaDevice


class PNA5225b(VisaDevice):
    """
    The device class for the Keysight VNA 5225b.

    It can possibly be used with different models from Keysight with
    little changes.
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

    The VNA will trigger that many sweeps, so the averaging requirement
    for each channel is satisfied.
    """

    def __init__(self, interface, reset=True, timeout=10e3, **kwargs):
        """
        Initialize a PNA5225b device.

        Parameters
        ----------
        interface : str
            The IP address and port where the device is located.
            e.g. TCPIP::192.98.143.1::5025::SOCKET
        reset : bool, optional
            If true, the VNA is reset on object creation using the reset method.
            Default is True.
        timeout : int, optional
            The timeout of the ethernet connection in milliseconds.
            Default is 10e3 ms.
        **kwargs
            Keyword arguments passed to the VisaDevice constructor.
            'open' : bool, optional
                If true, the connection to the VNA is opened on object creation.
                Default is True.
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

        Note that this does not reset the data transfer format! Use
        \*RST for this.
        """
        self.write("SYST:FPRESET")  # system:fpreset
        self.maxAverage = 1

    def selectTrace(self, channel, trace):
        """
        Select a trace for subsequent operations.

        Parameters
        ----------
        channel : int
            The channel number.
        trace : int
            The trace number to select.
        """
        self.write("CALC%i:PAR:MNUM %i" % (channel, trace))

    @synchronized
    def createParam(self, channel, param, name=None, scale="lin", createTrace=True):
        """
        Create a new measurement parameter.

        Parameters
        ----------
        channel : int
            The Channel on which the parameter is created.
        param : str
            The name of the parameter to be measured.
            e.g S12
        name : str, optional
            The name the parameter will be assigned.
            If None, a name will be automatically generated from
            the selected parameter and the channel.
            e.g. channel=1, param=S12 => name=ch1_S12
            Default is None.
        scale : str, optional
            The display format of the measurement.
            Currently implemented are 'lin': linear and 'log':
            logarithmic scale.
            Default is 'lin'.
        createTrace : bool, optional
            If true, a trace of the parameter is created using
            the createTrace method.
            Default is True.
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
        'MIN'/'MAX' arguments can be used instead of actual numbers,
        and use the highest/lowest setting the VNA is capable of.

        Parameters
        ----------
        channel : int
            The desired channel.
        fPoints : int or 'MIN'/'MAX'
            The number of points per sweep.
        if_bw : int
            The bandwidth of the digital IF filter.
            A lower value usually means a slower, but more accurate measurement.
        average : int, optional
            The number of averages which make up the final values.
            Default is None.

        Returns
        -------
        None
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
        'MIN'/'MAX' arguments can be used instead of actual numbers,
        and use the highest/lowest setting the VNA is capable of.

        Parameters
        ----------
        channel : int
            The desired channel.
        fStart : int
            The frequency on which the sweep starts.
        fStop : int
            The frequency on which the sweep ends.
        getData : bool, optional
            If true, trigger a sweep and return the results directly.
            Default is False.

        Returns
        -------
        np.ndarray or None
            The sweep data if getData is True, None otherwise.
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
        activate : bool, optional
            If true, activate the output after configuration.
            Default is True.
        """
        self.write("SENS%i:FREQ:CW %i" % (channel, freq))
        if activate:
            self.write("SENS%i:SWE:TYPE CW" % channel)
            self.write("OUTP ON")

    def setSourcePower(self, power, channel=1):
        """
        Configure the VNA output power.

        Parameters
        ----------
        power : int
            Power in dBm (setpoint between +30 and -30 dBm).
        channel : int, optional
            The desired channel.
            Default is 1.
        """
        self.write("SOUR%i:POW %i" % (channel, power))

    def getSourcePower(self, channel=1):
        """
        Get the VNA output power setting.

        Parameters
        ----------
        channel : int, optional
            The desired channel.
            Default is 1.

        Returns
        -------
        float
            Current power setting in dBm.
        """
        power = self.query(f"SOUR{channel}:POW?")
        return float(power)

    @synchronized
    def startSweep(self):
        """
        Prepare the VNA for triggering a sweep.

        The VNA activates the output, disables the continuous trigger
        and therefore enables manual triggering. Any currently running
        sweeps are aborted.
        """
        # OUTPut[:STATe] <ON | OFF>
        self.write("OUTP ON")
        # INITiate:CONTinuous <boolean> Trigger source to manual
        self.write("INIT:CONT OFF")
        self.write("ABOR")

    @synchronized
    def stopSweep(self):
        """Turn the VNA output off."""
        # OUTPut[:STATe] <ON | OFF>
        self.write("OUTP OFF")

    @synchronized
    def trigger(self, channel=1):
        """
        Trigger the sweep(s).

        Parameters
        ----------
        channel : int, optional
            The desired channel.
            Default is 1.
        """
        # get number of points and sweep time for timeout estimation
        n_points = float(self.query(f"SENS{channel}:SWE:POIN?"))
        sweep_time = float(self.query(f"SENS{channel}:SWE:TIME?"))

        # Clears & restart averaging of the measurement
        self.write(f"SENS{channel}:AVER:CLE")  # SENSe<cnum>:AVERage_CLEar
        for i in range(self.maxAverage):
            # estimate of sweep time by VNA + 1ms for frequency change
            self.connection.timeout = 1e3 * sweep_time + n_points + 10e3
            self.write("INIT:IMM")
            self.query("*OPC?")
            # reset timeout to default
            self.connection.timeout = self.timeout

    @synchronized
    def getData(self, channel, precision="single"):
        """
        Transfer measurement data from the VNA.

        Parameters
        ----------
        channel : int
            The desired channel.
        precision : str, optional
            One of {'single', 'double', 'ascii'}.
            'single' and 'double' precisions are transferred as binary data,
            and achieve much faster transfer speeds.
            'ascii' is only implemented as a fallback method, as it is
            much easier to debug.
            Default is 'single'.

        Returns
        -------
        np.ndarray
            The measured data from the specified channel.
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
            data_bit = data[i * byte_width : (i + 1) * byte_width]
            values.append(unpack(precdict[precision][2], data_bit))
        # add ravel to remove unnecessary dimensions of the array
        return np.array(values, dtype=precdict[precision][3]).ravel()

    @synchronized
    def getComplexData(self, channel, precision="single"):
        """
        Transfer complex measurement data from the VNA.

        Parameters
        ----------
        channel : int
            The desired channel.
        precision : str, optional
            One of {'single', 'double', 'ascii'}.
            'single' and 'double' precisions are transferred as binary data,
            and achieve much faster transfer speeds.
            'ascii' is only implemented as a fallback method, as it
            is much easier to debug.
            Default is 'single'.

        Returns
        -------
        np.ndarray
            The complex measured data from the specified channel
            as a 2xN array where the first row is the real part and
            the second row is the imaginary part.
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
            data_bit = data[i * byte_width : (i + 1) * byte_width]
            values.append(unpack(precdict[precision][2], data_bit))
        # add ravel to remove unnecessary dimensions of the array
        return np.array(values, dtype=precdict[precision][3]).reshape((-1, 2)).transpose()

    @synchronized
    def getSweepData(self, channel):
        """
        Prepare, trigger and fetch sweep data.

        This is a convenience method to prepare and trigger the sweep and transfer
        the data afterwards.

        Parameters
        ----------
        channel : int
            The used channel.

        Returns
        -------
        np.ndarray
            The measured data from the specified channel.
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
            The channel for which the sweep parameters should be returned.

        Returns
        -------
        fStart : float
            The frequency at which the sweep starts.
        fStop : float
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

        Currently, the method will display the reflection parameters
        in window 1 and the transmission parameters in window 2.
        At the moment it has no defined behavior for measurement of
        parameters other than the Sij.

        Parameters
        ----------
        name : str
            The name of the measurement parameter,
            by default ch<channel>_<parameter>.
        param : str
            The measured parameter.
        """
        # 1: Reflexion, 2: Transmission
        winNum = 1 if ("1" in param) ^ ("2" in param) else 2
        # DISPlay:WINDow<wnum>[:STATe] <ON | OFF>
        self.write("DISP:WIND%i:STAT ON" % winNum)
        self.write("DISP:WIND%i:TRAC%i:FEED '%s'" % (winNum, int(param[1]), name))

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
