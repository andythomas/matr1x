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
"""Module defines a minimal system for testing and demonstration purposes."""

# a dummy device is used to make it runable
from matr1x.devices.dummy import dummy
from matr1x.system import System


class Dummy(System):
    """Dummy system for testing and demonstration purposes."""

    def __init__(self):
        """Initialize the dummy device and its measurement parameter."""
        super().__init__()
        self.dcdata["source"] = "dummy system for testing matr1x-matrix"
        # Device definition and configuration takes place here, but devices are
        # not yet opened.
        self.add_dev(
            "dev",  # name of device, must be unique
            dummy,  # device class, not instanced
            args=("TCPIP::localhost::10007::SOCKET",),  # arguments for init
            # {"timeout": 100, }  # kwargs can be given if needed
        )
        # The device class is instantiated as dummy(*args) when self.set() is
        # called upon start of the measurement.

        # define columns for measurement
        self.add_param(
            "dev p2",  # parameter name, must be unique
            "cnt",  # parameter unit for the data file header
            ["dev", "p2"],  # setter attribute/function is self.devs["dev"].p2
            ["dev", "p2"],  # getter attribute/function is self.devs["dev"].p2
        )
