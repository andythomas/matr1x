"""
This module defines a minimal system for testing and demonstration purposes
"""
# a dummy device is used to make it runable
from matr1x.devices.dummy import dummy
from matr1x.system import System

# ============================
# initialize system instance
sys = System()
# define Dublin core source parameter
sys.dcdata["Source"] = "dummy system for testing matr1x-matrix"
# ============================


# ========================================================================
# This is the main system area
# Device definition and configuration takes plance here, but devices are
# not yet opened
# ========================================================================
sys.add_dev("dev",  # name of device, must be unique
            dummy,  # device class, not instanced
            args=("TCPIP::localhost::10007::SOCKET", ),  # arguments for init
            # {"timeout": 100, }  # kwargs can be given if needed
            )
# The device classes will be instanced and initalized as dummy(*args)
# when sys.set() is called upon start of the measurement.

# ==============================
# define columns for measurement
# ==============================
sys.add_param(
    "dev p2",  # parameter name, must be unique
    "cnt",  # parameter unit for the data file header
    ["dev", "p2"],  # setter attribute/function is sys.devs["dev"].p2
    ["dev", "p2"])  # getter attribute/function is sys.devs["dev"].p2
# ==============================
