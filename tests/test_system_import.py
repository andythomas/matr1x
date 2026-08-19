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
from pydantic import BaseModel

import matr1x
import matr1x.system as system_module
from matr1x.error_handling import Error, Success
from matr1x.models import SystemReference
from matr1x.system import MergedSystem, StatefulSystem, System

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
    capability = System.inspect_file(system_file)
    assert isinstance(capability, Success)
    reference = SystemReference(
        source=str(system_file),
        state=capability.value.states[0] if capability.value.stateful else None,
    )
    system = System.from_file(reference)
    assert isinstance(system, Success)


def test_invalid_config_preserves_supplied_values(monkeypatch):
    """One invalid field does not discard valid values or model defaults."""

    class IncompleteConfig(BaseModel):
        address: str
        sample_count: int
        initial_value: float = 3.14

    monkeypatch.setattr(
        system_module,
        "resolve_config_path",
        lambda _config, _section: {
            "address": "TCPIP::localhost::10034::SOCKET",
            "sample_count": "invalid",
        },
    )
    monkeypatch.setattr(matr1x, "validation_errors", [])
    system = System()

    system.load_config(IncompleteConfig, "test.system")

    assert system.config.address == "TCPIP::localhost::10034::SOCKET"
    assert system.config.initial_value == 3.14
    assert matr1x.validation_errors


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


@pytest.mark.parametrize("export_name", ["system"])
def test_system_file_supports_legacy_initialized_export(tmp_path, caplog, export_name):
    """Load initialized legacy exports while emitting a soft-deprecation warning."""
    system_file = tmp_path / "system_legacy.py"
    system_file.write_text(f"from matr1x.system import System\n\n{export_name} = System()\n")

    result = System.from_file(system_file)
    assert isinstance(result, Success)
    warning = result.value.warnings[0]
    assert f"exported as '{export_name}' is deprecated" in warning[0]


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


def test_stateful_system_selects_state_and_config_section(monkeypatch):
    """The selected state determines the accessor and configuration section."""
    sections = []

    class ExampleConfig(BaseModel):
        value: int

    class ConfiguredStatefulSystem(StatefulSystem):
        states = ("primary", "secondary")

        def __init__(self, state):
            super().__init__(state)
            self.load_config(ExampleConfig, "matr1x.systems.configured")

    def resolve_config(_config, section):
        sections.append(section)
        return {"value": 7}

    monkeypatch.setattr(system_module, "resolve_config_path", resolve_config)

    system = ConfiguredStatefulSystem("secondary")

    assert system.state == "secondary"
    assert system.accessor_name == "ConfiguredStatefulSystem_secondary"
    assert sections == ["matr1x.systems.configured.secondary"]
    assert system.config_section == "matr1x.systems.configured.secondary"
    assert system.config.value == 7


def test_state_exclusion_groups_control_coexistence():
    """States share one group by default and explicit groups may coexist."""

    class ExclusiveSystem(StatefulSystem):
        states = ("primary", "secondary")

    primary = ExclusiveSystem("primary")
    primary.source = "example"
    secondary = ExclusiveSystem("secondary")
    secondary.source = "example"

    with pytest.raises(ValueError, match="share exclusion group"):
        MergedSystem([primary, secondary])

    class IndependentSystem(StatefulSystem):
        states = ("primary", "secondary")
        state_exclusion_groups = {"primary": "first", "secondary": "second"}

    primary = IndependentSystem("primary")
    primary.source = "example"
    secondary = IndependentSystem("secondary")
    secondary.source = "example"

    assert [system.state for system in MergedSystem([primary, secondary]).subsys] == [
        "primary",
        "secondary",
    ]
