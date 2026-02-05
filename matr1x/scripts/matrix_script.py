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
import time
from collections.abc import Callable
from dataclasses import dataclass
from os.path import normpath
from pathlib import Path
from typing import TypeVar

import shiboken6
from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QPoint,
    QSize,
    Qt,
    QThread,
    QTimer,
    Signal,
    Slot,
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
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import matr1x
from matr1x.control.util import QtGracefulKiller
from matr1x.editor import CodeEditor, LSPServer
from matr1x.error_handling import Error, install_error_handler
from matr1x.gui_util import (
    AboutBox,
    ConfigEditWidget,
    EmittingStream,
    FileDropMixin,
    LoggingWindow,
    MApplication,
    MetaDataDialog,
    NumericalInputDialog,
    OutputDuplication,
    SaferQSettings,
    SystemListWidget,
    TerminationDialog,
    TextInputDialog,
    YesNoAbortDialog,
    check_config,
    detect_shortcut,
    find_parent_of_type,
    get_application_instance,
    get_matrix_icon,
    get_system_info,
    open_matrix_toml,
    protected_restore,
    save_messagebox,
)
from matr1x.models import SystemInfo
from matr1x.util import (
    create_temp_dir_with_symlinks,
    find_binary,
    generate_script,
    get_importable_module_name,
)

logger = logging.getLogger(Path(__file__).name)
config = matr1x.get_config_dict("matr1x.scripts.matrix-script")


MAX_LINES_STATUS = 10000
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
init_datafile(filename, comment, append, print_header, ntot)
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
        get_application_instance().isDarkSignal.connect(self.updateColors)

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

    def changeEvent(self, event: QEvent) -> None:
        """Detect theme change event."""
        if event.type() == event.Type.PaletteChange:
            self.updateColors()
        super().changeEvent(event)


if sys.platform == "win32":
    try:
        from ctypes import windll

        myappid = "python.matr1x.matrix-script.version"
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass


@dataclass(frozen=True)
class InputParameters:
    """Parameters for script input requests."""

    query: str
    input_type: str
    timeout: float = float("inf")
    default_value: str = ""
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    decimals: int | None = None


class ScriptThread(QThread):
    """Control and the thread running the measurements."""

    PATTERN_LINENO = r"__lineno(-?\d+)__"
    PATTERN_FILENAME = r"__//(.*)//__"
    PATTERN_INPUT = (
        r"__input_(?P<type>[^:]+):(?P<strlabel>[^:]+)(?::(?P<timeout>[^:]*))"
        r"?(?::(?P<default>[^:]*))?(?::(?P<min>[^:]*))?(?::(?P<max>[^:]*))"
        r"?(?::(?P<step>[^:]*))?(?::(?P<decimals>[^:]*))?__"
    )

    # signal initiating user input from the GUI.
    input_signal = Signal(InputParameters)
    # signal to report the currently executing line number to the editor.
    lineno_signal = Signal(int)
    # signal to report the filename of the file that is written by the process
    filename_signal = Signal(str)

    def __init__(
        self,
        meta_data: dict[str, str],
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
        self.meta_data: dict[str, str] = meta_data
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
            print("Force killed thread! Please verify all devices are")
            print("operational before starting another script.")
        except OSError:
            print("Thread terminated gracefully.")  # this will likely not happen

    def safe_parse(
        self, value: str, param_name: str, converter: Callable[[str], R], default: T
    ) -> R | T:
        """
        Safely parse a string.

        Use a converter callable with error handling and a default
        return value.

        Parameters
        ----------
        value : str
            The string value to parse.
        param_name : str
            Name of the parameter for error reporting.
        converter : e.g. float, int
            Function to convert string to desired type.
        default : T
            Default value to return if parsing yields a value error.

        Returns
        -------
        Usually a subset of float | int | None
            Parsed value of type "converter" or type "default" if
            parsing fails.
        """
        try:
            return converter(value)
        except ValueError:
            print(f"Warning: Invalid {param_name} value received: {value}")
            return default

    def _handle_line_number(self, line: str) -> str:
        """
        Handle line number pattern extraction and emission.

        Parameters
        ----------
        line : str
            Input line to process for line number patterns.

        Returns
        -------
        str
            Line with line number patterns removed.
        """
        if match := re.search(self.PATTERN_LINENO, line):
            digits = int(match.group(1))
            if digits >= 0:
                self.lineno_signal.emit(digits)
            line = re.sub(self.PATTERN_LINENO, "", line)
        return line

    def _handle_filename(self, line: str) -> str:
        """
        Handle filename pattern extraction and emission.

        Parameters
        ----------
        line : str
            Input line to process for filename patterns.

        Returns
        -------
        str
            Line with filename patterns removed.
        """
        if match := re.search(self.PATTERN_FILENAME, line):
            path = match.group(1)
            self.filename_signal.emit(path)
            line = re.sub(self.PATTERN_FILENAME, "", line)
        return line

    def _handle_input_request(self, line: str) -> str:
        """
        Handle input request pattern extraction and emission.

        Parameters
        ----------
        line : str
            Input line to process for input request patterns.

        Returns
        -------
        str
            Line with input request patterns removed.
        """
        if match := re.search(self.PATTERN_INPUT, line):
            input_params = self._parse_input_parameters(match)

            logger.info(
                "Requesting input type: %s, Query: %s, Timeout: %g, Default: %s, "
                "Min: %s, Max: %s, Step: %s",
                input_params.input_type,
                input_params.query,
                input_params.timeout,
                input_params.default_value,
                input_params.min_value,
                input_params.max_value,
                input_params.step,
            )

            self.input_signal.emit(input_params)
            line = re.sub(self.PATTERN_INPUT, "", line)
        return line

    def _parse_input_parameters(self, match: re.Match) -> InputParameters:
        """
        Parse input parameters from regex match groups.

        Parameters
        ----------
        match : re.Match
            Regex match object containing input parameter groups.

        Returns
        -------
        InputParameters
            Parsed input parameters with type, query, timeout, defaults,
            and numerical constraints.
        """
        input_type = match.group("type")
        strlabel = match.group("strlabel").replace("%0A", "\n")

        # Parse optional parameters
        timeout = float("inf")
        if timeout_str := match.group("timeout"):
            timeout = self.safe_parse(timeout_str, "timeout", float, float("inf"))

        default_value = match.group("default") or ""

        # Parse numerical parameters
        min_value = max_value = step = decimals = None
        if input_type == "numerical":
            if min_str := match.group("min"):
                min_value = self.safe_parse(min_str, "min", float, None)
            if max_str := match.group("max"):
                max_value = self.safe_parse(max_str, "max", float, None)
            if step_str := match.group("step"):
                step = self.safe_parse(step_str, "step", float, None)
            if decimals_str := match.group("decimals"):
                decimals = self.safe_parse(decimals_str, "decimals", int, None)

        return InputParameters(
            query=strlabel,
            input_type=input_type,
            timeout=timeout,
            default_value=default_value,
            min_value=min_value,
            max_value=max_value,
            step=step,
            decimals=decimals,
        )

    def recv_line(self, inp: str) -> None:
        """
        Receive a line from the input and handle it accordingly.

        From inp the current executing line or an input request are
        attemped to find, all other input is printed.

        TODO: not tolerant against split strings, i.e. if sent string
        is longer than 1024, one can expect a problematic behavior.
        Migrate to ZMQ and directly pass strings as python objects?
        """
        lines = inp.split(os.linesep)
        for i, line in enumerate(lines[:-1]):
            # add \"\\n\" to all but the last element in split
            # (last element contains everything after last "\n")
            lines[i] += "\n"

        for line in lines:
            line = self._handle_line_number(line)
            line = self._handle_input_request(line)
            line = self._handle_filename(line)
            if line:
                print(line, end="")

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
                stderr=subprocess.STDOUT,
                bufsize=0,
            )
            # accept a connection from the subprocess
            # will block until a new client connects, might want to use select
            # here to make sure the subprocess actually connects?
            self.conn, address = s.accept()
            # wait until the subprocess terminates and pipe its stdout to the
            # user window
            while self.proc.poll() is None:
                try:
                    datachunk = self.conn.recv(8192).decode()
                    if len(datachunk) > 0:
                        while datachunk[-1] != "\0":
                            datachunk += self.conn.recv(8192).decode()
                        self.recv_line(datachunk.replace("\0", ""))
                except OSError:
                    print("OS error in thread communication.")
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


