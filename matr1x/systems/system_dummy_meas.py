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
Defines a system for testing and demonstration purposes.

This module provides a sample implementation to showcase how
various systems can be merged together.
"""
# ============================
# Custom import area
# ============================

from matr1x.devices.dummy import dummy
from matr1x.system import System

# ============================


# ============================
# This area contains the required MeasSystem definition and
# the optional reimplementation of the set and reset function
# ============================

# ============================


# ============================
# initialize system
sys = System()
sys.dcdata["source"] = "dummy system for testing system merging"
# ============================

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
# device initialization is done by providing the class name of the device
# together with the constructor arguments needed to initialize the class later
# Here dev1F, dev2F will be initalized when system is `set`.
# The third parameter (args) accepts a list/tuple (even for single parameter!)
# of arguments that is passed upon device initializeation when sys.set() is
# called.
# The fourth parameter (kwargs) accepts a dictionary with keyword arguments.
# The fifth parameter (config_params) can be a dictionary specifying possible
# query options which allow to readout the configuration of a device which will
# be stored in the data file header.
sys.add_dev("devmeas", dummy, args=("TCPIP::localhost::10005::SOCKET", ),
            kwargs={"p5": 5, "p4": [5, 3, 2, 1]}, config_params={"p4":
                                                                 "p4"})

# ============================
# define columns for measurement
# ============================
# first parameter is column name, second is units,
# Further parameters are the set function and read function, respectively.
# Those can be specified as callable function or as list with the entries
# [device_name, method, optional (extra) arguments, optional keyword arguments]
# Optional keyword arguments can be given for the trigger-function, chunks
# (=length of readout array, used only for HDF5 systems), and the default value
# to be used when setting the device (if no value is specified in the sweep
# file)
sys.add_param(
    ["devmeas p3a", "devmeas p3b"], ["cnta", "cntb"],
    ["devmeas", "p3"],
    ["devmeas", "p3"])
sys.add_param(
    "devmeas p2", "cnt",
    setter=["devmeas", "p2"],
    getter=["devmeas", "p2"],
    trigger=["devmeas", "trg"],
    default=5)
sys.add_param(
    "devmeas p1", "cnt",
    None,
    ["devmeas", "p5"])
# ============================
