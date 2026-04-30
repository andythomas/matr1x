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
"""Test basic GUI functions in sweep generator."""

from collections.abc import Generator
from pathlib import Path

import numpy
import pytest
from matr1x.scripts import sweep_generator
from PySide6.QtWidgets import QLineEdit

path = Path(__file__).resolve().parent
test_sweep_file = path / "sweep_for_test.sw8"

_SWEEP_GENERATOR_WINDOW: sweep_generator.MainWindow | None = None


@pytest.fixture(scope="module")
def sweep_generator_window(qapp) -> Generator[sweep_generator.MainWindow, None, None]:
    """Create a shared sweep generator window for this module."""
    global _SWEEP_GENERATOR_WINDOW
    if _SWEEP_GENERATOR_WINDOW is None:
        _SWEEP_GENERATOR_WINDOW = sweep_generator.MainWindow()
        _SWEEP_GENERATOR_WINDOW.show()
        _SWEEP_GENERATOR_WINDOW.in_pytest = True
        qapp.processEvents()
    yield _SWEEP_GENERATOR_WINDOW
    _SWEEP_GENERATOR_WINDOW.close()
    _SWEEP_GENERATOR_WINDOW = None


@pytest.fixture(autouse=True)
def reset_sweep_generator_window(sweep_generator_window: sweep_generator.MainWindow, qapp) -> None:
    """Reset state to avoid cross-test interference."""
    window = sweep_generator_window
    for widget in qapp.allWidgets():
        if isinstance(widget, sweep_generator.SweepPreviewPopup):
            widget.close()
    window.new_file(reset_systems=True)
    qapp.processEvents()


def test_sweep_generator_systems(qtbot, qapp, sweep_generator_window: sweep_generator.MainWindow):
    """
    Test if the removal of a system works properly.

    Asserts
    -------
    The system filenames are correct after system removal
    """
    main_window = sweep_generator_window
    qtbot.waitExposed(main_window)
    qapp.processEvents()

    mod = str((path / "../matr1x/systems/system_dummy.py").resolve())
    mod2 = str((path / "../matr1x/systems/system_dummy_meas.py").resolve())
    main_window.ui.widgets.system_list.add_systems([mod, mod2])
    main_window.update_systems()
    qtbot.waitUntil(lambda: main_window.ui.widgets.system_list.count() > 1, timeout=2000)
    main_window.ui.widgets.system_list.delete_systems()
    qtbot.waitUntil(lambda: main_window.ui.widgets.system_list.count() == 1, timeout=2000)
    assert main_window.columns.filenames == ["matr1x.systems.system_dummy"]


def test_sweep_generator_run(qtbot, qapp, sweep_generator_window: sweep_generator.MainWindow):
    """
    Start a basic sweep generator run.

    Asserts
    -------
    main window is visible
    system dummy is added to the list
    title shows unsaved
    title clears unsaved
    loop is added to sweep table
    preview window popped up
    draft and compare sweep
    save and compare sweep
    """
    main_window = sweep_generator_window
    qtbot.waitExposed(main_window)
    qapp.processEvents()
    assert main_window.isVisible()

    module = str((path / "../matr1x/systems/system_dummy.py").resolve())
    main_window.ui.widgets.system_list.add_systems([module])
    main_window.update_systems()
    qtbot.waitUntil(lambda: main_window.ui.widgets.system_list.count() > 0, timeout=2000)
    assert main_window.windowTitle() == "Sweep Generator: *<unsaved>"

    main_window.update_window_title(dirty=False)
    assert main_window.windowTitle() == "Sweep Generator"

    system = main_window.ui.widgets.system_list.item(0).text()
    assert system == "matr1x.systems.system_dummy"

    start = "0"
    end = "10"
    points = "11"
    main_window.grid_widgets[0].start.setText(start)
    main_window.grid_widgets[0].end.setText(end)
    main_window.grid_widgets[0].points.setText(points)
    main_window.grid_widgets[0].append.click()
    sweep = numpy.linspace(float(start), float(end), int(points)).tolist()
    main_window.update_window_title(dirty=False)
    widget = main_window.ui.widgets.sweep_table.cellWidget(0, 0)
    assert isinstance(widget, QLineEdit)
    assert widget.text() == start
    widget = main_window.ui.widgets.sweep_table.cellWidget(0, 1)
    assert isinstance(widget, QLineEdit)
    assert widget.text() == end
    widget = main_window.ui.widgets.sweep_table.cellWidget(0, 2)
    assert isinstance(widget, QLineEdit)
    assert widget.text() == points

    main_window.ui.actions.preview.trigger()
    qtbot.waitUntil(
        lambda: any(
            isinstance(w, sweep_generator.SweepPreviewPopup) and w.isVisible()
            for w in qapp.allWidgets()
        ),
        timeout=2000,
    )
    previews = [
        w
        for w in qapp.allWidgets()
        if isinstance(w, sweep_generator.SweepPreviewPopup) and w.isVisible()
    ]
    assert len(previews) == 1

    main_window.ui.actions.sweep.trigger()
    for i in range(main_window.ui.widgets.sweep_preview.model().rowCount()):
        item = main_window.ui.widgets.sweep_preview.item(i, 0)
        assert item is not None
        assert item.text().strip() == "-a " + str(sweep[i])

    main_window.grid_widgets[1].start.setText("1")
    main_window.grid_widgets[1].end.setText("2")
    main_window.grid_widgets[1].points.setText("2")
    main_window.grid_widgets[1].append.click()
    main_window.grid_widgets[0].repeat.setValue(2)
    main_window.grid_widgets[0].updown.setChecked(True)
    filename = "sweep_sweep"
    save_file = path / filename
    main_window._write_file_to_disk(save_file, False)
    assert main_window.last_filename is not None
    assert main_window.last_filename.name == str(filename) + ".sw8"
    assert main_window.last_filename.exists()
    with main_window.last_filename.open() as f:
        written_file = f.readlines()
    assert test_sweep_file.exists()
    with test_sweep_file.open() as f:
        original_file = f.readlines()
    for i, _ in enumerate(written_file):
        if i != 9:  # this is the timestamp
            assert written_file[i] == original_file[i]
    main_window.last_filename.unlink()


