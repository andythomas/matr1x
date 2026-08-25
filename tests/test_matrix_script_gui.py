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
"""Test basic GUI functions in matrix script."""

from collections.abc import Generator
from pathlib import Path

import pytest
from PySide6.QtCore import Qt

import matr1x.eval
from matr1x.models import Envelope, Message, Modifier
from matr1x.scripts import matrix_script

_MATRIX_SCRIPT_WINDOW: matrix_script.MainWindow | None = None


@pytest.fixture(scope="module")
def matrix_script_window(qapp) -> Generator[matrix_script.MainWindow, None, None]:
    """Create a shared matrix-script window for this module."""
    global _MATRIX_SCRIPT_WINDOW
    if _MATRIX_SCRIPT_WINDOW is None:
        _MATRIX_SCRIPT_WINDOW = matrix_script.MainWindow()
        _MATRIX_SCRIPT_WINDOW.show()
        _MATRIX_SCRIPT_WINDOW.in_pytest = True
        qapp.processEvents()
    yield _MATRIX_SCRIPT_WINDOW
    _MATRIX_SCRIPT_WINDOW.close()
    _MATRIX_SCRIPT_WINDOW = None


@pytest.fixture(autouse=True)
def reset_matrix_script_window(matrix_script_window: matrix_script.MainWindow, qapp) -> None:
    """Reset state to avoid cross-test interference."""
    window = matrix_script_window
    if window.is_running:
        window.ui.widgets.measurement_thread.abort("a")
        qapp.processEvents()
    window.new_file()
    window.ui.widgets.status_preview.setPlainText("")
    window.ui.widgets.meta_view.clear()
    if window.ui.widgets.config_editor.isVisible():
        window.ui.actions.config.setChecked(False)
    qapp.processEvents()


@pytest.mark.timeout(timeout=60)
def test_basic_script_run(qtbot, qapp, matrix_script_window: matrix_script.MainWindow):
    """
    Start a basic matrix script measurement.

    Load a script, set the metadata info, look at the config, reload it
    once, start the measurement and look at it.

    Asserts
    -------
    main window is visible
    no error occured during the run
    preview action is enabled
    name fits the init_datafile
    a file was created
    all dcterms are in the file
    the status is 'finished'
    10 rows of data were saved
    """
    main_window = matrix_script_window
    qtbot.waitExposed(main_window)
    qapp.processEvents()

    assert main_window.isVisible()
    base = Path(__file__).parent
    script_filename = "matrix_script_gui.matrix"
    inputfile = base / Path(script_filename)
    main_window.load_from_filename(inputfile)
    assert main_window.windowTitle() == "Matrix Script: " + script_filename

    metadata = main_window.ui.widgets.meta_view
    creator = "Power User"
    metadata.creator.setText(creator)
    identifier = "np20250929b"
    metadata.identifier.setText(identifier)
    relation = "Adamantium93"
    metadata.relation.setText(relation)
    description = "I: 9,3\nV: 12,2"
    metadata.description.setText(description)

    main_window.ui.actions.config.setChecked(True)
    qtbot.waitUntil(lambda: main_window.ui.widgets.config_editor.isVisible(), timeout=2000)
    assert main_window.ui.widgets.config_editor.isVisible()
    main_window.ui.widgets.config_editor.w_update_config.click()

    main_window.ui.actions.start.trigger()
    qtbot.waitUntil(lambda: main_window.ui.widgets.measurement_thread is not None, timeout=2000)
    thread = main_window.ui.widgets.measurement_thread
    qtbot.waitSignal(thread.finished, timeout=2000)
    # Next line: Increased timeout needed for Windows
    qtbot.waitUntil(lambda: not main_window.is_running, timeout=5000)
    qapp.processEvents()
    assert not main_window.log_window.isVisible()
    assert main_window.ui.actions.preview.isEnabled()

    assert main_window.measurement_file.name[:14] == "boring_testrun"
    assert main_window.measurement_file.exists()
    header, data = matr1x.eval.loadmatrix(main_window.measurement_file)
    assert header["dcterms:creator"] == creator
    assert header["dcterms:identifier"] == identifier
    assert header["dcterms:relation"] == relation
    assert description in header["dcterms:description"]
    assert "This is a testrun!" in header["dcterms:description"]
    assert header["status"] == "finished"
    assert len(data) == 10
    main_window.measurement_file.unlink()

    main_window.new_file()
    qtbot.waitUntil(lambda: main_window.windowTitle() == "Matrix Script", timeout=2000)
    assert main_window.windowTitle() == "Matrix Script"


def test_start_action_disabled_for_invalid_config(
    matrix_script_window: matrix_script.MainWindow, monkeypatch
):
    """Invalid device config disables Start and exposes the reason in the tooltip."""
    main_window = matrix_script_window
    monkeypatch.setattr(
        main_window.ui.widgets.config_editor,
        "get_validation_errors",
        lambda: ["matr1x.systems.demo.devices.dev.address: invalid address"],
    )

    main_window.update_start_action_state()

    assert not main_window.ui.actions.start.isEnabled()
    assert "invalid address" in main_window.ui.actions.start.toolTip()
    assert main_window.ui.widgets.config_editor.isVisible()


