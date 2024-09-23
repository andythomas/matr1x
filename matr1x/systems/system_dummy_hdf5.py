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
This module defines a system for testing and demonstration purposes including
the HDF5 data file format option.
"""
# ============================
# Custom import area
# ============================
import numpy
from matr1x.devices.dummy import dummy
from matr1x.system import System


# ============================
# This area contains the required MeasSystem definition and
# the optional reimplementation of the set and reset function
# ============================
class MeasSystem(System):
    def __init__(self):
        super().__init__()
        self.dcdata["source"] = "dummy system with HDF5 for testing matr1x-matrix"

    def get_p4(self, shape=-1):
        return numpy.asarray(self.devs["devhdf"].p4).reshape(shape)
# ============================


# initialize system
sys = MeasSystem()
# ========================================================================
# This is the main system area
# Device definition and configuration takes place here, but devices do
# not yet get opened!
#
# IMPORTANT:
#   The devices are not allowed to be opened here!
#   Otherwise the import would block any other use of the devices
#   Make sure to adhere to this or errors will occur!
# ========================================================================
sys.add_dev("devhdf", dummy,
            args=("TCPIP::localhost::10009::SOCKET", ))

# enforce HDF5 flag, will be set automatically if needed by any Parameter
# sys.hdf5 = True

# define columns for measurement
sys.add_param(
    "devhdfp4_flat", "cnt",
    getter=["devhdf", "p4"], dtype="f8", chunks=4)
sys.add_param(
    "devhdfp4_1d", "cnt",
    getter=["devhdf", "p4"], chunks=(4,))
sys.add_param(
    ["devhdf p3a", "devhdf p3b"], ["cnta", "cntb"],
    ["devhdf", "p3"],
    ["devhdf", "p3"],
    chunks=[1, 1], dtype=["i8", "i8"])
sys.add_param(
    "devhdfp4_2d", "cnt",
    getter='get_p4',
    getter_kwargs={"shape": (2, 2)},
    chunks=(2, 2))
sys.add_param(
    ["rand2d_1", "rand2d_2"], ["cnt", "cnt"],
    getter=numpy.random.random,
    getter_args=[(2, 4, 4), ],
    chunks=[(4, 4), (4, 4)])
# ============================
