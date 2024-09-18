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
dummy system demonstrating how to interface to a control gui (control_dummy)
"""
# ============================
# Custom import area
# ============================


from matr1x.control import control_dummy
from matr1x.scpi_tcpserver import PORT
from matr1x.system import System

# ============================


# ============================
# initialize system
sys = System()
sys.dcdata["Source"] = "dummy system with GUI for testing matr1x-matrix"
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
sys.add_dev("gui", control_dummy.clientdevice,
            (f"TCPIP::localhost::{PORT}::SOCKET",))
# ============================
# define columns for measurement
# ============================
sys.add_param(
    "guiv1", "int",
    ["gui", "v1"],
    ["gui", "v1"])
sys.add_param(
    ["guiv2", "guiv3"], ["float", "float"],
    ["gui", "v2v3"],
    ["gui", "v2v3"])
sys.add_param(
    "guiv4", "bool",
    ["gui", "v4"],
    ["gui", "v4"])
sys.add_param(
    "guiv5", "float",
    None,
    ["gui", "v5"])

# ============================
