# This file is part of a software collection for data aquisition (matr1x).
# Copyright (C) 2006-2025 matr1x developers
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
"""Test basic GUI functions in matrix script."""

import sys
from pathlib import Path

import matr1x.eval
import pytest
from matr1x.gui_util import MApplication
from matr1x.scripts import matrix_preview, matrix_script

GUI_WAIT = 100  # ms

path = Path(__file__).resolve().parent


@pytest.fixture(scope="session")
def qapp():
    """Create and later exit an MApplication instance."""
    argv = sys.argv or ["pytest"]
    app = MApplication(argv)
    yield app


@pytest.mark.timeout(timeout=30, method="thread")
def test_basic_script_run(qtbot, qapp):
    """
    Start a basic matrix script measurement.

    Load a script, set the metadata info, look at the config, reload it
    once, start the measurement and look at it.

    Asserts
    -------
    main window is visible
    preview window popped up
    name fits the init_datafile
    a file was created
    all dcterms are in the file
    the status is 'finished'
    10 rows of data were saved
    """
    main_window = matrix_script.MainWindow()
    main_window.show()
    qtbot.addWidget(main_window)
    qtbot.waitExposed(main_window)
    qapp.processEvents()
    qtbot.wait(GUI_WAIT)

    assert main_window.isVisible()
    base = Path(__file__).parent
    script_filename = "matrix_script_gui.matrix"
    inputfile = base / Path(script_filename)
    main_window.load_from_filename(inputfile)
    assert main_window.windowTitle() == "Matrix Script: " + script_filename

    metadata = main_window.metadata
    creator = "Power User"
    metadata.creator.setText(creator)
    identifier = "np20250929b"
    metadata.identifier.setText(identifier)
    relation = "Adamantium93"
    metadata.relation.setText(relation)
    description = "I: 9,3\nV: 12,2"
    metadata.description.setText(description)

    main_window.config_action.setChecked(True)
    qtbot.wait(GUI_WAIT)
    assert main_window.config_editor.isVisible()
    main_window.config_editor.w_update_config.click()

    main_window.start_pause_action.trigger()
    qtbot.waitUntil(lambda: not main_window.is_running, timeout=5000)
    main_window.preview_action.trigger()
    qtbot.wait(GUI_WAIT)
    previews = [
        w
        for w in qapp.allWidgets()
        if isinstance(w, matrix_preview.SweepPreview) and w.isVisible()
    ]

    assert len(previews) == 1
    assert main_window.measurement_file.name[:14] == "boring_testrun"  # type:ignore
    assert main_window.measurement_file.exists()  # type:ignore
    header, data = matr1x.eval.loadmatrix(main_window.measurement_file)
    assert header["dcterms:creator"] == creator
    assert header["dcterms:identifier"] == identifier
    assert header["dcterms:relation"] == relation
    assert description in header["dcterms:description"]
    assert "This is a testrun!" in header["dcterms:description"]
    assert header["status"] == "finished"
    assert len(data) == 10
    Path(main_window.measurement_file).unlink()

    main_window.new_file()
    qtbot.wait(GUI_WAIT)
    assert main_window.windowTitle() == "Matrix Script"
    qtbot.wait(GUI_WAIT)


def test_CodeEditor_API(qtbot, qapp):
    """
    Confirm the existance of all required methods.

    Asserts
    -------
    Check the existance of these methods: setPlainText, toPlainText,
    toggleLineComment, find_panel, zoomIn, zoomOut, undo, redo, cut,
    copy, paste, formatCode, isModified, setModified, setReadOnly,
    highlight, removeHighlight, setTheme, supportedThemes,
    enableTabCompletion, setSettables, insertText, returnIssues.
    """
    main_window = matrix_script.MainWindow()
    main_window.show()
    qtbot.addWidget(main_window)
    qtbot.waitExposed(main_window)
    qapp.processEvents()
    assert main_window.isVisible()
    editor = main_window.script_edit

    assert hasattr(editor, "setPlainText")
    assert hasattr(editor, "toPlainText")
    assert hasattr(editor, "toggleLineComment")
    assert hasattr(editor, "find")
    assert hasattr(editor, "zoomIn")
    assert hasattr(editor, "zoomOut")
    assert hasattr(editor, "undo")
    assert hasattr(editor, "redo")
    assert hasattr(editor, "cut")
    assert hasattr(editor, "copy")
    assert hasattr(editor, "paste")
    assert hasattr(editor, "formatCode")
    assert hasattr(editor, "isModified")
    assert hasattr(editor, "setModified")
    assert hasattr(editor, "setReadOnly")
    assert hasattr(editor, "highlight")
    assert hasattr(editor, "removeHighlight")
    assert hasattr(editor, "setTheme")
    assert hasattr(editor, "supportedThemes")
    assert hasattr(editor, "enableTabCompletion")
    assert hasattr(editor, "setSettables")
    assert hasattr(editor, "insertText")
    assert hasattr(editor, "returnIssues")


@pytest.mark.timeout(timeout=30, method="thread")
def test_CodeEditor(qtbot, qapp):
    """
    Test to visually inspect the matrix GUI window.

    Asserts
    -------
    visible main window
    code can be set and read back
    can uncomment comment
    can zoom in
    can zoom back
    can zoom out
    can undo
    can redo
    can format code
    can read modified state
    can set modified state to False
    receives a theme list
    returns no linter error for correct code
    can insert text
    returns error for incorrect code
    """
    main_window = matrix_script.MainWindow()
    main_window.show()
    qtbot.addWidget(main_window)
    qtbot.waitExposed(main_window)
    qapp.processEvents()

    assert main_window.isVisible()
    code = "#print(  1 )"
    no_comment = code[1:]
    editor = main_window.script_edit
    qtbot.wait(GUI_WAIT)
    editor.setPlainText(code)
    qtbot.wait(5 * GUI_WAIT)
    return_code = editor.toPlainText()
    assert return_code == code
    editor.toggleLineComment()
    return_code = editor.toPlainText()
    assert return_code == no_comment
    # need to find out how to do raw interactions, e.g. keyboard
    # to check find panel
    start_zoom = editor.zoomFactor()
    editor.zoomIn()
    assert editor.zoomFactor() > start_zoom
    editor.zoomOut()
    assert editor.zoomFactor() == start_zoom
    editor.zoomOut()
    assert editor.zoomFactor() < start_zoom
    editor.undo()
    return_code = editor.toPlainText()
    assert return_code == code
    editor.redo()
    return_code = editor.toPlainText()
    assert return_code == no_comment
    # need to find out how to do raw interactions, e.g. keyboard
    # to test cut, copy, paste
    editor.formatCode()
    return_code = editor.toPlainText()
    formatted_no_comment = no_comment.replace(" ", "") + "\n"
    assert return_code == formatted_no_comment
    assert editor.isModified() is True
    editor.setModified(False)
    assert editor.isModified() is False
    # need to find out how to do raw interactions, i.e. keyboard
    # to test read-only
    # highlight, removeHighlight and setTheme are untestable?!
    themes = editor.supportedThemes()
    assert isinstance(themes, list)
    # enableTabCompletion is untestable?!
    # test linting later -> in the (future) linter pytest
    issues = editor.returnIssues()
    assert issues == 0
    error_code = "unknown(1)\n"
    editor.insertText(error_code)
    return_code = editor.toPlainText()
    assert return_code == error_code + formatted_no_comment
    qtbot.wait(1500)  # linter runs asynchronously at least every second
    issues = editor.returnIssues()
    assert issues == 1

    editor.setModified(False)
    qtbot.wait(GUI_WAIT)
