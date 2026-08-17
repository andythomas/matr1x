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
"""Test basic GUI functions in matrix preview."""

from pathlib import Path

from matr1x.scripts import matrix_preview

path = Path(__file__).resolve().parent
test_ma8_file = path / "data/random_test.ma8"


def test_matrix_preview_run(qtbot, qapp):
    """
    Start a basic matrix preview.

    Asserts
    -------
    main window is visible
    the full GUI is built before a file is loaded
    filename is set after load
    the file and column selectors are populated after load
    the simple plot widget is visible
    """
    main_window = matrix_preview.SweepPreview()
    main_window.show()
    qtbot.addWidget(main_window)
    qtbot.waitExposed(main_window)
    qapp.processEvents()
    assert main_window.isVisible()
    # full GUI is available before any file is loaded
    assert main_window.spw.isVisible()
    assert main_window.ui.file_selector.isEnabled() is False
    assert main_window.ui.actions.export_png.isEnabled() is False

    main_window.open_file(test_ma8_file)
    qtbot.waitUntil(
        lambda: main_window.filename is not None
        and main_window.ui.file_selector.count() > 0,
        timeout=2000,
    )
    assert main_window.filename is not None
    assert main_window.filename.name == test_ma8_file.name
    assert main_window.spw.isVisible()
    assert main_window.ui.file_selector.currentText() == test_ma8_file.name
    assert main_window.column_selector[0].count() > 1
    assert main_window.ui.actions.export_png.isEnabled() is True
