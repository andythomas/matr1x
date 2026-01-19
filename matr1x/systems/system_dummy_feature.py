# This file is part of a software collection for data acquisition (matr1x).
# Copyright (C) 2006-2026 matr1x developers
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

Here different types of syntaxes which can be used in the device/column
definitions are demonstrated.
"""
# ============================
# Custom import area
# ============================

from matr1x import get_config_dict
from matr1x.devices.dummy import dummy
from matr1x.system import System

# ============================


# ============================
# This area contains the required MeasSystem definition and
# the optional reimplementation of the set and reset function
# ============================
class MeasSystem(System):
    """Measurement system for dummy feature demonstration."""

    def __init__(self):
        """
        Initialize the MeasSystem.

        This method initializes the measurement system by setting up
        default configurations, updating them from user settings, and
        initializing data collection attributes.
        """
        super().__init__()
        # define default parameters for configurable settings
        self.config = {
            "setting1": "VOLT",
            "setting2": True,
            "setting3": 3.3215,
            "setting4": "~/.matr1x.toml",
        }
        # here one updates the config with settings potentially saved in the
        # user config. The ~/.matr1x.toml or local matr1x.toml file can contain
        # the following:
        # [matr1x.systems.system_dummy_feature]
        # setting1 = "CURR"
        # setting2 = 2
        # additionally, types and limits can be specified in the config
        # using the following:
        # [matr1x.systems.system_dummy_feature._types]
        # # type definition can be
        # # int, float, string
        # # string according to this specification:
        # # type;;strict;;val1;;val2;;val3;;val4
        # # type;;range;;lower;;upper;;step
        # # the latter only works for int/float and upper/step are optional
        # # string value must not contain ;;
        # setting1 = "str;;strict;;CURR;;VOLT"
        # # positive ints
        # setting2 = "int;;range;;0;;300;;30"
        # setting3 = "float"
        self.config.update(get_config_dict("matr1x.systems.system_dummy_feature"))
        self.dcdata["source"] = "Dummy feature system"
        self.dcdata["publisher"] = "matr1x measurement suite"

    def get_dev2_p1(self):
        """
        Test function for using in parameter getter.

        In order to use a method as a getter it should must have no
        required arguments.
        """
        return self.devs["dev2"].p1

    def set_dev2_p1(self, value):
        """
        Test function for using in parameter setter.

        In order to use a method as setter it must have exactly one
        argument, which corresponds to the value to which the parameter
        should be set.
        """
        self.devs["dev2"].p1 = value

    def set(self, *args, **kwargs):
        """
        Initialize and configure the measurement.

        This function is called by matrix upon initialization of the
        measurement. The devices in the devs dictionary are
        opened/initialized and can be configured if necessary.
        """
        # wrap base system function for safe handling of opening
        super().set(*args, **kwargs)
        # configure devices upon initialization
        self.devs["dev1"].p2 = 10
        self.devs["dev2"].configure(
            setting1=self.config["setting1"], setting2=self.config["setting2"]
        )
        # add a comment when set is finished
        # this might not be required (i.e. added automatically) depending on your device
        self.dcdata["description"] = f"configuring dev2 to '{self.config['setting1']}'"

    def reset(self, *args, **kwargs):
        """
        Deinitialize the measurement.

        This function is called by matrix upon deinitialization of the
        measurement.
        """
        # set some parameter upon deinitializtion
        self.devs["dev1"].p2 = 0
        if "status" in kwargs and kwargs["status"] == "errored":
            # perform special cleanup on error
            self.devs["dev2"].p1 = -1
        # wrap base system function for safe handling of opening
        super().reset(*args, **kwargs)


# ============================


# ============================
# initialize system
system = MeasSystem()
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
# of arguments that is passed upon device initializeation when system.set() is
# called.
# The fourth parameter (kwargs) accepts a dictionary with keyword arguments.
# The fifth parameter (config_params) can be a dictionary specifying possible
# query options which allow to readout the configuration of a device which will
# be stored in the data file header.
system.add_dev(
    "dev1",
    dummy,
    args=("TCPIP::localhost::10008::SOCKET",),
    kwargs={"p1": 5, "p4": [5, 3, 2, 1]},
    config_params={"p4": "p4"},
)
system.add_dev(
    "dev2", dummy, args=("TCPIP::localhost::10009::SOCKET",), config_params={"p2": "p2"}
)

# ============================
# define columns for measurement
# ============================
# first parameter is column name, second is units,
# Further parameters are the set and read functions (keyword setter/getter).
# Those can be specified as callable function or as list with the entries
# [device_name, method, optional (extra) arguments, optional keyword arguments]
# Alternatively a string can be passed, which resolves to a function of sys,
# i.e., has to be defined in the MeasSystem.
# Further keyword arguments include the trigger function, chunks
# (=length of readout array, used only for HDF5 systems), and a default value
# to be used when setting the device (used if no value is specified
# in the sweep file)
system.add_param(["dev1 p3a", "dev1 p3b"], ["cnta", "cntb"], ["dev1", "p3"], ["dev1", "p3"])
system.add_param(
    "dev1 p2",
    "cnt",
    setter=["dev1", "p2"],
    getter=["dev1", "p2"],
    trigger=["dev1", "trg"],
    default=5.0,
)
system.add_param("dev1 p1", "cnt", None, ["dev1", "p1"])
system.add_param("dev2 p1", "cnt", "set_dev2_p1", "get_dev2_p1")
# ============================
