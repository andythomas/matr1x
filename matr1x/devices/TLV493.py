# This file is part of a software collection for data aquisition (matr1x).
# Copyright (C) 2024 matr1x developers
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
TLV493-A1B6

3D magnetic sensor

register 0: Bx
register 1: By
register 2: Bz
register 3: Temp, FRM, CH
register 4: Bx, By
register 5: reserved, PD, Bz
register 6: Temp
register 7: reserved
register 8: reserved
register 9: reserved
"""
import subprocess

import numpy as np
import smbus


class TLV493():
    def __init__(self):
        # open bus
        self.bys = smbus.SMBus(1)

        # look for adress
        addr = subprocess.check_output(["i2cdetect", "-y", "1"]).decode()
        if "5e" in addr:
            self.addr = 0x5e
        elif "1f" in addr:
            self.addr = 0x1f
        else:
            return -1

        # read storage
        self.reset()
        self.store = self.bys.read_i2c_block_data(self.addr, 0)[0:10]
        self.counter = self.store[3] & 0b1100
        self.config()

    def getParity(self, storage):
        s = 0
        for val in storage:
            for j in range(8):
                s += (val >> j) & 1
        return s % 2

    def reset(self):
        self.bys.write_byte(0x00, 0)

    # send data to the bus:
    def config(self):
        interrupt = 1  # interrupt pin
        fast = 1  # fast mode
        low = 1  # low power mode
        lp = 0  # low power period
        pt = 1  # parity test
        t = 0  # temperature NOT enabled
        write = [(self.store[7] & 0b00011000 |
                  interrupt << 2 |
                  fast << 1 |
                  low),
                 self.store[8],
                 (self.store[9] & 0b11111 |
                  lp << 6 |
                  pt << 5 |
                  t << 7)]
        if 0 == self.getParity(write):
            write[0] |= 1 << 7
        self.bys.write_i2c_block_data(self.addr, 0, write)

    def getTemperature(self):
        # reads the temperature in degrees Celsius
        regs = np.int8(self.bys.read_i2c_block_data(self.addr, 0))[0:7]
        t = regs[6] | ((regs[3] & 0xf0) << 4)
        t = t - 340
        t = t*1.1
        return t

    def getFieldCart(self):
        # reads the field in T in cartesian coordinates
        regs = np.int8(self.bys.read_i2c_block_data(self.addr, 0))[0:6]
        if regs[3] & 0b1100 == self.counter:
            self.reset()
            self.config()
            regs = np.int8(self.bys.read_i2c_block_data(self.addr, 0))[0:6]
        self.counter = regs[3] & 0b1100
        bx = (regs[0] << 4) | ((regs[4] & 0xf0) >> 4)
        by = (regs[1] << 4) | (regs[4] & 0x0f)
        bz = (regs[2] << 4) | (regs[5] & 0x0f)
        b = 0.098e-3*np.array([bx, by, bz])
        return b

    def getFieldSphe(self):
        # displays magnetic field in T in spherical coordinates

        bcart = self.getFieldCart()
        bx = bcart[0]
        by = bcart[1]
        bz = bcart[2]

        rho = np.sqrt(bx*bx + by*by + bz*bz)
        theta = np.arctan2(np.sqrt(bx*bx + by*by), bz)
        phi = np.arctan2(by, bx)

        bsphe = np.array([rho, theta, phi])
        return bsphe
