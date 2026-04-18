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

import logging
import sys
from collections.abc import Callable, Generator, Iterable
from dataclasses import dataclass
from pathlib import Path

import matr1x.eval
import pytest
from matr1x.scripts import matrix_script
from matr1x.util import StreamToLogger

_MATRIX_SCRIPT_WINDOW: matrix_script.MainWindow | None = None


@dataclass(frozen=True)
class _OutputScenario:
    """Define shared fragment scenarios for GUI and logfile tests."""

    id: str
    stream_mode: str
    fragments: tuple[str, ...]
    expected_gui_present: tuple[str, ...]
    expected_gui_absent: tuple[str, ...]
    expected_log_lines: tuple[str, ...]


_OUTPUT_SCENARIOS = (
    _OutputScenario(
        id="direct-gui-stream",
        stream_mode="direct",
        fragments=(
            "test\n",
            "not sure what to say",
            "\r",
            "again",
            "\r3 seconds remaining",
            "\r2 seconds remaining",
            "\rWaiting done",
            "\n",
        ),
        expected_gui_present=("test", "Waiting done"),
        expected_gui_absent=(
            "again",
            "not sure what to say",
            "3 seconds remaining",
            "2 seconds remaining",
        ),
        expected_log_lines=(),
    ),
    _OutputScenario(
        id="duplicated-wait-output",
        stream_mode="duplicated",
        fragments=(
            "Waiting 11 seconds until 16:57:24\n",
            "\r11 seconds remaining",
            "\r10 seconds remaining",
            "\r9 seconds remaining",
            "\rWaiting done",
            "\n",
        ),
        expected_gui_present=("Waiting 11 seconds until 16:57:24", "Waiting done"),
        expected_gui_absent=(
            "11 seconds remaining",
            "10 seconds remaining",
            "9 seconds remaining",
        ),
        expected_log_lines=(
            "INFO:Waiting 11 seconds until 16:57:24",
            "INFO:Waiting done",
        ),
    ),
    _OutputScenario(
        id="duplicated-split-print",
        stream_mode="duplicated",
        fragments=(
            "test",
            "final line\n",
        ),
        expected_gui_present=("testfinal line",),
        expected_gui_absent=(),
        expected_log_lines=("INFO:testfinal line",),
    ),
)

_DUPLICATED_OUTPUT_SCENARIOS = tuple(
    scenario for scenario in _OUTPUT_SCENARIOS if scenario.stream_mode == "duplicated"
)


def _prepare_status_preview(qtbot, qapp, main_window: matrix_script.MainWindow):
    """Reset the status preview and output buffer for output tests."""
    qtbot.waitExposed(main_window)
    qapp.processEvents()

    status_preview = main_window.ui.widgets.status_preview
    status_preview.setPlainText("")
    main_window._output_buffer.clear()
    main_window._output_timer.stop()
    return status_preview


def _flush_status_preview(main_window: matrix_script.MainWindow, qapp) -> None:
    """Flush buffered GUI output and process queued Qt events."""
    main_window._flush_output_buffer()
    qapp.processEvents()


def _write_fragments_to_status_preview(
    main_window: matrix_script.MainWindow,
    qapp,
    write_fragment: Callable[[str], None],
    fragments: Iterable[str],
    *,
    finish: Callable[[], None] | None = None,
) -> str:
    """Write a sequence of output fragments and return the final text."""
    for fragment in fragments:
        write_fragment(fragment)
        _flush_status_preview(main_window, qapp)

    if finish is not None:
        finish()
        _flush_status_preview(main_window, qapp)

    return main_window.ui.widgets.status_preview.toPlainText()


def _create_duplicate_output_stream(
    logger_name: str,
    handler: logging.Handler,
    main_window: matrix_script.MainWindow,
) -> StreamToLogger:
    """Create a StreamToLogger that mirrors output to the GUI stream."""
    logger = logging.getLogger(logger_name)
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.INFO)
    return StreamToLogger(
        logger,
        logging.INFO,
        duplicate_stream=main_window.output_stream,
    )


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
def reset_matrix_script_window(matrix_script_window, qapp) -> None:
    """Reset state to avoid cross-test interference."""
    window = matrix_script_window
    if window.is_running:
        window.abort_thread("a")
        qapp.processEvents()
    window.ui.widgets.script_edit.setModified(False)
    window._reset_state(reset_metadata=True)
    if window.ui.widgets.config_editor.isVisible():
        window.ui.actions.config.setChecked(False)
    qapp.processEvents()


