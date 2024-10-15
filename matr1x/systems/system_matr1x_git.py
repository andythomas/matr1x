# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2024 matr1x developers. All rights reserved.
# ---
"""
This module defines a system which adds information about the matr1x code used
to run the measurement to the data file header.
"""
from matr1x.devices.git import gitDevice
from matr1x.system import System
from matr1x.util import get_package_path

# ============================
# initialize system instance
sys = System()
# define Dublin core source parameter
sys.dcdata["Source"] = "git information of matr1x"
# ============================

sys.add_dev("git",
            gitDevice,
            # package path of matr1x can be used if an editable install out
            # of a git repository is used. Otherwise hard code the path here.
            args=(get_package_path("matr1x"), ),
            )
