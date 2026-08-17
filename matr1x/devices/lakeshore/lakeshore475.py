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
"""Interface for Lakeshore 475 Gaussmeter."""

from matr1x.devices.visadevice import VisaDevice


class Lakeshore475(VisaDevice):
    """
    Class for controlling the Lakeshore 475 Gaussmeter.

    A class to interact with the Lakeshore 475 Gaussmeter, providing
    methods to read field and temperature values, set control
    parameters, configure analog outputs, and control probe settings.
    """

    def __init__(self, interface, **kwargs):
        """
        Initialize the Lakeshore475 device.

        Parameters
        ----------
        interface : str
            VISA resource name for the device
        **kwargs : dict
            Additional keyword arguments for the VISA device
        """
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 2000
        if "cmdpers" not in kwargs:
            kwargs["cmdpers"] = 20
        super().__init__(interface, **kwargs)

    # high level functions
    def getField(self):
        """
        Get the current magnetic field reading.

        Returns
        -------
        float
            Current magnetic field value
        """
        return float(self.query("RDGFIELD?"))

    def getTemp(self):
        """
        Get the current temperature reading.

        Returns
        -------
        float
            Current temperature value
        """
        return float(self.query("RDGTEMP?"))

    def setSetpoint(self, setpoint):
        """
        Set the control setpoint value.

        Parameters
        ----------
        setpoint : float
            The desired setpoint value
        """
        self.write(f"CSETP {float(setpoint):.5f}")

    def readSetpoint(self):
        """
        Read the current control setpoint value.

        Returns
        -------
        float
            Current setpoint value
        """
        return float(self.query("CSETP?"))

    def zeroProbe(self, clear=False):
        """
        Zero the Hall probe or clear the zero setting.

        Parameters
        ----------
        clear : bool, optional
            If True, clears the zero probe setting. If False, zeros the probe.
            Default is False.
        """
        if clear is False:
            self.write("ZPROBE")
        elif clear is True:
            self.write("ZCLEAR")

    def configureAnalogOut(self, voltlimit, lowfield, highfield, bipolar=2, mode=4, manualOut=0):
        """
        Configure analog output of the LS475.

        Note: Function not tested.

        Parameters
        ----------
        voltlimit : int
            Maximum voltage (1 to 10V)
        lowfield : float
            Field value at which the analog output reaches -100% (0%)
        highfield : float
            Field value at which the analog output reaches +100%
        bipolar : int, optional
            Analog output mode: 1 (unipolar) or 2 (bipolar). Default is 2.
        mode : int, optional
            Output mode: 0 (off), 1 (default), 2 (user defined), 3 (manual),
            4 (control). Default is 4.
        manualOut : float, optional
            Manual output value. Default is 0.
        """
        self.write(
            f"ANALOG {mode!s}, {bipolar!s}, {lowfield!s}, "
            f"{highfield!s}, {manualOut:.4f}, {voltlimit!s}"
        )

    def configureControl(self, pValue, iValue, rampRate, maxVSlope, on=False):
        """
        Configure the control mode parameters.

        Note: Function not tested.

        Parameters
        ----------
        pValue : float
            Proportional gain (0.01 to 1000)
        iValue : float
            Integral gain (0.0001 to 1000)
        rampRate : float
            Ramp rate in units/minute (unit is given by measurement unit setting)
        maxVSlope : float
            Maximum rate of voltage output change (0.01 to 1000 V/min)
        on : bool, optional
            If True, configures and turns on the control, otherwise just
            configures. Default is False.
        """
        if on is False:
            self.write("CMODE 0")
        self.write(f"CPARAM {pValue!s}, {iValue!s}, {rampRate!s}, " + f"{maxVSlope!s}")
        if on is True:
            self.write("CMODE 1")

    def configure(self, reset=False, autoRange=True, range_val=None, dcRes=None, fUnit=None):
        """
        Configure LS475 measurement parameters.

        Parameters
        ----------
        reset : bool, optional
            If True, reset the instrument. Default is False.
        autoRange : bool, optional
            If True, enable auto range. Default is True.
        range_val : int, optional
            Range value between 1 and 5, where 1 is the smallest range and 5
            the largest (probe dependent). Default is None.
        dcRes : int, optional
            DC resolution between 1 and 3, where 1 is 3 digits and 3 is 5 digits.
            Default is None.
        fUnit : int, optional
            Field unit: 1 (Gauss), 2 (Tesla), 3 (Oersted), 4 (Amp/meter).
            Default is None.
        """
        if reset is True:
            self.write("*RST")
        if autoRange is True:
            self.write("AUTO 1")
        elif range_val is not None and range_val > 0 and range_val < 6:
            self.write("AUTO 0")
            self.write("RANGE " + str(range_val))
        if dcRes is not None and dcRes > 0 and dcRes < 4:
            self.write("RDGMODE 1," + str(dcRes) + ",1,1,1")
        if fUnit is not None and fUnit > 0 and fUnit < 5:
            self.write("UNIT " + str(fUnit))
