# This file is part of a software collection for data acquisition (matr1x).
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
"""Allow to write measurement scripts in Python."""

import logging
import os
import platform
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import shiboken6
from pydantic import ValidationError
from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QPoint,
    QSize,
    Qt,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QFontDatabase,
    QKeyEvent,
    QKeySequence,
    QPalette,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import matr1x
from matr1x.editor import CodeEditor, LSPServer
from matr1x.error_handling import Error, InternalInvariantError, install_error_handler
from matr1x.gui_util import (
    AboutBox,
    AutoSlot,
    ConfigEditWidget,
    FileDropMixin,
    LoggerMixin,
    LoggingWindow,
    MApplication,
    blocked_signals,
    check_config,
    detect_shortcut,
    find_parent_of_type,
    get_matrix_icon,
    install_metadata_config_docks,
    open_matrix_toml,
    save_messagebox,
    sync_visibility_actions,
)
from matr1x.models import (
    Datafile,
    Envelope,
    Header,
    InputParameters,
    LineNumber,
    MeasuredValues,
    Message,
    Modifier,
    SetValues,
    Telemetry,
)
from matr1x.post_install import (
    check_desktop_integration,
    post_installation,
    remove_desktop_integration,
)
from matr1x.scripts.shared_classes import (
    MetaData,
    MetaDataDialog,
    MetadataDockWidget,
    NotifierMessage,
    SaferQSettings,
    SystemListWidget,
)
from matr1x.util import (
    StreamToLogger,
    find_binary,
    generate_script,
    get_script_prefix_offset,
)

logger = logging.getLogger(__name__)
scriptlogger = logging.getLogger(__name__ + "_subprocess")
script_config = matr1x.config.matr1x.scripts.matrix_script


MAX_LINES_STATUS = 10000
LAYOUT_SETTINGS_GROUP = "MainWindowLayoutV2"
# to test what a good limiting value is, use the following:
# ```
# for i in range(1000):
#   print(f"{i}" + 10*"snsnsnsnsn\n" + f"{i}")
#   wait(0.1)
# ```
# By setting the appropriate wait and multiplier, the highest expected
# number of lines/s can be set (here 110 lines/s). With this in place
# run matrix-script until it reaches the limit and see whether the
# display perforamnce of the GUI drops.


help_text = (
    """
MATRIX SCRIPT HELP

The available functions are listed in the following lines. Please use hover (mouseover) """
    """in the left editor window to get more specific information about a particular function. """
    """Furthermore, auto-completion will try to suggest possible parameters.

set_value(value_index/name, value)
trigger_value(value_index/name)
read_value(value_index/name)
wait(seconds, until, message, silent)
input(query, timeout, default_value)
input_bool(query, timeout, default_value)
input_numerical(query, timeout, default_value, min_value, max_value, step, decimals)
end_script(finished)
print(*args, sep, end, file, flush)
init_datafile(filename, comment, append, print_header, ntot,
              reset_meta_data, reset_date)
measure_system(print_setpoint, print_data, print_telemetry)

In addition, the following variables are available. Please use help to get a list of """
    """available parameters and devices. Note that user variable names must not start with """
    """an underscore!

devs  # dictionary that contains all devices
sys  # merged system object from the selected systems
meta_data  # dictionary that contains all meta information

---

"""
)

T = TypeVar("T")
R = TypeVar("R")


