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


def test_matrix_preview_run(qtbot, qapp, data_dir: Path):
    """
    Start a basic matrix preview.

    Asserts
    -------
    main window is visible
    filename is set after load
    the simple plot widget is visible
    """
    main_window = matrix_preview.SweepPreview()
    main_window.show()
    qtbot.addWidget(main_window)
    qtbot.waitExposed(main_window)
    qapp.processEvents()
    assert main_window.isVisible()

    ma8_file = data_dir / "random_test.ma8"
    main_window.open_file(ma8_file)
    qtbot.waitUntil(
        lambda: (
            main_window.filename is not None and main_window.ui.widgets.file_selector.count() > 0
        ),
        timeout=2000,
    )
    assert main_window.filename is not None
    assert main_window.filename.name == ma8_file.name
    assert main_window.spw.isVisible()


def test_meta_viewer_toggle(qtbot, qapp):
    """
    Toggle the metadata view via its menu action.

    Asserts
    -------
    the dock widget follows the action's checked state
    the action stays in sync when the dock is closed on its own
    """
    main_window = matrix_preview.SweepPreview()
    main_window.show()
    qtbot.addWidget(main_window)
    qtbot.waitExposed(main_window)
    qapp.processEvents()

    meta_action = main_window.ui.actions.meta
    meta_action.setEnabled(True)

    meta_action.trigger()
    qapp.processEvents()
    assert main_window.meta_viewer.isVisible()
    assert meta_action.isChecked()

    meta_action.trigger()
    qapp.processEvents()
    assert not main_window.meta_viewer.isVisible()
    assert not meta_action.isChecked()

    # closing the dock itself unchecks the action again
    main_window.meta_viewer.show()
    qapp.processEvents()
    assert meta_action.isChecked()
    main_window.meta_viewer.close()
    qapp.processEvents()
    assert not meta_action.isChecked()