def test_adding_system_preserves_unsaved_config(
    qapp, matrix_script_window: matrix_script.MainWindow
):
    """Rebuilding for another static system retains compatible editor values."""
    main_window = matrix_script_window
    system_list = main_window.ui.widgets.system_list
    system_list.clear()
    system_list.add_systems(["matr1x.systems.system_dummy_feature"])
    entered_index = main_window.ui.widgets.config_editor._index_for_config_path(
        "matr1x.systems.system_dummy_feature.reference_value"
    )
    assert entered_index.isValid()
    main_window.ui.widgets.config_editor.model.setData(
        entered_index,
        42.5,
        Qt.ItemDataRole.EditRole,
    )

    system_list.add_systems(["matr1x.systems.system_dummy_meas"])
    qapp.processEvents()

    retained_index = main_window.ui.widgets.config_editor._index_for_config_path(
        "matr1x.systems.system_dummy_feature.reference_value"
    )
    assert retained_index.data(Qt.ItemDataRole.EditRole) == "42.5"


def test_CodeEditor_API(qtbot, qapp, matrix_script_window: matrix_script.MainWindow):
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
    main_window = matrix_script_window
    qtbot.waitExposed(main_window)
    qapp.processEvents()
    assert main_window.isVisible()
    editor = main_window.ui.widgets.script_edit

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
    assert hasattr(editor, "setSystemInfo")
    assert hasattr(editor, "insertText")
    assert hasattr(editor, "returnIssues")


def test_CodeEditor(qtbot, qapp, matrix_script_window: matrix_script.MainWindow):
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
    main_window = matrix_script_window
    qtbot.waitExposed(main_window)
    qapp.processEvents()

    assert main_window.isVisible()
    code = "#print(  1 )"
    no_comment = code[1:]
    editor = main_window.ui.widgets.script_edit
    editor.setPlainText(code)
    qtbot.waitUntil(lambda: editor.toPlainText() == code, timeout=5000)
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
    qtbot.waitUntil(
        lambda: editor.toPlainText() == error_code + formatted_no_comment,
        timeout=2000,
    )
    return_code = editor.toPlainText()
    assert return_code == error_code + formatted_no_comment
    qtbot.waitUntil(lambda: editor.returnIssues() == 1, timeout=5000)
    issues = editor.returnIssues()
    assert issues == 1

    editor.setModified(False)


def test_status_preview_handles_carriage_return(
    qtbot, qapp, tmp_path, capsys, matrix_script_window: matrix_script.MainWindow
):
    """
    Ensure carriage returns from a running script overwrite the current line.

    Run a temporary script that prints a string containing a carriage
    return and verify the rendered output in the status preview.
    """
    main_window = matrix_script_window
    qtbot.waitExposed(main_window)
    qapp.processEvents()

    header_lines = (
        (Path(__file__).resolve().parent / "matrix_script_gui.matrix").read_text().splitlines()[:4]
    )
    carriage_script = "\n".join(
        header_lines + ['print("test\\nnot sure what to say\\ragain")', ""]
    )
    temp_script = tmp_path / "carriage_test.matrix"
    temp_script.write_text(carriage_script)
    main_window.load_from_filename(temp_script)
    qtbot.waitUntil(lambda: main_window.windowTitle().endswith(temp_script.name), timeout=2000)
    qapp.processEvents()

    main_window.ui.actions.start.trigger()
    qtbot.waitUntil(lambda: main_window.ui.widgets.measurement_thread is not None, timeout=2000)
    thread = main_window.ui.widgets.measurement_thread
    qtbot.waitSignal(thread.finished, timeout=2000)
    # Next line: Increased timeout needed for Windows
    qtbot.waitUntil(lambda: not main_window.is_running, timeout=5000)
    qtbot.waitUntil(
        lambda: "again" in main_window.ui.widgets.status_preview.toPlainText(),
        timeout=100,
    )
    qapp.processEvents()

    output_text = main_window.ui.widgets.status_preview.toPlainText()
    assert "test" in output_text
    assert "again" in output_text
    assert "what to say" not in output_text


@pytest.mark.timeout(timeout=30, method="thread")
def test_message_to_progress_label(
    qtbot, qapp, tmp_path, capsys, matrix_script_window: matrix_script.MainWindow
):
    """
    Test the to_progress_label modifier of message.

    Asserts
    -------
    The messages validate via the pydantic model.
    The flagged message is only shown in the progress label.
    """
    main_window = matrix_script_window
    qtbot.waitExposed(main_window)
    qapp.processEvents()
    messages = []
    messages.append(Message("To print", end=""))
    messages.append(Message("only in the label", modifier=Modifier.TO_PROGRESS_LABEL))
    messages.append(Message("that is the question"))
    for message in messages:
        env = Envelope.model_validate_json(message.model_dump_json())
        main_window.process_data(env)
    qtbot.wait(200)
    output_text = main_window.ui.widgets.status_preview.toPlainText()
    assert output_text == "To printthat is the question\n"
    assert main_window.ui.widgets.progress.text() == "only in the label"
