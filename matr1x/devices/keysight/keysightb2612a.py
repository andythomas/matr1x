# This file is part of a software collection for data acquisition (matr1x).
# Copyright (C) 2006-2025 matr1x developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, opr
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Module for controlling Keysight B2961 power supply devices."""

from matr1x.devices.util import strToList
from matr1x.devices.visadevice import VisaDevice


class KeysightB2961(VisaDevice):
    """
    Keysight B2961 DC (and low frequency AC) power supply.

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
        """
        Initialize the KeysightB2961 device.

        Parameters
        ----------
        interface : str
            Communication interface identifier.
        **kwargs : dict
            Additional parameters for the VisaDevice.
        """
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
        Configure the Keysight B2961A to source current/voltage and sense voltage/current.

        Parameters
        ----------
        sourceMode : str, optional
            "VOLT" or "CURR" -- predefined physical parameter.
        senseMode : str, optional
            "VOLT" or "CURR" -- measured parameter.
        fourWire : bool, optional
            Four wire measurement. Use current configuration if None.
        sourceAutoRange : bool, optional
            Autodetect the source range.
        sourceRange : float, optional
            Largest expected source current, device will pick the next inclusive range.
        senseLimit : float, optional
            Source compliance level.
        output : bool, optional
            Turn the output on if True.
        delayAuto : bool, optional
            Automatically choose the delay for stabilizing the output.
        delay : float, optional
            Delay in seconds for stabilizing the output before doing an internal measurement.
            WON'T AFFECT/DELAY OTHER DEVICES! Default: 0.1(s).
        nplc : float, optional
            Number of power line cycles to average (4e-4 to 100).
        reset : bool, optional
            If true, reset the device. Default is False.

        Examples
        --------
        >>> device.configure(fourWire=True, senseAutoRange=True,
        ...                  sourceRange=0.001, output=True)

        The output will initially be turned off during configuration.
        This will configure the device to be in 4W sense mode,
        detect the sense range automatically. The range is chosen to
        include 1mA and the output is turned on.
        """
        # do nothing if sourcemode is not defined
        if sourceMode is None:
            return
        # assert source and sense mode are correct
        assert (sourceMode == "VOLT") or (sourceMode == "CURR"), (
            'source ("'
            + sourceMode
            + '") and/or sense ("'
            + senseMode
            + '") mode are incorrect'
        )
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
            cmdlist.append(
                ":SOUR:{}:PROT {}".format(self.sourceMode, float(senseLimit))
            )

        if nplc is not None:
            cmdlist.append(":SENS:{}:NPLC {}".format(self.sourceMode, float(nplc)))
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
            cmdlist.append(
                ":SOUR:{}:RANG {}".format(self.sourceMode, float(sourceRange))
            )

        cmdlist.append(":FORM:ELEM:SENS VOLT,CURR,SOUR")

        for cmd in cmdlist:
            self.write(cmd)
        self.output(output)

    def output(self, state=False):
        """
        Turn output on or off.

        Parameters
        ----------
        state : bool, optional
            Turn output on if state is True, off when state is False,
            otherwise do nothing. Default is False.
        """
        if state is True:
            self.write(":OUTP ON")
        elif state is False:
            self.write(":OUTP OFF")

    def setSource(self, value):
        """
        Set the output value of the source.

        This happens immediately without changing the source output status.

        Parameters
        ----------
        value : float
            The output value to set.
        """
        cmd = ":SOUR:{} {}".format(self.sourceMode, float(value))
        self.write(cmd)

    def getMeas(self):
        """
        Perform a self triggered measurement and return the values.

        Returns
        -------
        list
            List of measurement values.
        """
        self.write("MEAS?")
        return strToList(self.read())

    def getSource(self):
        """
        Get the current source value.

        Returns
        -------
        float
            The source value.
        """
        self.write("MEAS:{}?".format(self.sourceMode))
        return float(self.read())

    def getSense(self):
        """
        Get the current sense value.

        Returns
        -------
        float
            The sense value.
        """
        self.write("MEAS:{}?".format(self.senseMode))
        return float(self.read())

    def setAcquisitionTriggerMode(self, mode="BUS", count=None):
        """
        Set up the SMU for triggered acquisition of the measurement system.

        Note: the source still has another independent trigger system which is
        not changed by this function!

        Parameters
        ----------
        mode : str, optional
            Trigger mode: AINT (=Automatic), BUS (for use with triggerReading),
            TIMER (for time trace recording). Default is "BUS".
        count : int or str, optional
            Amount of triggers (typically 1 for BUS), allowed are: None,
            integer, or "inf".
        """
        self.write(":TRIG:ACQ:SOUR {}".format(mode))
        if count:
            self.write(":TRIG:ACQ:COUN {}".format(count))

    def triggerReading(self):
        """Send a trigger to trigger a reading when trigger is set to BUS."""
        self.write(":ABOR:ACQ")
        self.write(":INIT:ACQ")
        self.write(":ARM:ACQ")
        self.write("*TRG")

    def getReading(self):
        """
        Fetch measured data after a trigger was sent.

        Returns
        -------
        list
            List of measured values.
        """
        self.write("FETCH?")
        return strToList(self.read())

    def configure_sine(self, amp, freq, offset=0, count="INF", onlysetamp=False):
        """
        Configure for generation of a sine wave.

        Use configure first to set up the sourceMode. Use run_wave after this
        command to actually start the output.

        Note: this function also sets up the phase marker output (mapped to
        EXT1) which can be used as a sync signal for a lockin.

        Parameters
        ----------
        amp : float
            Amplitude of the sine wave.
        freq : float
            Frequency of the sine wave.
        offset : float, optional
            Vertical offset of the sine wave. Default is 0.
        count : str, optional
            Number of sine waves to output. Default is "INF".
        onlysetamp : bool, optional
            Flag to only set a new amplitude and leave the rest unchanged,
            which keeps the output on. Default is False.
        """
        cmdlist = [":ABOR"]

        if onlysetamp:
            cmdlist.append(":SOUR:ARB:{}:SIN:AMPL {}".format(self.sourceMode, amp))
            cmdlist.append(":INIT")
        else:
            cmdlist.append(":OUTP OFF")
            # set sin mode
            cmdlist.append(":SOUR:{}:MODE ARB".format(self.sourceMode))
            cmdlist.append(":SOUR:ARB:FUNC SIN")
            cmdlist.append(
                ":SOUR:ARB:{}:SIN:AMPL {}".format(self.sourceMode, float(amp))
            )
            cmdlist.append(
                ":SOUR:ARB:{}:SIN:FREQ {}".format(self.sourceMode, float(freq))
            )
            cmdlist.append(
                ":SOUR:ARB:{}:SIN:OFFS {}".format(self.sourceMode, float(offset))
            )
            # set number of repetitions
            cmdlist.append(":SOUR:ARB:COUN {}".format(count))
            # set phase marker (trigger/sync) output
            cmdlist.append(":SOUR:ARB:{}:SIN:PMAR:PHAS 0".format(self.sourceMode))
            cmdlist.append(":SOUR:ARB:{}:SIN:PMAR:STAT 1".format(self.sourceMode))
            cmdlist.append(":SOUR:ARB:{}:SIN:PMAR:SIGN ext1".format(self.sourceMode))
            cmdlist.append(":SOUR:DIG:EXT1:FUNC TOUT")
            cmdlist.append(":SOUR:DIG:EXT1:POL POS")
            cmdlist.append(":SOUR:DIG:EXT1:TOUT:WIDT 50e-6")

            # generate triggers for source internally
            cmdlist.append(":TRIG:TRAN:COUN 1")
            cmdlist.append(":TRIG:TRAN:SOUR TIMER")

        for cmd in cmdlist:
            self.write(cmd)

    def run_wave(self):
        """
        Start the waveform output.

        Initializes the waveform generation and turns on the output.
        """
        self.write(":INIT")
        self.output(True)

    def visualize_trace(self, dt=1e-3, points=1000):
        """
        Configure the device for trace visualization.

        Parameters
        ----------
        dt : float, optional
            Time interval between measurements in seconds. Default is 1e-3.
        points : int, optional
            Number of points to acquire. Default is 1000.
        """
        self.setAcquisitionTriggerMode(mode="TIMER", count=points)
        self.write(":TRIG:ACQ:TIM {}".format(dt))
