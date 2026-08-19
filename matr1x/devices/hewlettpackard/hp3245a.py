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
"""
HP3245A AC function generator interface module.

This module provides a class for controlling the HP3245A AC function
generator.
"""

from matr1x.devices.visadevice import VisaDevice


class HP3245A(VisaDevice):
    """
    HP3245A AC function generator.

    Typically connected via GPIB::<address>::INSTR

    Parameters
    ----------
    interface : str
        VISA resource string for the instrument.
    **kwargs : dict
        Additional keyword arguments passed to VisaDevice.

    Attributes
    ----------
    output : list
        Current and offset values [current, offset].
    frequency : float
        The current frequency setting.
    config_params : dict
        Configuration parameters for the device.
    """

    def __init__(self, interface, **kwargs):
        """
        Initialize the HP3245A function generator.

        Parameters
        ----------
        interface : str
            VISA resource string for the instrument.
        **kwargs : dict
            Additional keyword arguments passed to VisaDevice.
        """
        if "write_termination" not in kwargs:
            kwargs["write_termination"] = "\r"
        if "read_termination" not in kwargs:
            kwargs["read_termination"] = "\r"
        self.output = [0, 0]
        self.frequency = 0
        super().__init__(interface, **kwargs)

    def ident(self):
        """
        Query the instrument identification.

        Returns
        -------
        str
            Instrument identification string.
        """
        return self.query("ID?")

    def set_current(self, curr):
        """
        Set the output current amplitude.

        Parameters
        ----------
        curr : float
            Current amplitude value in amperes.
        """
        self.write(f"APPLY ACI {curr}")
        self.output[0] = curr

    def set_freq(self, freq):
        """
        Set the output frequency.

        Parameters
        ----------
        freq : float
            Frequency value in hertz.
        """
        self.frequency = freq
        self.write(f"FREQ {freq}")

    def set_offset(self, dcoff):
        """
        Set the DC offset value.

        Parameters
        ----------
        dcoff : float
            DC offset value in volts.
        """
        self.write(f"DCOFF {dcoff}")
        self.output[1] = dcoff
