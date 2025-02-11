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

"""
Communication with DAC8532 on DA/AD Board
"""
import numpy as np
import RPi.GPIO as GPIO
import spidev

# There is warning saying to disable warnings is it works anyway
GPIO.setwarnings(False)


class BCM8532():
    # Class for handling and setup of the BCM2835 of the Waveshare AD/DA board

    # Definitions of pins used by the SPI
    SPICS = 16

    # Definitions of the communication parameters
    SPI_FREQUENCY = 1000000

    # Definition of channels
    A = 0x30
    B = 0x34

    def __init__(self):
        # Initialize the pin layout to BOARD (RPi 40 pin layout)
        GPIO.setmode(GPIO.BOARD)
        # Define SPICS as output and set to HIGH
        GPIO.setup(self.SPICS, GPIO.OUT, initial=GPIO.HIGH)

        self.spi = spidev.SpiDev()
        # open /dev/spidev0,0
        self.spi.open(0, 0)
        # define SPI parameters
        self.spi.bits_per_word = 8
        self.spi.mode = 0b01
        self.spi.max_speed_hz = self.SPI_FREQUENCY

    # low level functions
    def CS(self, state):
        # Sets the chip select to the state given, high/true means chip is NOT selected (inverting)
        if state is True:
            GPIO.output(self.SPICS, GPIO.HIGH)
        else:
            GPIO.output(self.SPICS, GPIO.LOW)

    def set(self, V_ref, set_value, channel, bipolar=False, V_0=2.5):
        # Selects the BCM2835 and sets voltage on selected channel
        self.CS(False)
        if bipolar is True:
            voltage = self.voltage_conversion_bipolar(V_ref, V_0, set_value)
        else:
            voltage = self.voltage_conversion(V_ref, set_value)
        x = np.uint16(voltage)
        # Split the uint16 number into to 8bit parts
        x1_str = hex((x >> 8) & 0xFF)
        x2_str = hex(x & 0xFF)
        x1 = int(x1_str, 16)
        x2 = int(x2_str, 16)
        if channel == 0:
            self.spi.writebytes([0x30, x1, x2])
        elif channel == 1:
            self.spi.writebytes([0x34, x1, x2])
        self.CS(True)

    def voltage_conversion(self, V_ref, set_value):
        # Converts a voltage into a number within the uint16 range (0-65535)
        output = 65535*set_value/V_ref
        return output

    def voltage_conversion_bipolar(self, V_ref, V_mid, set_value):
        # Converts a voltage into a number within the uint16 range (0-65535)
        output = 65535*(set_value+V_mid)/V_ref
        return output