@pytest.mark.timeout(timeout=60)
def test_basic_script_run(qtbot, qapp, matrix_script_window):
    """
    Start a basic matrix script measurement.

    Load a script, set the metadata info, look at the config, reload it
    once, start the measurement and look at it.

    Asserts
    -------
    main window is visible
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

    metadata = main_window.ui.widgets.metadata
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

    main_window.ui.actions.start_pause.trigger()
    qtbot.waitUntil(lambda: main_window.measurement_thread is not None, timeout=2000)
    thread = main_window.measurement_thread
    qtbot.waitSignal(thread.finished, timeout=2000)
    # Next line: Increased timeout needed for Windows
    qtbot.waitUntil(lambda: not main_window.is_running, timeout=5000)
    qapp.processEvents()
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


def test_CodeEditor_API(qtbot, qapp, matrix_script_window):
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
    assert hasattr(editor, "setSettables")
    assert hasattr(editor, "insertText")
    assert hasattr(editor, "returnIssues")


def test_CodeEditor(qtbot, qapp, matrix_script_window):
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
    qtbot, qapp, tmp_path, capsys, matrix_script_window
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

    with capsys.disabled():
        original_stdout = sys.stdout
        sys.stdout = main_window.output_stream
        try:
            main_window.ui.actions.start_pause.trigger()
            qtbot.waitUntil(lambda: main_window.measurement_thread is not None, timeout=2000)
            thread = main_window.measurement_thread
            qtbot.waitSignal(thread.finished, timeout=2000)
            # Next line: Increased timeout needed for Windows
            qtbot.waitUntil(lambda: not main_window.is_running, timeout=5000)
            qtbot.waitUntil(
                lambda: "again" in main_window.ui.widgets.status_preview.toPlainText(),
                timeout=100,
            )
            qapp.processEvents()
        finally:
            sys.stdout = original_stdout

    output_text = main_window.ui.widgets.status_preview.toPlainText()
    assert "test" in output_text
    assert "again" in output_text
    assert "what to say" not in output_text


@pytest.mark.parametrize("scenario", _OUTPUT_SCENARIOS, ids=lambda scenario: scenario.id)
def test_status_preview_handles_fragmented_output(qtbot, qapp, matrix_script_window, scenario):
    r"""
    Ensure fragmented carriage return output overwrites the active line.

    This covers both the direct GUI stream path and the duplicated
    output-to-logfile path used via StreamToLogger.
    """
    main_window = matrix_script_window
    status_preview = _prepare_status_preview(qtbot, qapp, main_window)

    if scenario.stream_mode == "direct":
        write_fragment = main_window.output_written
        finish = None
    else:
        output_stream = _create_duplicate_output_stream(
            "test_matrix_script_gui.duplicate_output",
            logging.NullHandler(),
            main_window,
        )
        write_fragment = output_stream.write
        finish = output_stream.flush

    output_text = _write_fragments_to_status_preview(
        main_window,
        qapp,
        write_fragment,
        scenario.fragments,
        finish=finish,
    )

    assert status_preview.toPlainText() == output_text
    for text in scenario.expected_gui_present:
        assert text in output_text
    for text in scenario.expected_gui_absent:
        assert text not in output_text


@pytest.mark.parametrize(
    "scenario",
    _DUPLICATED_OUTPUT_SCENARIOS,
    ids=lambda scenario: scenario.id,
)
def test_stream_to_logger_file_output_matches_shared_scenarios(
    qtbot, qapp, matrix_script_window, tmp_path: Path, scenario
):
    """
    Ensure the real logfile path keeps only the stable output lines.

    This exercises a FileHandler instead of an in-memory collector so
    the regression matches the serialized logfile behavior.
    """
    main_window = matrix_script_window
    _prepare_status_preview(qtbot, qapp, main_window)
    log_path = tmp_path / "wait.log"
    file_handler = logging.FileHandler(log_path, mode="w")
    file_handler.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))
    output_stream = _create_duplicate_output_stream(
        "test_matrix_script_gui.wait_file_output",
        file_handler,
        main_window,
    )

    try:
        _write_fragments_to_status_preview(
            main_window,
            qapp,
            output_stream.write,
            scenario.fragments,
            finish=output_stream.flush,
        )
    finally:
        file_handler.close()

    log_lines = log_path.read_text().splitlines()
    assert log_lines == list(scenario.expected_log_lines)
