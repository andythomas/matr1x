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
"""Driver for Agilent 8114A High Power Pulse Generator."""

import time

import numpy as np

from matr1x.devices.visadevice import VisaDevice


class Agilent8114A(VisaDevice):
    """
    Driver for Agilent 8114A High Power Pulse Generator.

    Manual can be found here:
    https://www.keysight.com/us/en/assets/9018-05116/user-manuals/9018-05116.pdf
    """

    config_params = {}

    def __init__(self, interface, **kwargs):
        """
        Initialize the Agilent 8114A High Power Pulse Generator.

        Parameters
        ----------
        interface : str
            VISA resource name or interface identifier
        **kwargs : dict
            Additional keyword arguments to pass to the VisaDevice constructor
        """
        self.local = False
        self.output = False
        self.voltage = 0
        self.offset = 0
        self.imp_int = 0
        self.imp_ext = 0
        self.polarity = 0
        self.period = 0
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r"
        super().__init__(interface, **kwargs)
        # after initialization get the source function to determine
        # whether voltage or current is the sourced

    # high level functions
    def reset(self):
        """Reset instrument to factory details."""
        self.write("*RST")

    def display_state(self, display):
        """
        Set display state on or off.

        Parameters
        ----------
        display : bool
            True to turn display on, False to turn it off
        """
        if display:
            self.write("DISP ON")
        else:
            self.write("DISP OFF")

    def set_output(self, output):
        """
        Enable or disable output.

        Parameters
        ----------
        output : bool
            True to enable output, False to disable
        """
        if output:
            self.write("OUTP ON")
            self.output = True
        else:
            self.write("OUTP OFF")
            self.output = False

    def last_button(self):
        """
        Return the last pressed button.

        Returns
        -------
        str
            Identifier of the last pressed button
        """
        return self.query("SYST:KEY?")

    def set_imp_int(self, imp):
        """
        Set impedance of input, can be 50 Ohm or 100 Ohm.

        Parameters
        ----------
        imp : bool
            True for 50 Ohm, False for 100 Ohm
        """
        if imp:
            self.write("OUTP:IMP 50 OHM")
            self.imp_int = 50
        else:
            self.write("OUTP:IMP 100 OHM")
            self.imp_int = 100

    def set_imp_ext(self, imp):
        """
        Set impedance of output.

        Disables the output for the setting and reenables if output was on
        before command was called.

        Parameters
        ----------
        imp : float
            Output impedance in Ohm, valid range is 0.1 to 999e3 Ohm
        """
        store = self.output
        if store:
            self.set_output(False)
        if imp > 0.1 and imp < 999e3:
            self.write(f"OUTP:IMP:EXT {imp:.1f} OHM")
        else:
            self.write("OUTP:IMP:EXT 50 OHM")
            imp = 50
        if store:
            self.set_output(True)
        self.imp_ext = imp

    def set_polarity(self, polarity):
        """
        Set pulse voltage polarity.

        Parameters
        ----------
        polarity : float
            Should not be 0. Positive polarity for values larger than 0,
            negative polarity for values smaller than 0
        """
        if polarity > 0:
            self.write("OUTP:POL POS")
        elif polarity < 0:
            self.write("OUTP:POL NEG")
        self.polarity = np.sign(polarity)

    def set_voltage(self, voltage):
        """
        Set peak pulse voltage.

        Parameters
        ----------
        voltage : float
            Peak voltage in volts, valid range is 1 to 100 V
        """
        if voltage >= 1 and voltage <= 100:
            self.write("HOLD VOLT ")
            self.write(f"VOLT {voltage:.3f} V")
            self.voltage = voltage

    def set_voltage_offset(self, voltage):
        """
        Set voltage offset in volt.

        Parameters
        ----------
        voltage : float
            Voltage offset in volts, valid range is -25 to 25 V
        """
        if abs(voltage) <= 25:
            self.write("HOLD VOLT ")
            self.write(f"VOLT:BAS {voltage:.3f} V")
            self.offset = voltage

    def set_period(self, period):
        """
        Set pulse period.

        Parameters
        ----------
        period : float
            Pulse period in nanoseconds, valid range is 66.7 ns to 999 ms
        """
        if period > 66.6:
            self.write(f"PULS:PER {period:.1f} NS")
            self.period = period

    def set_width(self, width):
        """
        Set pulse width.

        Parameters
        ----------
        width : float
            Pulse width in nanoseconds, valid range is 10 ns to 949 ms
        """
        if width >= 10 and width < 949e6:
            self.write(f"PULS:WIDT {width:.0f} ns")
            self.width = width

    def set_duty(self, duty):
        """
        Set duty cycle.

        The pulse width is calculated as width = duty/100*period.

        Parameters
        ----------
        duty : float
            Duty cycle in percent, valid range is 0.1% to 99.9%
        """
        if duty > 0.1 and duty < 99.9:
            self.write(f"PULSE:DCYC {duty:.1f} PCT")

    def set_duty_lim(self, lim):
        """
        Specify maximum duty cycle.

        Parameters
        ----------
        lim : float
            Maximum duty cycle in percent
        """
        self.write(f"PULSE:LIM:DCYC {lim:.1f} PCT")

    def set_num(self, count):
        """
        Specify number of pulses to be sent.

        Parameters
        ----------
        count : int
            Number of pulses to be sent
        """
        self.write(f"TRIG:COUN {int(count):d}")
        self.write("PULS:DOUB OFF")

    def control(self, state):
        """
        Set control state to local or remote.

        Parameters
        ----------
        state : str
            Either "loc" for local control or "rem" for remote control
        """
        if state == "loc":
            self.write("SYST:KEY 19")
            self.local = True
        elif state == "rem":
            self.local = False

    def set_trigger(self, trig):
        """
        Set trigger mode for the pulse generator.

        Different trigger modes are available:
        - continuous: Start with output = 1
        - external/edge/positive slope
        - manual trigger: Will be used with the start_pulsing() function.
          It replaces MAN Key button.

        Parameters
        ----------
        trig : str
            One of "continuous", "triggered external", "triggered edge",
            "triggered positive", "triggered manually"
        """
        if trig == "continuous":
            self.write("TRIG:SOUR IMM")
        elif trig == "triggered external":
            self.write("TRIG:SOUR EXT")
        elif trig == "triggered edge":
            self.write("TRIG:SENS EDGE")
        elif trig == "triggered positive":
            self.write("TRIG:SLOP POS")
        elif trig == "triggered manually":
            self.write("TRIG:SOUR MAN")

    def start_pulsing(self):
        """
        Start pulsing operation.

        Initiates the pulse generation according to the configured
        settings.
        """
        if self.local is True:
            self.control("loc")

        if self.output is False:
            self.write("SYST:KEY 19")
            self.write("SYST:KEY 0")
            self.set_output(True)

        self.write("SYST:KEY 16")
        time.sleep(0.1)

    def configure(self, p_amp, p_offset, p_width, p_period, p_count, dut_imp):
        """
        Configure the Agilent 8114A with common settings.

        This is a utility function to quickly set up the most common parameters.

        Parameters
        ----------
        p_amp : float
            Pulse amplitude in volts
        p_offset : float
            Pulse offset in volts
        p_width : float
            Pulse width in nanoseconds
        p_period : float
            Pulse period in nanoseconds
        p_count : int
            Number of pulses to generate
        dut_imp : float
            Impedance of device under test in ohms
        """
        self.reset()
        time.sleep(0.1)

        self.set_voltage(abs(p_amp))
        self.set_voltage_offset(p_offset)
        self.set_period(p_period)

        self.set_width(p_width)
        self.set_num(p_count)
        self.set_polarity(p_amp)
        self.set_trigger("triggered manually")
        self.set_imp_ext(dut_imp)
