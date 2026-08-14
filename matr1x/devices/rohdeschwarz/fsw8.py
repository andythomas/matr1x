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
"""Module for controlling the Rohde & Schwarz FSW8 spectrum analyzer."""

from struct import unpack
from typing import Literal

import numpy as np
from wrapt import synchronized

from matr1x.devices.visadevice import VisaDevice


class FSW8(VisaDevice):
    """
    The device class for the Rohde & Schwarz FSW8 spectrum analyzer.

    It can possibly be used with different models with little changes.
    """

    config_params = {
        "n_points": "SWE:POIN?",
        "resBW_Hz": "BWID:RES?",
        "vidBW_Hz": "BWID:VID?",
        "refLev_dBm": "DISP:TRAC:Y:RLEV?",
        "intPreamp_status": "INP:GAIN:STAT?",
        "intPreamp_value_dB": "INP:GAIN:VAL?",
        "average_status": "AVER:STAT?",
        "average_type": "AVER:TYPE?",
        "n_average": "AVERage:COUNt?",
        "attenuation_auto_status": "INP:ATT:AUTO?",
        "attenuation_value_dB": "INP:ATT?",
        "sweep_type": "SWE:TYPE?",
        "sweep_time_s": "SWE:TIME?",
        "sweep_optimization": "SWE:OPT?",
        "detector_type": "DET?",
        "coupling_type": "INP:COUP?",
        "noise_cancellation": "POW:NCOR?",
    }

    maxAverage = 1
    """
    The maximum average setting.

    The FSW8 will trigger that many sweeps, so the averaging requirement
    is satisfied.
    """

    def __init__(self, interface, reset=True, timeout=60e3, **kwargs):
        """
        Initialize the device.

        Parameters
        ----------
        interface : str
            The ip andress and port where the device is located.
            e.g. TCPIP::192.168.5.52::5025::SOCKET
        reset : bool, optional
            If true, the PSA is reset on object creation using the reset method.
            Default is True.
        timeout : int, optional
            The timeout of the ethernet connection in milliseconds.
            Default is 60e3 ms.
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
        if reset:
            self.reset()

    def reset(self):
        """Reset the FSW8 device."""
        self.write("*RST")
        self.write("INIT:CONT OFF")
        self.maxAverage = 1

    @synchronized
    def configureSweep(
        self,
        swePoints,
        refLev,
        resBW,
        vidBW=None,
        intpreamp=None,
        average=None,
        avgType="power",
        detector="rms",
        attAuto=True,
        attVal=0,
        sweType="fft",
        getData=False,
    ):
        """
        Change the sweep settings.

        Frequency units are in Hz.

        Parameters
        ----------
        swePoints : int
            The number of points per sweep.
        refLev : int
            Defines the reference level for a spurious emission measurement
            range.
        resBW : int
            Defines the resolution bandwidth and decouples the resolution
            bandwidth from the span.
            In the Real-Time application, the resolution bandwidth is always
            coupled to the span.
        vidBW : int, optional
            Defines the video bandwidth.
            If not None, the command decouples the video bandwidth from the
            resolution bandwidths. Default is None.
        intpreamp : int, optional
            Turns the internal preamplifier on and off. It requires the
            optional preamplifier hardware.
            Note that if an optional external preamplifier is activated, the
            internal preamplifier is automatically disabled, and vice versa.
            For R&S FSW 8 or 13 models, the preamplification is defined by
            INPut<ip>:GAIN[:VALue]. Default is None.
        average : int, optional
            The number of averages which make up the final values.
            Default is None.
        avgType : str, optional
            The average type of the measurement.
            Currently implemented are:
            - 'power': Power levels are converted into Watt prior averaging
            - 'linear': Power values are averaged before being converted to
                        logarithmic values
            - 'logarithmic': Logarithmic power values are averaged.
            Default is 'power'.
        detector : str, optional
            The detector type of the measurement.
            Currently implemented are:
            - 'rms': Power (RMS) averaging
            - 'log': Log-Power (video) averaging
            - 'scalar': Voltage averaging.
            Default is 'rms'.
        attAuto : bool, optional
            Couples or decouples the attenuation to the reference level.
            Thus, when the reference level is changed, the R&S FSW determines
            the signal level for optimal internal data processing and sets
            the required attenuation accordingly. Default is True.
        attVal : int, optional
            Defines the total attenuation for RF input. Default is 0.
        sweType : str, optional
            Selects the sweep type.
            Currently implemented are:
            - 'fft': FFT mode
            - 'sweep': Sweep list
            - 'auto': Automatic selection of the sweep type between sweep
                     mode and FFT.
            Default is 'fft'.
        getData : bool, optional
            If true, trigger a sweep and return the results directly.
            Default is False.

        Returns
        -------
        numpy.ndarray or None
            The sweep data if getData is True, otherwise None.
        """
        if sweType == "fft":  # selects the sweep type
            self.write("SWE:TYPE FFT")
            # Set optimization parameters in FFT mode
            # options: dynamic/speed/auto
            self.write("SWE:OPT DYN")  # DYNamic
        elif sweType == "sweep":
            self.write("SWE:TYPE SWE")
        elif sweType == "auto":
            self.write("SWE:TYPE AUTO")
        else:
            print(f"Please choose a valid sweep type! Your input was:{sweType}")  # noqa: T201
        self.query("*OPC?")

        if average:
            if avgType == "linear":
                self.write("AVER:TYPE LIN")
                # The power values are averaged before they are converted
                # to logarithmic values.
            elif avgType == "logarithmic":
                self.write("AVER:TYPE VID")
                # The logarithmic power values are averaged.
            elif avgType == "power":
                self.write("AVER:TYPE POW")
                # The power level values are converted into unit Watt prior
                # to averaging. After the averaging, the data is converted
                # back into its original unit.
                # Use this mode to average power values in Volts or Amperes correctly.
                # In particular, for small VBW values (smaller than the RBW), use
                # power averaging mode for correct power measurements in FFT
                # sweep mode
            else:
                print(f"Please choose a valid average type! Your input was:{avgType}")  # noqa: T201
            self.query("*OPC?")

            if detector == "rms":
                # Calculates the root mean square of all samples contained in a sweep point.
                self.write("DETector RMS")
            elif detector == "ape":
                self.write("DETector APE")
            elif detector == "average":
                # Calculates the linear average of all samples contained in a sweep point
                self.write("DETector AVER")
            else:
                print(f"Please choose a valid detector type! Your input was:{detector}")  # noqa: T201

            self.write("AVER:STAT ON")
            self.write(f"AVER:COUN {average}")
            self.maxAverage = max(average, self.maxAverage)
        else:
            self.write("AVER:STAT OFF")
        self.query("*OPC?")

        if intpreamp:  # internal preamplifier
            self.write("INP:GAIN:STAT ON")
            self.write(f"INP:GAIN:VAL {intpreamp}")
        else:
            self.write("INP:GAIN:STAT OFF")
        self.query("*OPC?")

        if attAuto is True:  # automatic internal attenuator
            self.write("INP:ATT:AUTO ON")
        else:
            self.write("INP:ATT:AUTO OFF")
            self.write(f"INP:ATT {attVal}dB")
        self.query("*OPC?")

        self.write(f"SWE:POIN {str(swePoints)}")
        self.write(f"BWID:RES {str(resBW)} Hz")
        if vidBW:
            self.write(f"BWID:VID {str(vidBW)} Hz")
        else:
            # automatic video bandwidth selection
            self.write("BAND:VID:AUTO ON")
        self.write(f"DISP:TRAC:Y:RLEV {str(refLev)}dbm")
        self.query("*OPC?")

        # activates automatic sweep time.
        self.write("SWE:TIME:AUTO ON")

        # selects the coupling type AC of the RF input
        self.write("INP:COUP AC")  # options : AC / DC
        self.query("*OPC?")

        if getData:
            return self.getSweepData()

    @synchronized
    def noise_cancellation(self, state=False):
        """
        Turn noise cancellation on and off.

        If noise cancellation is on, the R&S FSW performs a reference
        measurement to determine its inherent noise and subtracts the
        result from the channel power measurement result (first active
        trace only).

        Parameters
        ----------
        state : bool, optional
            Whether to enable noise cancellation.
            Default is False.
        """
        if state is True:
            self.write("POW:NCOR ON")
        else:
            self.write("POW:NCOR OFF")

    @synchronized
    def setFreq(self, fCent, fSpan):
        """
        Set the center frequency and frequency span.

        Parameters
        ----------
        fCent : float
            The center frequency in Hz.
        fSpan : float
            The frequency span in Hz.
        """
        self.write(f"FREQ:CENT {str(fCent)} HZ")
        self.write(f"FREQ:SPAN {str(fSpan)} HZ")

    @synchronized
    def setStartStopFreq(self, fStart, fStop):
        """
        Set the start and stop frequencies.

        Parameters
        ----------
        fStart : float
            The start frequency in Hz.
        fStop : float
            The stop frequency in Hz.
        """
        self.write(f"FREQ:START {fStart} HZ")
        self.write(f"FREQ:STOP {fStop} HZ")

    @synchronized
    def startSweep(self):
        """
        Prepare the FSW8 for triggering a sweep.

        The FSW8 disables the continuous trigger and therefore enables
        manual triggering. Any currently running sweeps are aborted.
        """
        # aborts the measurement in the current channel and resets the
        # trigger system
        self.write("ABOR")
        # wait until abortion has been completed
        self.write("*WAI")
        # switches to single sweep mode
        self.write("INIT:CONT OFF")

    @synchronized
    def trigger(self):
        """
        Trigger the sweep(s).

        Parameters
        ----------
        sync : bool, optional
            If true, the function will wait for the sweep to complete
            before returning. Default is True.
        """
        self.write("INIT:IMM")
        self.write("*WAI")

    @synchronized
    def getData(self, precision: Literal["single", "double", "ascii"] = "single") -> np.ndarray:
        """
        Transfer measurement data from the VNA.

        Parameters
        ----------
        precision : str, optional
            One of {'single', 'double', 'ascii'}
            'single' and 'double' precisions are transferred as binary data,
            and achieve much faster transfer speeds.
            'ascii' is only implemented as a fallback method, as it is
            much easier to debug. Default is 'single'.

        Returns
        -------
        numpy.ndarray
            The measured data from the device.
        """
        precdict: dict[str, tuple[str, int, str, str]] = {
            "single": ("REAL,32", 4, ">f", "float32"),
            "double": ("REAL,64", 8, ">d", "float64"),
            "ascii": ("ASC,0", 0, "", ""),
        }

        p = str(precision).lower().strip()
        if p not in precdict:
            valid = ", ".join(sorted(precdict))
            raise ValueError(f"Invalid precision {precision!r}. Expected one of: {valid}")

        self.write(f"FORM {precdict[p][0]}")

        if p == "ascii":
            txt = self.query("TRAC:DATA? TRACE1")
            return np.fromstring(txt, sep=",").transpose()

        byte_width = precdict[p][1]
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
            chunk = data[i * byte_width : (i + 1) * byte_width]
            values.append(unpack(precdict[p][2], chunk))

        return np.array(values, dtype=precdict[p][3]).ravel()

    @synchronized
    def getSweepData(self):
        """
        Prepare, trigger, and retrieve sweep data.

        This is a convenience method to prepare and trigger the sweep and transfer
        the data afterwards.

        Returns
        -------
        numpy.ndarray
            The measured data from the specified channel.
        """
        self.startSweep()
        self.trigger()
        return self.getData()

    @synchronized
    def readSweepParams(self):
        """
        Read the sweep parameters from the FSW8.

        Frequencies are returned in Hz.

        Returns
        -------
        tuple
            A tuple containing (fStart, fStop, fPoints) where:

            fStart : float
                The frequency at which the sweep starts.
            fStop : float
                The frequency at which the sweep stops.
            fPoints : int
                The number of points in the sweep.
        """
        self.write("FREQ:STAR?")
        fStart = float(self.read())
        self.write("FREQ:STOP?")
        fStop = float(self.read())
        self.write("SWE:POIN?")
        fPoints = int(self.read())
        return fStart, fStop, fPoints
