"""
This module defines a system for testing and demonstration purposes including
the HDF5 data file format option.
"""
# ============================
# Custom import area
# ============================

from matr1x.devices.dummy import dummy
from matr1x.system import System

# ============================
# This area contains the required MeasSystem definition and
# the optional reimplementation of the set and reset function
# ============================

# ============================

# initialize system
sys = System()
sys.dcdata["Source"] = "dummy system with HDF5 for testing matr1x-matrix"


# ========================================================================
# define custom functions here
# ========================================================================
# ========================================================================


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

# set require HDF5 flag can also be deleted if not needed
sys.hdf5 = True

# define columns for measurement
sys.add_param(
    "devhdf", "cnt",
    getter=["devhdf", "p4"], chunks=4)
sys.add_param(
    ["devhdf p3a", "devhdf p3b"], ["cnta", "cntb"],
    ["devhdf", "p3"],
    ["devhdf", "p3"],
    chunks=[1, 1])
# ============================
