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
"""Module for controlling PicoVNA Vector Network Analyzer instruments."""

from struct import iter_unpack

from numpy import argmin, array, fromstring

from matr1x.devices.visadevice import VisaDevice


class PicoVNA(VisaDevice):
    """
    Driver for PicoVNA Vector Network Analyzer instruments.

    This class provides control and data acquisition capabilities for
    PicoVNA instruments using the VISA communication protocol.
    """

    # danfysik power supply driver
    maxAverage = 1

    def __init__(self, interface, reset=False, **kwargs):
        """
        Initialize the PicoVNA instrument.

        Parameters
        ----------
        interface : str
            VISA resource name or interface identifier.
        reset : bool, optional
            If True, reset the instrument during initialization.
            Default is False.
        **kwargs
            Additional arguments to pass to the VisaDevice constructor.
            If not provided, default values are set for write_termination,
            read_termination, and timeout.
        """
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n"
        if "timeout" not in kwargs:
            kwargs["timeout"] = 600000

        if reset:
            self.reset()

        super().__init__(interface, **kwargs)

    # high level functions
    def reset(self):
        r"""
        Reset the VNA using the SYST:FPRESET command.

        Note that this does not reset the data transfer format! Use
        \*RST for this
        """
        self.query("SYST:FPRESET")  # system:fpreset
        self.maxAverage = 1

    def configureSweep(self, fStart, fEnd, fPoints, if_bw, average=None):
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
        average : int, optional
            The number of averages which make up the final values.
            Default is None.
        """
        if average:
            # SENSe<cnum>:AVERage
            self.query("CALC:AVER ON")
            # SENSe<cnum>:AVERage:COUNt <num>
            self.query(f"CALC:AVER:COUNT {int(average)}")
            self.maxAverage = max(average, self.maxAverage)
        else:
            self.query("CALC:AVER OFF")

        # SENSe<cnum>:FREQuency:STARt <num>
        self.query(f"SENS:FREQ:STAR {str(fStart)} Hz")
        # SENSe<cnum>:FREQuency:STOP <num>
        self.query(f"SENS:FREQ:STOP {str(fEnd)} Hz")
        # SENSe<cnum>:SWEep:POINts <num>
        self.query(f"SENS:SWE:POIN {str(fPoints)}")
        # SENSe<cnum>:BWIDth
        possible_bandwidths = array(
            [10, 50, 100, 500, 1000, 5000, 10000, 15000, 35000, 70000, 140000]
        )
        ind = argmin(abs(possible_bandwidths - if_bw))
        self.query(f"SENS:BAND {possible_bandwidths[ind]} Hz")

    def setSourcePower(self, power, channel=1):
        """
        Configure the VNA output power (setpoint between +5 and -30dbm).

        Parameters
        ----------
        power : int
            Power in dbm.
        channel : int, optional
            Channel number. Default is 1.
        """
        self.query(f"SENS:LEV {int(power):d}")

    def getSourcePower(self):
        """
        Read the VNA output power.

        Returns
        -------
        float
            Power in dbm.
        """
        return float(self.query("SENS:LEV?").replace(" dBm", ""))

    def startSweep(self):
        """
        Activate the VNA output and enable manual triggering.

        The VNA activates the output, disables the continuous trigger
        and therefore enables manual triggering. Any currently running
        sweeps are aborted.
        """
        self.query("INIT")

    def getComplexData(self, param, precision="double"):
        """
        Transfer mesurement data from the VNA.

        Parameters
        ----------
        param : str
            The parameter to retrieve from the VNA.
        precision : {'single', 'double', 'ascii'}, optional
            Precision of the data transfer.
            'single' and 'double' precisions are transferd as binary data,
            and achive much faster transfer speeds.
            'ascii' is only implemented as a fallback method, as it is
            much easier to debug.
            Default is 'double'.

        Returns
        -------
        numpy.ndarray
            The measured data from the specified channel.
        """
        precdict: dict[str, tuple[str, int, str, str]] = {
            "single": ("REAL,32", 4, ">f", "float32"),
            "double": ("REAL,64", 8, ">d", "float64"),
            "ascii": ("ASC,0", 0, "", ""),
        }

        if precision == "ascii":
            data = self.query(f"CALC:DATA {param},POLAR")
            return fromstring(data, sep=",").transpose()

        n_points = self.readSweepParams()[2]
        byte_width = precdict[precision][1]

        self.write(f"CALC:DATA {param},POLAR")
        data = self.read(2 * n_points * byte_width)
        data = array(list(iter_unpack(">d", data)), dtype=precdict[precision][3]).ravel()
        self.read()  # clear EOL character
        return data.reshape((-1, 2)).transpose()

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
        fStart = float(self.query("SENS:FREQ:STAR?").replace(" Hz", ""))
        fStop = float(self.query("SENS:FREQ:STOP?").replace(" Hz", ""))
        fPoints = int(self.query("SENS:SWE:POIN?").replace(" Hz", ""))
        return fStart, fStop, fPoints
