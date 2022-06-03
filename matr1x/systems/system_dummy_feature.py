# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
"""
This module defines a system for testing and demonstration purposes of various
different types of syntaxes which can be used in the device/column definitions
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
class MeasSystem(System):
    def __init__(self):
        super().__init__()
        self.dcdata["Source"] = "Dummy feature system"
        self.dcdata["Publisher"] = "matr1x measurement suite"

    def set(self, *args, **kwargs):
        """
        This function is called by matrix upon initialization of the
        measurement.
        The devices in the devs dictionary are opened/initialized
        and can be configured if necessary.
        """
        # wrap base system function for safe handling of opening
        super().set(*args, **kwargs)
        # configure devices upon initialization
        sys.devs["dev1"].p2 = 10
        sys.devs["dev2"].configure(setting1="VOLT", setting2=5)

    def reset(self, *args, **kwargs):
        """
        This function is called by matrix upon deinitialization of the
        measurement.
        """
        # set some parameter upon deinitializtion
        sys.devs["dev1"].p2 = 0
        # wrap base system function for safe handling of opening
        super().reset(*args, **kwargs)


# ============================


# ============================
# initialize system
sys = MeasSystem()
sys.dcdata["Source"] = "dummy system for testing matr1x-matrix"
# ============================


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
sys.add_dev("dev1", dummy, args=("TCPIP::localhost::10008::SOCKET", ),
            kwargs={"p1": 5, "p4": [5, 3, 2, 1]}, config_params={"p4":
                                                                 "p4"})
sys.add_dev("dev2", dummy, args=("TCPIP::localhost::10007::SOCKET", ))

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
    ["dev p3a", "dev p3b"], ["cnta", "cntb"],
    ["dev1", "p3"],
    ["dev1", "p3"])
sys.add_param(
    "dev p2", "cnt",
    setter=["dev1", "p2"],
    getter=["dev1", "p2"],
    trigger=["dev1", "trg"],
    default=5.)
sys.add_param(
    "dev p1", "cnt",
    None,
    ["dev1", "p1"])
sys.add_param(
    "dev2 p1", "cnt",
    None,
    ["dev2", "p1"])
# ============================
