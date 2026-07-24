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

import logging
from pathlib import Path

import pytest

from matr1x.error_handling import Error, Success
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


def test_system_file_discovers_local_subclass(tmp_path):
    """Load the sole System subclass defined by the system file."""
    system_file = tmp_path / "system_compatibility.py"
    system_file.write_text(
        """\
from matr1x.system import System

class ClassSystem(System):
    def __init__(self):
        super().__init__()
        self.add_param("class value", "V")
"""
    )

    result = System.from_file(system_file)

    assert isinstance(result, Success)
    assert result.value.columns == ["class value"]


@pytest.mark.parametrize("export_name", ["system", "sys"])
def test_system_file_supports_legacy_initialized_export(tmp_path, caplog, export_name):
    """Load initialized legacy exports while emitting a soft-deprecation warning."""
    system_file = tmp_path / "system_legacy.py"
    system_file.write_text(
        "from matr1x.system import System\n\n"
        f"{export_name} = System()\n"
    )

    with caplog.at_level(logging.WARNING, logger="matr1x.system"):
        result = System.from_file(system_file)

    assert isinstance(result, Success)
    assert f"exported as '{export_name}' is deprecated" in caplog.text


def test_system_file_ignores_imported_system_base(tmp_path, monkeypatch):
    """Only a subclass defined by the system file is considered an entry point."""
    base_file = tmp_path / "imported_system_base.py"
    base_file.write_text(
        """\
from matr1x.system import System

class ImportedBase(System):
    pass
"""
    )
    system_file = tmp_path / "system_derived.py"
    system_file.write_text(
        """\
from imported_system_base import ImportedBase

class LocalSystem(ImportedBase):
    pass
"""
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    result = System.from_file(system_file)

    assert isinstance(result, Success)
    assert type(result.value).__name__ == "LocalSystem"


@pytest.mark.parametrize(
    ("contents", "error"),
    [
        ("from matr1x.system import System\n", "none found"),
        (
            """\
from matr1x.system import System

class First(System):
    pass

class Second(System):
    pass
""",
            "found: First, Second",
        ),
    ],
    ids=["no-local-subclass", "multiple-local-subclasses"],
)
def test_system_file_requires_exactly_one_local_subclass(tmp_path, contents, error):
    """Reject system files that do not meet the single-local-subclass contract."""
    system_file = tmp_path / "system_invalid.py"
    system_file.write_text(contents)

    result = System.from_file(system_file)

    assert isinstance(result, Error)
    assert error in result.error
