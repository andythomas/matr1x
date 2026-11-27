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

import shutil
from pathlib import Path
from typing import ClassVar

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from matr1x.apps import queue as matrix_gui
from matr1x.core.eval import loadmatrix
from matr1x.gui import input_dialogs


def test_script_input_calls():
    """Test detection of script input calls, ignoring comments and strings."""
    assert matrix_gui._script_input_calls('input("a")') == ["input"]
    assert matrix_gui._script_input_calls("input_bool('q')\nx = input_numerical('v')") == [
        "input_bool",
        "input_numerical",
    ]
    assert matrix_gui._script_input_calls("# input('a')\nx = 'input(b)'") == []
    assert matrix_gui._script_input_calls("x = dev.input('a')") == []
    assert matrix_gui._script_input_calls("def broken(:") == []


def test_matrix_gui_run(qtbot, qapp, monkeypatch, input_dir: Path, tmp_path: Path):
    """
    Test basic matrix-gui functionality.

    Asserts
    -------
    main window is visible
    sweep exists
    config reference value is successfully changed
    queue action is disabled and exposes the reason for an invalid config
    """
    main_window = matrix_gui.MainWindow()
    main_window.show()
    qtbot.waitExposed(main_window)
    qapp.processEvents()
    assert main_window.isVisible()

    test_sweep_file = tmp_path / "sweep_for_matrix_gui.sw8"
    shutil.copy(input_dir / "sweep_for_matrix_gui.sw8", test_sweep_file)
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
    header, _data = loadmatrix(ma8file, to_polars=True)
    assert header["system query"]["system_config"]["reference_value"] == reference_value

    main_window.ui.widgets.input_file.setText(str(input_dir / "sweep_for_matrix_gui.sw8"))
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


def test_matrix_gui_queue_script(qtbot, qapp, monkeypatch, input_dir: Path, tmp_path: Path):
    """
    Test queueing and running a .matrix script in matrix-gui.

    Asserts
    -------
    queue action is enabled for a .matrix input file
    the queued item is a script item showing the input file name
    the script runs and writes a data file with the expected points
    """
    main_window = matrix_gui.MainWindow()
    main_window.show()
    qtbot.waitExposed(main_window)
    qapp.processEvents()

    script_file = tmp_path / "test_script.matrix"
    shutil.copy(input_dir / "matrix_script_gui.matrix", script_file)
    monkeypatch.chdir(tmp_path)

    main_window.ui.widgets.input_file.setText(str(script_file))
    qtbot.waitUntil(lambda: main_window.ui.actions.queue.isEnabled(), timeout=2000)
    main_window.queue_measurement()

    assert main_window.ui.widgets.meas_list.count() == 1
    item = main_window.ui.widgets.meas_list.parameters(0)
    assert item.kind == "script"
    assert item.display_name == str(script_file)
    assert "boring_testrun" in item.input_file  # generated script content
    assert (
        main_window.ui.widgets.meas_list.item(0).text()
        == "Input: test_script.matrix - Output: <use input>"
    )

    main_window.ui.actions.start.trigger()
    qtbot.waitUntil(lambda: not main_window.running, timeout=15000)
    files = list(tmp_path.glob("boring_testrun*"))
    assert len(files) == 1
    _header, data = loadmatrix(files[0], to_polars=True)
    assert len(data) == 10


def test_matrix_gui_queue_script_input(qtbot, qapp, monkeypatch, tmp_path: Path):
    """
    Test user input dialogs for a queued .matrix script.

    Asserts
    -------
    a text input request from the script opens the (faked) dialog
    the dialog answer is passed to the script and ends up in the datafile
    """
    main_window = matrix_gui.MainWindow()
    main_window.show()
    qtbot.waitExposed(main_window)
    qapp.processEvents()

    class FakeTextInputDialog:
        """Stand-in for TextInputDialog that answers without user interaction."""

        queries: ClassVar[list[str]] = []

        def __init__(self, query, parent=None, timeout=None, default_value=""):
            self.queries.append(query)

        def exec(self):
            return True

        def get_input_text(self):
            return "Andy"

        def result(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(input_dialogs, "TextInputDialog", FakeTextInputDialog)

    script_file = tmp_path / "input_test.matrix"
    script_file.write_text(
        "# system def : matr1x.systems.system_dummy\n"
        "# system names : dev p2,timeUTC\n"
        "# system units : cnt,s\n"
        "# file v8, time stamp : 2026-02-06T12:00:00\n"
        'name = input("Who is running this?")\n'
        'init_datafile("input_e2e", comment=name)\n'
        "set_value(1, 0.01)\n"
        "measure_system()\n"
        "end_script(True)\n"
    )
    monkeypatch.chdir(tmp_path)

    main_window.ui.widgets.input_file.setText(str(script_file))
    qtbot.waitUntil(lambda: main_window.ui.actions.queue.isEnabled(), timeout=2000)
    main_window.queue_measurement()
    main_window.ui.actions.start.trigger()
    qtbot.waitUntil(lambda: not main_window.running, timeout=15000)

    assert FakeTextInputDialog.queries == ["Who is running this?"]
    files = list(tmp_path.glob("input_e2e*"))
    assert len(files) == 1
    header, _data = loadmatrix(files[0], to_polars=True)
    assert header["dcterms:description"] == "Andy"