class CentralWidget(FileDropMixin, QWidget):
    """Enable drag and drop of matrix files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setValidExtensions([MainWindow.extension])


class TimeoutDialogBase(QDialog):
    """Base class for dialogs with timeout functionality."""

    def __init__(
        self,
        query: str,
        parent: QWidget | None = None,
        timeout: float = float("inf"),
        default_value: Any = "",
    ):
        """
        Initialize the base dialog with timeout functionality.

        Parameters
        ----------
        query : str
            The text to display on the label above the input field.
        parent : QWidget, optional
            The parent widget of the dialog.
        timeout : float, optional
            Timeout in seconds before dialog automatically closes. Default is infinity (no timeout).
            0 is interpreted as infinity.
        default_value : Any, optional
            Default value to show in input field.
        """
        super().__init__(parent)
        self.setWindowTitle("Matrix-script input")

        self.default_value = default_value
        self.user_responded = False  # Track if user clicked a button
        self.timeout = timeout if timeout else float("inf")

        self.label = QLabel(query, self)

        # This will be created by subclasses
        self.input_widget = None

        self.timer_label = QLabel("", self)
        self.timer_label.setVisible(self.timeout != float("inf"))

        self.ok_button = QPushButton("Send input", self)
        self.abort_button = QPushButton("Abort script", self)

        self.ok_button.clicked.connect(self._button_clicked)
        self.ok_button.clicked.connect(self.accept)
        self.abort_button.clicked.connect(self._button_clicked)
        self.abort_button.clicked.connect(self.reject)

        # Ensure the dialog stays on top of the main window
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        # Set up timer if timeout is finite
        if self.timeout != float("inf"):
            self.remaining_time = self.timeout * 1000  # Convert to milliseconds
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_timer)
            self.timer.start(100)  # Update every 100ms for better precision

    def _button_clicked(self):
        """Mark that user has responded to prevent timeout override."""
        self.user_responded = True

    def update_timer(self):
        """Update the timer display and handle timeout."""
        if self.user_responded:
            return

        self.remaining_time -= 100  # Decrement by 100ms

        if self.remaining_time <= 0:
            if not self.user_responded:
                self.timer.stop()
                self.accept()
            return

        # Convert milliseconds back to seconds for display
        remaining_seconds = self.remaining_time / 1000

        # Format the time display
        if remaining_seconds < 100:
            # Show seconds for short timeouts
            self.timer_label.setText(f"Time remaining: {int(remaining_seconds)} seconds")
        else:
            # Show hours:minutes format for longer timeouts
            hours = int(remaining_seconds / 3600)
            minutes = int((remaining_seconds % 3600) / 60)
            seconds = int(remaining_seconds % 60)
            if hours > 0:
                self.timer_label.setText(f"Time remaining: {hours}h {minutes}m {seconds}s")
            else:
                self.timer_label.setText(f"Time remaining: {minutes}m {seconds}s")

    def setup_layout(self):
        """Set up the dialog layout."""
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.abort_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.label)
        if self.input_widget:
            main_layout.addWidget(self.input_widget)
        main_layout.addWidget(self.timer_label)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    def accept(self):
        """Handle dialog acceptance."""
        if hasattr(self, "timer") and self.timer.isActive():
            self.timer.stop()
        super().accept()

    def reject(self):
        """Handle dialog rejection."""
        if hasattr(self, "timer") and self.timer.isActive():
            self.timer.stop()
        super().reject()


class TextInputDialog(TimeoutDialogBase):
    """Modal dialog for text input for matrix-script."""

    def __init__(
        self,
        query: str,
        parent: QWidget | None = None,
        timeout: float = float("inf"),
        default_value: str = "",
    ):
        """
        Initialize the text input dialog with a its GUI elements.

        Parameters
        ----------
        query : str
            The text to display on the label above the input field.
        parent : QWidget, optional
            The parent widget of the dialog.
        timeout : float, optional
            Timeout in seconds before dialog automatically closes. Default is infinity (no timeout).
            0 is interpreted as infinity.
        default_value : str, optional
            Default value to show in input field.
        """
        super().__init__(query, parent, timeout, default_value)

        # Create the input widget
        self.input = QLineEdit(self)
        self.input.setPlaceholderText("input to send to script")
        self.input.setText(default_value)
        self.input_widget = self.input

        # Set up the layout
        self.setup_layout()

    def get_input_text(self):
        """
        Get the text entered by the user.

        Returns
        -------
        str
            The user input.
        """
        return self.input.text()


class NumericalInputDialog(TimeoutDialogBase):
    """Modal dialog for numerical input for matrix-script."""

    def __init__(
        self,
        query: str,
        parent: QWidget | None = None,
        timeout: float = float("inf"),
        default_value: float = 0.0,
        min_value: float | None = -100e9,
        max_value: float | None = 100e9,
        step: float | None = 1.0,
        decimals: int | None = 2,
    ):
        """
        Initialize the numerical input dialog with its GUI elements.

        Parameters
        ----------
        query : str
            The text to display on the label above the input field.
        parent : QWidget, optional
            The parent widget of the dialog.
        timeout : float, optional
            Timeout in seconds before dialog automatically closes. Default is infinity (no timeout).
            0 is interpreted as infinity.
        default_value : float, optional
            Default value to show in input field.
        min_value : float, optional
            Minimum value for the QDoubleSpinbox. Default is -100e9.
        max_value : float, optional
            Maximum value for the QDoubleSpinbox. Default is 100e9.
        step : float, optional
            Step size for the QDoubleSpinbox. Default is 1.0.
        decimals : int, optional
            Number of decimal places. Default is 2.
        """
        super().__init__(query, parent, timeout, default_value)

        # Create the spinbox
        self.input_spinbox = QDoubleSpinBox(self)
        if min_value is not None:
            self.input_spinbox.setMinimum(min_value)
        if max_value is not None:
            self.input_spinbox.setMaximum(max_value)
        if step is not None:
            self.input_spinbox.setSingleStep(step)
        if decimals is not None:
            self.input_spinbox.setDecimals(decimals)
        if default_value is not None:
            self.input_spinbox.setValue(default_value)
        self.input_spinbox.setToolTip(
            f"Enter a numerical value (Range: {min_value} to {max_value})"
        )
        self.input_widget = self.input_spinbox

        # Set up the layout
        self.setup_layout()

    def get_input_value(self):
        """
        Get the value from the spinbox.

        Returns
        -------
        float
        The user input value.
        """
        return self.input_spinbox.value()


class YesNoAbortDialog(QMessageBox, LoggerMixin):
    """Modal dialog for boolean input for matrix-script."""

    def __init__(
        self,
        question: str,
        parent: QWidget | None = None,
        timeout: float = float("inf"),
        default_value: str = "yes",
    ):
        """
        Initialize the yes/no dialog with a question and buttons.

        Parameters
        ----------
        question : str
            The question to display on the label.
        parent : QWidget, optional
            The parent widget of the dialog.
        timeout : float, optional
            Timeout in seconds before dialog automatically returns default_value.
            Default is infinity (no timeout). 0 is interpreted as infinity.
        default_value : str, optional
            Default value to return if timeout occurs. Should be "Yes", "No", or empty.
            Default is True.
        """
        super().__init__(parent)
        self.setWindowTitle("Question")
        self.setText(question)
        self.setIcon(QMessageBox.Icon.Question)

        # Normalize default value and ensure it's either "yes" or "no"
        self.default_value = (
            default_value.lower() if default_value.lower() in ["yes", "no"] else "yes"
        )
        self.timeout_occurred = False  # Required for YesNoAbortDialog functionality
        self.user_responded = False  # Track if user clicked a button
        self.timeout = timeout if timeout else float("inf")

        # Add custom buttons with default button indication when timeout is set
        button_text_yes = "Yes"
        button_text_no = "No"

        # If timeout is set, add visual indications to the default button
        if self.timeout != float("inf"):
            if self.default_value == "yes":
                button_text_yes = "Yes (Default)"
            else:
                button_text_no = "No (Default)"

        # Create buttons
        self.yes_button = self.addButton(button_text_yes, QMessageBox.ButtonRole.AcceptRole)
        self.no_button = self.addButton(button_text_no, QMessageBox.ButtonRole.RejectRole)
        self.abort_button = self.addButton("Abort script", QMessageBox.ButtonRole.DestructiveRole)

        # Connect button signals to track user response
        self.yes_button.clicked.connect(self._button_clicked)
        self.no_button.clicked.connect(self._button_clicked)
        self.abort_button.clicked.connect(self._button_clicked)

        # Simple styling for default button if timeout is set
        if self.timeout != float("inf"):
            # Set bold font for the default button
            default_button = self.yes_button if self.default_value == "yes" else self.no_button
            font = default_button.font()
            font.setBold(True)
            default_button.setFont(font)

            # Make this the default button (responds to Enter key)
            self.setDefaultButton(default_button)

            # Set up timer and label - use milliseconds for better precision
            self.timer_label = QLabel(f"Time remaining: {int(self.timeout)} seconds", self)
            layout = self.layout()
            if isinstance(layout, QGridLayout):
                layout.addWidget(self.timer_label, 1, 1, 1, 3)
            else:
                raise InternalInvariantError("No grid-layout was returned!")
            self.remaining_time = self.timeout * 1000  # Convert to milliseconds
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_timer)
            self.timer.start(100)  # Update every 100ms for better precision

    def _button_clicked(self):
        """Mark that user has responded to prevent timeout override."""
        self.user_responded = True
        if hasattr(self, "timer"):
            self.timer.stop()

    def update_timer(self):
        """Update the timer display and handle timeout."""
        # Don't process timeout if user already responded
        if self.user_responded:
            return

        self.remaining_time -= 100  # Decrement by 100ms

        if self.remaining_time <= 0:
            # Give a small grace period for button clicks
            if not self.user_responded:
                self.timeout_occurred = True
                self.timer.stop()
                self.close()
                return

        # Convert milliseconds back to seconds for display
        remaining_seconds = self.remaining_time / 1000

        # Format the time display
        if remaining_seconds < 100:
            # Show seconds for short timeouts
            self.timer_label.setText(f"Time remaining: {int(remaining_seconds)} seconds")
        else:
            # Show hours:minutes format for longer timeouts
            hours = int(remaining_seconds / 3600)
            minutes = int((remaining_seconds % 3600) / 60)
            seconds = int(remaining_seconds % 60)
            if hours > 0:
                self.timer_label.setText(f"Time remaining: {hours}h {minutes}m {seconds}s")
            else:
                self.timer_label.setText(f"Time remaining: {minutes}m {seconds}s")

    def exec_and_get_response(self):
        """
        Show the dialog and return the button clicked by the user.

        Returns
        -------
        str
            The response based on the button clicked ("yes", "no", or "abort").
            If timeout occurred, returns the default_value.
        """
        self.exec()

        # Check timeout first, but only if user didn't respond
        if self.timeout_occurred and not self.user_responded:
            if self.default_value in ["yes", "no"]:
                self.logger.info(
                    "Dialog timeout occurred - automatically selected: %s", self.default_value
                )
                return self.default_value
            fallback_default = "yes"
            self.logger.info(
                "Dialog timeout occurred with invalid default value, automatically selected: %s",
                fallback_default,
            )
            return fallback_default

        # User responded - return their choice
        if self.clickedButton() == self.yes_button:
            return "yes"
        elif self.clickedButton() == self.no_button:
            return "no"
        elif self.clickedButton() == self.abort_button:
            return "abort"
        return "Unknown"


class TerminationDialog(QMessageBox):
    """Dialog to determine how a terminated datafile should be marked."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Termination Status")
        self.setText("How should the terminated datafile be marked?")
        self.setIcon(QMessageBox.Icon.Question)
        self.addButton("Aborted", QMessageBox.ButtonRole.RejectRole)
        self.finish_button = self.addButton("Finished", QMessageBox.ButtonRole.AcceptRole)

    def get_selection(self):
        """Display the dialog and return the user's selection."""
        self.exec()
        return "finished" if self.clickedButton() == self.finish_button else "aborted"


class TerminalOutput(QPlainTextEdit):
    """
    Custom class for terminal-like text output.

    Init the class with a mono-spaced font and respect theme.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)
        mono_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono_font.setPointSizeF(self.font().pointSize())
        self.setFont(mono_font)
        self.updateColors()
        MApplication.instance().isDarkSignal.connect(self.updateColors)

    def updateColors(self) -> None:
        """Update terminal colors based on system theme."""
        palette = self.palette()
        text_edit = QPlainTextEdit()
        text_edit.setEnabled(False)
        changed_palette = text_edit.palette()
        palette.setColor(
            QPalette.ColorRole.Base,
            QColor(changed_palette.color(QPalette.ColorRole.Base)),
        )
        self.setPalette(palette)

    def print_colored(self, line: str) -> None:
        """
        Print a colored text.

        Parameters
        ----------
        line : str
            The line to be printed.
        """
        scrollbar = self.verticalScrollBar()
        at_bottom = scrollbar.value() == scrollbar.maximum()
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        text_char_format = QTextCharFormat()
        text_char_format.setForeground(QColor("royalblue"))
        cursor.insertText(line, text_char_format)
        cursor.insertText("\n", QTextCharFormat())
        if at_bottom:
            self.moveCursor(QTextCursor.MoveOperation.End)


if sys.platform == "win32":
    try:
        from ctypes import windll

        myappid = "python.matr1x.matrix-script.version"
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass


class ScriptThread(QThread):
    """Control and the thread running the measurements."""

    data_received = Signal(Envelope)

    def __init__(
        self,
        metadata: MetaData,
        script: str,
        fallbackname: Path | None,
        temp_config: Path,
        systems: list[str],
    ) -> None:
        """
        Initialize thread that handles script execution.

        Parameters
        ----------
        meta_data : dict
            Dictionary containing meta data such as user and comment.
        script : str
            User script that is supposed to be run by the ScriptThread.
        fallbackname : Path | str
            Filename used to initialize the data file if not specified
            in the script. Its directory path will be used as execution
            directory.
        temp_config : Path
            Temporary configuration file path.
        systems : list
            List of system files to load.
        """
        super().__init__()
        self.proc: subprocess.Popen | None = None
        self.conn: socket.socket | None = None
        self.meta_data: MetaData = metadata
        self.script: str = script
        self.datafilefallback: str = str(fallbackname) if fallbackname else ""
        self.temp_config: Path = temp_config
        self.systems: list[str] = systems

    def pass_input(self, inp: str) -> None:
        """
        Communicate user input to the subprocess.

        Parameters
        ----------
        inp: str
            The input to be communicated.
        """
        if self.proc is None or self.conn is None:
            return
        if len(inp) < 1 or inp[-1] != "\n":
            inp += "\n"  # input needs to have terminating character
        self.conn.send(("i" + inp).encode("utf-8"))

    def pause(self) -> None:
        """Communicate pause to the subprocess."""
        if self.proc is None or self.conn is None:
            return
        self.conn.send(b"p")

    def abort(self, char: str = "q") -> None:
        """
        Communicate stop to the subprocess' stdin.

        Parameters
        ----------
        char : str
            Single length string that is passed to the process.
            - "q" stops and queries user for state
            - "a" stops and sets state to `aborted`
            - "f" stops and sets state to `finished`
        """
        if self.proc is None or self.conn is None:
            return
        self.conn.send(char.encode())

    def kill(self) -> None:
        """Kill the process and make sure it is indeed stopped."""
        if self.proc is None or self.conn is None:
            return
        pid = self.proc.pid
        self.proc.terminate()
        try:  # if thread is still alive, kill it
            os.kill(pid, 0)
            self.proc.kill()
            text = (
                "Force killed thread! Please verify all devices are\n"
                "operational before starting another script.\n"
            )
        except OSError:
            text = "Thread terminated gracefully."
        self.process_received_data(Message(text).model_dump_json())

    def process_received_data(self, inp: str) -> None:
        """Receive a line from the input and handle it accordingly."""
        lines = inp.split(os.linesep)
        for i, line in enumerate(lines[:-1]):
            lines[i] += "\n"
        for line in lines:
            try:
                env = Envelope.model_validate_json(line)
            except ValidationError:
                if line.strip():
                    logger.error("Unknown data received: %s", line)
                continue
            self.data_received.emit(env)

    def relay_subprocess_output(self, stream, is_error: bool):
        """Relay stdout and stderr of the subprocess to the logger."""
        for line in iter(stream.readline, b""):
            if is_error:
                scriptlogger.warning(line.decode().strip())
            else:
                scriptlogger.info(line.decode().strip())

    def run(self) -> None:
        """
        Run the subprocess.

        First writes the user script into a temporary file to make sure
        all formating is conserved, then passes that file to the
        interpreter to run the script. The purpose of using a subprocess
        is to keep the namespace clear of all system files. That allows
        changes to the system while matrix-script is running.
        """
        with tempfile.NamedTemporaryFile(mode="w+b") as tf:
            for line in self.script:
                tf.write(line.encode())
            # all information has been written to temporary file, make sure it
            # is updated
            tf.flush()
            # start socket that is used to communicate with the child process
            # that runs the script
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # only accept local connections and start listening
            s.bind(("127.0.0.1", 0))  # use dynamic port
            port = s.getsockname()[1]
            s.listen(1)
            # start subprocess, stderr is piped to stdout, and both of them are
            # piped so that we can read them
            # pass the script that we want to execute and generate correct
            # parameters to pass to matr1x/utils.py:matrix_script_process
            cmd = f"""import matr1x
