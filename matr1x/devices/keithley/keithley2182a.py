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
"""Module providing the Keithley2182A nanovoltmeter interface."""

import logging
from typing import ClassVar

from wrapt import synchronized

from matr1x.devices.visadevice import VisaDevice

logger = logging.getLogger(__name__)


class Keithley2182A(VisaDevice):
    """
    Keithley2182A nanovoltmeter instrument driver.

    This class provides methods to control and interface with a Keithley 2182A
    nanovoltmeter over a VISA connection.

    Parameters
    ----------
    interface : str
        VISA resource name for connecting to the instrument
    **kwargs : dict
        Additional parameters to pass to the VISA connection

    Attributes
    ----------
    config_params : dict
        Dictionary of common configuration parameter queries
    triggered : bool
        Flag indicating if a measurement has been triggered
    interface : str
        The VISA resource name used for this connection
    """

    config_params: ClassVar[dict[str, str]] = {
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
        self.interface = interface
        try:  # will fail if pyvisa connection does not support clear()
            self.connection.clear()
        except Exception:
            logger.debug("Could not clear the instrument connection", exc_info=True)

    def query(self, *args, **kwargs):
        """
        Send a query to the instrument and return the response.

        This method overrides the parent class query method.

        Parameters
        ----------
        *args : tuple
            Variable length argument list to pass to the parent query method
        **kwargs : dict
            Arbitrary keyword arguments to pass to the parent query method

        Returns
        -------
        str
            The response from the instrument
        """
        return super().query(*args, **kwargs)

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
        Configure the Keithley 2182A to detect voltages.

        Parameters
        ----------
        digits : int, optional
            Number of digits to display (4-8)
        count : int, optional
            Filter count for the digital filter
        window : float, optional
            Filter window for the digital filter
        NPLC : int or float, optional
            Number of power line cycles to integrate over
        dFil : bool, optional
            If True, turn on the digital filter. If False, window and filter count are ignored
        voltage_range : float, optional
            Range of the voltage detection. Selected by the instrument to include the value
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
        cmdList = []
        if reset is True:
            self.write("*RST")
            self.query("*OPC?")
        else:
            # make sure the device is in the idle state
            self.write(":ABOR")

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
            self.query("*OPC?")
            self.write(cmd)

    def triggerReading(self):
        """
        Trigger a measurement reading on the instrument.

        Sets the triggered flag to True after a trigger has been sent.
        This prevents multiple triggers from being sent before a reading
        is retrieved.

        Returns
        -------
        None
        """
        if self.triggered is False:
            self.write("*TRG")
            self.triggered = True

    def getReading(self):
        """
        Get the most recent reading from the instrument.

        This method should be called after triggering a reading with
        triggerReading(). Resets the triggered flag to False after
        retrieving the reading.

        Returns
        -------
        float
            The measured voltage value

        Notes
        -----
        Returns None if no reading has been triggered.
        """
        if self.triggered is True:
            result = self.query(":SENS:DATA:FRES?")
            self.triggered = False
            return float(result)
