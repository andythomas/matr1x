# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2024 matr1x developers. All rights reserved.
# ---
import time

import numpy as np
from wrapt import synchronized

from .visadevice import VisaDevice


class SR830(VisaDevice):
    """
    The device class for the Stanford Research Systems SR830 DSP
    Lock-In amplifier.
    """

    config_params = {
        "phase": "PHAS?",
        "reference_source": "FMOD?",
        "reference_frequency": "FREQ?",
        "reference_trigger": "RSLP?",
        "detection_harmonic": "HARM?",
        "input_source": "ISRC?",
        "input_ground": "IGND?",
        "input_coupling": "ICPL?",
        "input_line_notch_filter_status": "ILIN?",
        "sensitivity": "SENS?",
        "dynamic_reserve_mode": "RMOD?",
        "time_constant": "OFLT?",
        "low_pass_filter_slope": "OFSL?",
        "synchronous_filter_status": "SYNC?",
    }

    def __init__(self, interface, reset=False, timeout=1e3, **kwargs):
        """
        Initialize a SR830 device.

        Parameters
        ----------
        interface : str
          PyVisa resource string.
        reset : bool
          (Default = True)
          If true, the SR830 is reset on object creation using the reset method.
        timeout : int
          (Default = 1000 ms)
          The timeout of the connection.
        **kwargs :
          Keyword arguments passed to the VisaDevice constructor.
        """
        super().__init__(
            interface,
            write_termination="\r",
            read_termination="\r",
            timeout=timeout,
            cmdpers=50,
            **kwargs,
        )

        if reset:
            self.reset()

    def reset(self):
        """
        Reset the SR830
        """
        self.write("*RST")

    @synchronized
    def configureSR830(self, refSource="ext", refTrig="sine"):
        """
        Configure the SR830 device.

        Parameters
        ----------
        refSource : str
          The FMOD command sets or queries the reference source. The
          parameter i selects internal (i=1) or external (i=0).
        refTrig : str
          The RSLP command sets or queries the reference trigger when
          using the external reference mode At frequencies below 1 Hz,
          the a TTL reference must be used.
        """
        if refSource == "ext":  # set external reference source
            self.write("FMOD 0")
        elif refSource == "int":  # set internal reference source
            self.write("FMOD 1")
        else:
            print(
                f"Please choose a valid reference source! Your input was: {refSource}")

        if refTrig == "sine":
            self.write("RSLP 0")  # sine zero crossing
        elif refTrig == "rising":
            self.write("RSLP 1")  # TTL rising edge
        elif refTrig == "falling":
            self.write("RSLP 2")  # TTL falling edge
        else:
            print(
                f"Please choose a valid reference trigger! Your input was: {refTrig}")

        # set reserve mode
        self.write("RMOD 2")  # Reserve (i=0), Normal (i=1), Low Noise (i=2)
        # self.write(f"ARSV")  # or not automatic ?

    @synchronized
    def configureExtTrigger(self):
        self.write("REST")  # resets buffer
        self.write("SEND 0")  # end of buffer mode (0=shot)
        self.write("SRAT 14")  # data sample rate (14=Trigger)
        self.write("TSTR 1")  # turning on trigger by "TRIG IN" connector

    @synchronized
    def setInput(self, inputSource, inputGround="Float", inputCoupling="AC"):
        """
        Configure the SR830 input configuration.

        Parameters
        ----------
        inputSource : str
        The ISRC command sets or queries the input configuration. The
        parameter i selects A (i=0), A-B (i=1), I (1 MΩ) (i=2) or
        I (100 MΩ) (i=3).
        Values:
          A : A (i=0)
          diff : A-B (i=1)
          1Mohm : A-B (i=1)
          100Mohm : A-B (i=1)
        """
        if inputSource == "A":
            self.write("ISRC 0")
        elif inputSource == "diff":
            self.write("ISRC 1")
        elif inputSource == "1Mohm":
            self.write("ISRC 2")
        elif inputSource == "100Mohm":
            self.write("ISRC 3")
        else:
            print(
                f"Please choose a valid input configuration! Your input was: {inputSource}")

        if inputGround == "Float":
            self.write("IGND 0")
        elif inputGround == "Ground":
            self.write("IGND 1")
        else:
            print(
                f"Please choose a valid input shield grounding! Your input was: {inputGround}")

        if inputCoupling == "AC":
            self.write("ICPL 0")
        elif inputCoupling == "DC":
            self.write("ICPL 1")
        else:
            print(
                f"Please choose a valid input coupling! Your input was: {inputCoupling}")

    @synchronized
    def setFilters(self, inputFilter=None):
        """
        Configure the SR830 input configuration.

        Parameters
        ----------
        inputSource : str
          The ILIN command sets or queries the input line notch filter
          status. The parameter i selects Out or no filters (i=0), Line
          notch in (i=1), 2xLine notch in (i=2) or Both notch filters
          in (i=3).
        """
        if inputFilter is None:
            self.write("ILIN 0")
        elif inputFilter == "lineNotch":
            self.write("ILIN 1")
        elif inputFilter == "2xlineNotch":
            self.write("ILIN 2")
        elif inputFilter == "both":
            self.write("ILIN 3")
        else:
            print(
                f"Please choose a valid input line notch filter status! Your input was: {inputFilter}")

    @synchronized
    def setTimeConstant(self, timeConst=None):
        """
        Configure the SR830 input configuration.

        Parameters
        ----------
        timeConst : str
          T...
        """
        time_arr1 = [10e-6, 30e-6, 100e-6, 300e-6]
        time_arr2 = [1e-3, 3e-3, 10e-3, 30e-3, 100e-3, 300e-3]
        time_arr3 = [1, 3, 10, 30, 100, 300]
        time_arr4 = [1e3, 3e3, 10e3, 30e3]
        time_arr = np.array(time_arr1 + time_arr2 + time_arr3 + time_arr4)
        if timeConst:
            time_idx = int(np.argwhere(time_arr == timeConst))
            self.write(f"OFLT {time_idx}")
        else:  # using default value of 100 ms
            self.write("OFLT 8")

    @synchronized
    def autoGain(self):
        """
        Get the SR830 phase.

        Parameters
        ----------
        phase : float
          T...
        """
        # set automatic gain (=sensetivity)
        self.write("AGAN")

    @synchronized
    def autoPhase(self):
        """
        Get the SR830 phase.

        Parameters
        ----------
        phase : float
          T...
        """
        # set automatic phase
        self.write("APHS")

    @synchronized
    def getPhase(self):
        """
        Get the SR830 phase.

        Parameters
        ----------
        phase : float
          T...
        """
        phase = float(self.query("PHAS ?"))
        return phase

    @synchronized
    def getSingleParameterSet(self):
        """
        The SNAP? command requires at least two parameters and at most six
        """
        X, Y, R, phase = self.query("SNAP ?1,2,3,4").split(",")
        return float(X), float(Y), float(R), float(phase)

    @synchronized
    def getData(self, fPoints):
        """
        Get the SR830 data.

        Parameters
        ----------
        fPoints : int
          T...
        """
        print("\n", "buffer_size:", self.query("SPTS ?"), "\n")
        x = self.query(f"TRCA? 1,0,{fPoints}")
        X = np.fromstring(x, sep=",").transpose()
        print("finished reading X, len X : ", len(X))
        if len(X) != fPoints:
            print("X too short, rereading")
            x = self.query(f"TRCA? 1,0,{fPoints}")
            X = np.fromstring(x, sep=",").transpose()
            print("finished rereading X, len X : ", len(X))
        time.sleep(0.1)
        y = self.query(f"TRCA? 2,0,{fPoints}")
        Y = np.fromstring(y, sep=",").transpose()
        print("finished reading Y, len Y : ", len(Y))
        if len(Y) != fPoints:
            print("Y too short, rereading")
            y = self.query(f"TRCA? 2,0,{fPoints}")
            Y = np.fromstring(y, sep=",").transpose()
            print("finished rereading Y, len Y : ", len(Y))
        self.write("REST")  # resets buffer
        print("buffer reset")
        return X, Y