import matr1x.util as mu
matr1x.reload_config({repr(str(self.temp_config))})
mu.matrix_script_process({repr(tf.name)}, {repr(self.meta_data)},
                         {repr(self.datafilefallback)}, {repr(port)}, {repr(self.systems)})"""

            self.proc = subprocess.Popen(
                [sys.executable, "-c", cmd],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
            self.conn, address = s.accept()
            threading.Thread(
                target=self.relay_subprocess_output, args=(self.proc.stdout, False), daemon=True
            ).start()
            threading.Thread(
                target=self.relay_subprocess_output, args=(self.proc.stderr, True), daemon=True
            ).start()
            buffer = ""
            while self.proc.poll() is None:
                try:
                    chunk = self.conn.recv(8192)
                    if not chunk:
                        break  # connection closed
                    buffer += chunk.decode()
                    while "\0" in buffer:
                        msg, buffer = buffer.split("\0", 1)
                        if msg:
                            self.process_received_data(msg)
                except OSError:
                    self.process_received_data("OS error in thread communication.\n")
                    break
            self.conn.close()
            self.temp_config.unlink()


@dataclass(frozen=True)
class ActionGroup:
    """Actions to be utilized in the GUI."""

    matrix_settings: QAction
    about: QAction
    config: QAction
    new_file: QAction
    load: QAction
    save: QAction
    save_as: QAction
    add_system: QAction
    remove_system: QAction
    quit_app: QAction
    undo: QAction
    redo: QAction
    cut: QAction
    copy: QAction
    paste: QAction
    line_comment: QAction
    zoom_in: QAction
    zoom_out: QAction
    print: QAction
    find: QAction
    start_pause: QAction
    stop: QAction
    abort: QAction
    finish: QAction
    kill: QAction
    preview: QAction
    pep8: QAction
    autocomplete: QAction
    show_log: QAction
    toggle_metadata: QAction
    toggle_toolbar: QAction
    system_help: QAction
    theme_actions: list[QAction]
    theme_group: QActionGroup
    post_install: QAction
    remove_desktop_integration: QAction


@dataclass(frozen=True)
class WidgetGroup:
    """Widgets to be used in the GUI."""

    dockable_metadata: MetadataDockWidget
    meta_view: MetaDataDialog
    system_list: SystemListWidget
    status_preview: TerminalOutput
    script_edit: CodeEditor
    system_command_help: QDialog
    system_command_text_edit: QTextEdit
    config_editor: ConfigEditWidget
    save_button: QToolButton
    stop_button: QToolButton
    splitter: QSplitter
    central_widget: CentralWidget
    python_info: QLabel
    lsp_info: QLabel
    save_pulldown: QMenu
    stop_pulldown: QMenu


class UIBuilder:
    """Create the GUI elements."""

    def __init__(self):
        self.widgets: WidgetGroup = self._create_widgets()
        self.actions: ActionGroup = self._create_actions()
        self.toolbar: QToolBar = self._create_toolbar()
        self.menubar: QMenuBar = self._create_menu()
        self._create_gui()

    def _standard_action(self, name: str, display_name: str | None = None) -> QAction:
        """
        Create and return a standard action such as 'Undo'.

        Also connects the action with a system agnostic shortcut and
        with the corresponding method.

        Parameters
        ----------
        name : str
            The name of the method as in QKeySequence.StandardKey.
        display_name : str, optional
            The name to be displayed in menu and toolbar.

        Returns
        -------
        QAction
            The action.
        """
        if not display_name:
            display_name = name
        action = QAction(display_name)
        action.setShortcut(getattr(QKeySequence.StandardKey, name))
        method_name = name[:1].lower() + name[1:]
        action.triggered.connect(lambda checked, method=method_name: self._standard_method(method))
        return action

    def _standard_method(self, method_name: str) -> None:
        """
        Perform a standard method such as 'undo' on the focussed widget.

        Parameters
        ----------
        method_name : str
            The name of the method.
        """
        focus_widget = MApplication.focusWidget()
        webview = None

        if focus_widget is not None:
            webview = find_parent_of_type(focus_widget, QWebEngineView)
        if isinstance(webview, QWebEngineView):
            focus_widget = webview

        try:
            method = getattr(focus_widget, method_name)
            if callable(method):
                method()
        except AttributeError:
            pass

    def _create_widgets(self) -> WidgetGroup:
        """
        Create all widgets for the GUI.

        Returns
        -------
        WidgetGroup
            The dataclass with all the widgets.
        """
        dockable_metadata = MetadataDockWidget()
        config_editor = ConfigEditWidget()
        system_list = SystemListWidget()
        system_list.setMinimumHeight(50)
        system_list.setMaximumHeight(50)
        status_preview = TerminalOutput()
        status_preview.document().setMaximumBlockCount(MAX_LINES_STATUS)
        lsp_name = "ty"
        lsp_binary = find_binary(lsp_name)
        if isinstance(lsp_binary, Error):
            raise lsp_binary.error
        lsp_parameters = ["server"]
        lsp_server = LSPServer(binary=str(lsp_binary.value), parameters=lsp_parameters)
        script_edit = CodeEditor(lsp_server)
        system_command_help = QDialog()
        box_layout = QVBoxLayout()
        system_command_text_edit = QTextEdit()
        system_command_text_edit.setReadOnly(True)
        box_layout.addWidget(system_command_text_edit)
        system_command_help.setLayout(box_layout)
        title = "Selected systems information"
        system_command_help.setWindowTitle(title)
        system_command_help.setWindowModality(Qt.WindowModality.NonModal)
        save_button = QToolButton()
        save_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        save_button.setIcon(get_matrix_icon("SP_DialogSaveButton"))
        save_button.setText("Save")
        stop_button = QToolButton()
        stop_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        stop_button.setIcon(get_matrix_icon("CUSTOM_Stop"))
        stop_button.setText("Abort")
        splitter = QSplitter()
        central_widget = CentralWidget()
        python_info = QLabel(f"Python {platform.python_version()}")
        python_info.setToolTip(f"Python: {sys.version}")
        lsp_info = QLabel(f"LSP: {lsp_name}")
        lsp_info.setToolTip(f"{lsp_binary.value}")
        save_pulldown = QMenu()
        stop_pulldown = QMenu()

        return WidgetGroup(
            dockable_metadata=dockable_metadata,
            meta_view=dockable_metadata.meta_view,
            system_list=system_list,
            status_preview=status_preview,
            script_edit=script_edit,
            system_command_help=system_command_help,
            system_command_text_edit=system_command_text_edit,
            config_editor=config_editor,
            save_button=save_button,
            stop_button=stop_button,
            splitter=splitter,
            central_widget=central_widget,
            python_info=python_info,
            lsp_info=lsp_info,
            save_pulldown=save_pulldown,
            stop_pulldown=stop_pulldown,
        )

    def _create_actions(self) -> ActionGroup:
        """
        Create all required actions.

        Returns
        -------
        ActionGroup
            The dataclass with all the actions.
        """
        matrix_settings = QAction("Show matrix toml")
        matrix_settings.setMenuRole(QAction.MenuRole.PreferencesRole)
        matrix_settings.setShortcut(QKeySequence.StandardKey.Preferences)
        about = QAction("About")
        about.setMenuRole(QAction.MenuRole.AboutRole)
        config_action = QAction(get_matrix_icon("CHAR_≡"), "Device config")
        config_action.setToolTip("Show the devices preferences/ configuration.")
        config_action.setCheckable(True)
        new_file = QAction(get_matrix_icon("SP_FileIcon"), "New")
        new_file.setShortcut(QKeySequence.StandardKey.New)
        load = QAction(get_matrix_icon("SP_DialogOpenButton"), "Open")
        load.setToolTip("Open a script file.")
        load.setShortcut(QKeySequence.StandardKey.Open)
        save = QAction(get_matrix_icon("SP_DialogSaveButton"), "Save")
        save.setToolTip("Save the under the current filename.")
        save.setShortcut(QKeySequence.StandardKey.Save)
        save_as = QAction(get_matrix_icon("SP_DialogSaveButton"), "Save As...")
        save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.widgets.save_button.setDefaultAction(save)
        self.widgets.save_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.widgets.save_pulldown.addAction(save_as)
        self.widgets.save_button.setMenu(self.widgets.save_pulldown)
        add_system = QAction(get_matrix_icon("CHAR_+"), "Add System")
        add_system.setToolTip("Add a matrix system file.")
        remove_system = QAction(get_matrix_icon("CHAR_-"), "Remove System")
        remove_system.setEnabled(False)
        remove_system.setToolTip("Remove the selected or last matrix system file.")
        quit_app = QAction("Quit")
        if os.name == "nt":
            quit_app.setShortcut(QKeySequence.StandardKey.Close)
        else:
            quit_app.setShortcut(QKeySequence.StandardKey.Quit)
        undo = self._standard_action("Undo")
        redo = self._standard_action("Redo")
        cut = self._standard_action("Cut")
        copy = self._standard_action("Copy")
        paste = self._standard_action("Paste")
        caption = "Toggle Line Comment\t" + script_config.shortcuts.line_comment_display
        line_comment = QAction(caption)
        line_comment.setShortcut(QKeySequence(script_config.shortcuts.line_comment_shortcut))
        zoom_in = self._standard_action("ZoomIn", "Zoom in")
        zoom_out = self._standard_action("ZoomOut", "Zoom Out")
        print_action = QAction("Print")
        print_action.setShortcut(QKeySequence.StandardKey.Print)
        find = QAction("Find")
        find.setShortcut(QKeySequence.StandardKey.Find)
        start_pause = QAction(get_matrix_icon("CUSTOM_Play"), "Start")
        start_pause.setToolTip("Execute the script.")
        start_pause.setCheckable(True)
        stop = QAction(get_matrix_icon("CUSTOM_Stop"), "Stop")
        stop.setToolTip("Stop the script and query status.")
        stop.setEnabled(False)
        abort = QAction(get_matrix_icon("CUSTOM_Stop"), "Abort")
        abort.setEnabled(False)
        finish = QAction(get_matrix_icon("CUSTOM_Stop"), "Finish")
        finish.setEnabled(False)
        self.widgets.stop_button.setDefaultAction(stop)
        self.widgets.stop_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.widgets.stop_pulldown.addAction(abort)
        self.widgets.stop_pulldown.addAction(finish)
        self.widgets.stop_button.setMenu(self.widgets.stop_pulldown)
        kill = QAction(get_matrix_icon("SP_DialogCancelButton"), "Kill")
        kill.setEnabled(False)
        preview = QAction(
            get_matrix_icon("matr1x-matrix-preview.png", QColor("RoyalBlue")),
            "Preview",
        )
        preview.setEnabled(False)
        pep8 = QAction("Format with ruff")
        pep8.setShortcut(QKeySequence("Ctrl+8"))
        theme_actions = []
        theme_group = QActionGroup(MApplication.instance())
        theme_group.setExclusionPolicy(QActionGroup.ExclusionPolicy.Exclusive)
        for theme in self.widgets.script_edit.supportedThemes():
            action = QAction(theme)
            action.setCheckable(True)
            if theme == self.widgets.script_edit.supportedThemes()[0]:
                action.setChecked(True)
            action.triggered.connect(
                lambda checked=False, theme=theme: self.widgets.script_edit.setTheme(theme)
            )
            theme_group.addAction(action)
            theme_actions.append(action)
        autocomplete = QAction("Tab completion")
        autocomplete.setCheckable(True)
        autocomplete.setChecked(True)
        show_log = QAction("Show Log Window")
        toggle_metadata = QAction("Show Metadata")
        toggle_metadata.setShortcut(QKeySequence("Ctrl+2"))
        toggle_metadata.setCheckable(True)
        toggle_metadata.setChecked(True)
        toggle_toolbar = QAction("Show Toolbar")
        toggle_toolbar.setShortcut(QKeySequence("Ctrl+1"))
        toggle_toolbar.setCheckable(True)
        toggle_toolbar.setChecked(True)
        system_help = QAction("Show System Help")
        post_install = QAction("Install Desktop Integration")
        remove_desktop_integration = QAction("Remove Desktop Integration")

        return ActionGroup(
            matrix_settings=matrix_settings,
            about=about,
            config=config_action,
            new_file=new_file,
            load=load,
            save=save,
            save_as=save_as,
            add_system=add_system,
            remove_system=remove_system,
            quit_app=quit_app,
            undo=undo,
            redo=redo,
            cut=cut,
            copy=copy,
            paste=paste,
            line_comment=line_comment,
            zoom_in=zoom_in,
            zoom_out=zoom_out,
            print=print_action,
            find=find,
            start_pause=start_pause,
            stop=stop,
            abort=abort,
            finish=finish,
            kill=kill,
            preview=preview,
            pep8=pep8,
            autocomplete=autocomplete,
            show_log=show_log,
            toggle_metadata=toggle_metadata,
            toggle_toolbar=toggle_toolbar,
            system_help=system_help,
            theme_actions=theme_actions,
            theme_group=theme_group,
            post_install=post_install,
            remove_desktop_integration=remove_desktop_integration,
        )

    def _create_toolbar(self) -> QToolBar:
        """
        Create the toolbar.

        Returns
        -------
        QToolBar
            The (main) toolbar.
        """
        toolbar = QToolBar("Toolbar")
        toolbar.setObjectName("main_toolbar")
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        toolbar.setFloatable(False)
        toolbar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        toolbar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea | Qt.ToolBarArea.BottomToolBarArea)
        icon_size = MApplication.instance().toolbar_icon_size()
        empty = QWidget()
        empty.setFixedWidth(icon_size)
        empty2 = QWidget()
        empty2.setFixedWidth(icon_size)
        empty3 = QWidget()
        empty3.setFixedWidth(icon_size)
        toolbar.setIconSize(QSize(icon_size, icon_size))
        toolbar.addAction(self.actions.new_file)
        toolbar.addAction(self.actions.load)
        toolbar.addWidget(self.widgets.save_button)
        toolbar.addWidget(empty)
        toolbar.addAction(self.actions.start_pause)
        toolbar.addWidget(self.widgets.stop_button)
        toolbar.addWidget(empty2)
        toolbar.addAction(self.actions.preview)
        toolbar.addWidget(empty3)
        toolbar.addSeparator()
        toolbar.addAction(self.actions.add_system)
        toolbar.addWidget(self.widgets.system_list)
        toolbar.addAction(self.actions.remove_system)
        toolbar.addSeparator()
        toolbar.addAction(self.actions.config)
        return toolbar

    def _create_menu(self) -> QMenuBar:
        """Create the main menu."""
        menu = QMenuBar()
        file = menu.addMenu("&File")
        file.addAction(self.actions.new_file)
        file.addAction(self.actions.load)
        file.addSeparator()
        file.addAction(self.actions.save)
        file.addAction(self.actions.save_as)
        file.addSeparator()
        file.addAction(self.actions.add_system)
        file.addAction(self.actions.remove_system)
        file.addSeparator()
        file.addAction(self.actions.print)
        file.addSeparator()
        file.addAction(self.actions.quit_app)  # This gets auto-moved on a Mac
        edit = menu.addMenu("&Edit")
        edit.addAction(self.actions.undo)
        edit.addAction(self.actions.redo)
        edit.addSeparator()
        edit.addAction(self.actions.cut)
        edit.addAction(self.actions.copy)
        edit.addAction(self.actions.paste)
        edit.addSeparator()
        edit.addAction(self.actions.find)
        edit.addSeparator()
        edit.addAction(self.actions.line_comment)
        edit.addSeparator()
        edit.addAction(self.actions.pep8)
        editor = menu.addMenu("&Editor")
        theme = editor.addMenu("Theme")
        for action in self.actions.theme_actions:
            theme.addAction(action)
        editor.addSeparator()
        editor.addAction(self.actions.zoom_in)
        editor.addAction(self.actions.zoom_out)
        editor.addSeparator()
        editor.addAction(self.actions.autocomplete)
        control = menu.addMenu("&Control")
        control.addAction(self.actions.start_pause)
        control.addAction(self.actions.abort)
        control.addAction(self.actions.finish)
        control.addAction(self.actions.kill)
        control.addSeparator()
        control.addAction(self.actions.preview)
        view = menu.addMenu("&View")
        view.addAction(self.actions.toggle_toolbar)
        view.addAction(self.actions.toggle_metadata)
        view.addAction(self.actions.matrix_settings)
        view.addAction(self.actions.config)
        help_menu = menu.addMenu("&Help")
        help_menu.addAction(self.actions.system_help)
        help_menu.addAction(self.actions.show_log)
        help_menu.addSeparator()
        help_menu.addAction(self.actions.post_install)
        help_menu.addAction(self.actions.remove_desktop_integration)
        help_menu.addAction(self.actions.about)  # This is auto-moved on a Mac
        return menu

    def _create_gui(self) -> None:
        """Create and set up the main GUI."""
        layout = QVBoxLayout(self.widgets.central_widget)
        layout.setSpacing(6)
        layout.setContentsMargins(11, 4, 11, 11)
        self.widgets.splitter.addWidget(self.widgets.script_edit)
        self.widgets.splitter.addWidget(self.widgets.status_preview)
        self.widgets.splitter.setChildrenCollapsible(False)
        layout.addWidget(self.widgets.splitter, 1)
        infobar = QHBoxLayout()
        infobar.addStretch()
        infobar.addWidget(self.widgets.python_info)
        infobar.addWidget(QLabel("  |  "))
        infobar.addWidget(self.widgets.lsp_info)
        layout.addLayout(infobar, 0)


class MainWindow(QMainWindow):
    """
    Run the logical code.

    Parameters
    ----------
    filename: str, optional
        The file to load automatically.
    """

    extension = ".matrix"

    def __init__(self, filename: Path | None = None):
        super().__init__()
        self.in_pytest = False
        self.log_window = LoggingWindow(parent=self)  # Immediately needed, not moved to widgets!
        self.log_window.hide()
        logger.info("matrix-script starting")
        self.scriptname: Path | None = None
        self.line_offset = get_script_prefix_offset()
        self.measurement_file: Path
        self.is_running = False
        self.shortcut_dir: tempfile.TemporaryDirectory[str] | None = None
        self.last_filename: Path | None = None
        self.settings = SaferQSettings("matr1x", "script")
        self._output_buffer: list[str] = []
        self._output_timer = QTimer()
        self._output_timer.timeout.connect(self._flush_output_buffer)
        self._output_timer.setSingleShot(False)
        self._output_timer.setInterval(50)
        self.setWindowIcon(get_matrix_icon("matr1x-matrix-script.png"))
        self.ui: UIBuilder = UIBuilder()
        self.ui.widgets.script_edit.setValidExtensions([self.extension])
        self.setMenuBar(self.ui.menubar)
        self.addToolBar(self.ui.toolbar)
        install_metadata_config_docks(
            self,
            self.ui.widgets.dockable_metadata,
            self.ui.widgets.config_editor,
        )
        self.setCentralWidget(self.ui.widgets.central_widget)
        self.create_connections()
        self.ui.widgets.script_edit.setFocus()  # this does not do anything?!
        self.update_window_title()
        check_config(matr1x.config)
        sys.stdout = StreamToLogger(logger, logging.INFO)
        sys.stderr = StreamToLogger(logger, logging.ERROR)
        if filename is not None:
            self.load_from_filename(filename)
        else:
            self.update_systems()
        self.ui.widgets.status_preview.appendPlainText(help_text)
        check_desktop_integration()

    def create_connections(self) -> None:
        """Connect actions and widgets with application logic."""
        self.ui.actions.about.triggered.connect(self.info_box)
        self.ui.actions.matrix_settings.triggered.connect(open_matrix_toml)
        self.ui.actions.new_file.triggered.connect(self.new_file)
        self.ui.actions.load.triggered.connect(self.load_from_file)
        self.ui.actions.save.triggered.connect(self.save_file)
        self.ui.actions.save_as.triggered.connect(self.save_file_as)
        self.ui.actions.add_system.triggered.connect(self.ui.widgets.system_list.query_systems)
        self.ui.actions.remove_system.triggered.connect(self.ui.widgets.system_list.delete_systems)
        self.ui.actions.print.triggered.connect(self.print_document)
        self.ui.actions.quit_app.triggered.connect(self.close)
        self.ui.actions.find.triggered.connect(self.ui.widgets.script_edit.show_find)
        self.ui.actions.line_comment.triggered.connect(
            self.ui.widgets.script_edit.toggleLineComment
        )
        self.ui.actions.pep8.triggered.connect(self.ui.widgets.script_edit.formatCode)
        self.ui.actions.autocomplete.toggled.connect(
            self.ui.widgets.script_edit.enableTabCompletion
        )
        self.ui.actions.start_pause.triggered.connect(self.start_process)
        self.ui.actions.stop.triggered.connect(lambda: self.abort_thread("q"))
        self.ui.actions.abort.triggered.connect(lambda: self.abort_thread("a"))
        self.ui.actions.finish.triggered.connect(lambda: self.abort_thread("f"))
        self.ui.actions.kill.triggered.connect(self.kill_thread)
        self.ui.actions.preview.triggered.connect(self.preview_data)
        self.ui.actions.toggle_toolbar.triggered.connect(self.toggle_toolbar_view)
        self.ui.actions.toggle_metadata.triggered.connect(self.toggle_metadata_view)
        self.ui.actions.config.toggled.connect(self.toggle_preferences)
        self.ui.actions.system_help.triggered.connect(self.show_system_commands)
        self.ui.actions.show_log.triggered.connect(self.show_log_window)
        self.ui.actions.post_install.triggered.connect(post_installation)
        self.ui.actions.remove_desktop_integration.triggered.connect(remove_desktop_integration)
        self.ui.widgets.config_editor.visibilityChanged.connect(self._sync_layout_actions)
        self.ui.widgets.dockable_metadata.visibilityChanged.connect(self._sync_layout_actions)
        self.ui.toolbar.visibilityChanged.connect(self._sync_layout_actions)
        self.ui.widgets.script_edit.contentModified.connect(self.update_window_title)
        self.ui.widgets.script_edit.file_dropped.connect(self._load_file_from_signal)
        self.ui.widgets.system_list.changed.connect(self.update_systems)
        self.ui.widgets.system_list.message.connect(self.show_message)
        self.ui.widgets.system_list.changed.connect(
            lambda: self.ui.widgets.script_edit.setModified(True)
        )
        self.ui.widgets.central_widget.file_dropped.connect(self._load_file_from_signal)

    @AutoSlot
    def process_data(self, env: Envelope) -> None:
        """Process the data from the measurement thread."""
        data = env.payload
        if isinstance(data, (Telemetry, Header, SetValues, MeasuredValues)) and data.to_stdout:
            self.write_output(str(data) + "\n")
        elif isinstance(data, LineNumber):
            self.ui.widgets.script_edit.highlight(data.line - self.line_offset)
        elif isinstance(data, Datafile):
            self.update_filename(data.datafile)
        elif isinstance(data, InputParameters):
            self.get_script_input(data)
        elif isinstance(data, Message):
            if data.modifier == Modifier.DELETE_CURRENT_LINE:
                self.write_output("\r" + data.message + data.end)
            else:
                self.write_output(data.message + data.end)

    def show_message(self, message: NotifierMessage):
        """Show a message text and log."""
        self.ui.widgets.status_preview.print_colored(message.text)
        logger.log(message.level, message.text)

    def print_document(self) -> None:
        """Print the script."""
        text_edit = QTextEdit()  # go via QTextEdit functions for better portability
        text_edit.setText(self.ui.widgets.script_edit.toPlainText())
        printer = QPrinter()
        if QPrintDialog(printer, self).exec():
            text_edit.print_(printer)

    def save_window_state(self) -> None:
        """Save application configuration until next startup."""
        self.settings.setValue("created", 1)
        self.settings.beginGroup(LAYOUT_SETTINGS_GROUP)
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("window_state", self.saveState())
        self.settings.setValue("splitter", self.ui.widgets.splitter.sizes())
        self.settings.endGroup()

        self.settings.beginGroup("script_edit")
        self.settings.setValue("monaco_zoom", self.ui.widgets.script_edit.zoomFactor())
        self.settings.setValue("theme", self.ui.actions.theme_group.checkedAction().text())
        self.settings.setValue("autocomplete", self.ui.actions.autocomplete.isChecked())
        self.settings.endGroup()

        if shiboken6.isValid(self.log_window):
            self.settings.setValue("log_window/position", self.log_window.pos())
            self.settings.setValue("log_window/size", self.log_window.size())

        # Only save help dialog size and position if it has been shown at least once
        if hasattr(self, "_help_dialog_shown") and self._help_dialog_shown:
            self.settings.beginGroup("system_command_help")
            self.settings.setValue("size", self.ui.widgets.system_command_help.size())
            self.settings.setValue("position", self.ui.widgets.system_command_help.pos())
            self.settings.endGroup()

    def _sync_layout_actions(self) -> None:
        """Match view action state to the restored widget visibility."""
        sync_visibility_actions(
            [
                (self.ui.actions.config, self.ui.widgets.config_editor),
                (self.ui.actions.toggle_metadata, self.ui.widgets.dockable_metadata),
                (self.ui.actions.toggle_toolbar, self.ui.toolbar),
            ]
        )

    def _restored_splitter_sizes(self) -> list[int] | None:
        """Return saved splitter sizes unless a pane would be collapsed."""
        if not self.settings.contains("splitter"):
            return None
        sizes = self.settings.safer_value("splitter", [], type=list)
        if len(sizes) != self.ui.widgets.splitter.count():
            return None
        try:
            restored_sizes = [int(size) for size in sizes]
        except (TypeError, ValueError):
            return None
        if any(size <= 0 for size in restored_sizes):
            return None
        return restored_sizes

    def restore_window_state(self) -> None:
        """Restore app configuration from the previous use."""
        self.resize(self.sizeHint())  # Just in case it is the first start
        self.settings.beginGroup(LAYOUT_SETTINGS_GROUP)
        self.restoreGeometry(self.settings.safer_value("geometry", QByteArray(), type=QByteArray))
        with blocked_signals(
            self.ui.actions.config,
            self.ui.actions.toggle_metadata,
            self.ui.actions.toggle_toolbar,
        ):
            self.restoreState(
                self.settings.safer_value("window_state", QByteArray(), type=QByteArray)
            )
        splitter_sizes = self._restored_splitter_sizes()
        if splitter_sizes is not None:
            self.ui.widgets.splitter.setSizes(splitter_sizes)
        self.settings.endGroup()
        self._sync_layout_actions()

        # Check if there is a settings file. This improves the robustness
        # against strange side effect, caused by the default values.
        if self.settings.contains("created"):
            self.settings.beginGroup("script_edit")
            self.ui.widgets.script_edit.setZoomFactor(
                self.settings.safer_value("monaco_zoom", 1, type=float)
            )
            last_theme = self.settings.safer_value("theme", "", type=str)
            for theme in self.ui.actions.theme_actions:
                if theme.text() == last_theme:
                    theme.setChecked(True)
                    self.ui.widgets.script_edit.setTheme(last_theme)
            self.ui.actions.autocomplete.setChecked(
                self.settings.safer_value("autocomplete", True, type=bool)
            )
            self.settings.endGroup()
            self.log_window.move(
                self.settings.safer_value(
                    "log_window/position", self.log_window.pos(), type=QPoint
                )
            )
            self.log_window.resize(
                self.settings.safer_value("log_window/size", self.log_window.size(), type=QSize)
            )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        Allow to modify systems list with keyboard shortcuts.

        Parameters
        ----------
        event: QKeyEvent
            The key-combination to be evaluated.
        """
        if self.ui.widgets.system_list.hasFocus():
            if detect_shortcut(event, QKeySequence(QKeySequence.StandardKey.Delete)):
                self.ui.widgets.system_list.delete_systems()
            if detect_shortcut(event, QKeySequence(Qt.Key.Key_Backspace)):
                self.ui.widgets.system_list.delete_systems()
        super().keyPressEvent(event)

    def closeEvent(self, event: QEvent) -> None:
        """
        Close app and ask user if script should be saved.

        If a script is running, the event is ignored and an explanation
        is given. If the script was modified without saving and not
        empty, a dialog asks how to proceed.

        Parameters
        ----------
        event : QEvent
            The received 'close event'
        """
        if self.is_running:
            QMessageBox.critical(
                QWidget(),
                "Script running!",
                """Please wait for the script to finish. Alternatively,
                stop or kill the script before exiting 'Matrix Script'!""",
            )
            event.ignore()
            return
        if (
            self.ui.widgets.script_edit.isModified()
            and self.ui.widgets.script_edit.toPlainText() != ""
            and not self.in_pytest
        ):
            if not save_messagebox(self, self.save_file):
                return
        self.save_window_state()
        self.ui.widgets.script_edit.lsp.stop()
        self.ui.widgets.script_edit.server.stop()
        # QWebEngineView: Disconnect the webpage to prevent memory leaks
        if hasattr(self.ui.widgets.script_edit, "page") and self.ui.widgets.script_edit.page():
            self.ui.widgets.script_edit.page().loadFinished.disconnect()
            self.ui.widgets.script_edit.page().deleteLater()
        self.ui.widgets.script_edit.deleteLater()
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.log_window.log_handler)
        self.log_window.deleteLater()
        self.ui.widgets.system_command_help.close()
        event.accept()

    def info_box(self) -> None:
        """Display an 'about this app' widget."""
        box = AboutBox(
            "Matrix Script",
            get_matrix_icon("matr1x-matrix-script.png"),
            matr1x,
            matr1x.datetimefmt,
        )
        box.exec()

    def toggle_toolbar_view(self, checked: bool) -> None:
        """
        Toggle the visibility of the toolbar.

        Parameters
        ----------
        checked: bool
            Show (True) or hide (False) the toolbar.
        """
        if checked:
            self.ui.toolbar.show()
        else:
            self.ui.toolbar.hide()

    def toggle_metadata_view(self, checked: bool) -> None:
        """
        Toggle the visibility of the metadata.

        Parameters
        ----------
        checked: bool
            Show (True) or hide (False) the metadata.
        """
        if checked:
            self.ui.widgets.dockable_metadata.show()
        else:
            self.ui.widgets.dockable_metadata.hide()

    def preview_data(self) -> None:
        """Launch matrix-preview with current measurement file."""
        preview = [
            sys.executable,
            "-c",
            f"from matr1x.scripts import matrix_preview; "
            f"matrix_preview.main(file=r'{self.measurement_file}')",
        ]
        subprocess.Popen(preview)

    def toggle_preferences(self, checked: bool) -> None:
        """
        Open the preferences pane.

        Parameters
        ----------
        checked: bool
            Show (True) or hide (False) the preferences.
        """
        if checked:
            self.ui.widgets.config_editor.show()
            self.ui.widgets.config_editor.raise_()
            self.ui.widgets.config_editor.activateWindow()
        else:
            self.ui.widgets.config_editor.hide()

    def show_log_window(self) -> None:
        """Show the logging window."""
        self.log_window.show()
        self.log_window.raise_()
        self.log_window.activateWindow()

    def _load_file_from_signal(self, filename: str) -> None:
        """Convert string to Path for opening file."""
        self.load_from_filename(Path(filename))

    def update_window_title(self) -> None:
        """Indicate if the file was edited with an asterisk."""
        text = "Matrix Script"
        if self.ui.widgets.script_edit.isModified():
            text += ": *"
        elif self.scriptname:
            text += ": "
        if self.scriptname:
            text += self.scriptname.name
        elif self.ui.widgets.script_edit.isModified():
            text += "<unsaved>"
        self.setWindowTitle(text)
        lsp_name = self.scriptname.name if self.scriptname else None
        self.ui.widgets.script_edit.setFilename(lsp_name)

    @AutoSlot
    def get_script_input(self, params: InputParameters) -> None:
        """
        Open a dialog and forward input to the script.

        Parameters
        ----------
        params: InputParameters
            Object containing all input parameters including query,
            input_type, timeout, default_value, min_value, max_value,
            step, and decimals.
        """
        if params.timeout is None:
            params.timeout = float("inf")
        if params.input_type == "string":
            dialog = TextInputDialog(
                params.query,
                parent=self,
                timeout=params.timeout,
                default_value=params.default_value,
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                ret = dialog.get_input_text()
            else:
                self.abort_thread()  # abort executing script
                return
        elif params.input_type == "bool":
            dialog = YesNoAbortDialog(
                params.query,
                parent=self,
                timeout=params.timeout,
                default_value=params.default_value,
            )
            ret = dialog.exec_and_get_response()
            if ret == "abort":
                self.abort_thread()
                return
        elif params.input_type == "numerical":
            try:
                # Convert default_value string to float
                numerical_default_value = (
                    float(params.default_value) if params.default_value else 0.0
                )
            except ValueError:
                self.ui.widgets.status_preview.appendPlainText(
                    f"Warning: Invalid default_value '{params.default_value}' "
                    "for numerical input. Using 0.0",
                )
                numerical_default_value = 0.0

            dialog = NumericalInputDialog(
                params.query,
                parent=self,
                timeout=params.timeout,
                default_value=numerical_default_value,
                min_value=params.min_value,
                max_value=params.max_value,
                step=params.step,
                decimals=params.decimals,
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                ret = str(dialog.get_input_value())
            else:
                self.abort_thread()  # abort executing script
                return
        elif params.input_type == "__end_script__":
            ret = TerminationDialog().get_selection()
        else:
            ret = ""
        self.measurement_thread.pass_input(ret)

    def pause_thread(self) -> None:
        """Pause thread execution."""
        self.measurement_thread.pause()

    def abort_thread(self, char="q") -> None:
        """
        Abort thread execution, define measurement state as per `char`.

        Parameters
        ----------
        char : str
            Single length string that is passed to the process.
            - "q" stops and queries user for state
            - "a" stops and sets state to `aborted`
            - "f" stops and sets state to `finished`
        """
        if self.ui.actions.start_pause.isChecked():
            self.ui.actions.start_pause.setChecked(False)
        self.measurement_thread.abort(char)

    def kill_thread(self) -> None:
        """Kill the thread."""
        self.measurement_thread.kill()
        self.ui.widgets.status_preview.print_colored(
            "Script terminated by user - file integrity might be compromised"
        )

    def update_system_commands(self) -> None:
        """Update the help info about the current system(s)."""
        system_info = self.ui.widgets.system_list.system_info
        text = "The following systems were selected:<br><b>"
        for system in self.ui.widgets.system_list.systems:
            text = text + system + "<br>"
        text += "<br></b>These systems provide the following:<br>"
        bg_color = "#565656" if MApplication.instance().isDark else "#f0f0f0"
        if system_info.parameters != {}:
            text += "<h3>Parameters</h3>"
            text += '<table border="1" cellpadding="5" cellspacing="0" '
            text += 'style="border-collapse: collapse; text-align: left; '
            text += 'margin-bottom: 20px;">'
            text += f'<tr style="background-color: {bg_color}; text-align: left;">'
            text += '<th style="text-align: left;">Index</th>'
            text += '<th style="text-align: left;">Name</th>'
            text += '<th style="text-align: left;">Description</th></tr>'
            for parameter in system_info.parameters.values():
                if parameter.settable:
                    text += f"<tr><td>{parameter.index}</td>"
                    text += f"<td><b>{parameter.name}</b></td>"
                    text += f"<td>{parameter.description}</td></tr>"
                else:
                    text += f"<tr><td>{parameter.index}</td>"
                    text += f"<td>{parameter.name}</td>"
                    text += f"<td>{parameter.description}</td></tr>"
            text += "</table>"
        if system_info.devices != {}:
            text += "<h3>Devices</h3>"
            text += '<table border="1" cellpadding="5" cellspacing="0" '
            text += 'style="border-collapse: collapse; text-align: left; '
            text += 'margin-bottom: 20px;">'
            text += f'<tr style="background-color: {bg_color}; text-align: left;">'
            text += '<th style="text-align: left;">Name</th>'
            text += '<th style="text-align: left;">Description</th></tr>'
            for device in system_info.devices.values():
                text += f"<tr><td><b>{device.name}</b></td><td>{device.description}</td></tr>"
            text += "</table>"
        if system_info.methods != {}:
            text += "<h3>System Methods and Variables</h3>"
            text += '<table border="1" cellpadding="5" cellspacing="0" '
            text += 'style="border-collapse: collapse; text-align: left; '
            text += 'margin-bottom: 20px;">'
            text += f'<tr style="background-color: {bg_color}; text-align: left;">'
            text += '<th style="text-align: left;">Name</th>'
            text += '<th style="text-align: left;">Description</th></tr>'
            for method in system_info.methods.values():
                text += f"<tr><td><b>{method.name}</b></td><td>{method.description}</td></tr>"
            text += "</table>"
        text += "<br>"
        self.ui.widgets.system_command_text_edit.setText(text)

    def show_system_commands(self) -> None:
        """Print information about current system(s) in a help window."""
        self.ui.widgets.system_command_help.setMinimumSize(
            self.ui.widgets.system_command_help.sizeHint()
        )

        # Load size and position from settings (only if not already visible)
        if not self.ui.widgets.system_command_help.isVisible():
            self.settings.beginGroup("system_command_help")
            saved_size = self.settings.safer_value(
                "size", self.ui.widgets.system_command_help.sizeHint(), type=QSize
            )
            saved_position = self.settings.safer_value(
                "position", self.ui.widgets.system_command_help.pos(), type=QPoint
            )
            self.settings.endGroup()
            self.ui.widgets.system_command_help.resize(saved_size)
            self.ui.widgets.system_command_help.move(saved_position)

        self.ui.widgets.system_command_help.show()
        self.ui.widgets.system_command_help.raise_()
        # Mark that the help dialog has been shown at least once
        self._help_dialog_shown = True

    def write_output(self, text: str) -> None:
        """
        Buffer text and update GUI periodically to prevent crashes.

        Parameters
        ----------
        text: str
            Text to be appended.
        """
        self._output_buffer.append(text)
        if not self._output_timer.isActive():
            self._output_timer.start()

    def _flush_output_buffer(self) -> None:
        """Flush buffered text to the GUI."""
        if not self._output_buffer:
            self._output_timer.stop()
            return

        combined_text = "".join(self._output_buffer)
        self._output_buffer.clear()

        # Operate on a disposable cursor so we do not move the user's cursor/selection.
        # Handle plain text and control characters in one path, because buffered writes
        # can split "\r" from the text it is meant to overwrite.
        edit = self.ui.widgets.status_preview
        scrollbar = edit.verticalScrollBar()
        at_bottom = scrollbar.value() == scrollbar.maximum()
        doc = self.ui.widgets.status_preview.document()
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.beginEditBlock()
        parts = re.split(r"([\r\n])", combined_text)
        for index in range(0, len(parts), 2):
            text = parts[index]
            if text:
                cursor.insertText(text)

            if index + 1 >= len(parts):
                continue

            if parts[index + 1] == "\r":
                cursor.movePosition(
                    QTextCursor.MoveOperation.StartOfBlock,
                    QTextCursor.MoveMode.KeepAnchor,
                )
                cursor.removeSelectedText()
            else:
                cursor.insertBlock()
        cursor.endEditBlock()
        if at_bottom:
            edit.moveCursor(QTextCursor.MoveOperation.End)
        if not self._output_buffer:
            self._output_timer.stop()

    def update_filename(self, path: str) -> None:
        """
        Update the current measurement filename.

        Parameters
        ----------
        path: str
            Path to current measurement file.
        """
        self.measurement_file = Path(path)
        self.ui.actions.preview.setEnabled(True)

    def enable_buttons(self, flag: bool) -> None:
        """
        Switch the buttons to either running or stopped mode.

        Parameters
        ----------
        flag : bool
            True means script is running
        """
        self.is_running = flag
        if flag:
            self.ui.actions.start_pause.setIcon(get_matrix_icon("CUSTOM_Pause"))
            self.ui.actions.start_pause.setText("Pause")
            self.ui.actions.start_pause.setToolTip("Pause the currently running script.")
            self.ui.actions.start_pause.triggered.disconnect(self.start_process)
            self.ui.actions.start_pause.triggered.connect(self.pause_thread)
        else:
            self.ui.widgets.script_edit.removeHighlight()
            self.ui.actions.start_pause.setIcon(get_matrix_icon("CUSTOM_Play"))
            self.ui.actions.start_pause.setText("Start")
            self.ui.actions.start_pause.setToolTip("Execute the script.")
            self.ui.actions.start_pause.triggered.disconnect(self.pause_thread)
            self.ui.actions.start_pause.triggered.connect(self.start_process)
        self.ui.actions.start_pause.setChecked(False)
        self.ui.actions.stop.setEnabled(flag)
        self.ui.actions.abort.setEnabled(flag)
        self.ui.actions.finish.setEnabled(flag)
        self.ui.actions.kill.setEnabled(flag)
        self.ui.widgets.script_edit.setReadOnly(flag)
        self.ui.actions.new_file.setEnabled(not flag)
        self.ui.actions.load.setEnabled(not flag)
        self.ui.actions.system_help.setEnabled(not flag)
        self.ui.actions.add_system.setEnabled(not flag)
        self.ui.actions.remove_system.setEnabled(not flag)
        self.ui.widgets.meta_view.setEnabled(not flag)

    def process_finished(self) -> None:
        """
        Handle GUI changes and clean up thread after it has finished.

        Return buttons to original state, delete the finished process.
        """
        self.enable_buttons(False)
        self.ui.widgets.status_preview.print_colored("\nExecution finished")
        del self.measurement_thread

    def run_linter(self) -> int:
        """
        Call the linter for the editor view.

        Returns
        -------
        int
            The number of issues.
        """
        self.ui.widgets.script_edit.setSettables(self.ui.widgets.system_list.system_info)
        return self.ui.widgets.script_edit.returnIssues()

    def start_process(self) -> None:
        """
        Start the matrix_script process.

        Disable/enable buttons to reflect run state and get selected
        systems. Then runs the script defined in the edit.
        """
        if (
            self.run_linter() > 0 and not self.in_pytest
        ):  # run linter to make sure there are no errors
            self.ui.widgets.status_preview.print_colored(
                "Script execution was halted because of linter errors"
            )
            MApplication.instance().processEvents()
            a = QMessageBox(parent=self)  # open a popup window to inform about the error
            a.setText("Linter error")
            a.setInformativeText("Error found in script, continue anyway?")
            a.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            a.setDefaultButton(QMessageBox.StandardButton.Ok)
            ret = a.exec()
            if ret == QMessageBox.StandardButton.Cancel:
                self.ui.actions.start_pause.setChecked(False)
                return
        self.ui.widgets.status_preview.print_colored("### Running script now")
        user_script = self.ui.widgets.script_edit.toPlainText()
        script = generate_script(user_script)
        metadata = self.ui.widgets.meta_view.metadata
        temp_config = self.ui.widgets.config_editor.write_config()
        self.measurement_thread = ScriptThread(
            metadata, script, self.scriptname, temp_config, self.ui.widgets.system_list.systems
        )
        self.measurement_thread.finished.connect(self.process_finished)
        self.measurement_thread.data_received.connect(self.process_data)

        logger.info("The following user script is started:\n%s", user_script)
        self.measurement_thread.start()
        self.enable_buttons(True)

    def update_systems(self, update_config: bool = True) -> None:
        """
        Update the systems list and config editor.

        Parameters
        ----------
        update_config: bool
            Whether to update the config editor.
        """
        if len(self.ui.widgets.system_list.systems) > 0:
            self.ui.actions.remove_system.setEnabled(True)
        # only systems that are part of matrix or ifwlib can be configured via files
        configurable = [
            system for system in self.ui.widgets.system_list.systems if not Path(system).exists()
        ]
        matr1x.reload_config()
        if update_config:
            self.ui.widgets.config_editor.set_systemfile(configurable)
            self.ui.widgets.config_editor.set_full_system_list(self.ui.widgets.system_list.systems)
            self.ui.widgets.config_editor.set_system_info(self.ui.widgets.system_list.system_info)
            self.ui.widgets.config_editor.update_data()
        # Update system commands with cached info
        self.update_system_commands()
        if self.ui.widgets.system_command_help.isVisible():
            self.show_system_commands()
        self.run_linter()

    def save_file_as(self) -> bool:
        """
        Ask for the filename and calls write_file().

        Returns
        -------
        bool
            True (Sucess) or False (Error).
        """
        filename = QFileDialog.getSaveFileName(
            self,
            "Specify filename to save",
            str(matr1x.usersfolder if not self.scriptname else Path(self.scriptname).parent),
            f"matrix files (*{self.extension})",
        )
        filename = Path(filename[0])
        if filename == Path():
            return False
        else:
            return self.write_file(filename)

    def save_file(self) -> bool:
        """
        Try to save under the last name and call write_file().

        If no last filename exists calls save_file_as().

        Returns
        -------
        bool
            True (Sucess) or False (Error).
        """
        if not self.last_filename:
            return self.save_file_as()
        else:
            return self.write_file(self.last_filename)

    def write_file(self, filename: Path) -> bool:
        """
        Save script to file and write system information to header.

        Returns
        -------
        bool
            True (Sucess) or False (Error).
        """
        if filename.suffix != self.extension:
            filename = filename.with_suffix(self.extension)
        try:
            output_file = filename.open("w")
        except OSError:
            self.ui.widgets.status_preview.print_colored("File cannot be written.")
            return False
        self.scriptname = filename
        self.update_systems(update_config=False)
        # set new script in editor and save it to the file
        newscript = self.generate_save_content()
        self.ui.widgets.script_edit.setPlainText(newscript)
        output_file.write(newscript)
        output_file.close()
        self.last_filename = filename
        self.ui.widgets.script_edit.setModified(False)
        self.update_window_title()
        return True

    def generate_save_content(self) -> str:
        """
        Add the systems in the header of a script.

        Returns
        -------
        str
            The script including the generated header.
        """
        system_list = self.ui.widgets.system_list
        flat_parameters = system_list.system_info.flat_parameters
        header_lines = [
            "# system def : " + ",".join(str(s) for s in system_list.systems),
            "# system names : " + ",".join(p.name for p in flat_parameters),
            "# system units : " + ",".join(p.unit for p in flat_parameters),
            "# file v8, time stamp : " + time.strftime(matr1x.datetimefmt, time.localtime()),
        ]
        script = self.ui.widgets.script_edit.toPlainText().rstrip()
        body_lines = [
            line
            for i, line in enumerate(script.splitlines())
            if not (i < 4 and line.startswith(("# system ", "# file v")))
        ]
        return "\n".join(header_lines + body_lines) + "\n"

    def load_from_filename(self, filename: Path) -> None:
        """
        Load the script from file denoted by filename.

        Also, make sure that header information specified still agree
        with the corresponding system.

        Parameters
        ----------
        filename: Path
            The file to load.
        """
        try:
            input_file = filename.open()
        except OSError:
            self.ui.widgets.status_preview.print_colored("File cannot be opened")
            return
        self.scriptname = filename
        code = ""
        self.ui.widgets.system_list.clear()
        #
        # system files
        #
        line = input_file.readline()
        if "# system def : " in line:
            # load system from definition in file
            system_line = line.replace("# system def : ", "").strip()
            systems = [s.strip() for s in system_line.split(",") if s.strip()]
            self.ui.widgets.system_list.add_systems(systems)
            system_info = self.ui.widgets.system_list.system_info
            flat_parameters = system_info.flat_parameters
            column_names = [p.name for p in flat_parameters]
            units = [p.unit for p in flat_parameters]
        else:
            self.ui.widgets.status_preview.print_colored(
                "No system defined in script, please choose system(s)"
            )
        code += line
        #
        # system columns definiton
        #
        line = input_file.readline()
        code += line
        # make sure that system column definition agrees with
        # current system
        if "# system names : " in line:
            system_names = line.strip().replace("# system names : ", "")
            current_columns = [str(col).strip() for col in column_names]
            # Handle both "," and ", " as separators since compound columns use ", "
            loaded_columns = []
            for col in system_names.split(","):
                col = col.strip()
                if col:
                    loaded_columns.append(col)
            if current_columns != loaded_columns:
                self.ui.widgets.status_preview.print_colored(
                    "Column names have changed between generation "
                    "of script and now, please make sure that "
                    "columns are set correctly before running the "
                    "script"
                )
        else:
            self.ui.widgets.status_preview.print_colored(
                "Could not verify column names, please verify that columns have not changed"
            )
        #
        # system unit definiton
        #
        line = input_file.readline()
        code += line
        # make sure that system unit definition agrees with
        # current system
        if "# system units : " in line:
            system_units = line.strip().replace("# system units : ", "")
            current_units = [str(unit).strip() for unit in units]
            # Handle both "," and ", " as separators since compound columns use ", "
            loaded_units = []
            for unit in system_units.split(","):
                loaded_units.append(unit.strip())
            if current_units != loaded_units:
                self.ui.widgets.status_preview.print_colored(
                    "Column units have changed between generation "
                    "of script and now, please make sure that "
                    "columns are set correctly before running the "
                    "script"
                )
        else:
            self.ui.widgets.status_preview.print_colored(
                "Could not verify column units, please verify that columns have not changed"
            )
        #
        # read actual code
        #
        for i, line in enumerate(input_file):
            code += line
        input_file.close()
        self.ui.widgets.script_edit.setPlainText(code)
        self.ui.widgets.script_edit.setModified(False)
        self.last_filename = filename
        self.update_window_title()
        if self.ui.widgets.system_list.count() > 0:
            self.ui.actions.remove_system.setEnabled(True)

    def load_from_file(self) -> None:
        """Open file dialog and call load_from_filename."""
        # First, check if unsaved changes exist
        if self.ui.widgets.script_edit.isModified() and not self.in_pytest:
            if not save_messagebox(self, self.save_file):
                return
        filename = QFileDialog.getOpenFileName(
            self,
            "Select filename to open",
            str(matr1x.usersfolder if not self.scriptname else Path(self.scriptname).parent),
            f"matrix files (*{self.extension})",
        )
        filename = Path(filename[0])
        if filename != Path():
            self.load_from_filename(filename)

    def new_file(self) -> None:
        """Start over with a blank script."""
        if self.ui.widgets.script_edit.isModified() and not self.in_pytest:
            if not save_messagebox(self, self.save_file):
                return
        self.last_filename = None
        self.scriptname = None
        self.ui.widgets.script_edit.setPlainText("")
        self.ui.widgets.script_edit.setModified(False)


def main() -> None:
    """Set the basic GUI parameters and run."""
    install_error_handler()
    app = MApplication(sys.argv)
    appname = "matrix-script"
    app.setDesktopFileName(appname)
    ex = MainWindow(filename=Path(sys.argv[1]) if len(sys.argv) >= 2 else None)
    ex.restore_window_state()
    ex.show()
    # handle MacOS specific FileOpenEvent from MApplication
    app.connect_file_handler(ex._load_file_from_signal)
    ret = app.exec()
    sys.exit(ret)
