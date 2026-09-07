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
"""Module for interfacing with the Agilent PSA E4440A spectrum analyzer."""

from struct import unpack
from typing import ClassVar

import numpy as np
from wrapt import synchronized

from matr1x.devices.visadevice import VisaDevice


class PSA_E4440A(VisaDevice):
    """
    The device class for the Agilent PSA E4440A - Spectrum Analyzer.

    It can possibly be used with different models with little changes.
    """

    config_params: ClassVar[dict[str, str]] = {
        "vidBW": "BAND:VID?",
        "resBW": "BAND?",
        "average": "AVER:STAT?",
        "naverage": "AVERage:COUNt?",
    }
    maxAverage = 1
    """
    The maximum average setting of all configured channels.

    The PSA will trigger that many sweeps, so the averaging requirement
    for each channel is satisfied.
    """

    def __init__(self, interface, reset=True, timeout=10e3, **kwargs):
        """
        Initialize the device.

        Parameters
        ----------
        interface : str
            The IP address and port where the device is located.
            e.g. TCPIP::192.168.5.52::5025::SOCKET
        reset : bool, optional
            If true, the PSA is reset on object creation using the reset method.
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
        """
        Reset the PSA using the SYST:PRES command.

        Note that this does not reset the data transfer format! Use *RST
        for this.
        """
        self.write("SYST:PRES:TYPE MODE")
        self.write("SYST:PRES")  # SYSTem:PRESet
        self.write("CAL:AUTO ON")
        self.maxAverage = 1

    @synchronized
    def configureSweep(
        self,
        fCent,
        fSpan,
        fPoints,
        refLev,
        resBW,
        vidBW,
        average=None,
        avgType="rms",
        scale="log",
        getData=False,
    ):
        """
        Configure sweep settings for the spectrum analyzer.

        Sets frequency, bandwidth, averaging, and display parameters.
        Frequency units are in Hz.
        'MIN'/'MAX' arguments can be used instead of actual numbers,
        and use the highest/lowest setting the PSA is capable of.

        Parameters
        ----------
        fCent : float
            The center frequency of the sweep in Hz.
        fSpan : float
            The frequency span of the sweep in Hz.
        fPoints : int
            The number of points per sweep.
        refLev : float
            The reference level for the display in dBm.
        resBW : float
            The resolution bandwidth in Hz.
        vidBW : float
            The video bandwidth in Hz.
        average : int, optional
            The number of averages which make up the final values.
            Default is None (no averaging).
        avgType : {'rms', 'log', 'scalar'}, optional
            The average type of the measurement.
            'rms': Power (RMS) averaging,
            'log': Log-Power (video) averaging,
            'scalar': Voltage averaging.
            Default is 'rms'.
        scale : {'log', 'lin'}, optional
            The display format of the measurement.
            'lin': linear scale,
            'log': logarithmic scale.
            Default is 'log'.
        getData : bool, optional
            If true, trigger a sweep and return the results directly.
            Default is False.

        Returns
        -------
        numpy.ndarray or None
            The sweep data if getData is True, None otherwise.
        """
        fStop = fCent + (fSpan / 2)
        if fStop > 8e9:
            print("Warning, attempting to set Frequency exceeding 8GHz, returning")  # noqa: T201
            return

        if average:
            if avgType == "rms":
                self.write("AVERage:TYPE RMS")
            elif avgType == "log":
                self.write("AVERage:TYPE LOG")
            elif avgType == "scalar":
                self.write("AVERage:TYPE SCAL")
            else:
                print(f"Please choose a valid average type! Your input was: {avgType!s}")  # noqa: T201
            self.write("AVER:STAT ON")
            self.write(f"AVERage:COUNt {average}")
            self.maxAverage = max(average, self.maxAverage)
        else:
            self.write("AVER:STAT OFF")

        self.write(f"FREQ:CENT {fCent!s} HZ")
        self.write(f"FREQ:SPAN {fSpan!s} HZ")
        self.write(f"SWE:POIN {fPoints!s}")
        self.write(f"BAND:VID {vidBW!s} Hz")
        self.write(f"BAND {resBW!s} Hz")
        self.write(f"DISP:WIND:TRAC:Y:RLEV {refLev!s} dbm")

        if scale == "lin":
            self.write("DISP:WIND:TRAC:Y:SCAL:SPAC LIN")
        elif scale == "log":
            self.write("DISP:WIND:TRAC:Y:SCAL:SPAC LOG")
        else:
            print(f"Please choose a valid scale! Your input was: {scale!s}")  # noqa: T201

        # selects the sweep type automatic mode
        self.write("SWEep:TYPE AUTO")
        # sets the rules for the sweep type auto mode to dynamic range
        self.write("SWE:TYPE:AUTO:RUL DRAN")

        if getData:
            return self.getSweepData()

    @synchronized
    def startSweep(self):
        """
        Prepare the PSA for triggering a sweep.

        The PSA disables the continuous trigger and therefore enables
        manual triggering. Any currently running sweeps are aborted.
        """
        self.write(":ABORT")
        # INITiate:CONTinuous <boolean> Trigger source to manual
        self.write(":INIT:CONT OFF")

    @synchronized
    def trigger(self):
        """
        Trigger a sweep and wait for completion.

        Adjusts the connection timeout based on the sweep parameters to
        ensure the operation completes successfully.
        """
        # get number of points and sweep time for timeout estimation
        n_points = float(self.query(":SWE:POIN?"))
        sweep_time = float(self.query(":SWE:TIME?"))

        # estimate of sweep time by PSA + 1ms for frequency change
        self.connection.timeout = self.maxAverage * (1e3 * sweep_time + n_points) + 120e3
        self.write("INIT:IMM")
        self.query("*OPC?")
        # reset timeout to default
        self.connection.timeout = self.timeout

    @synchronized
    def getData(self, precision="single"):
        """
        Transfer measurement data from the PSA.

        Reads trace data in different formats based on the precision parameter.

        Parameters
        ----------
        precision : {'single', 'double', 'ascii'}, optional
            The data format precision to use:
            'single' and 'double' precisions are transferred as binary data,
            and achieve much faster transfer speeds.
            'ascii' is only implemented as a fallback method, as it is
            much easier to debug.
            Default is 'single'.

        Returns
        -------
        numpy.ndarray
            The measured data from the spectrum analyzer.
        """
        precdict: dict[str, tuple[str, int, str, str]] = {
            "single": ("REAL,32", 4, ">f", "float32"),
            "double": ("REAL,64", 8, ">d", "float64"),
            "ascii": ("ASC,0", 0, "", ""),
        }

        try:
            self.write(f"FORM {precdict[precision][0]}")
        except KeyError:
            print(f"{precision!s} is not a valid precision")  # noqa: T201
            # return
        if precision == "ascii":
            data = self.query("TRAC:DATA? TRACE1")
            return np.fromstring(data, sep=",").transpose()

        byte_width = precdict[precision][1]
        self.write("TRAC:DATA? TRACE1")
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
    def getSweepData(self):
        """
        Prepare, trigger, and get data from a sweep operation.

        This is a convenience method that combines startSweep(), trigger(),
        and getData() operations into a single call.

        Returns
        -------
        numpy.ndarray
            The measured data from the spectrum analyzer.
        """
        self.startSweep()
        self.trigger()
        return self.getData()

    @synchronized
    def readSweepParams(self):
        """
        Read the current sweep parameters from the PSA.

        Queries the center frequency, span, and number of points settings
        and calculates the start/stop frequencies. All frequencies are
        returned in Hz.

        Returns
        -------
        tuple
            A tuple containing (fStart, fStop, fPoints) where:
            - fStart (float): The frequency at which the sweep starts in Hz
            - fStop (float): The frequency at which the sweep stops in Hz
            - fPoints (int): The number of points in the sweep
        """
        self.write("FREQ:CENT?")
        fCent = float(self.read())
        self.write("FREQ:SPAN?")
        fSpan = float(self.read())
        self.write("SWE:POIN?")
        fPoints = int(self.read())
        return fCent - fSpan, fCent + fSpan, fPoints
