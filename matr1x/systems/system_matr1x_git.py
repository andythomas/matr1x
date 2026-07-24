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
Define a system which adds information about the matr1x code.

This adds code changes and git reference to the data file header.
"""

from matr1x.devices.git import gitDevice
from matr1x.system import System
from matr1x.util import get_package_path


# ============================
# define system class
class Git(System):
    """System adding git information to the data file header."""

    def __init__(self):
        """Initialize the git metadata device."""
        super().__init__()
        self.dcdata["source"] = "git information of matr1x"
        self.add_dev(
            "git",
            gitDevice,
            # package path of matr1x can be used if an editable install out
            # of a git repository is used. Otherwise hard code the path here.
            args=(get_package_path("matr1x"),),
        )

# ============================
