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
Tests for verifying import and instantiation of matr1x systems from system configuration files.

This module discovers all system configuration files in the
matr1x/systems directory and runs tests to ensure they can be imported
as valid System objects.
"""

from pathlib import Path

import pytest

from matr1x.error_handling import Success
from matr1x.system import System

# Collect all files in the system-folder
path = Path(__file__).resolve().parent
system_folder = path / ".." / "matr1x" / "systems"
system_files = list(system_folder.glob("system_*"))

# Check if elab dependency is available
elab_available = False
try:
    import elabapi_python  # noqa: F401

    elab_available = True
except ImportError:
    pass  # elab dependency is not installed

# If elab dependency is not available, remove system_elabftw.py from the list
if not elab_available:
    elab_system_file = system_folder / "system_elabftw.py"
    if elab_system_file in system_files:
        system_files.remove(elab_system_file)


@pytest.mark.parametrize("system_file", system_files, ids=lambda p: p.name)
def test_system_import(system_file):
    """
    Test that a system file can be imported as a System object.

    Parameters
    ----------
    system_file : Path
        Path to the system configuration file to import.
    """
    system = System.from_file(system_file)
    assert isinstance(system, Success)


@pytest.mark.parametrize(
    ("contents", "expected_columns"),
    [
        (
            """\
from matr1x.system import System

system = System()
system.add_param("legacy value", "V")
""",
            ["legacy value"],
        ),
        (
            """\
from matr1x.system import System

system = System
""",
            [],
        ),
        (
            """\
from matr1x.system import System

class ClassSystem(System):
    def __init__(self):
        super().__init__()
        self.add_param("class value", "V")

system = ClassSystem
""",
            ["class value"],
        ),
    ],
    ids=["legacy-instance", "base-class-export", "subclass-export"],
)
def test_system_file_accepts_instance_and_subclass(tmp_path, contents, expected_columns):
    """Load both the legacy instance and preferred class-based system forms."""
    system_file = tmp_path / "system_compatibility.py"
    system_file.write_text(contents)

    result = System.from_file(system_file)

    assert isinstance(result, Success)
    assert result.value.columns == expected_columns
