# This file is part of a software collection for data acquisition (matr1x).
# Copyright (C) 2006-2025 matr1x developers
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
Tests for verifying import and instantiation of matr1x systems from system configuration files.

This module discovers all system configuration files in the matr1x/systems directory and
runs tests to ensure they can be imported as valid System objects.
"""
from pathlib import Path

import pytest
from matr1x.system import System

# Collect all files in the system-folder
path = Path(__file__).resolve().parent
system_folder = path / ".." / "matr1x" / "systems"
system_files = list(system_folder.glob("system_*"))


@pytest.mark.parametrize("system_file", system_files, ids=lambda p: p.name)
def test_system_import(system_file):
    """
    Test that a system file can be imported as a System object.

    Parameters
    ----------
    system_file : Path
        Path to the system configuration file to import.

    Raises
    ------
    AssertionError
        If the loaded object is not an instance of System.
    """
    system = System.from_file(system_file)
    assert isinstance(system, System)
