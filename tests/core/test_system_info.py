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
"""Tests for the SystemInfo model."""

from matr1x.core.models import SystemInfo, SystemSelectionInfo


def test_queue_config_uses_resolved_stateful_sections():
    """Queue editors must not treat state references as config paths."""
    source = "matr1x.systems.system_stateful_dummy"
    section = f"{source}.primary"
    system_info = SystemInfo(
        classes=["StatefulDummy_primary"],
        devices={},
        parameters={},
        methods={},
        variables={},
        config={section: {}},
        selections=[
            SystemSelectionInfo(
                source=source,
                stateful=True,
                states=("primary",),
                state_exclusion_groups={"primary": "__default__"},
                class_name="StatefulDummy",
                state="primary",
                accessor_name="StatefulDummy_primary",
                config_section=section,
            )
        ],
    )

    assert system_info.configurable_sections == [section]