@dataclass(frozen=True)
class WidgetGroup:
    """Widgets to be used in the GUI."""

    dockable_metadata: QDockWidget
    metadata: MetaDataDialog
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


class UIBuilder:
    """
    Create the GUI.

    In particular, widgets, actions, the toolbar, the menu and the final
    layout of the application.

    Parameters
    ----------
    window: MainWindow
        The reference the the main application class.
    """

    def __init__(self, window: "MainWindow"):
        self.window: MainWindow = window
        self.widgets: WidgetGroup = self._create_widgets()
        self.actions: ActionGroup = self._create_actions()
        self.toolbar: QToolBar = self._create_toolbar()
        self._create_menu()
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
        action = QAction(display_name, self.window)
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
        dockable_metadata = QDockWidget("Metadata", self.window)
        metadata = MetaDataDialog()
        dockable_metadata.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        dockable_metadata.setWidget(metadata)
        config_editor = ConfigEditWidget()
        config_editor.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, config_editor)
        config_editor.setFloating(True)
        config_editor.close()
        system_list = SystemListWidget()
        system_list.setMinimumHeight(50)
        system_list.setMaximumHeight(50)
        status_preview = TerminalOutput()
        status_preview.document().setMaximumBlockCount(MAX_LINES_STATUS)
        lsp_name = "pyrefly"
        lsp_binary = find_binary(lsp_name)
        if isinstance(lsp_binary, Error):
            raise lsp_binary.error
        lsp_parameters = ["lsp"]
        lsp_server = LSPServer(binary=str(lsp_binary.value), parameters=lsp_parameters)
        script_edit = CodeEditor([self.window.extension], lsp_server)
        system_command_help = QDialog(self.window)
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
        splitter = QSplitter(self.window)
        central_widget = CentralWidget(self.window)
        python_info = QLabel(f"Python {platform.python_version()}")
        python_info.setToolTip(f"Python: {sys.version}")
        lsp_info = QLabel(f"LSP: {lsp_name}")
        lsp_info.setToolTip(f"{lsp_binary.value}")

        return WidgetGroup(
            dockable_metadata=dockable_metadata,
            metadata=metadata,
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
        )

    def _create_actions(self) -> ActionGroup:
        """
        Create all required actions.

        Returns
        -------
        ActionGroup
            The dataclass with all the actions.
        """
        matrix_settings = QAction("Show matrix toml", self.window)
        matrix_settings.setMenuRole(QAction.MenuRole.PreferencesRole)
        matrix_settings.setShortcut(QKeySequence.StandardKey.Preferences)
        about = QAction("About", self.window)
        about.setMenuRole(QAction.MenuRole.AboutRole)
        config_action = QAction(get_matrix_icon("CHAR_≡"), "Device config", self.window)
        config_action.setToolTip("Show the devices preferences/ configuration.")
        config_action.setCheckable(True)
        new_file = QAction(get_matrix_icon("SP_FileIcon"), "New", self.window)
        new_file.setShortcut(QKeySequence.StandardKey.New)
        load = QAction(get_matrix_icon("SP_DialogOpenButton"), "Open", self.window)
        load.setToolTip("Open a script file.")
        load.setShortcut(QKeySequence.StandardKey.Open)
        save = QAction(get_matrix_icon("SP_DialogSaveButton"), "Save", self.window)
        save.setToolTip("Save the under the current filename.")
        save.setShortcut(QKeySequence.StandardKey.Save)
        save_as = QAction(get_matrix_icon("SP_DialogSaveButton"), "Save As...", self.window)
        save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.widgets.save_button.setDefaultAction(save)
        self.widgets.save_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        save_pulldown = QMenu(self.window)
        save_pulldown.addAction(save_as)
        self.widgets.save_button.setMenu(save_pulldown)
        add_system = QAction(get_matrix_icon("CHAR_+"), "Add System", self.window)
        add_system.setToolTip("Add a matrix system file.")
        remove_system = QAction(get_matrix_icon("CHAR_-"), "Remove System", self.window)
        remove_system.setEnabled(False)
        remove_system.setToolTip("Remove the selected or last matrix system file.")
        quit_app = QAction("Quit", self.window)
        if os.name == "nt":
            quit_app.setShortcut(QKeySequence.StandardKey.Close)
        else:
            quit_app.setShortcut(QKeySequence.StandardKey.Quit)
        undo = self._standard_action("Undo")
        redo = self._standard_action("Redo")
        cut = self._standard_action("Cut")
        copy = self._standard_action("Copy")
        paste = self._standard_action("Paste")
        caption = "Toggle Line Comment\t" + config["shortcuts"]["line_comment_display"]
        line_comment = QAction(caption, self.window)
        line_comment.setShortcut(QKeySequence(config["shortcuts"]["line_comment_shortcut"]))
        zoom_in = self._standard_action("ZoomIn", "Zoom in")
        zoom_out = self._standard_action("ZoomOut", "Zoom Out")
        print_action = QAction("Print", self.window)
        print_action.setShortcut(QKeySequence.StandardKey.Print)
        find = QAction("Find", self.window)
        find.setShortcut(QKeySequence.StandardKey.Find)
        start_pause = QAction(get_matrix_icon("CUSTOM_Play"), "Start", self.window)
        start_pause.setToolTip("Execute the script.")
        start_pause.setCheckable(True)
        stop = QAction(get_matrix_icon("CUSTOM_Stop"), "Stop", self.window)
        stop.setToolTip("Stop the script and query status.")
        stop.setEnabled(False)
        abort = QAction(get_matrix_icon("CUSTOM_Stop"), "Abort", self.window)
        abort.setEnabled(False)
        finish = QAction(get_matrix_icon("CUSTOM_Stop"), "Finish", self.window)
        finish.setEnabled(False)
        self.widgets.stop_button.setDefaultAction(stop)
        self.widgets.stop_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        stop_pulldown = QMenu(self.window)
        stop_pulldown.addAction(abort)
        stop_pulldown.addAction(finish)
        self.widgets.stop_button.setMenu(stop_pulldown)
        kill = QAction(get_matrix_icon("SP_DialogCancelButton"), "Kill", self.window)
        kill.setEnabled(False)
        preview = QAction(
            get_matrix_icon("matr1x-matrix-preview.png", QColor("RoyalBlue")),
            "Preview",
            self.window,
        )
        preview.setEnabled(False)
        pep8 = QAction("Format with ruff", self.window)
        pep8.setShortcut(QKeySequence("Ctrl+8"))
        theme_actions = []
        theme_group = QActionGroup(self.window)
        theme_group.setExclusionPolicy(QActionGroup.ExclusionPolicy.Exclusive)
        for theme in self.widgets.script_edit.supportedThemes():
            action = QAction(theme, self.window)
            action.setCheckable(True)
            if theme == self.widgets.script_edit.supportedThemes()[0]:
                action.setChecked(True)
            action.triggered.connect(
                lambda checked=False, theme=theme: self.widgets.script_edit.setTheme(theme)
            )
            theme_group.addAction(action)
            theme_actions.append(action)
        autocomplete = QAction("Tab completion", self.window)
        autocomplete.setCheckable(True)
        autocomplete.setChecked(True)
        show_log = QAction("Show Log Window", self.window)
        show_log.setCheckable(True)
        toggle_metadata = QAction("Show Metadata", self.window)
        toggle_metadata.setShortcut(QKeySequence("Ctrl+2"))
        toggle_metadata.setCheckable(True)
        toggle_metadata.setChecked(True)
        toggle_toolbar = QAction("Show Toolbar", self.window)
        toggle_toolbar.setShortcut(QKeySequence("Ctrl+1"))
        toggle_toolbar.setCheckable(True)
        toggle_toolbar.setChecked(True)
        system_help = QAction("Show System Help", self.window)

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
        )

    def _create_toolbar(self) -> QToolBar:
        """
        Create the toolbar.

        Returns
        -------
        QToolBar
            The (main) toolbar.
        """
        main_window = self.window
        toolbar = QToolBar("Toolbar")
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        toolbar.setFloatable(False)
        toolbar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        toolbar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea | Qt.ToolBarArea.BottomToolBarArea)
        icon_size = get_application_instance().toolbar_icon_size()
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
        main_window.addToolBar(toolbar)
        return toolbar

    def _create_menu(self) -> None:
        """Create the main menu."""
        menu = self.window.menuBar()
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
        help_menu.addAction(self.actions.about)  # This is auto-moved on a Mac

    def _create_gui(self) -> None:
        """Create and set up the main GUI."""
        self.window.setCentralWidget(self.widgets.central_widget)
        layout = QVBoxLayout(self.widgets.central_widget)
        layout.setSpacing(6)
        layout.setContentsMargins(11, 4, 11, 11)
        self.widgets.splitter.addWidget(self.widgets.script_edit)
        self.widgets.splitter.addWidget(self.widgets.status_preview)
        layout.addWidget(self.widgets.splitter, 1)
        infobar = QHBoxLayout()
        infobar.addStretch()
        infobar.addWidget(self.widgets.python_info)
        infobar.addWidget(QLabel("  |  "))
        infobar.addWidget(self.widgets.lsp_info)
        layout.addLayout(infobar, 0)
        self.window.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self.widgets.dockable_metadata
        )


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
        self.log_window = LoggingWindow(parent=self)  # Immediately needed, not moved to widgets!
        self.log_window.hide()
        logger.info("matrix-script starting")
        self.systems: list[str]
        self.scriptname: Path | None = None
        self.measurement_file: Path
        self.systems_dirty = False
        self.last_loaded_file: Path | None = None
        self.is_running = False
        self.shortcut_dir: tempfile.TemporaryDirectory[str] | None = None
        self.last_filename: Path | None = None
        self.settings = SaferQSettings("matr1x", "script")
        self.output_stream = EmittingStream()
        self.output_stream.text_written.connect(self.output_written)
        self._cached_system_info: SystemInfo | None = None
        self._output_buffer: list[str] = []
        self._output_timer = QTimer()
        self._output_timer.timeout.connect(self._flush_output_buffer)
        self._output_timer.setSingleShot(False)
        self._output_timer.setInterval(50)
        get_application_instance().isDarkSignal.connect(self.update_systems)
        self.setWindowIcon(get_matrix_icon("matr1x-matrix-script.png"))
        self.ui = UIBuilder(self)
        self.create_connections()
        self.ui.widgets.script_edit.setFocus()  # this does not do anything?!
        self.update_window_title()
        check_config(matr1x.config)
        sys.stdout = self.output_stream  # all output (stdout) is written to status preview
        if filename is not None:
            self.load_from_filename(filename)
        self.update_systems()  # in case the load failed just to be sure
        print(help_text)

    def create_connections(self) -> None:
        """Connect actions and widgets with application logic."""
        self.ui.actions.about.triggered.connect(self.info_box)
        self.ui.actions.matrix_settings.triggered.connect(open_matrix_toml)
        self.ui.actions.new_file.triggered.connect(self.new_file)
        self.ui.actions.load.triggered.connect(self.load_from_file)
        self.ui.actions.save.triggered.connect(self.save_file)
        self.ui.actions.save_as.triggered.connect(self.save_file_as)
        self.ui.actions.add_system.triggered.connect(self.add_system)
        self.ui.actions.remove_system.triggered.connect(self.delete_selected_system)
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
        self.ui.actions.show_log.triggered.connect(self.toggle_log_window)
        self.ui.widgets.config_editor.visibilityChanged.connect(self.ui.actions.config.setChecked)
        self.ui.widgets.dockable_metadata.visibilityChanged.connect(
            self.ui.actions.toggle_metadata.setChecked
        )
        self.ui.toolbar.visibilityChanged.connect(self.ui.actions.toggle_toolbar.setChecked)
        self.ui.widgets.script_edit.contentModified.connect(self.update_window_title)
        self.ui.widgets.script_edit.file_dropped.connect(self._load_file_from_signal)
        self.ui.widgets.system_list.orderChanged.connect(self.update_systems)
        self.ui.widgets.central_widget.file_dropped.connect(self._load_file_from_signal)
        self.log_window.visibility_changed.connect(self._on_log_window_visibility_changed)

    def print_colored(self, line: str) -> None:
        """
        Print a colored text.

        Afterwards, recover the original text color. Follow theme
        changes.

        Parameters
        ----------
        line : str
            The line to be printed.
        """
        cursor = self.ui.widgets.status_preview.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        emphasize = QTextCharFormat()
        emphasize.setForeground(QColor("royalblue"))
        cursor.insertText(line, emphasize)
        cursor.insertText("\n", QTextCharFormat())

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
        self.settings.beginGroup("MainWindow")
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter", self.ui.widgets.splitter.sizes())
        self.settings.endGroup()
        self.settings.beginGroup("script_edit")
        self.settings.setValue("size", self.ui.widgets.script_edit.size())
        self.settings.setValue("monaco_zoom", self.ui.widgets.script_edit.zoomFactor())
        self.settings.setValue("theme", self.ui.actions.theme_group.checkedAction().text())
        self.settings.setValue("autocomplete", self.ui.actions.autocomplete.isChecked())
        self.settings.endGroup()
        self.settings.beginGroup("status_preview")
        self.settings.setValue("size", self.ui.widgets.status_preview.size())
        self.settings.endGroup()
        self.settings.beginGroup("Toolbars")
        self.settings.setValue("buttons_visible", self.ui.toolbar.isVisible())
        self.settings.setValue("position", self.toolBarArea(self.ui.toolbar).value)
        self.settings.setValue("buttons_geometry", self.ui.toolbar.geometry())
        self.settings.endGroup()
        self.settings.beginGroup("dockable_metadata")
        self.settings.setValue("visible", self.ui.widgets.dockable_metadata.isVisible())
        self.settings.setValue(
            "dock_position", self.dockWidgetArea(self.ui.widgets.dockable_metadata).value
        )
        self.settings.setValue("floating", self.ui.widgets.dockable_metadata.isFloating())
        self.settings.setValue("position", self.ui.widgets.dockable_metadata.pos())
        self.settings.setValue("size", self.ui.widgets.dockable_metadata.size())
        self.settings.endGroup()
        self.settings.beginGroup("config_editor")
        self.settings.setValue("position", self.ui.widgets.config_editor.pos())
        self.settings.setValue("size", self.ui.widgets.config_editor.size())
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

    def restore_window_state(self) -> None:
        """Restore app configuration from the previous use."""
        self.resize(self.sizeHint())  # Just in case it is the first start
        self.settings.beginGroup("MainWindow")
        self.restoreGeometry(self.settings.safer_value("geometry", QByteArray(), type=QByteArray))
        self.ui.widgets.splitter.setSizes(
            [
                int(size)
                for size in self.settings.safer_value(
                    "splitter", self.ui.widgets.splitter.sizes(), type=list
                )
            ]
        )
        self.settings.endGroup()
        # Check if there is a settings file. This improves the robustness
        # against strange side effect, caused by the default values.
        if self.settings.contains("created"):
            self.settings.beginGroup("script_edit")
            self.ui.widgets.script_edit.resize(
                self.settings.safer_value("size", self.ui.widgets.script_edit.size(), type=QSize)
            )
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
            self.settings.beginGroup("status_preview")
            self.ui.widgets.status_preview.resize(
                self.settings.safer_value(
                    "size", self.ui.widgets.status_preview.size(), type=QSize
                )
            )
            self.settings.endGroup()
            self.settings.beginGroup("Toolbars")
            self.ui.toolbar.setVisible(
                self.settings.safer_value("buttons_visible", True, type=bool)
            )
            self.ui.actions.toggle_toolbar.setChecked(
                self.settings.safer_value("buttons_visible", True, type=bool)
            )
            toolbar_pos = self.settings.safer_value(
                "position", Qt.ToolBarArea.TopToolBarArea.value, type=int
            )
            self.addToolBar(Qt.ToolBarArea(toolbar_pos), self.ui.toolbar)
            self.settings.endGroup()
            self.settings.beginGroup("dockable_metadata")
            visible = self.settings.safer_value("visible", True, type=bool)
            self.ui.widgets.dockable_metadata.setVisible(visible)
            self.ui.actions.toggle_metadata.setChecked(visible)
            dock_pos = self.settings.safer_value(
                "dock_position", Qt.DockWidgetArea.RightDockWidgetArea.value, type=int
            )
            self.addDockWidget(Qt.DockWidgetArea(dock_pos), self.ui.widgets.dockable_metadata)
            self.ui.widgets.dockable_metadata.setFloating(
                self.settings.safer_value("floating", False, type=bool)
            )
            if self.ui.widgets.dockable_metadata.isFloating():
                self.ui.widgets.dockable_metadata.move(
                    self.settings.safer_value(
                        "position", self.ui.widgets.dockable_metadata.pos(), type=QPoint
                    )
                )
                self.ui.widgets.dockable_metadata.resize(
                    self.settings.safer_value(
                        "size", self.ui.widgets.dockable_metadata.size(), type=QSize
                    )
                )
            else:
                self.resizeDocks(
                    [self.ui.widgets.dockable_metadata],
                    [
                        self.settings.safer_value(
                            "size", self.ui.widgets.dockable_metadata.size(), type=QSize
                        ).width()
                    ],
                    Qt.Orientation.Horizontal,
                )
            self.settings.endGroup()
            self.settings.beginGroup("config_editor")
            self.ui.widgets.config_editor.move(
                self.settings.safer_value(
                    "position", self.ui.widgets.config_editor.pos(), type=QPoint
                )
            )
            self.ui.widgets.config_editor.resize(
                self.settings.safer_value("size", self.ui.widgets.config_editor.size(), type=QSize)
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
                self.delete_selected_system()
            if detect_shortcut(event, QKeySequence(Qt.Key.Key_Backspace)):
                self.delete_selected_system()
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
        if self.systems_dirty and self.scriptname is not None:
            # if no file is given, nothing is saved
            self.update_systems(update_config=False)
            newscript = self.generate_save_content()
            with Path(self.scriptname).open() as f:
                saved_text = f.read()
                if saved_text == newscript:
                    self.systems_dirty = False

        if (
            self.ui.widgets.script_edit.isModified() or self.systems_dirty
        ) and self.ui.widgets.script_edit.toPlainText() != "":
            qApp = get_application_instance()
            qApp.processEvents()
            ret = save_messagebox(self)
            if ret == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if ret == QMessageBox.StandardButton.Save:
                # save the file
                if -1 == self.save_file():
                    # if save fails, ignore message
                    event.ignore()
                    return
        self.save_window_state()
        self.ui.widgets.script_edit.server.stop()
        # QWebEngineView: Disconnect the webpage to prevent memory leaks
        if hasattr(self.ui.widgets.script_edit, "page") and self.ui.widgets.script_edit.page():
            self.ui.widgets.script_edit.page().loadFinished.disconnect()
            self.ui.widgets.script_edit.page().deleteLater()
        self.ui.widgets.script_edit.deleteLater()
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.log_window.log_handler)
        self.log_window.deleteLater()
        qApp = get_application_instance()
        qApp.processEvents()
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

    def toggle_log_window(self) -> None:
        """Toggle the visibility of the logging window."""
        if self.log_window.isVisible():
            self.log_window.hide()
        else:
            self.log_window.show()
            self.log_window.raise_()
            self.log_window.activateWindow()

    def _on_log_window_visibility_changed(self, visible: bool) -> None:
        """Keep the log-window action in sync with the window state."""
        self.ui.actions.show_log.setChecked(visible)
        self.ui.actions.show_log.setText("Hide Log Window" if visible else "Show Log Window")

    def _load_file_from_signal(self, filename: str) -> None:
        """Convert string to Path for opening file."""
        self.load_from_filename(Path(filename))

    def update_window_title(self) -> None:
        """Indicate if the file was edited with an asterisk."""
        text = "Matrix Script"
        if self.ui.widgets.script_edit.isModified() or self.systems_dirty:
            text += ": *"
        elif self.scriptname:
            text += ": "
        if self.scriptname:
            text += self.scriptname.name
        elif self.ui.widgets.script_edit.isModified() or self.systems_dirty:
            text += "<unsaved>"
        self.setWindowTitle(text)
        lsp_name = self.scriptname.name if self.scriptname else None
        self.ui.widgets.script_edit.setFilename(lsp_name)

    def add_system(self) -> None:
        """
        Add a system file to the system list.

        Opens a QFileDialog with filter system*.py. Update help if need
        be.
        """
        directory = matr1x.system_directories[-1]
        if not self.shortcut_dir and len(matr1x.system_names) > 1:
            self.shortcut_dir = create_temp_dir_with_symlinks(
                matr1x.system_names, matr1x.system_directories
            )
        if self.shortcut_dir:
            directory = Path(self.shortcut_dir.name) / matr1x.system_names[-1]
        if self.last_loaded_file:
            directory = self.last_loaded_file.parent
        # get filenames from dialog
        filenames = QFileDialog.getOpenFileNames(
            self, "Select system file to add", str(directory), "system files (system*.py)"
        )[0]
        if filenames == []:
            return
        for filename in filenames:
            self.last_loaded_file = Path(filename)
            filename = str(Path(filename).resolve())
            module_name = get_importable_module_name(filename)
            if module_name:
                self.ui.widgets.system_list.addItem(module_name)
            else:
                self.ui.widgets.system_list.addItem(filename)
        self.ui.actions.remove_system.setEnabled(True)
        self.systems_dirty = True
        self.update_window_title()
        self.update_systems()
        if self.ui.widgets.system_command_help.isVisible():
            self.show_system_commands()

    def delete_selected_system(self) -> None:
        """
        Remove selected system from system_list.

        If no selection is active the last system will be removed.
        Update help if need be.
        """
        selected = self.ui.widgets.system_list.selectedItems()
        if len(selected) > 0:
            self.ui.widgets.system_list.takeItem(self.ui.widgets.system_list.row(selected[0]))
        elif 0 < self.ui.widgets.system_list.count():
            self.ui.widgets.system_list.takeItem(self.ui.widgets.system_list.count() - 1)
        if self.ui.widgets.system_list.count() == 0:
            self.ui.actions.remove_system.setEnabled(False)
        self.systems_dirty = True
        self.update_window_title()
        self.update_systems()
        if self.ui.widgets.system_command_help.isVisible():
            self.show_system_commands()

    @Slot(InputParameters)
    def get_script_input(self, params: InputParameters):
        """
        Open a dialog and forward input to the script.

        Parameters
        ----------
        params: InputParameters
            Object containing all input parameters including query,
            input_type, timeout, default_value, min_value, max_value,
            step, and decimals.
        """
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
                print(
                    f"Warning: Invalid default_value '{params.default_value}' "
                    "for numerical input. Using 0.0"
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
            dialog = TerminationDialog()
            ret = dialog.get_selection()
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
        self.print_colored("Script terminated by user - file integrity might be compromised")

    def update_system_commands(self) -> None:
        """Update the help info about the current system(s)."""
        if len(self.systems) == 0:
            text = "<p style='margin: 20px;'><b>No system file selected!</b></p>"
            text += "<p style='margin: 20px;'>"
            text += "Please add a system file using the 'Add System' button or File menu.</p>"
            text += "<p style='margin: 20px;'>"
            text += "Once a system is loaded, this dialog will show information about:</p>"
            text += "<ul style='margin-left: 40px;'>"
            text += "<li>Available parameters that can be set or read</li>"
            text += "<li>Connected devices and their configurations</li>"
            text += "<li>System methods and variables</li>"
            text += "</ul>"
            self.ui.widgets.system_command_text_edit.setText(text)
            return
        system_info = self._cached_system_info
        if system_info is None:
            self.ui.widgets.system_command_text_edit.setText("Could not parse the system file(s)!")
            return
        text = "The following systems were selected:<br><b>"
        for system in self.systems:
            text = text + system + "<br>"
        text += "<br></b>These systems provide the following:<br>"
        bg_color = "#565656" if get_application_instance().isDark else "#f0f0f0"
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

    def output_written(self, text: str) -> None:
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

        if "\r" not in combined_text:
            self.ui.widgets.status_preview.appendPlainText(combined_text)
        else:
            # operate on a disposable cursor so we do not move the user's cursor/selection
            doc = self.ui.widgets.status_preview.document()
            cursor = QTextCursor(doc)
            cursor.movePosition(QTextCursor.MoveOperation.End)
            for char in combined_text:
                if char == "\r":
                    cursor.movePosition(
                        QTextCursor.MoveOperation.StartOfBlock,
                        QTextCursor.MoveMode.KeepAnchor,
                    )
                    cursor.removeSelectedText()
                else:
                    cursor.insertText(char)

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
        self.ui.widgets.metadata.setEnabled(not flag)

    def process_finished(self) -> None:
        """
        Handle GUI changes and clean up thread after it has finished.

        Return buttons to original state, delete the finished process.
        """
        self.enable_buttons(False)
        self.print_colored("\nExecution finished")
        del self.measurement_thread

    def run_linter(self) -> int:
        """
        Call the linter for the editor view.

        Returns
        -------
        int
            The number of issues.
        """
        self.ui.widgets.script_edit.setSettables(self._cached_system_info)
        return self.ui.widgets.script_edit.returnIssues()

    def start_process(self) -> None:
        """
        Start the matrix_script process.

        Disable/enable buttons to reflect run state and get selected
        systems. Then runs the script defined in the edit.
        """
        if 0 == len(self.systems):
            self.ui.actions.start_pause.setChecked(False)
            self.print_colored("No system selected")
            return
        if self.run_linter() > 0:  # run linter to make sure there are no errors
            self.print_colored("Script execution was halted because of linter errors")
            get_application_instance().processEvents()
            a = QMessageBox(parent=self)  # open a popup window to inform about the error
            a.setText("Linter error")
            a.setInformativeText("Error found in script, continue anyway?")
            a.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            a.setDefaultButton(QMessageBox.StandardButton.Ok)
            ret = a.exec()
            if ret == QMessageBox.StandardButton.Cancel:
                self.ui.actions.start_pause.setChecked(False)
                return
        self.print_colored("### Running script now")
        user_script = self.ui.widgets.script_edit.toPlainText()
        script = generate_script(user_script)
        meta_data = self.ui.widgets.metadata.get_metadata()
        temp_config = self.ui.widgets.config_editor.write_config()
        self.measurement_thread = ScriptThread(
            meta_data, script, self.scriptname, temp_config, self.systems
        )
        self.measurement_thread.lineno_signal.connect(self.ui.widgets.script_edit.highlight)
        self.measurement_thread.input_signal.connect(self.get_script_input)
        self.measurement_thread.filename_signal.connect(self.update_filename)
        self.measurement_thread.finished.connect(self.process_finished)
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
        self.systems = [
            # use normpath here since there is no pathlib equivalent
            normpath(self.ui.widgets.system_list.item(j).text())
            for j in range(self.ui.widgets.system_list.count())
        ]
        system_info = get_system_info(self.systems)
        if isinstance(system_info, Error):
            print(system_info.error)
            self._cached_system_info = None
        else:
            self._cached_system_info = system_info.value
        # only systems that are part of matrix or ifwlib can be configured via files
        configurable = [system for system in self.systems if not Path(system).exists()]
        matr1x.reload_config()
        if update_config:
            self.ui.widgets.config_editor.set_systemfile(configurable)
            self.ui.widgets.config_editor.set_full_system_list(self.systems)
            self.ui.widgets.config_editor.set_system_info(self._cached_system_info)
            self.ui.widgets.config_editor.update_data()
        # Update system commands with cached info
        self.update_system_commands()
        self.run_linter()

    def _extract_settable_info(
        self, system_info: SystemInfo
    ) -> tuple[list[int], list[str], list[str]]:
        """
        Extract settable information from system info.

        Parameters
        ----------
        system_info: SystemInfo
            The system info object with the parameters to evaluate.
        """
        indexes = []
        columns = []
        units = []
        for parameter in system_info.parameters.values():
            if ", " in parameter.name:
                name_parts = [name.strip() for name in parameter.name.split(", ")]
                unit_parts = [unit.strip() for unit in parameter.unit.split(", ")]
                for name, unit in zip(name_parts, unit_parts):
                    indexes.append(parameter.index)
                    columns.append(name)
                    units.append(unit)
            else:
                indexes.append(parameter.index)
                columns.append(parameter.name)
                units.append(parameter.unit)

        return (indexes, columns, units)

    def save_file_as(self) -> int:
        """
        Ask for the filename and calls write_file().

        Returns
        -------
        int
            0 (Sucess) or -1 (Error).
        """
        filename = QFileDialog.getSaveFileName(
            self,
            "Specify filename to save",
            str(matr1x.usersfolder if not self.scriptname else Path(self.scriptname).parent),
            f"matrix files (*{self.extension})",
        )
        filename = Path(filename[0])
        if filename == Path():
            return -1
        else:
            return self.write_file(filename)

    def save_file(self) -> int:
        """
        Try to save under the last name and call write_file().

        If no last filename exists calls save_file_as().

        Returns
        -------
        int
            0 (Sucess) or -1 (Error).
        """
        if not self.last_filename:
            return self.save_file_as()
        else:
            return self.write_file(self.last_filename)

    def write_file(self, filename: Path) -> int:
        """
        Save script to file and write system information to header.

        Returns
        -------
        int
            0 (Sucess) or -1 (Error).
        """
        if filename.suffix != self.extension:
            filename = filename.with_suffix(self.extension)
        try:
            output_file = filename.open("w")
        except OSError:
            self.print_colored("File cannot be opened")
            return -1
        self.scriptname = filename
        self.update_systems(update_config=False)
        # set new script in editor and save it to the file
        newscript = self.generate_save_content()
        self.ui.widgets.script_edit.setPlainText(newscript)
        output_file.write(newscript)
        output_file.close()
        self.last_filename = filename
        self.ui.widgets.script_edit.setModified(False)
        self.systems_dirty = False
        self.update_window_title()
        return 0

    def generate_save_content(self) -> str:
        """
        Add the systems in the header of a script.

        Returns
        -------
        str
            The script including the generated header.
        """
        header = ""
        system_info = self._cached_system_info
        if 0 < len(self.systems):
            # only attempt generating a header if a system is selected
            try:
                # get settable information to put into the header
                # (columns/units)
                settable_info = (
                    self._extract_settable_info(system_info) if system_info is not None else None
                )

                if settable_info is not None and len(settable_info) >= 3:
                    # write matrix file header
                    header += (
                        "# system def : "
                        + ",".join(repr(s).strip("'") for s in self.systems)
                        + "\n"
                    )

                    # Extract column names and units from settable_info
                    # settable_info = (indexes, columns, units)
                    column_names = [str(col).strip() for col in settable_info[1]]
                    units = [str(unit).strip() for unit in settable_info[2]]

                    header += "# system names : " + ",".join(column_names) + "\n"
                    header += "# system units : " + ",".join(units) + "\n"
                    header += "# file v8, time stamp : " + time.strftime(
                        f"{matr1x.datetimefmt}\n", time.localtime()
                    )
                else:
                    self.print_colored(
                        "warning: settable_info is incomplete, creating basic header"
                    )
                    header += (
                        "# system def : "
                        + ",".join(repr(s).strip("'") for s in self.systems)
                        + "\n"
                    )
                    header += "# file v8, time stamp : " + time.strftime(
                        f"{matr1x.datetimefmt}\n", time.localtime()
                    )
            except Exception as e:
                self.print_colored(
                    f"error in generating settable_info from file: {e}, telemetry "
                    "header could not be generated"
                )
        # take out script and remove trailling newlines
        script = self.ui.widgets.script_edit.toPlainText().rstrip()
        newscript = header
        for i, line in enumerate(script.splitlines()):
            if i < 4 and (line.startswith("# system ") or line.startswith("# file v")):
                # if there are already definitions of the system, skip them
                continue
            newscript += line + "\n"
        return newscript

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
            self.print_colored("File cannot be opened")
            return
        self.scriptname = filename
        code = ""
        self.ui.widgets.system_list.clear()
        settable_info = None
        #
        # system files
        #
        line = input_file.readline()
        if "# system def : " in line:
            # load system from definition in file
            system_line = line.replace("# system def : ", "").strip()
            for syst in system_line.split(","):
                try:
                    self.ui.widgets.system_list.addItem(syst)
                    self.update_systems()
                    settable_info = (
                        self._extract_settable_info(self._cached_system_info)
                        if self._cached_system_info is not None
                        else None
                    )
                except KeyError:
                    self.print_colored(
                        "System that was used to generate the "
                        "script was not found in installed systems."
                        " Please check .matrix.conf file."
                    )
                    return
        else:
            self.print_colored("No system defined in script, please choose system(s)")
        code += line
        #
        # system columns definiton
        #
        line = input_file.readline()
        code += line
        # make sure that system column definition agrees with
        # current system
        if "# system names : " in line and settable_info is not None and len(settable_info) >= 2:
            system_names = line.strip().replace("# system names : ", "")
            current_columns = [str(col).strip() for col in settable_info[1]]
            # Handle both "," and ", " as separators since compound columns use ", "
            loaded_columns = []
            for col in system_names.split(","):
                col = col.strip()
                if col:
                    loaded_columns.append(col)
            if current_columns != loaded_columns:
                self.print_colored(
                    "Column names have changed between generation "
                    "of script and now, please make sure that "
                    "columns are set correctly before running the "
                    "script"
                )
        else:
            self.print_colored(
                "Could not verify column names, please verify that columns have not changed"
            )
        #
        # system unit definiton
        #
        line = input_file.readline()
        code += line
        # make sure that system unit definition agrees with
        # current system
        if "# system units : " in line and settable_info is not None and len(settable_info) >= 3:
            system_units = line.strip().replace("# system units : ", "")
            current_units = [str(unit).strip() for unit in settable_info[2]]
            # Handle both "," and ", " as separators since compound columns use ", "
            loaded_units = []
            for unit in system_units.split(","):
                loaded_units.append(unit.strip())
            if current_units != loaded_units:
                self.print_colored(
                    "Column units have changed between generation "
                    "of script and now, please make sure that "
                    "columns are set correctly before running the "
                    "script"
                )
        else:
            self.print_colored(
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
        self.systems_dirty = False
        self.last_filename = filename
        self.update_window_title()
        if self.ui.widgets.system_list.count() > 0:
            self.ui.actions.remove_system.setEnabled(True)

    def load_from_file(self) -> None:
        """Open file dialog and call load_from_filename."""
        # First, check if unsaved changes exist
        if self.ui.widgets.script_edit.isModified() or self.systems_dirty:
            qApp = get_application_instance()
            qApp.processEvents()
            ret = save_messagebox(self)
            if ret == QMessageBox.StandardButton.Cancel:
                return
            if ret == QMessageBox.StandardButton.Save:
                saved = self.save_file()
                if saved == -1:
                    return
        # Now, proceed opeing the file
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
        """
        Start over with a blank script.

        Ask the user to write unsaved changes to a file, remove the
        'system dirty' flag and forget last filename.
        """
        if self.ui.widgets.script_edit.isModified() or self.systems_dirty:
            get_application_instance().processEvents()
            ret = save_messagebox(self)
            if ret == QMessageBox.StandardButton.Cancel:
                return
            if ret == QMessageBox.StandardButton.Save:
                saved = self.save_file()
                if saved == -1:
                    return
        self.systems_dirty = False
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
    with QtGracefulKiller():
        ex = MainWindow(filename=Path(sys.argv[1]) if len(sys.argv) >= 2 else None)
        if config["duplicate_output_to_logfile"]:
            sys.stdout = OutputDuplication(sys.stdout, prefix=appname)
            sys.stderr = OutputDuplication(sys.stderr, prefix=appname, fallbackname="stderr")
        ex.show()
        protected_restore(ex.restore_window_state)
        # handle MacOS specific FileOpenEvent from MApplication
        app.connect_file_handler(ex._load_file_from_signal)
        ret = app.exec()
    if config["duplicate_output_to_logfile"]:
        sys.stdout.close()
        sys.stderr.close()
    sys.stderr = sys.__stderr__
    sys.stdout = sys.__stdout__
    sys.exit(ret)
