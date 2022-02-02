# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
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

# ============================
