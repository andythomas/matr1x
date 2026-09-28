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
"""Provides an example and test implementation of a control GUI."""

import logging
import sys
from pathlib import Path
from typing import ClassVar

from matr1x.control import (
    ControlWindow,
    GuiDict,
    control_main,
    var,
)
from matr1x.control import guiObject as go
from matr1x.core.util import Command, Get
from matr1x.devices.scpi_dev import makeSCPIdevice

sys.path.insert(0, str(Path(__file__).resolve().parent))


# format is "LayoutKey": Command(type, setfunc, getfunc)
# type can be one of int, float, bool, tuple or list.
# If a pure setter command is needed use Set(type, setfunc)
# If a pure getter command is needed use Get(type getfunc)
# All functions can take optional setargs, getargs arguments containing lists of
# additional arguments for the setfunc and getfunc
common_commands = {
    "*idn": Get(str, "dummy_control"),
}

logger = logging.getLogger(__name__)


class exampleDict(GuiDict):
    """Template One."""

    data: ClassVar[dict[str, var]] = {
        "Example": var(None, columns=["Readout", "Setpoint"]),
        "Set": var(
            None,
            columns=[go.button, go.button],
            init=["Set", "Copy"],
        ),
    }


class exampleDict2(GuiDict):
    """Template Two."""


# define clientdevice to be used by measurement systems interfacing with this
# controlGUI. If no interfacing of a measurement system is intended this can be
# removed.
clientdevice = makeSCPIdevice(exampleDict.cmds, exampleDict2.cmds, common_commands, system=True)


def main():
    """Run the actual control window."""
    control_main(
        "dummy",
        ControlWindow,
        guidicts=(exampleDict, exampleDict2),
        extra_cmds=common_commands,
        # use specific port to allow running next to other controlGUIs
        port=8897,
    )
