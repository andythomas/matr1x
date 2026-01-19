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
"""Module for controlling Keithley 2400 and 2450 source measurement units."""

from wrapt import synchronized

from matr1x.devices.visadevice import VisaDevice


class Keithley2400(VisaDevice):
    """
    Class for controlling Keithley 2400 SourceMeter.

    This class provides methods to configure and control the Keithley
    2400 source measurement unit for various sourcing and measurement
    operations.
    """

    config_params = {"sourceMode": "sourceMode", "senseMode": "senseMode"}

    def __init__(self, interface, **kwargs):
        """
        Initialize the Keithley 2400 SourceMeter.

        Parameters
        ----------
        interface : str
            VISA resource name for the instrument
        **kwargs : dict
            Additional arguments to pass to the VISA device initialization
        """
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

    def read(self, nbytes=None):
        """
        Read data from the instrument, removing any control characters.

        Parameters
        ----------
        nbytes : int, optional
            Number of bytes to read

        Returns
        -------
        str
            Response from the instrument with control characters removed
        """
        return super().read(nbytes).replace("\x13", "")

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
        Configure the Keithley 2400.

        Parameters
        ----------
        sourceMode : str, optional
            "VOLT" or "CURR", predefined physical parameter to source
        senseMode : str, optional
            "VOLT" or "CURR", parameter to measure
        fourWire : bool, optional
            Four wire measurement. Default: None (use current configuration)
        senseAutoRange : bool, optional
            Autodetect the sense range. Default: None
        senseRange : float, optional
            Largest expected measurement value, device will
            pick the next inclusive range. Default: None
        sourceAutoRange : bool, optional
            Autodetect the source range. Default: None
        sourceRange : float, optional
            Largest expected source current, device will
            pick the next inclusive range. Default: None
        senseLimit : float, optional
            Voltage limit. Default: 10V
        output : bool, optional
            Turn the output on. Default: None
        delayAuto : bool, optional
            Automatically choose the delay for stabilizing
            the output. Default: None
        delay : float, optional
            Delay in seconds for stabilizing the output before
            doing an internal measurement. WON'T AFFECT/DELAY
            OTHER DEVICES! Default: 0.1(s)
        reset : bool, optional
            If true, reset the device. Default: False

        Examples
        --------
        >>> device.configure(sourceMode="CURR", senseMode="VOLT",
        ...                 fourWire=True, senseAutoRange=True,
        ...                 sourceRange=0.001, output=True)

        Notes
        -----
        The output will initially be turned off during configuration.
        This will configure the Keithley to be in 4W sense mode,
        detect the sense range automatically. The range is chosen to
        include 1mA and the output is turned on.
        """
        # do nothing if source/sensemode is not defined
        if sourceMode is None or senseMode is None:
            return
        # assert source and sense mode are correct
        assert (sourceMode == "VOLT" and senseMode == "CURR") or (
            sourceMode == "CURR" and senseMode == "VOLT"
        ), 'source ("' + sourceMode + '") and/or sense ("' + senseMode + '") mode are incorrect'
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
            cmdlist.append(":SENS:" + senseMode + ":RANG " + str(float(senseRange)))

        if sourceAutoRange is True:
            cmdlist.append(":SOUR:" + sourceMode + ":RANG:AUTO ON")
        elif sourceRange is not None:
            cmdlist.append(":SOUR:" + sourceMode + ":RANG:AUTO OFF")
            cmdlist.append(":SOUR:" + sourceMode + ":RANG " + str(float(sourceRange)))

        if senseLimit is not None:
            cmdlist.append(":SENS:" + senseMode + ":PROT:LEV " + str(float(senseLimit)))

        for cmd in cmdlist:
            self.write(cmd)
        # if self.outputState != bool(output):
        self.output(output)

    def output(self, state=False):
        """
        Set the output state of the instrument.

        Parameters
        ----------
        state : bool, optional
            Turn output on (True) or off (False). Default: False
        """
        if bool(state) is True:
            self.write(":OUTP:STAT ON")
            self.outputState = True
        elif bool(state) is False:
            self.write(":OUTP:STAT OFF")
            self.outputState = False

    def setSource(self, current):
        """
        Set the source value.

        Parameters
        ----------
        current : float
            The value to set for the source, either voltage or current depending on the source mode
        """
        cmd = ":SOUR:" + self.sourceMode + ":LEV " + str(current)
        self.write(cmd)

    def getSource(self):
        """
        Get the current source value from the instrument.

        Returns
        -------
        float
            The measured source value
        """
        self.write("READ?")
        return float(self.read().split(",")[1])

    def getSense(self):
        """
        Get the current sense value from the instrument.

        Returns
        -------
        float
            The measured sense value
        """
        self.write("READ?")
        res = self.read().split(",")[0]
        return float(res)


class Keithley2450(VisaDevice):
    """
    Class for controlling Keithley 2450 SourceMeter.

    This class provides methods to configure and control the Keithley
    2450 source measurement unit for various sourcing and measurement
    operations.
    """

    config_params = {"sourceMode": "sourceMode", "senseMode": "senseMode"}

    def __init__(self, interface, **kwargs):
        """
        Initialize the Keithley 2450 SourceMeter.

        Parameters
        ----------
        interface : str
            VISA resource name for the instrument
        **kwargs : dict
            Additional arguments to pass to the VISA device initialization
        """
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n"
        super().__init__(interface, **kwargs)
        # ignore telnet commands sent by the instrument
        # after initialization get the source function to determine
        # whether voltage or current is the sourced

        self.sourceMode = self.query(":SOUR:FUNC?")
        self.senseMode = self.query(":SENS:FUNC?")
        self.outputState = bool(int(self.query(":OUTP?")))

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
        Configure the Keithley 2450 to source current and sense voltage.

        Parameters
        ----------
        sourceMode : str, optional
            "VOLT" or "CURR", predefined physical parameter to source
        senseMode : str, optional
            "VOLT" or "CURR", parameter to measure
        fourWire : bool, optional
            Four wire measurement. Default: None (use current configuration)
        senseAutoRange : bool, optional
            Autodetect the sense range. Default: None
        senseRange : float, optional
            Largest expected measurement value, device will
            pick the next inclusive range. Default: None
        sourceAutoRange : bool, optional
            Autodetect the source range. Default: None
        sourceRange : float, optional
            Largest expected source current, device will
            pick the next inclusive range. Default: None
        senseLimit : float, optional
            Voltage limit. Default: None
        output : bool, optional
            Turn the output on. Default: None
        delayAuto : bool, optional
            Automatically choose the delay for stabilizing
            the output. Default: None
        delay : float, optional
            Delay in seconds for stabilizing the output before
            doing an internal measurement. WON'T AFFECT/DELAY
            OTHER DEVICES! Default: 0.1(s)
        resetUnits : bool, optional
            If true, Ampere and Volt are restored as default unit for
            current and voltage measurements. Default: True
        reset : bool, optional
            If true, reset the device. Default: False

        Examples
        --------
        >>> device.configure(sourceMode="CURR", senseMode="VOLT",
        ...                 fourWire=True, senseAutoRange=True,
        ...                 sourceRange=0.001, output=True)

        Notes
        -----
        The output will initially be turned off during configuration.
        This will configure the Keithley to be in 4W sense mode,
        detect the sense range automatically. The range is chosen to
        include 1mA and the output is turned on.
        """
        # do nothing if source/sensemode is not defined
        if sourceMode is None or senseMode is None:
            return
        # assert source and sense mode are correct
        assert (sourceMode == "VOLT" and senseMode == "CURR") or (
            sourceMode == "CURR" and senseMode == "VOLT"
        ), 'source ("' + sourceMode + '") and/or sense ("' + senseMode + '") mode are incorrect'
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
        cmdlist.append(f":SOUR:FUNC {self.sourceMode}")
        cmdlist.append(f':SENS:FUNC "{self.senseMode}"')
        # reset units to amp/volt to avoid unintentional reading of\
        # resistance
        if resetUnits:
            cmdlist.append(":SENS:CURR:UNIT AMP")
            cmdlist.append(":SENS:VOLT:UNIT VOLT")
        # turn on the readback so we get the actual value and not the setpoint
        cmdlist.append(f":SOUR:{self.sourceMode}:READ:BACK ON")

        if senseLimit is not None:
            cmdlist.append(
                f":SOUR:{self.sourceMode}:{limDef[self.senseMode]}LIM {float(senseLimit)}"
            )
        if delayAuto is True:
            cmdlist.append(f":SOUR:{self.sourceMode}:DEL:AUTO ON")
        elif delay is not None:
            cmdlist.append(f":SOUR:{self.sourceMode}:DEL:AUTO OFF")
            cmdlist.append(f":SOUR:{self.sourceMode}:DEL {float(delay)}")

        if fourWire is True:
            cmdlist.append(f":SENS:{self.senseMode}:RSEN ON")
        elif fourWire is False:
            cmdlist.append(f":SENS:{self.senseMode}:RSEN OFF")

        if senseAutoRange is True:
            cmdlist.append(f":SENS:{self.senseMode}:RANG:AUTO ON")
        elif senseRange is not None:
            cmdlist.append(f":SENS:{self.senseMode}:RANG:AUTO OFF")
            cmdlist.append(f":SENS:{self.senseMode}:RANG {float(senseRange)}")

        if sourceAutoRange is True:
            cmdlist.append(f":SOUR:{self.sourceMode}:RANG:AUTO ON")
        elif sourceRange is not None:
            cmdlist.append(f":SOUR:{self.sourceMode}:RANG:AUTO OFF")
            cmdlist.append(f":SOUR:{self.sourceMode}:RANG {float(sourceRange)}")

        for cmd in cmdlist:
            self.write(cmd)
        self.output(output)

    def output(self, state=False):
        """
        Set the output state of the instrument.

        Parameters
        ----------
        state : bool, optional
            Turn output on (True) or off (False). Default: False
        """
        if state is True:
            self.write(":OUTP ON")
            self.outputState = True
        elif state is False:
            self.write(":OUTP OFF")
            self.outputState = False

    def setSource(self, current):
        """
        Set the source value.

        Parameters
        ----------
        current : float
            The value to set for the source, either voltage or current depending on the source mode
        """
        cmd = ":SOUR:" + self.sourceMode + " " + str(current)
        self.write(cmd)

    def getSource(self):
        """
        Get the current source value from the instrument.

        Returns
        -------
        float
            The measured source value
        """
        return float(self.query('READ? "defbuffer1", SOUR'))

    def getSense(self):
        """
        Get the current sense value from the instrument.

        Returns
        -------
        float
            The measured sense value
        """
        return float(self.query("READ?"))
