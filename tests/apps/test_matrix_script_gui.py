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

from pathlib import Path

import pytest
from PySide6.QtCore import Qt

import matr1x.core.eval
from matr1x.apps import script as matrix_script
from matr1x.core.models import Envelope, Message, Modifier


def reset_matrix_script_window(window: matrix_script.MainWindow, qapp) -> None:
    """Reset state to avoid cross-test interference."""
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
def test_basic_script_run(qtbot, qapp, monkeypatch, input_dir: Path, tmp_path: Path):
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
    invalid device config disables start and exposes the reason
    adding a system retains compatible editor values
    code can be set, edited, formatted and linted
    carriage returns overwrite the current status preview line
    flagged messages are only shown in the progress label
    """
    main_window = matrix_script.MainWindow()
    main_window.show()
    main_window.in_pytest = True
    qtbot.waitExposed(main_window)
    qapp.processEvents()

    assert main_window.isVisible()
    script_filename = "matrix_script_gui.matrix"
    # Load a copy of the script whose init_datafile call writes the data file
    # into the temporary test directory instead of the current working dir.
    script_file = tmp_path / script_filename
    script_file.write_text(
        (input_dir / script_filename)
        .read_text()
        .replace(
            'init_datafile("boring_testrun"',
            f'init_datafile("{(tmp_path / "boring_testrun").as_posix()}"',
        )
    )
    main_window.load_from_filename(script_file)
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
    # Increased timeout needed for Windows
    qtbot.waitUntil(lambda: not main_window.is_running, timeout=5000)
    qapp.processEvents()
    assert not main_window.log_window.isVisible()
    assert main_window.ui.actions.preview.isEnabled()

    assert main_window.measurement_file.name[:14] == "boring_testrun"
    assert main_window.measurement_file.exists()
    header, data = matr1x.core.eval.loadmatrix(main_window.measurement_file, to_polars=True)
    assert header["dcterms:creator"] == creator
    assert header["dcterms:identifier"] == identifier
    assert header["dcterms:relation"] == relation
    assert description in header["dcterms:description"]
    assert "This is a testrun!" in header["dcterms:description"]
    assert header["status"] == "finished"
    assert len(data) == 10

    main_window.new_file()
    qtbot.waitUntil(lambda: main_window.windowTitle() == "Matrix Script", timeout=2000)
    assert main_window.windowTitle() == "Matrix Script"

    monkeypatch.setattr(
        main_window.ui.widgets.config_editor,
        "get_validation_errors",
        lambda: ["matr1x.systems.demo.devices.dev.address: invalid address"],
    )

    main_window.update_start_action_state()

    assert not main_window.ui.actions.start.isEnabled()
    assert "invalid address" in main_window.ui.actions.start.toolTip()
    assert main_window.ui.widgets.config_editor.isVisible()
    monkeypatch.undo()
    reset_matrix_script_window(main_window, qapp)

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

    header_lines = (input_dir / "matrix_script_gui.matrix").read_text().splitlines()[:4]
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
    # Increased timeout needed for Windows
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

    reset_matrix_script_window(main_window, qapp)

    messages = []
    messages.append(Message("To print", end=""))
    messages.append(Message("only in the label", modifier=Modifier.TO_PROGRESS_LABEL))
    messages.append(Message("that is the question"))
    for message in messages:
        env = Envelope.model_validate_json(message.model_dump_json())
        main_window.process_data(env)
    # write_output buffers the text and a 50 ms timer flushes it to the GUI
    qtbot.waitUntil(
        lambda: (
            main_window.ui.widgets.status_preview.toPlainText() == "To printthat is the question\n"
        ),
        timeout=1000,
    )
    output_text = main_window.ui.widgets.status_preview.toPlainText()
    assert output_text == "To printthat is the question\n"
    assert main_window.ui.widgets.progress.text() == "only in the label"
