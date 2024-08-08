import time

from pyvisa import VisaIOError

from .visadevice import VisaDevice


class FH55(VisaDevice):
    """
    Driver for Hall probe FH55 from Magnet Physik
    """

    def __init__(self, interface, timeout=1e3, **kwargs):
        """
        Initialize FH55.

        Parameters
        ----------
        interface : str
          The ip andress and port where the device is located.
          e.g. TCPIP::192.98.143.1::5025::SOCKET
        timeout : int
          (Default = 1e3 ms)
          The timeout of the ethernet connection.
        **kwargs :
          Keyword arguments passed to the VISAdevice constructor.
        """
        super().__init__(interface, timeout=timeout,
                         write_termination="\r", read_termination="\r\n", **kwargs)
        # Instrument is sending some character on successful connection
        try:
            self.read()
        except VisaIOError:
            pass
        self.query("#AUTO 1")  # sets autorange OFF
        self.query("#UNIT 0")  # sets unit to Tesla
        self.query("#TEMP 1")  # sets temp unit to Celsius

    def reset(self):
        """
        Reset the FH55 using the RESET command.
        This resets all peak (max/min) settings. RESET returns a "OK".
        """
        self.query("#AUTO 1")  # sets autorange
        self.query("#RESET")

    # high level functions
    def getField(self):
        """
        Returns magnetic field in T.
        units = ["mT","T"]
        """
        try:
            field, unit = self.query("?MEAS").split(" ")
        except ValueError:
            time.sleep(0.5)
            field, unit = self.query("?MEAS").split(" ")
        field = float(field)

        if unit == "mT":
            return float(field) * 1e-3
        else:
            return float(field)

    def setRange(self):
        field = self.getField()
        field_abs = abs(field)
        if field_abs < 30e-6:
            self.query("#RANGE 1")
        elif field_abs < 300e-6:
            self.query("#RANGE 2")
        elif field_abs < 3e-3:
            self.query("#RANGE 3")
        elif field_abs < 30e-3:
            self.query("#RANGE 4")
        elif field_abs < 300e-3:
            self.query("#RANGE 5")
        elif field_abs < 3:
            self.query("#RANGE 6")
        else:
            print(f"Field {field} T is not within a valid range!")

    def getTemp(self):
        """
        Returns temp in degree celsius
        """
        temp = self.query("?TEMP")
        return float(temp.strip(" C"))

    def setFilter(self, filter_status):
        """
        Sets the filter on or off
        0=OFF
        1=ON
        """
        if filter_status == "ON":
            self.query("#FILTER 1")
        elif filter_status == "OFF":
            self.query("#FILTER 0")
        else:
            print(
                f"Please choose a valid filter status (ON/OFF)! Your input was: {filter_status}")

    def getMode(self):
        """
        Returns the AC/DC mode
        """
        mode = self.query("?MODE")
        mode = float(mode.strip("MODE "))
        if mode == 0:
            return "DC"
        elif mode == 1:
            return "AC"
        else:
            return print(f"Please choose a valid mode (0/1)! Your input was: {mode}")

    def setMode(self, mode):
        """
        Sets the mode to
        0=DC mode
        1=AC mode
        """
        self.write(f"#MODE {int(mode)}")
