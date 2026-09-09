# This file is part of a software collection for data aquisition (matr1x).
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
"""Shared pytest fixtures for matr1x tests."""

import importlib
import sys
from pathlib import Path

import pytest

from matr1x.gui.app import MApplication

TESTS_ROOT = Path(__file__).resolve().parent


def discover_system_files() -> list[Path]:
    """
    Discover system files in the ``matr1x/systems`` folder.

    Systems with unavailable optional dependencies are excluded from the
    list, e.g. ``system_elabftw.py`` if ``elabapi_python`` is not installed.

    Returns
    -------
    list[Path]
        Paths of the importable system files.
    """
    system_folder = TESTS_ROOT.parent / "matr1x" / "systems"
    system_files = list(system_folder.glob("system_*"))
    try:
        importlib.import_module("elabapi_python")
    except ImportError:
        elab_system_file = system_folder / "system_elabftw.py"
        if elab_system_file in system_files:
            system_files.remove(elab_system_file)
    return system_files


def pytest_generate_tests(metafunc):
    """Parametrize tests over the discovered system files."""
    if "system_file" in metafunc.fixturenames:
        metafunc.parametrize(
            "system_file",
            discover_system_files(),
            ids=lambda p: p.name,
        )


@pytest.fixture(scope="session")
def qapp():
    """Create and later exit an MApplication instance."""
    argv = sys.argv or ["pytest"]
    app = MApplication(argv)
    yield app


@pytest.fixture
def tests_root() -> Path:
    """Return the root directory of the test suite."""
    return TESTS_ROOT


@pytest.fixture
def repo_root() -> Path:
    """Return the root directory of the repository."""
    return TESTS_ROOT.parent


@pytest.fixture
def input_dir() -> Path:
    """Return the directory containing test input files."""
    return TESTS_ROOT / "input"


@pytest.fixture
def data_dir() -> Path:
    """Return the directory containing test data files."""
    return TESTS_ROOT / "data"
