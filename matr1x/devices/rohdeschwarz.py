import time
from struct import unpack

import numpy as np
from wrapt import synchronized

from .visadevice import VisaDevice


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
    The FSW8 will trigger that many sweeps, so the averaging
    requirement is satisfied.
    """

    def __init__(self, interface, reset=True, timeout=60e3, **kwargs):
        """
        Initialize the device.

        Parameters
        ----------
        interface : str
          The ip andress and port where the device is located.
          e.g. TCPIP::192.168.5.52::5025::SOCKET
        open : bool
          (Default = True)
          If true, the connection to the PSA is opened on object creation.
        reset : bool
          (Default = True)
          If true, the PSA is reset on object creation using the reset method.
        timeout : int
          (Default = 60e3 ms)
          The timeout of the ethernet connection.
        **kwargs :
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
        """
        Reset the FSW8.
        """
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
        vidBW : int
            (Default = None)
            Defines the video bandwidth.
            If not None, the command decouples the video bandwidth from the
            resolution bandwidths.
        intpreamp : int
            (Default = None)
            Turns the internal preamplifier on and off. It requires the
            optional preamplifier hardware.
            Note that if an optional external preamplifier is activated, the
            internal preamplifier is automatically disabled, and vice versa.
            For R&S FSW 8 or 13 models, the preamplification is defined by
            INPut<ip>:GAIN[:VALue].
        average : int
            (Default = None)
            The number of averages which make up the final values.
        avgType : str
            (Default = 'power')
            The average typ of the mesurement.
            Currently implemented are 'power': Power levels are converted
            into Watt prior averaging, 'linear' : Power values are
            averaged before being converted to logarithmic values
            and 'logarithmic' : Logarithmic power values are averaged.
        detector : str
            (Default = 'rms')
            The detector typ of the mesurement.
            Currently implemented are 'rms': Power (RMS) averaging,
            'log' : Log-Power (video) averaging and 'scalar' : Voltage
            averaging.
        attAuto : bool
          (Default = True)
          Couples or decouples the attenuation to the reference level.
          Thus, when the reference level is changed, the R&S FSW determines
          the signal level for optimal internal data processing and sets
          the required attenuation accordingly.
        attVal : int
          (Default = 0)
          Defines the total attenuation for RF input.
        sweType : str
          (Default = 'fft')
          Selects the sweep type.
          Currently implemented are 'fft' : FFT mode, 'sweep' : Sweep list
          and 'auto' : Automatic selection of the sweep type between sweep
          mode and FFT.
        getData : bool
             (Default =  False)
            If true, trigger a sweep and return the results directly.
        Returns
        -------
        data : npArray
            The sweep data (if getData is true).
        """
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
                print(
                    "Please choose a valid average type! Your input was:{}".format(avgType))
            time.sleep(0.5)
            if detector == "rms":
                # Calculates the root mean square of all samples contained in a sweep point.
                self.write("DETector RMS")
            elif detector == "average":
                # Calculates the linear average of all samples contained in a sweep point
                self.write("DETector AVER")
            else:
                print(
                    "Please choose a valid detector type! Your input was:{}".format(avgType))
            self.write("AVER:STAT ON")
            self.write(f"AVER:COUN {average}")
            self.maxAverage = max(average, self.maxAverage)
        else:
            self.write("AVER:STAT OFF")
        time.sleep(0.5)

        if intpreamp:  # internal preamplifier
            self.write("INP:GAIN:STAT ON")
            self.write(f"INP:GAIN:VAL {intpreamp}")
        else:
            self.write("INP:GAIN:STAT OFF")
        time.sleep(0.5)

        if attAuto is True:  # automatic internal attenuator
            self.write("INP:ATT:AUTO ON")
        else:
            self.write("INP:ATT:AUTO OFF")
            self.write(f"INP:ATT {attVal}dB")
        time.sleep(0.5)

        self.write(f"SWE:POIN {str(swePoints)}")
        self.write(f"BWID:RES {str(resBW)} Hz")
        if vidBW:
            self.write(f"BWID:VID {str(vidBW)} Hz")
        else:
            # automatic video bandwidth selection
            self.write("BAND:VID:AUTO ON")
        self.write(f"DISP:TRAC:Y:RLEV {str(refLev)}dbm")
        time.sleep(0.5)

        if sweType == "fft":  # selects the sweep type
            self.write("SWE:TYPE FFT")
        elif sweType == "sweep":
            self.write("SWE:TYPE SWE")
        elif sweType == "auto":
            self.write("SWE:TYPE AUTO")
        else:
            print(
                f"Please choose a valid sweep type! Your input was:{avgType}")
        time.sleep(0.5)

        # Set optimization parameters in FFT mode
        # options: dynamic/speed/auto
        self.write("SWE:OPT DYN")  # DYNamic

        # activates automatic sweep time.
        self.write("SWE:TIME:AUTO ON")

        # selects the coupling type AC of the RF input
        self.write("INP:COUP AC")  # options : AC / DC

        if getData:
            return self.getSweepData()

    @synchronized
    def noise_cancellation(self, state=False):
        """
        Turns noise cancellation on and off.
        If noise cancellation is on, the R&S FSW performs a reference
        measurement to determine its inherent noise and subtracts the
        result from the channel power measurement result (first active
        trace only).
        """
        if state is True:
            self.write("POW:NCOR ON")
        else:
            self.write("POW:NCOR OFF")

    @synchronized
    def setFreq(self, fCent, fSpan):
        self.write(f"FREQ:CENT {str(fCent)} HZ")
        self.write(f"FREQ:SPAN {str(fSpan)} HZ")

    @synchronized
    def setStartStopFreq(self, fStart, fStop):
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
        sync : bool
          (Default = True)
          If true, the function will wait for the sweep to comlete
          before returning.
        """
        self.write("INIT:IMM")
        self.write("*WAI")

    @synchronized
    def getData(self, precision="single"):
        """
        Transfer mesurement data from the VNA.

        Parameters
        ----------
        channel : int
          The desired channel
        precision : str
          (Default = 'single')
          One of {'single', 'double', 'ascii'}
          'single' and 'double' precisions are transferd as binary data,
          and achive much faster transfer speeds.
          'ascii' is only implemented as a fallback method, as it is
          much easier to debug.
        Returns
        -------
        data : np.array
            The mesured data from the specified channel.
        """
        precdict = {
            "single": ("REAL,32", 4, ">f", "float32"),
            "double": ("REAL,64", 8, ">d", "float64"),
            "ascii": ("ASC,0", None, None),
        }

        try:
            self.write("FORM {}".format(precdict[precision][0]))
        except KeyError:
            print("{} is not a valid precision".format(str(precision)))
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
            data_bit = data[i * byte_width: (i + 1) * byte_width]
            values.append(unpack(precdict[precision][2], data_bit))
        # add ravel to remove unnecessary dimensions of the array
        return np.array(values, dtype=precdict[precision][3]).ravel()

    @synchronized
    def getSweepData(self, channel):
        """
        Convenience method to prepare and trigger the sweep and transfer
        the data afterwards.

        Parameters
        ----------
        channel : int
            The used channel.
        Returns
        -------
        data : np.array
            The mesured data from the specified channel.
        """
        self.startSweep()
        self.trigger()
        return self.getData()

    @synchronized
    def readSweepParams(self):
        """
        Read the sweep parameters from the FSW8.
        Frequencies are returned in Hz.

        Parameters
        ----------
        channel : int
            The channel for which the sweep parameters should be returned
        Returns
        -------
        fStart : int
            The frequency at which the sweep starts.
        fStop : int
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
