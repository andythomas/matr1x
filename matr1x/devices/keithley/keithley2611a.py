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
"""
Provides a driver for the Keithley 2611A Source Measure Unit.

This module implements full control of the Keithley 2611A SMU, including
voltage/current sourcing and measurement, range control, and various
sensing configurations.
"""

from typing import ClassVar

from wrapt import synchronized

from matr1x.core.visadevice import VisaDevice


class Keithley2611A(VisaDevice):
    """
    Control interface for Keithley 2611A Source Measure Unit (SMU).

    This class provides methods to control and read data from the Keithley 2611A.
    It supports voltage and current sourcing and sensing in both 2-wire and 4-wire
    configurations.

    Attributes
    ----------
    config_params : dict
        Dictionary of configuration parameters and their corresponding commands
    mode_int : dict
        Mapping of mode strings to numeric values
    mode_char : dict
        Mapping of mode strings to character identifiers used in commands
    """

    config_params: ClassVar[dict[str, str]] = {
        "sourceMode": "print(smua.source.func)",
        "senseMode": "print(smua.sense)",
        "voltageLimit": "print(smua.source.limitv)",
        "currentLimit": "print(smua.source.limiti)",
        "Model-identifing": "*IDN?",
    }
    mode_int: ClassVar[dict[str, int]] = {"VOLT": 1, "CURR": 0}
    mode_char: ClassVar[dict[str, str]] = {"VOLT": "v", "CURR": "i"}

    def __init__(self, interface, **kwargs):
        """
        Initialize the Keithley 2611A instrument.

        Parameters
        ----------
        interface : str
            VISA resource name or other interface identifier
        **kwargs
            Additional arguments passed to the parent VisaDevice class

        Notes
        -----
        Sets default termination characters and initializes the device.
        Reads the initial state including source mode, four-wire setting,
        and output state.
        """
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n"
        super().__init__(interface, **kwargs)
        # after initialization get the source function to determine
        # whether voltage or current is the sourced
        # get the sourceMode 0 -> OUTPUT_DCAMPS (sourceCurrent)
        # 1 -> OUTPUT_DCAMPS (sourceVoltage)
        self.write("print(smua.source.func)")
        # python cannot directly parse float-string to int
        self.sourceModeInt = int(float(self.read()))
        # get fourWire 0 -> senseMode local (2wire)
        # 1 -> senseMode remote (4wire)
        self.write("print(smua.sense)")
        # can't directly pars the output to bool
        self.fourWire = bool(float(self.read()))
        # get output status
        self.write("print(smua.source.output)")
        # can't directly pars the value to int
        self.outputState = int(float(self.read()))

    # high level functions
    @synchronized
    def configure(
        self,
        sourceMode: str | None = None,
        senseMode: str | None = None,
        fourWire: bool | None = None,
        senseAutoRange: bool | None = None,
        senseRange: float | None = None,
        sourceAutoRange: bool | None = None,
        sourceRange: float | None = None,
        senseLimit: float | None = None,
        output: bool = False,
        delayAuto: bool = False,
        delay: bool | float | None = None,
        reset: bool = False,
    ):
        """
        Configure the Keithley 2611A to source and sense parameters.

        Parameters
        ----------
        sourceMode : str, optional
            The parameter to source, either "VOLT" or "CURR"
        senseMode : str, optional
            The parameter to measure, either "VOLT" or "CURR"
        fourWire : bool, optional
            Whether to use four-wire (True) or two-wire (False) sensing
        senseAutoRange : bool, optional
            Whether to automatically set the measurement range
        senseRange : float, optional
            Manual range for measurements, device selects next inclusive range
        sourceAutoRange : bool, optional
            Whether to automatically set the sourcing range
        sourceRange : float, optional
            Manual range for sourcing, device selects next inclusive range
        senseLimit : float, optional
            Voltage or current limit for the sense circuit
        output : bool, default False
            Whether to enable the output after configuration
        delayAuto : bool, default False
            Whether to automatically set the stabilization delay
        delay : float or bool, optional
            Manual delay in seconds for output stabilization, or False to disable
        reset : bool, default False
            Whether to reset the device before configuration

        Returns
        -------
        None

        Notes
        -----
        The output will be turned off during configuration.
        If sourceMode and senseMode are not provided, no configuration is done.

        Examples
        --------
        >>> instrument.configure(sourceMode="CURR", senseMode="VOLT",
                                 fourWire=True, senseAutoRange=True,
                                 sourceRange=0.001, output=True)

        This configures the instrument to source current, measure voltage,
        use 4-wire sensing, automatically set the voltage measurement range,
        set the current sourcing range to include 1mA, and enable the output.
        """
        # do nothing if source/sensemode is not defined
        if sourceMode is None or senseMode is None:
            return
        # assert source and sense mode are correct
        assert (sourceMode == "VOLT" and senseMode == "CURR") or (
            sourceMode == "CURR" and senseMode == "VOLT"
        ), f'source ("{sourceMode}") and/or sense ("{senseMode}") mode are incorrect'
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
        # cmdlist.append(f":SENS:FUNC \"{self.senseMode}\"")
        # check if the last line is necessary for the new smu
        # turn on the readback so we get the actual value and not the setpoint
        # cmdlist.append(f":SOUR:{self.sourceMode}:READ:BACK ON")

        if senseLimit is not None:
            cmdlist.append(
                f"smua.source.limit{self.mode_char[self.senseMode]}={float(senseLimit)}"
            )

        if fourWire is True:
            cmdlist.append("smua.sense=smua.SENSE_REMOTE")
        elif fourWire is False:
            cmdlist.append("smua.sense=smua.SENSE_LOCAL")

        if senseAutoRange is True:
            cmdlist.append(
                f"smua.measure.autorange{self.mode_char[self.senseMode]}=smua.AUTORANGE_ON"
            )
        elif senseRange is not None:
            cmdlist.append(
                f"smua.measure.autorange{self.mode_char[self.senseMode]}=smua.AUTORANGE_OFF"
            )
            cmdlist.append(
                f"smua.measure.range{self.mode_char[self.senseMode]}={float(senseRange)}"
            )

        if sourceAutoRange is True:
            cmdlist.append(
                f"smua.source.autorange{self.mode_char[self.sourceMode]}=smua.AUTORANGE_ON"
            )
        elif sourceRange is not None:
            cmdlist.append(
                f"smua.source.autorange{self.mode_char[self.sourceMode]}=smua.AUTORANGE_OFF"
            )
            cmdlist.append(
                f"smua.source.range{self.mode_char[self.sourceMode]}={float(sourceRange)}"
            )

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
        """
        Control the output state of the instrument.

        Parameters
        ----------
        state : bool, default False
            True to enable the output, False to disable

        Returns
        -------
        None
        """
        if state is True:
            self.write("smua.source.output=smua.OUTPUT_ON")
        elif state is False:
            self.write("smua.source.output=smua.OUTPUT_OFF")

    def setSource(self, current):
        """
        Set the source level.

        Parameters
        ----------
        current : float
            The value to set the source to (can be voltage or current
            depending on configured sourceMode)

        Returns
        -------
        None
        """
        cmd = f"smua.source.level{self.mode_char[self.sourceMode]}={float(current)}"
        self.write(cmd)

    def getSource(self):
        """
        Get the measured source value.

        Returns
        -------
        float
            The measured source value (voltage or current depending on
            configured sourceMode)
        """
        return float(
            self.query(f"print(smua.measure.{self.mode_char[self.sourceMode]}(smua.nvbuffer1))")
        )

    def getSense(self):
        """
        Get the measured sense value.

        Returns
        -------
        float
            The measured sense value (voltage or current depending on
            configured senseMode)
        """
        return float(
            self.query(f"print(smua.measure.{self.mode_char[self.senseMode]}(smua.nvbuffer1))")
        )
