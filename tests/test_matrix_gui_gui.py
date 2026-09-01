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
"""Test basic GUI functions in matrix-gui."""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt

from matr1x import output_extension
from matr1x.core.eval import loadmatrix
from matr1x.core.models import SystemInfo, SystemSelectionInfo
from matr1x.scripts import matrix_gui

path = Path(__file__).resolve().parent
test_sweep_file = path / "sweep_for_matrix_gui.sw8"


@pytest.fixture(autouse=True)
def clean_data_files():
    """
    Clean up data files created during tests.

    This fixture runs automatically before and after each test to clean up any
    data files that were created. It tracks existing files before the test and
    removes any new files created during test execution.

    Yields
    ------
    None
    """
    existingfiles = set(path.glob(f"*{output_extension}"))
    # run test
    yield
    files = set(path.glob(f"*{output_extension}"))
    newfiles = files - existingfiles
    for f in newfiles:
        f.unlink()


def test_matrix_gui_run(qtbot, qapp):
    """
    Test basic matrix-gui functionality.

    Asserts
    -------
    main window is visible
    sweep exists
    config reference value is successfully changed
    """
    main_window = matrix_gui.MainWindow()
    main_window.show()
    qtbot.waitExposed(main_window)
    qapp.processEvents()
    assert main_window.isVisible()

    assert test_sweep_file.exists()

    main_window.ui.widgets.input_file.setText(str(test_sweep_file))
    main_window.ui.actions.config.trigger()
    system_index = main_window.ui.widgets.config_editor.model.index(0, 0)
    reference_value_row = next(
        row
        for row in range(main_window.ui.widgets.config_editor.model.rowCount(system_index))
        if main_window.ui.widgets.config_editor.model.index(row, 0, system_index).data()
        == "reference_value"
    )
    reference_value_index = main_window.ui.widgets.config_editor.model.index(
        reference_value_row, 1, system_index
    )
    reference_value = 2
    main_window.ui.widgets.config_editor.model.setData(
        reference_value_index, reference_value, Qt.ItemDataRole.EditRole
    )
    main_window.queue_measurement()
    main_window.ui.actions.start.trigger()
    qtbot.waitUntil(lambda: not main_window.running, timeout=5000)
    ma8file = test_sweep_file.with_suffix(".ma8")
    header, _data = loadmatrix(ma8file)
    assert header["system query"]["system_config"]["reference_value"] == reference_value


def test_queue_action_disabled_for_invalid_config(qtbot, qapp, monkeypatch):
    """Invalid device config disables Queue and exposes the reason in the tooltip."""
    main_window = matrix_gui.MainWindow()
    main_window.show()
    qtbot.waitExposed(main_window)
    qapp.processEvents()

    main_window.ui.widgets.input_file.setText(str(test_sweep_file))
    qtbot.waitUntil(lambda: main_window.ui.actions.queue.isEnabled(), timeout=2000)
    main_window.ui.actions.config.setChecked(False)
    monkeypatch.setattr(
        main_window.ui.widgets.config_editor,
        "get_validation_errors",
        lambda: ["matr1x.systems.demo.devices.dev.address: invalid address"],
    )

    main_window.update_queue_action_state()

    assert not main_window.ui.actions.queue.isEnabled()
    assert "invalid address" in main_window.ui.actions.queue.toolTip()
    assert main_window.ui.widgets.config_editor.isVisible()
    main_window.queue_measurement()
    assert main_window.ui.widgets.meas_list.count() == 0


def test_queue_config_uses_resolved_stateful_sections():
    """Queue editors must not treat serialized state references as config paths."""
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