def test_sweep_generator_load(qtbot, qapp, sweep_generator_window: sweep_generator.MainWindow):
    """
    Start a basic sweep generator run.

    Asserts
    -------
    main window is visible
    sweep test file exists
    sweep_params, repeat, up_down, and loop_over are correctly loaded
    repeat, updown, and loopover widgets are correctly set
    """
    main_window = sweep_generator_window
    qtbot.waitExposed(main_window)
    qapp.processEvents()
    assert main_window.isVisible()
    assert test_sweep_file.exists()

    main_window.open_file(test_sweep_file)
    assert main_window.columns.loop_over == [-1, -1]
    assert main_window.columns.up_down == [2, 0]
    assert main_window.columns.repeat == [2, 1]
    assert main_window.columns.parameter == [[["0", "10", "11"]], [["1", "2", "2"]]]
    assert main_window.grid_widgets[0].repeat.value() == 2
    assert main_window.grid_widgets[1].repeat.value() == 1
    assert main_window.grid_widgets[0].updown.isChecked() is True
    assert main_window.grid_widgets[1].updown.isChecked() is False
    assert main_window.grid_widgets[0].loopover.currentText() == "None"
    assert main_window.grid_widgets[1].loopover.currentText() == "None"


def test_sweep_generator_sweep_table(
    qtbot, qapp, sweep_generator_window: sweep_generator.MainWindow
):
    """
    Test changing points entry in sweep_table.

    Asserts
    -------
    main window is visible
    sweep parameters are set up correctly
    points value can be changed in sweep_table
    window title becomes dirty after change
    sweep_params data is updated correctly
    """
    main_window = sweep_generator_window
    qtbot.waitExposed(main_window)
    qapp.processEvents()
    assert main_window.isVisible()

    module = str((path / "../matr1x/systems/system_dummy.py").resolve())
    main_window.ui.widgets.system_list.add_systems([module])
    main_window.update_systems()
    qtbot.waitUntil(lambda: main_window.ui.widgets.system_list.count() > 0, timeout=2000)
    main_window.grid_widgets[0].start.setText("0")
    main_window.grid_widgets[0].end.setText("10")
    main_window.grid_widgets[0].points.setText("2")
    main_window.grid_widgets[0].append.click()
    qtbot.waitUntil(
        lambda: main_window.ui.widgets.sweep_table.cellWidget(0, 2) is not None, timeout=2000
    )
    widget = main_window.ui.widgets.sweep_table.cellWidget(0, 2)
    assert isinstance(widget, QLineEdit)
    assert widget.text() == "2"
    assert main_window.columns.parameter[0][0][2] == "2"

    main_window.update_window_title(dirty=False)
    assert "unsaved" not in main_window.windowTitle().lower()

    points_widget = main_window.ui.widgets.sweep_table.cellWidget(0, 2)
    assert isinstance(points_widget, QLineEdit)

    points_widget.clear()
    qtbot.keyClicks(points_widget, "3")
    points_widget.editingFinished.emit()
    qtbot.waitUntil(lambda: points_widget.text() == "3", timeout=2000)
    assert points_widget.text() == "3"
    assert main_window.columns.parameter[0][0][2] == "3"
    assert "*" in main_window.windowTitle()

    main_window.update_window_title(dirty=False)
