# This file is part of a software collection for data acquisition (matr1x).
# Copyright (C) 2006-2026 matr1x developers
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
"""Module for controlling the Keysight PSG 8257D-521 microwave signal generator."""

from wrapt import synchronized

from matr1x.devices.visadevice import VisaDevice


class PSG8257D(VisaDevice):
    """The device class for the Keysight PSG 8257D-521, a microwave signal generator."""

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
            The IP address and port where the device is located.
            e.g. TCPIP::192.168.5.102::5025::SOCKET
        reset : bool, optional
            If True, the device is reset on object creation using the reset method.
            Default is True.
        timeout : int, optional
            The timeout of the ethernet connection in milliseconds.
            Default is 10e3 ms.
        **kwargs
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
        """Disable the signal modulation and turn off the output of the PSG."""
        self.write(":OUTPUT:MOD OFF;")
        self.write(":lfo:stat off;")
        self.write(":OUTPUT OFF")

    @synchronized
    def setModulation(self, mod=False):
        """
        Enable or disable the signal modulation.

        Parameters
        ----------
        mod : bool, optional
            If True, enable modulation. If False, disable modulation.
            Default is False.
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
        LFO : bool, optional
            If True, enable LFO. If False, disable LFO.
            Default is True.
        source : str, optional
            The source of the low frequency output, which can take the values:
            internal:'INT', internal2:'INT2', function:'FUNC', function2:'FUNC2'
            internal & internal2: for the internal source
            function & function2: for an internal function generator which can
            be configured.
            Default is "INT".
        amplitude : float, optional
            Peak voltage (amplitude) of the low frequency output in volts,
            which can take values from 0-3.5V.
            Default is 3.
        """
        if LFO is False:
            self.write(":SOUR:LFO:STAT OFF")
        else:
            self.write(":SOUR:LFO:STAT ON")
            self.write(f":SOUR:LFO:SOUR {source}")
            self.write(f":SOUR:LFO:AMPL {amplitude:g} VP")

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
        AmpMod : bool, optional
            If True, enable amplitude modulation. If False, disable amplitude modulation.
            Default is True.
        amMode : str, optional
            Amplitude modulation mode, either "DEEP" or "NORM".
            Default is "DEEP".
        ampSource : str, optional
            The source of the amplitude modulation signal, which can take the values:
            internal:'INT', internal 2:'INT2',
            external:'EXT', external 2:'EXT2'.
            Default is "INT".
        intFreq : float, optional
            Frequency of the internal oscillator in Hertz,
            which can take values from 0.5 Hz to 1 MHz.
            Default is 1e3.
        intShape : str, optional
            Shape of the internal oscillations, which can take the values:
            sine:'SINE', triangle:'TRI', square:'SQU', ramp:'RAMP',
            noise:'NOIS', dual-sine:'DUAL', swept-sine:'SWEP'.
            Default is "SINE".
        ampDepth : int, optional
            Amplitude modulation in percent, which can take values from 0 to 100%.
            Default is 100.
        """
        if AmpMod is False:
            self.write(":SOUR:AM:STAT OFF")
        else:
            self.write(":SOUR:AM:STAT ON")
            self.write(f":AM:MODE {amMode}")  # NORM or DEEP
            self.write(f":SOUR:AM:SOUR {ampSource}")
            self.write(f":SOUR:AM:INT:FREQ {intFreq:g}")
            self.write(f":SOUR:AM:INT:FUNC:SHAP {intShape}")
            self.write(f":SOUR:AM:DEPT {ampDepth:g}")

    @synchronized
    def configurePulseMod(self, PulseMod=True, pulseSource="INT", pulseInput="SQU", frequency=1e3):
        """
        Configure the pulse modulation of the output signal.

        Parameters
        ----------
        PulseMod : bool, optional
            If True, enable pulse modulation. If False, disable pulse modulation.
            Default is True.
        pulseSource : str, optional
            Source of the pulse modulation signal, which can take the values:
            internal:'INT', external:'EXT', scalar:'SCAL'.
            Default is "INT".
        pulseInput : str, optional
            Internally generated modulation input for the pulse modulation,
            which can take the values: square:'SQU', free-run:'FRUN',
            triggered:'TRIG', doublet:'DOUB', gated:'GATE'.
            Default is "SQU".
        frequency : float, optional
            Pulse rate frequency in Hertz, which can take values from 0.1 Hz to 10 MHz.
            Default is 1e3.
        """
        if PulseMod is False:
            self.write(":SOUR:PULM:STAT OFF")
        else:
            self.write(":SOUR:PULM:STAT ON")
            self.write(f":SOUR:PULM:SOUR {pulseSource}")
            self.write(f":SOUR:PULM:SOUR:INT {pulseInput}")
            self.write(f":SOUR:PULM:INT:FREQ {frequency:g}")

    @synchronized
    def readFreq(self):
        """
        Read the frequency parameter from the PSG.

        Returns
        -------
        float
            The output frequency in Hz.
        """
        self.write(":FREQ?")
        freq = float(self.read())
        return freq

    @synchronized
    def setSourcePower(self, power):
        """
        Configure the PSG output power.

        Parameters
        ----------
        power : float
            Power in dBm (setpoint between +25 and -20 dBm).
        """
        self.write(f":POW {power} dBm")

    @synchronized
    def getSourcePower(self):
        """
        Get the PSG output power.

        Returns
        -------
        str
            Power in dBm.
        """
        power = self.query(":POW?")
        return power

    @synchronized
    def trigger(self):
        """
        Trigger the sweep(s).

        Notes
        -----
        The function will wait for the sweep to complete before returning.
        """
        # get number of points and sweep time for timeout estimation
        n_points = float(self.query(":SOUR:SWE:POIN?"))
        sweep_time = float(self.query(":SOUR:SWE:TIME?"))

        self.write(":ABOR")
        # estimate of sweep time by VNA + 1ms for frequency change
        self.connection.timeout = 1e3 * sweep_time + n_points + 10e3
        self.write("INIT:IMM")
        self.query("*OPC?")
        # reset timeout to default
        self.connection.timeout = self.timeout

    @synchronized
    def configureSweep(self, fStart, fStop, fPoints, stepDwell):
        """
        Change the sweep settings in the given channel.

        Frequency units are in Hz. 'MIN'/'MAX' arguments can be used instead of actual numbers,
        and use the highest/lowest setting the device is capable of.

        Parameters
        ----------
        fStart : int or float
            The frequency at which the sweep starts.
        fStop : int or float
            The frequency at which the sweep ends.
        fPoints : int or str
            The number of points per sweep. Can be an integer or 'MIN'/'MAX'.
        stepDwell : int or float
            The dwell time for a step sweep.

        Notes
        -----
        This method configures the device for step sweeping with automatic sweep timing.
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
        Configure the PSG to output a wave with a constant frequency.

        Parameters
        ----------
        freq : int, float, or str
            The frequency in Hz. Can be a number or 'MIN'/'MAX'.
        """
        self.write(":FREQ:MODE CW")  # set frequency mode
        self.write(f":FREQ {freq}Hz")
        self.write(":OUTPUT ON")

    @synchronized
    def output(self, state):
        """
        Set the output state of the PSG.

        Parameters
        ----------
        state : bool
            If True, enable the output. If False, disable the output.
        """
        if state is True:
            self.write(":OUTP ON")
            return
        self.write(":OUTP OFF")

    @synchronized
    def startSweep(self):
        """
        Prepare the PSG for triggering a sweep.

        The PSG activates the output, disables the continuous trigger
        and therefore enables manual triggering. Any currently running
        sweeps are aborted.
        """
        self.output(True)
        # INITiate:CONTinuous <boolean> Trigger source to manual
        self.write(":INIT:CONT OFF")
        self.write(":ABOR")

    @synchronized
    def stopSweep(self):
        """Turn the PSG output off."""
        self.output(False)

    @synchronized
    def readSweepParams(self):
        """
        Read the sweep parameters from the device.

        Frequencies are returned in Hz.

        Returns
        -------
        tuple
            A tuple containing (fStart, fStop) where:
            - fStart (float): The frequency at which the sweep starts.
            - fStop (float): The frequency at which the sweep stops.
        """
        fStart = float(self.query(":FREQ:STAR?"))
        fStop = float(self.query(":FREQ:STOP?"))
        return fStart, fStop
