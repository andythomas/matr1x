# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2024 matr1x developers. All rights reserved.
# ---
import time

from .visadevice import VisaDevice


class CS04(VisaDevice):
    """
    Cryomagnetics CS04 magnet power supply.

    Typically connected via GPIB::<address>::INSTR
    The user shall set `max_field` to a reasonable value upon initialization.
    """
    config_params = {}

    def __init__(self, interface, **kwargs):
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r\n"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\n"
        self.max_field = kwargs.pop("max_field", 0.1)
        self._setpoint = 0
        super().__init__(interface, **kwargs)

    def ident(self):
        return self.query('*IDN?')

    def reset(self):
        self._setpoint = 0
        self.write("SWEEP PAUSE")
        self.write('ULIM 0')
        self.write('LLIM 0')
        self.write("SWEEP ZERO SLOW")

    def set_field(self, field):
        if field == 0:
            self.reset()
            return
        if abs(field) > self.max_field:
            print(
                f"Request for too large field ({field} T). Max is {self.max_field} T")
            return
        self._setpoint = field
        if field > 0:
            self.write("SWEEP PAUSE")
            self.write('LLIM 0')
            self.write(f'ULIM {field}')
            self.write("SWEEP UP SLOW")
        else:
            self.write("SWEEP PAUSE")
            self.write('ULIM 0')
            self.write(f'LLIM {field}')
            self.write("SWEEP DOWN SLOW")

    def get_field(self):
        return float(self.query("IOUT?").strip(" T"))

    def wait_field(self, setpoint=None, delta=0.0002):
        if not setpoint:
            setpoint = self._setpoint
        inrange = 0
        while True:
            if abs(self.get_field() - setpoint) < delta:
                inrange += 1
            if inrange >= 2:
                break
            time.sleep(1)
        time.sleep(1)
        self.write("SWEEP PAUSE")
