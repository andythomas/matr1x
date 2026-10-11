# This file is part of a software collection for data aquisition (matr1x).
# Copyright (C) 2006-2026 matr1x developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3.0, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Tests for the SystemListWidget state handling."""

from matr1x.core.error_handling import Success
from matr1x.core.models import SystemCapability, SystemReference
from matr1x.gui.shared import SystemListWidget


def test_stateful_system_list_swaps_conflicting_states(qapp, monkeypatch):
    """Selecting an occupied state swaps both system-reference tokens."""
    system_list = SystemListWidget(report_config_errors=False)
    capability = SystemCapability(
        source="example",
        stateful=True,
        states=("primary", "secondary"),
        state_exclusion_groups={"primary": "first", "secondary": "second"},
        class_name="ExampleSystem",
    )
    monkeypatch.setattr(system_list, "test_import", lambda _source: Success(capability))
    monkeypatch.setattr(system_list, "systems_changed", lambda: None)

    system_list.add_systems(["first::primary", "second::secondary"])
    first = system_list.item(0)
    second = system_list.item(1)

    system_list._select_state(first, "secondary")

    assert SystemReference.from_value(first.text()).state == "secondary"
    assert SystemReference.from_value(second.text()).state == "primary"


def test_stateful_system_list_rejects_conflicting_classes_across_sources(qapp, monkeypatch):
    """Same-named classes cannot occupy one state exclusion group twice."""
    system_list = SystemListWidget(report_config_errors=False)
    capability = SystemCapability(
        source="example",
        stateful=True,
        states=("primary", "secondary"),
        state_exclusion_groups={"primary": "shared", "secondary": "shared"},
        class_name="ExampleSystem",
    )
    monkeypatch.setattr(system_list, "test_import", lambda _source: Success(capability))
    monkeypatch.setattr(system_list, "systems_changed", lambda: None)

    system_list.add_systems(["first::primary", "second::secondary"])

    assert system_list.count() == 1
    assert SystemReference.from_value(system_list.item(0).text()).state == "primary"
