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
"""Dummy system demonstrating integration of a control gui (control_dummy)."""
# ============================
# Custom import area
# ============================

from matr1x.control import control_dummy
from matr1x.system import System

# ============================


# ============================
# define system class
class GuiIntegration(System):
    """Dummy system demonstrating integration of a control gui (control_dummy)."""

    def __init__(self):
        """Initialize the control GUI device and its parameters."""
        super().__init__()
        self.dcdata["source"] = "dummy system with GUI for testing matr1x-matrix"
        # ========================================================================
        # This is the main system area.
        # Device definition and configuration takes place here, but devices do
        # not yet get opened!
        #
        # IMPORTANT:
        #   The devices are not allowed to be opened here!
        #   Otherwise the import would block any other use of the devices.
        #   Make sure to adhere to this or errors will occur!
        # ========================================================================
        self.add_dev(
            "gui",
            control_dummy.clientdevice,
            ("TCPIP::localhost::8897::SOCKET",),
            kwargs={"name": "control-dummy"},
        )
        # ============================
        # define columns for measurement
        # ============================
        self.add_param("guiv1", "int", ["gui", "v1"], ["gui", "v1"])
        self.add_param(["guiv2", "guiv3"], ["float", "float"], ["gui", "v2v3"], ["gui", "v2v3"])
        self.add_param("guiv4", "bool", ["gui", "v4"], ["gui", "v4"])
        self.add_param("guiv5", "float", None, ["gui", "v5"])

# expose the class; System.from_file() instantiates it
system = GuiIntegration
