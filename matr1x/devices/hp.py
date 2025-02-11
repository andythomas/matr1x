# This file is part of a software collection for data aquisition (matr1x).
# Copyright (C) 2006-2025 matr1x developers
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

from .visadevice import VisaDevice


class HP3245A(VisaDevice):
    """
    HP3245A AC function generator

    Typically connected via GPIB::<address>::INSTR
    """
    config_params = {}

    def __init__(self, interface, **kwargs):
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r"
        self.output = [0, 0]
        self.frequency = 0
        super().__init__(interface, **kwargs)

    def ident(self):
        return self.query('ID?')

    def set_current(self, curr):
        self.write(f'APPLY ACI {curr}')
        self.output[0] = curr

    def set_freq(self, freq):
        self.frequency = freq
        self.write(f'FREQ {freq}')

    def set_offset(self, dcoff):
        self.write(f'DCOFF {dcoff}')
        self.output[1] = dcoff
