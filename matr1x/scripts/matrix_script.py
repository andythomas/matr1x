# This file is part of a software collection for data acquisition (matr1x).
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
"""Allow to write measurement scripts in Python."""

import logging
import os
import re
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
from os.path import normpath
from pathlib import Path

import monaco_assets
from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QPoint,
    QSize,
    Qt,
    QThread,
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
    QMainWindow,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import matr1x
from matr1x.control.util import QtGracefulKiller
from matr1x.editor import CodeEditor
from matr1x.error_handling import install_error_handler
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
from matr1x.util import (
    create_temp_dir_with_symlinks,
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


class CentralWidget(FileDropMixin, QWidget):
    """Enable drag and drop of matrix files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setValidExtensions([MainWindow.extension])


class TerminalOutput(QTextEdit):
    """Custom class for terminal-like text output."""

    def __init__(self) -> None:
        """Init the class with a mono-spaced font and respect theme."""
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
        text_edit = QTextEdit()
        text_edit.setEnabled(False)
        changed_palette = text_edit.palette()
        palette.setColor(
            QPalette.ColorRole.Base,
            QColor(changed_palette.color(QPalette.ColorRole.Base)),
        )
        self.setPalette(palette)

    def changeEvent(self, event) -> None:
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


class ScriptThread(QThread):
    """Control and the thread running the measurements."""

    # signal initiating user input from the GUI.
    # Signature: query (str),
    #            input_type (str),
    #            timeout (float),
    #            default_value (str),
    #            min_value (object, float or None),
    #            max_value (object, float or None),
    #            step (object, float or None),
    #            decimals (object, int or None)
    input_signal = Signal(str, str, float, str, object, object, object, object)
    # signal to report the currently executing line number to the editor.
    lineno_signal = Signal(int)
    # signal to report the filename of the file that is written by the process
    filename_signal = Signal(str)

    def __init__(
        self,
        meta_data: dict,
        script: str,
        fallbackname: Path | None,
        temp_config: Path,
        systems: list,
    ):
        """
        Initialize thread that handles script execution.

        Parameters
        ----------
        meta_data : dict
            dictionary containing meta data such as user and comment
        script : str
            user script that is supposed to be run by the ScriptThread.
        fallbackname : Path | str
            filename used to initialize the data file if not specified
            in the script. Its directory path will be used as execution
            directory.
        temp_config : Path
            temporary configuration file path
        systems : list
            list of system files to load
        """
        super().__init__()
        self.proc = None
        self.conn = None
        self.meta_data = meta_data
        self.script = script
        self.datafilefallback = str(fallbackname) if fallbackname else ""
        self.temp_config = temp_config
        self.systems = systems

    def pass_input(self, inp):
        """Communicate user input to the subprocess."""
        if self.proc is None or self.conn is None:
            return
        if len(inp) < 1 or inp[-1] != "\n":
            # input needs to have terminating character
            inp += "\n"
        self.conn.send(("i" + inp).encode("utf-8"))

    def pause(self):
        """Communicate pause to the subprocess."""
        if self.proc is None or self.conn is None:
            return
        self.conn.send(b"p")

    def abort(self, char="q"):
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

    def kill(self):
        """Kill the process and make sure it is indeed stopped."""
        if self.proc is None or self.conn is None:
            return
        pid = self.proc.pid
        # terminate thread
        self.proc.terminate()
        # if thread is still alive, kill it
        try:
            os.kill(pid, 0)
            self.proc.kill()
            print("force killed thread")
            print("please verify all devices are operational before starting", "another script")
        except OSError:
            # this will likely not happen
            print("thread terminated gracefully")

    def recv_line(self, inp):
        """
        Receive a line from the input and handles it accordingly.

        From inp the current executing line or an input request are attemped
        to find, all other input is printed.

        TODO: not tolerant against split strings, i.e. if sent string
        is longer than 1024, one can expect a problematic behavior. Migrate
        to ZMQ and directly pass strings as python objects?
        """
        pattern_lineno = r"__lineno(-?\d+)__"
        pattern_filename = r"__//(.*)//__"
        # Format:
        # __input_type:message:timeout:default:min:max:step:decimals__
        # (trailing parameters are optional)
        # Regex to capture
        # type, message, timeout, default, min, max, step, decimals
        # Handles empty optional fields correctly
        # (e.g., :: means empty field)
        pattern_input = r"__input_(?P<type>[^:]+):(?P<strlabel>[^:]+)(?::(?P<timeout>[^:]*))?(?::(?P<default>[^:]*))?"  # noqa: E501
        pattern_input += r"(?::(?P<min>[^:]*))?(?::(?P<max>[^:]*))?(?::(?P<step>[^:]*))?(?::(?P<decimals>[^:]*))?__"  # noqa: E501
        lines = inp.split(os.linesep)
        for i, line in enumerate(lines[:-1]):
            # add \"\\n\" to all but the last element in split
            # (last element contains everything after last "\n")
            lines[i] += "\n"
        for line in lines:
            if match := re.search(pattern_lineno, line):
                digits = int(match.group(1))
                if digits >= 0:
                    self.lineno_signal.emit(digits)
                line = re.sub(pattern_lineno, "", line)
            if match := re.search(pattern_input, line):
                input_type = match.group("type")
                strlabel = match.group("strlabel")
                # convert back %0A to newline (URL-encoding)
                strlabel = strlabel.replace("%0A", "\n")

                default_value = ""  # Default for string/bool
                timeout = float("inf")
                min_value = None
                max_value = None
                step = None
                decimals = None

                # Parse timeout
                timeout_str = match.group("timeout")
                if timeout_str:
                    try:
                        timeout = float(timeout_str)
                    except ValueError:
                        print(f"Warning: Invalid timeout value received: {timeout_str}")
                        timeout = float("inf")  # Use default on error

                # Parse default value (depends on input_type, handle
                # as string initially)
                default_str = match.group("default")
                if (
                    default_str is not None
                ):  # match.group returns None if group wasn\'t in the match
                    default_value = default_str  # Keep as string for emitting

                # Parse numerical specific parameters if type is 'numerical'
                if input_type == "numerical":
                    min_str = match.group("min")
                    if min_str:
                        try:
                            min_value = float(min_str)
                        except ValueError:
                            print(f"Warning: Invalid min value received: {min_str}")
                            min_value = None  # Use default (None) on error

                    max_str = match.group("max")
                    if max_str:
                        try:
                            max_value = float(max_str)
                        except ValueError:
                            print(f"Warning: Invalid max value received: {max_str}")
                            max_value = None  # Use default (None) on error

                    step_str = match.group("step")
                    if step_str:
                        try:
                            step = float(step_str)
                        except ValueError:
                            print(f"Warning: Invalid step value received: {step_str}")
                            step = None  # Use default (None) on error

                    decimals_str = match.group("decimals")
                    if decimals_str:
                        try:
                            decimals = int(decimals_str)
                        except ValueError:
                            print(f"Warning: Invalid decimals value received: {decimals_str}")
                            decimals = None  # Use default (None) on error

                logger.info(
                    "Requesting input type: %s, Query: %s, Timeout: %g, Default: %s, Min: %s, "
                    "Max: %s, Step: %s",
                    input_type,
                    strlabel,
                    timeout,
                    default_value,
                    min_value,
                    max_value,
                    step,
                )

                # Emit the signal with all parameters
                self.input_signal.emit(
                    strlabel,
                    input_type,
                    timeout,
                    default_value,
                    min_value,
                    max_value,
                    step,
                    decimals,
                )

                line = re.sub(pattern_input, "", line)
            if match := re.search(pattern_filename, line):
                path = match.group(1)
                self.filename_signal.emit(path)
                line = re.sub(pattern_filename, "", line)
            if line != "":
                print(line, end="")

    def run(self):
        """
        Run the subprocess.

        first writes the user script into a temporary file to make sure
        all formating is conserved, then passes that file to the
        interpreter to run the script the purpose of using a subprocess
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
                    print("OS error in thread communication")
            self.conn.close()
            # clean up temporary config
            self.temp_config.unlink()


class MainWindow(QMainWindow):
    """Define layout, runs everything."""

    extension = ".matrix"

    def __init__(self, filename: Path | None = None):
        """Initialize the GUI for scripted matrix control."""
        super().__init__()
        self.log_window = LoggingWindow(parent=self)
        self.log_window.hide()
        logger.info("matrix-script starting")
        self.systems = []
        self.scriptname: Path | None = None
        self.measurement_file: Path
        self.systems_dirty = False
        self.last_loaded_file: Path | None = None
        self.is_running = False
        self.shortcut_dir = None
        self.last_filename: Path | None = None
        self.settings = SaferQSettings("matr1x", "script")
        self.output_stream = EmittingStream()
        self.output_stream.text_written.connect(self.output_written)

        self.server = monaco_assets.MonacoServer(port=54529)
        timeout = 20  # seconds
        start_time = time.time()
        while not self.server.is_running() and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        if not self.server.is_running():
            logger.error("Warning: Monaco server did not start within %d seconds", timeout)

        self.init_ui()
        # set outputStream as stdout (i.e. all output is written to status
        # preview
        sys.stdout = self.output_stream
        # If filename is passed when matrix-script is started, start
        # by loading the file
        if filename is not None:
            self.load_from_filename(filename)

    def print_colored(self, line: str) -> None:
        """
        Print a colored text.

        Afterwards, recover the original text color and follow theme changes.

        Parameters
        ----------
        line : str
            The line to be printed.
        """
        cursor = self.status_preview.textCursor()
        error_format = QTextCharFormat()
        # Royal Blue is one of the few colors that works in dark and light modes.
        error_format.setForeground(QColor("royalblue"))
        cursor.setCharFormat(error_format)
        cursor.insertText(line)
        default_format = QTextCharFormat()
        cursor.setCharFormat(default_format)
        cursor.insertText("\n")

    def print_document(self) -> None:
        """Print the script."""
        # go via QTextEdit functions for better portability
        text_edit = QTextEdit()
        text_edit.setText(self.script_edit.toPlainText())
        printer = QPrinter()
        print_dialog = QPrintDialog(printer, self)
        if print_dialog.exec():
            text_edit.print_(printer)
        del text_edit

    def save_window_state(self) -> None:
        """
        Save application configuration until next startup.

        For convenience, main window geometry, the toolbar placement,
        and the size and position of metadata and configuration pane are
        saved.
        """
        self.settings.setValue("created", 1)
        self.settings.beginGroup("MainWindow")
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter", self.splitter.sizes())
        self.settings.endGroup()

        self.settings.beginGroup("script_edit")
        self.settings.setValue("size", self.script_edit.size())
        self.settings.setValue("monaco_zoom", self.script_edit.zoomFactor())
        self.settings.setValue("theme", self.theme_group.checkedAction().text())
        self.settings.setValue("autocomplete", self.autocomplete_action.isChecked())
        self.settings.endGroup()

        self.settings.beginGroup("status_preview")
        self.settings.setValue("size", self.status_preview.size())
        self.settings.endGroup()

        self.settings.beginGroup("Toolbars")
        self.settings.setValue("buttons_visible", self.toolbar.isVisible())
        self.settings.setValue("position", self.toolBarArea(self.toolbar).value)
        self.settings.setValue("buttons_geometry", self.toolbar.geometry())
        self.settings.endGroup()

        self.settings.beginGroup("dockable_metadata")
        self.settings.setValue("visible", self.dockable_metadata.isVisible())
        self.settings.setValue("dock_position", self.dockWidgetArea(self.dockable_metadata).value)
        self.settings.setValue("floating", self.dockable_metadata.isFloating())
        self.settings.setValue("position", self.dockable_metadata.pos())
        self.settings.setValue("size", self.dockable_metadata.size())
        self.settings.endGroup()

        self.settings.beginGroup("config_editor")
        self.settings.setValue("position", self.config_editor.pos())
        self.settings.setValue("size", self.config_editor.size())
        self.settings.endGroup()

        self.settings.setValue("log_window/position", self.log_window.pos())
        self.settings.setValue("log_window/size", self.log_window.size())

        # Only save help dialog size and position if it has been shown at least once
        if hasattr(self, "_help_dialog_shown") and self._help_dialog_shown:
            self.settings.beginGroup("system_command_help")
            self.settings.setValue("size", self.system_command_help.size())
            self.settings.setValue("position", self.system_command_help.pos())
            self.settings.endGroup()

    def restore_window_state(self) -> None:
        """
        Restore application configuration to look similar to the previous use.

        Main window geometry, the toolbar placement, and the size and
        position of metadata and configuration pane are restored.
        """
        # Just in case it is the first start
        self.resize(self.sizeHint())
        self.settings.beginGroup("MainWindow")
        self.restoreGeometry(self.settings.safer_value("geometry", QByteArray(), type=QByteArray))
        self.splitter.setSizes(
            [
                int(size)
                for size in self.settings.safer_value("splitter", self.splitter.sizes(), type=list)
            ]
        )
        self.settings.endGroup()
        # Check if there is a settings file. This improves the robustness
        # against strange side effect, caused by the default values. The default
        # values are still required to ensure compatibilty in case the saved
        # settings are changed.
        if self.settings.contains("created"):
            self.settings.beginGroup("script_edit")
            self.script_edit.resize(
                self.settings.safer_value("size", self.script_edit.size(), type=QSize)
            )
            self.script_edit.setZoomFactor(self.settings.safer_value("monaco_zoom", 1, type=float))
            last_theme = self.settings.safer_value("theme", "", type=str)
            for theme in self.theme_actions:
                if theme.text() == last_theme:
                    theme.setChecked(True)
                    self.script_edit.setTheme(last_theme)
            self.autocomplete_action.setChecked(
                self.settings.safer_value("autocomplete", True, type=bool)
            )
            self.settings.endGroup()

            self.settings.beginGroup("status_preview")
            self.status_preview.resize(
                self.settings.safer_value("size", self.status_preview.size(), type=QSize)
            )
            self.settings.endGroup()

            self.settings.beginGroup("Toolbars")
            self.toolbar.setVisible(self.settings.safer_value("buttons_visible", True, type=bool))
            self.toggle_toolbar_action.setChecked(
                self.settings.safer_value("buttons_visible", True, type=bool)
            )
            toolbar_pos = self.settings.safer_value(
                "position", Qt.ToolBarArea.TopToolBarArea.value, type=int
            )
            self.addToolBar(Qt.ToolBarArea(toolbar_pos), self.toolbar)
            self.settings.endGroup()

            self.settings.beginGroup("dockable_metadata")
            self.dockable_metadata.setVisible(
                self.settings.safer_value("visible", True, type=bool)
            )
            self.toggle_metadata_action.setChecked(
                self.settings.safer_value("visible", True, type=bool)
            )
            dock_pos = self.settings.safer_value(
                "dock_position", Qt.DockWidgetArea.RightDockWidgetArea.value, type=int
            )
            self.addDockWidget(Qt.DockWidgetArea(dock_pos), self.dockable_metadata)
            self.dockable_metadata.setFloating(
                self.settings.safer_value("floating", False, type=bool)
            )
            if self.dockable_metadata.isFloating():
                self.dockable_metadata.move(
                    self.settings.safer_value(
                        "position", self.dockable_metadata.pos(), type=QPoint
                    )
                )
                self.dockable_metadata.resize(
                    self.settings.safer_value("size", self.dockable_metadata.size(), type=QSize)
                )
            else:
                self.resizeDocks(
                    [self.dockable_metadata],
                    [
                        self.settings.safer_value(
                            "size", self.dockable_metadata.size(), type=QSize
                        ).width()
                    ],
                    Qt.Orientation.Horizontal,
                )
            self.settings.endGroup()

            self.settings.beginGroup("config_editor")
            self.config_editor.move(
                self.settings.safer_value("position", self.config_editor.pos(), type=QPoint)
            )
            self.config_editor.resize(
                self.settings.safer_value("size", self.config_editor.size(), type=QSize)
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

    def keyPressEvent(self, event: QKeyEvent):
        """Allow to modify systems list with keyboard shortcuts."""
        if self.system_list.hasFocus():
            if detect_shortcut(event, QKeySequence(QKeySequence.StandardKey.Delete)):
                self.delete_selected_system()
            if detect_shortcut(event, QKeySequence(Qt.Key.Key_Backspace)):
                self.delete_selected_system()
        super().keyPressEvent(event)

    def closeEvent(self, event: QEvent) -> None:
        """
        Capture close events and ask user whether script should be saved.

        If a script is running, the event is ignored and an explanation is given.
        If the script was modified without saving and not empty, a dialog asks
        how to proceed.

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
            self.script_edit.isModified() or self.systems_dirty
        ) and self.script_edit.toPlainText() != "":
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
        # QWebEngineView: Disconnect the webpage to prevent memory leaks
        if hasattr(self.script_edit, "page") and self.script_edit.page():
            self.script_edit.page().loadFinished.disconnect()
            self.script_edit.page().deleteLater()
        self.script_edit.deleteLater()
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.log_window.log_handler)
        self.log_window.deleteLater()
        qApp = get_application_instance()
        qApp.processEvents()
        self.server.stop()
        event.accept()

    def standard_action(self, name, display_name=None) -> QAction:
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
        action = QAction(display_name, self)
        action.setShortcut(getattr(QKeySequence.StandardKey, name))
        method_name = name[:1].lower() + name[1:]
        action.triggered.connect(lambda checked, method=method_name: self.standard_method(method))
        return action

    def standard_method(self, method_name: str) -> None:
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

    def info_box(self):
        """Display an 'about this app' widget."""
        box = AboutBox(
            "Matrix Script",
            get_matrix_icon("matr1x-matrix-script.png"),
            matr1x,
            matr1x.datetimefmt,
        )
        box.exec()
        return

    def toggle_toolbar_view(self, checked):
        """Toogles the visibility of the toolbar on and off."""
        if checked:
            self.toolbar.show()
        else:
            self.toolbar.hide()

    def toggle_metadata_view(self, checked):
        """Toggles the visibility of the metadata dock onm and off."""
        if checked:
            self.dockable_metadata.show()
        else:
            self.dockable_metadata.hide()

    def preview_data(self):
        """Launch matrix-preview with current measurement file."""
        preview = [
            sys.executable,
            "-c",
            f"from matr1x.scripts import matrix_preview; matrix_preview.main(file={self.measurement_file})",  # noqa: E501
        ]
        subprocess.Popen(preview)

    def toggle_preferences(self, checked):
        """Open the preferences pane."""
        if checked:
            self.config_editor.show()
            self.config_editor.raise_()
            self.config_editor.activateWindow()
        else:
            self.config_editor.hide()

    def toggle_log_window(self):
        """Toggle the visibility of the logging window."""
        if self.log_window.isVisible():
            self.log_window.hide()
            self.show_log_action.setChecked(False)
            self.show_log_action.setText("Show Log Window")
        else:
            self.log_window.show()
            self.log_window.raise_()
            self.log_window.activateWindow()
            self.show_log_action.setChecked(True)
            self.show_log_action.setText("Hide Log Window")

    def _load_file_from_signal(self, filename: str):
        """Convert string to Path for opening file."""
        self.load_from_filename(Path(filename))

    def init_ui(self) -> None:
        """Generate the main GUI."""
        self.setWindowIcon(get_matrix_icon("matr1x-matrix-script.png"))
        self.central_widget = CentralWidget(self)
        self.central_widget.file_dropped.connect(self._load_file_from_signal)
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)
        layout.setSpacing(0)
        layout.setContentsMargins(11, 4, 11, 11)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.dockable_metadata = QDockWidget("Metadata", self)
        self.metadata = MetaDataDialog()
        self.dockable_metadata.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dockable_metadata)
        self.dockable_metadata.setWidget(self.metadata)
        self.toggle_metadata_action = QAction("Show Metadata", self)
        self.toggle_metadata_action.setShortcut(QKeySequence("Ctrl+2"))
        self.toggle_metadata_action.setCheckable(True)
        self.toggle_metadata_action.setChecked(True)
        self.toggle_metadata_action.triggered.connect(self.toggle_metadata_view)
        self.dockable_metadata.visibilityChanged.connect(self.toggle_metadata_action.setChecked)
        self.toggle_toolbar_action = QAction("Show Toolbar", self)
        self.toggle_toolbar_action.setShortcut(QKeySequence("Ctrl+1"))
        self.toggle_toolbar_action.setCheckable(True)
        self.toggle_toolbar_action.setChecked(True)
        self.toggle_toolbar_action.triggered.connect(self.toggle_toolbar_view)
        self.help_system_action = QAction("Show System Help", self)
        self.help_system_action.triggered.connect(self.show_system_commands)
        #
        self.system_list = SystemListWidget()
        self.system_list.orderChanged.connect(self.update_systems)
        self.status_preview = TerminalOutput()
        self.status_preview.document().setMaximumBlockCount(MAX_LINES_STATUS)
        self.script_edit = CodeEditor(extensions=[self.extension])
        self.script_edit.contentModified.connect(self.update_window_title)
        self.script_edit.file_dropped.connect(self._load_file_from_signal)
        self.create_actions()
        # initialize widgets in layout
        self.splitter = QSplitter(self)
        self.splitter.addWidget(self.script_edit)
        self.splitter.addWidget(self.status_preview)
        layout.addWidget(self.splitter)
        # change the size dynamically later and allow vertical streching
        # when floating
        self.system_list.setMinimumHeight(50)
        self.system_list.setMaximumHeight(50)
        # Create menu and toolbar
        self.create_menu()
        self.create_toolbar()
        # set focus to text editor
        self.script_edit.setFocus()
        self.system_command_help = QDialog(self)
        box_layout = QVBoxLayout()
        self.system_command_text_edit = QTextEdit()
        self.system_command_text_edit.setReadOnly(True)
        box_layout.addWidget(self.system_command_text_edit)
        self.system_command_help.setLayout(box_layout)
        title = "Selected systems information"
        self.system_command_help.setWindowTitle(title)
        self.system_command_help.setWindowModality(Qt.WindowModality.NonModal)
        # Initialize the help text
        self.update_system_commands()
        self.update_window_title()
        check_config(matr1x.config)

    def create_actions(self) -> None:
        """Create all required actions and toolbar buttons."""
        self.matrix_settings_action = QAction("Show matrix toml", self)
        self.matrix_settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        self.matrix_settings_action.setShortcut(QKeySequence.StandardKey.Preferences)
        self.matrix_settings_action.triggered.connect(open_matrix_toml)
        self.about_action = QAction("About", self)
        self.about_action.setMenuRole(QAction.MenuRole.AboutRole)
        self.about_action.triggered.connect(self.info_box)
        self.config_editor = ConfigEditWidget()
        self.config_editor.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.config_editor)
        self.config_editor.setFloating(True)
        self.config_editor.close()
        self.config_action = QAction(get_matrix_icon("CHAR_≡"), "Device config", self)
        self.config_action.setToolTip("Show the devices preferences/ configuration.")
        self.config_action.setCheckable(True)
        self.config_action.toggled.connect(self.toggle_preferences)
        self.config_editor.visibilityChanged.connect(self.config_action.setChecked)
        self.new_file_action = QAction(get_matrix_icon("SP_FileIcon"), "New", self)
        self.new_file_action.triggered.connect(self.new_file)
        self.new_file_action.setShortcut(QKeySequence.StandardKey.New)
        self.load_action = QAction(get_matrix_icon("SP_DialogOpenButton"), "Open", self)
        self.load_action.setToolTip("Open a script file.")
        self.load_action.triggered.connect(self.load_from_file)
        self.load_action.setShortcut(QKeySequence.StandardKey.Open)
        self.save_action = QAction(get_matrix_icon("SP_DialogSaveButton"), "Save", self)
        self.save_action.setToolTip("Save the under the current filename.")
        self.save_action.triggered.connect(self.save_file)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_as_action = QAction(get_matrix_icon("SP_DialogSaveButton"), "Save As...", self)
        self.save_as_action.triggered.connect(self.save_file_as)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.save_button = QToolButton()
        self.save_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.save_button.setIcon(get_matrix_icon("SP_DialogSaveButton"))
        self.save_button.setText("Save")
        self.save_button.setDefaultAction(self.save_action)
        self.save_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        save_pulldown = QMenu(self)
        save_pulldown.addAction(self.save_as_action)
        self.save_button.setMenu(save_pulldown)
        self.add_system_action = QAction(get_matrix_icon("CHAR_+"), "Add System", self)
        self.add_system_action.setToolTip("Add a matrix system file.")
        self.add_system_action.triggered.connect(self.add_system)
        self.remove_system_action = QAction(get_matrix_icon("CHAR_-"), "Remove System", self)
        self.remove_system_action.setEnabled(False)
        self.remove_system_action.setToolTip("Remove the selected or last matrix system file.")
        self.remove_system_action.triggered.connect(self.delete_selected_system)
        self.quit_action = QAction("Quit", self)
        if os.name == "nt":
            self.quit_action.setShortcut(QKeySequence.StandardKey.Close)
        else:
            self.quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.quit_action.triggered.connect(self.close)
        self.undo_action = self.standard_action("Undo")
        self.redo_action = self.standard_action("Redo")
        self.cut_action = self.standard_action("Cut")
        self.copy_action = self.standard_action("Copy")
        self.paste_action = self.standard_action("Paste")
        caption = "Toggle Line Comment\t" + config["shortcuts"]["line_comment_display"]
        self.line_comment_action = QAction(caption, self)
        self.line_comment_action.setShortcut(
            QKeySequence(config["shortcuts"]["line_comment_shortcut"])
        )
        self.line_comment_action.triggered.connect(self.script_edit.toggleLineComment)
        self.zoom_in_action = self.standard_action("ZoomIn", "Zoom in")
        self.zoom_out_action = self.standard_action("ZoomOut", "Zoom Out")
        self.print_action = QAction("Print", self)
        self.print_action.setShortcut(QKeySequence.StandardKey.Print)
        self.print_action.triggered.connect(self.print_document)
        self.find_action = QAction("Find", self)
        self.find_action.setShortcut(QKeySequence.StandardKey.Find)
        self.find_action.triggered.connect(self.script_edit.show_find)
        self.start_pause_action = QAction(get_matrix_icon("CUSTOM_Play"), "Start", self)
        self.start_pause_action.setToolTip("Execute the script.")
        self.start_pause_action.triggered.connect(self.start_process)
        self.start_pause_action.setCheckable(True)
        self.stop_action = QAction(get_matrix_icon("CUSTOM_Stop"), "Stop", self)
        self.stop_action.setToolTip("Stop the script and query status.")
        self.stop_action.triggered.connect(lambda: self.abort_thread("q"))
        self.stop_action.setEnabled(False)
        self.abort_action = QAction(get_matrix_icon("CUSTOM_Stop"), "Abort", self)
        self.abort_action.triggered.connect(lambda: self.abort_thread("a"))
        self.abort_action.setEnabled(False)
        self.finish_action = QAction(get_matrix_icon("CUSTOM_Stop"), "Finish", self)
        self.finish_action.triggered.connect(lambda: self.abort_thread("f"))
        self.finish_action.setEnabled(False)
        self.stop_button = QToolButton()
        self.stop_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.stop_button.setIcon(get_matrix_icon("CUSTOM_Stop"))
        self.stop_button.setText("Abort")
        self.stop_button.setDefaultAction(self.stop_action)
        self.stop_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        stop_pulldown = QMenu(self)
        stop_pulldown.addAction(self.abort_action)
        stop_pulldown.addAction(self.finish_action)
        self.stop_button.setMenu(stop_pulldown)
        self.kill_action = QAction(get_matrix_icon("SP_DialogCancelButton"), "Kill", self)
        self.kill_action.triggered.connect(self.kill_thread)
        self.kill_action.setEnabled(False)
        self.preview_action = QAction(
            get_matrix_icon("matr1x-matrix-preview.png", QColor("RoyalBlue")), "Preview", self
        )
        self.preview_action.triggered.connect(self.preview_data)
        self.preview_action.setEnabled(False)
        self.pep8_action = QAction("Format with ruff", self)
        self.pep8_action.triggered.connect(self.script_edit.formatCode)
        self.pep8_action.setShortcut(QKeySequence("Ctrl+8"))
        # Themes
        self.theme_actions = []
        self.theme_group = QActionGroup(self)
        self.theme_group.setExclusionPolicy(QActionGroup.ExclusionPolicy.Exclusive)
        for theme in self.script_edit.supportedThemes():
            action = QAction(theme, self)
            action.setCheckable(True)
            if theme == self.script_edit.supportedThemes()[0]:
                action.setChecked(True)
            action.toggled.connect(
                lambda checked=False, theme=theme: self.script_edit.setTheme(theme)
            )
            self.theme_group.addAction(action)
            self.theme_actions.append(action)
        self.autocomplete_action = QAction("Tab completion", self)
        self.autocomplete_action.setCheckable(True)
        self.autocomplete_action.setChecked(True)
        self.autocomplete_action.toggled.connect(self.script_edit.enableTabCompletion)
        self.show_log_action = QAction("Show Log Window", self)
        self.show_log_action.setCheckable(True)
        self.show_log_action.triggered.connect(self.toggle_log_window)

    def create_toolbar(self) -> None:
        """Create the toolbar."""
        self.toolbar = QToolBar("Toolbar")
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.toolbar.setFloatable(False)
        self.toolbar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.toolbar.setAllowedAreas(
            Qt.ToolBarArea.TopToolBarArea | Qt.ToolBarArea.BottomToolBarArea
        )
        icon_size = get_application_instance().toolbar_icon_size()
        empty = QWidget()
        empty.setFixedWidth(icon_size)
        empty2 = QWidget()
        empty2.setFixedWidth(icon_size)
        empty3 = QWidget()
        empty3.setFixedWidth(icon_size)
        self.toolbar.setIconSize(QSize(icon_size, icon_size))
        self.toolbar.addAction(self.new_file_action)
        self.toolbar.addAction(self.load_action)
        self.toolbar.addWidget(self.save_button)
        self.toolbar.addWidget(empty)
        self.toolbar.addAction(self.start_pause_action)
        self.toolbar.addWidget(self.stop_button)
        self.toolbar.addWidget(empty2)
        self.toolbar.addAction(self.preview_action)
        self.toolbar.addWidget(empty3)
        self.toolbar.visibilityChanged.connect(self.toggle_toolbar_action.setChecked)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.add_system_action)
        self.toolbar.addWidget(self.system_list)
        self.toolbar.addAction(self.remove_system_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.config_action)
        self.addToolBar(self.toolbar)

    def create_menu(self) -> None:
        """Create the main menu."""
        menu = self.menuBar()
        assert menu is not None
        # Populate the actions
        file_menu = menu.addMenu("&File")
        assert file_menu is not None
        file_menu.addAction(self.new_file_action)
        file_menu.addAction(self.load_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.add_system_action)
        file_menu.addAction(self.remove_system_action)
        file_menu.addSeparator()
        file_menu.addAction(self.print_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)  # This gets auto-moved on a Mac
        #
        edit_menu = menu.addMenu("&Edit")
        assert edit_menu is not None
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.cut_action)
        edit_menu.addAction(self.copy_action)
        edit_menu.addAction(self.paste_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.find_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.line_comment_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.pep8_action)
        #
        code_menu = menu.addMenu("&Editor")
        assert code_menu is not None
        theme_menu = code_menu.addMenu("Theme")
        for action in self.theme_actions:
            theme_menu.addAction(action)
        code_menu.addSeparator()
        code_menu.addAction(self.zoom_in_action)
        code_menu.addAction(self.zoom_out_action)
        code_menu.addSeparator()
        code_menu.addAction(self.autocomplete_action)
        #
        control_menu = menu.addMenu("&Control")
        assert control_menu is not None
        control_menu.addAction(self.start_pause_action)
        control_menu.addAction(self.abort_action)
        control_menu.addAction(self.finish_action)
        control_menu.addAction(self.kill_action)
        control_menu.addSeparator()
        control_menu.addAction(self.preview_action)
        #
        view_menu = menu.addMenu("&View")
        assert view_menu is not None
        view_menu.addAction(self.toggle_toolbar_action)
        view_menu.addAction(self.toggle_metadata_action)
        view_menu.addAction(self.matrix_settings_action)
        view_menu.addAction(self.config_action)
        #
        help_menu = menu.addMenu("&Help")
        assert help_menu is not None
        help_menu.addAction(self.help_system_action)
        help_menu.addAction(self.show_log_action)
        help_menu.addAction(self.about_action)  # This is auto-moved on a Mac

    def update_window_title(self):
        """Indicate if the file was edited with an asterisk."""
        text = "Matrix Script"
        if self.script_edit.isModified() or self.systems_dirty:
            text += ": *"
        elif self.scriptname:
            text += ": "
        if self.scriptname:
            text += self.scriptname.name
        elif self.script_edit.isModified() or self.systems_dirty:
            text += "<unsaved>"
        self.setWindowTitle(text)

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
                self.system_list.addItem(module_name)
            else:
                self.system_list.addItem(filename)
        self.remove_system_action.setEnabled(True)
        self.systems_dirty = True
        self.update_window_title()
        # update systems to use list for config editor
        self.update_systems()
        if self.system_command_help.isVisible():
            self.show_system_commands()

    def delete_selected_system(self) -> None:
        """
        Remove selected system from system_list.

        If no selection is active the last system will be removed.
        Update help if need be.
        """
        selected = self.system_list.selectedItems()
        if len(selected) > 0:
            self.system_list.takeItem(self.system_list.row(selected[0]))
        elif 0 < self.system_list.count():
            self.system_list.takeItem(self.system_list.count() - 1)
        if self.system_list.count() == 0:
            self.remove_system_action.setEnabled(False)
        self.systems_dirty = True
        self.update_window_title()
        self.update_systems()
        if self.system_command_help.isVisible():
            self.show_system_commands()

    @Slot(str, str, float, str, object, object, object, object)
    def get_script_input(
        self,
        query: str,
        input_type: str,
        timeout: float = float("inf"),
        default_value: str = "",
        min_value: float | None = None,
        max_value: float | None = None,
        step: float | None = None,
        decimals: int | None = None,
    ):
        """
        Open a dialog and forward input to the script.

        Parameters
        ----------
        query: str
         Label to explain the user what they input
        input_type: str
         Type of expected input. can be 'string' or 'bool' or 'numerical'
        timeout: float, optional
         Timeout in seconds before dialog automatically closes. Default is infinity (no timeout).
        default_value: str, optional
         Default value to show in input field and use if timeout occurs. Default is empty string.
        min_value: float, optional
         Minimum value for numerical input.
        max_value: float, optional
         Maximum value for numerical input.
        step: float, optional
         Step size for numerical input.
        """
        if input_type == "string":
            dialog = TextInputDialog(
                query, parent=self, timeout=timeout, default_value=default_value
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                ret = dialog.get_input_text()
            else:
                # abort executing script
                self.abort_thread()
                return
        elif input_type == "bool":
            dialog = YesNoAbortDialog(
                query, parent=self, timeout=timeout, default_value=default_value
            )
            ret = dialog.exec_and_get_response()
            if ret == "abort":
                self.abort_thread()
                return
        elif input_type == "numerical":
            try:
                # Convert default_value string to float
                numerical_default_value = float(default_value) if default_value else 0.0
            except ValueError:
                print(
                    f"Warning: Invalid default_value '{default_value}' "
                    "for numerical input. Using 0.0"
                )
                numerical_default_value = 0.0

            dialog = NumericalInputDialog(
                query,
                parent=self,
                timeout=timeout,
                default_value=numerical_default_value,
                min_value=min_value,
                max_value=max_value,
                step=step,
                decimals=decimals,
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                ret = str(dialog.get_input_value())
            else:
                # abort executing script
                self.abort_thread()
                return
        elif input_type == "__end_script__":
            dialog = TerminationDialog()
            ret = dialog.get_selection()
        else:
            ret = ""
        self.measurement_thread.pass_input(ret)

    def pause_thread(self):
        """Pause thread execution."""
        self.measurement_thread.pause()

    def abort_thread(self, char="q"):
        """
        Abort thread execution and define measurement state as per `char`.

        Parameters
        ----------
            char : str
                Single length string that is passed to the process.
                - "q" stops and queries user for state
                - "a" stops and sets state to `aborted`
                - "f" stops and sets state to `finished`
        """
        if self.start_pause_action.isChecked():
            self.start_pause_action.setChecked(False)
        self.measurement_thread.abort(char)

    def kill_thread(self):
        """Kill the thread."""
        self.measurement_thread.kill()
        self.print_colored("Script terminated by user - " + "file integrity might be compromised")

    def show_editor_commands(self):
        """Print shortcuts and editor functions."""
        help_string = textwrap.dedent(
            """
        The editor includes following features:
          ctrl+/ - toggling of comments in selection
          " or ' with selection - make block comment
        """
        )
        print(help_string)

    def get_settables(
        self,
    ) -> tuple[list[int] | None, list[bool] | None, list[str] | None]:
        """
        Get the settables of the system files.

        This is used to find errors in the script and
        the help message box.

        Returns
        -------
        indexes: list [int] or None
            The indexes of the columns.
        settables : list[bool] or None
            True, if the property is settable.
        columns : list[str] or None
            The names of the columns.
        """
        # Use cached system info if available
        if hasattr(self, "_cached_system_info") and self._cached_system_info:
            return self._process_system_data(self._cached_system_info)

        json_data = get_system_info(self.systems)
        if json_data is None:
            return (None, None, None)

        return self._process_system_data(json_data)

    def _extract_parameter_index(self, key, data):
        """Extract index from parameter key or description."""
        if key.startswith("param_"):
            try:
                return key.split("_")[1]
            except IndexError:
                return ""
        elif "at index" in data.get("description", ""):
            try:
                return data["description"].split("at index ")[1]
            except IndexError:
                return ""
        return ""

    def _process_system_data(self, output):
        """Process the parsed JSON data and extract system information."""
        indexes = []
        settables = []
        columns = []

        # Process parameters section (indexed items)
        if "parameters" in output:
            for key, data in output["parameters"].items():
                index = self._extract_parameter_index(key, data)
                indexes.append(index)
                settables.append(data.get("description", ""))
                columns.append(data.get("name", ""))

        # Process devices section (no indices)
        if "devices" in output:
            for dev_id, data in output["devices"].items():
                indexes.append("")
                settables.append(data.get("description", ""))
                columns.append(data.get("name", ""))

        # Process methods section (no indices)
        if "methods" in output:
            for method_id, data in output["methods"].items():
                indexes.append("")
                settables.append(data.get("description", ""))
                columns.append(data.get("name", ""))

        return (indexes, settables, columns)

    def update_system_commands(self, cached_info: dict | None = None) -> None:
        """
        Update the help info about the current system(s).

        Parameters
        ----------
        cached_info : dict, optional
            Dictionary containing cached system information.
            If provided, this will be used instead of calling
            :meth:`get_settables`.  By default, None
        """
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
        else:
            if cached_info is not None:
                # Use cached information
                indexes = cached_info.get("indexes")
                settables = cached_info.get("settables")
                columns = cached_info.get("columns")
            else:
                # Fall back to getting settables normally
                indexes, settables, columns = self.get_settables()

            if indexes and settables and columns:
                text = "The following systems were selected:<br><b>"
                for system in self.systems:
                    text = text + system + "<br>"
                text += "<br></b>These systems provide the following:<br><br>"

                # Group parameters, devices, and methods
                parameters = []
                devices = []
                methods = []

                for i in range(len(indexes)):
                    desc_str = str(settables[i]) if settables[i] is not None else ""
                    if "parameter" in desc_str.lower():
                        # Check if parameter is settable
                        is_settable = "settable" in desc_str.lower()
                        parameters.append((indexes[i], columns[i], settables[i], is_settable))
                    elif "device" in desc_str.lower():
                        devices.append((indexes[i], columns[i], settables[i]))
                    elif "method" in desc_str.lower() or "variable" in desc_str.lower():
                        methods.append((indexes[i], columns[i], settables[i]))
                    else:
                        # Fallback - anything not categorized goes to parameters
                        parameters.append((indexes[i], columns[i], settables[i], False))

                # Display parameters table
                if parameters:
                    text += "<h3>Parameters</h3>"
                    text += '<table border="1" cellpadding="5" cellspacing="0" '
                    text += 'style="border-collapse: collapse; text-align: left; '
                    text += 'margin-bottom: 20px;">'
                    text += '<tr style="background-color: #f0f0f0; text-align: left;">'
                    text += '<th style="text-align: left;">Index</th>'
                    text += '<th style="text-align: left;">Name</th>'
                    text += '<th style="text-align: left;">Description</th></tr>'
                    # Sort parameters by index for correct display order
                    parameters.sort(key=lambda x: int(x[0]) if x[0] and x[0].isdigit() else 999)
                    for idx, col, desc, is_settable in parameters:
                        if is_settable:
                            text += f"<tr><td>{idx}</td><td><b>{col}</b></td><td>{desc}</td></tr>"
                        else:
                            text += f"<tr><td>{idx}</td><td>{col}</td><td>{desc}</td></tr>"
                    text += "</table>"

                # Display devices table
                if devices:
                    text += "<h3>Devices</h3>"
                    text += '<table border="1" cellpadding="5" cellspacing="0" '
                    text += 'style="border-collapse: collapse; text-align: left; '
                    text += 'margin-bottom: 20px;">'
                    text += '<tr style="background-color: #f0f0f0; text-align: left;">'
                    text += '<th style="text-align: left;">Name</th>'
                    text += '<th style="text-align: left;">Description</th></tr>'
                    for idx, col, desc in devices:
                        text += f"<tr><td><b>{col}</b></td><td>{desc}</td></tr>"
                    text += "</table>"

                # Display methods table
                if methods:
                    text += "<h3>System Methods and Variables</h3>"
                    text += '<table border="1" cellpadding="5" cellspacing="0" '
                    text += 'style="border-collapse: collapse; text-align: left; '
                    text += 'margin-bottom: 20px;">'
                    text += '<tr style="background-color: #f0f0f0; text-align: left;">'
                    text += '<th style="text-align: left;">Name</th>'
                    text += '<th style="text-align: left;">Description</th></tr>'
                    for idx, col, desc in methods:
                        text += f"<tr><td><b>{col}</b></td><td>{desc}</td></tr>"
                    text += "</table>"

                text += "<br>"
            else:
                text = "Could not parse the system file(s)!"
        self.system_command_text_edit.setText(text)

    def show_system_commands(self) -> None:
        """Print information about current system(s) in a help window."""
        # Store current geometry if dialog is already visible
        current_geometry = None
        if self.system_command_help.isVisible():
            current_geometry = self.system_command_help.geometry()

        # Ensure the help text is updated
        self.update_system_commands()

        # Set minimum size to sizeHint
        self.system_command_help.setMinimumSize(self.system_command_help.sizeHint())

        # Load size and position from settings (only if not already visible)
        if not self.system_command_help.isVisible():
            self.settings.beginGroup("system_command_help")
            saved_size = self.settings.safer_value(
                "size", self.system_command_help.sizeHint(), type=QSize
            )
            saved_position = self.settings.safer_value(
                "position", self.system_command_help.pos(), type=QPoint
            )
            self.settings.endGroup()
            self.system_command_help.resize(saved_size)
            self.system_command_help.move(saved_position)

        self.system_command_help.show()
        self.system_command_help.raise_()

        # Restore previous geometry if available (this will override the
        # saved settings if dialog was already visible)
        if current_geometry:
            self.system_command_help.setGeometry(current_geometry)

        # Mark that the help dialog has been shown at least once
        self._help_dialog_shown = True

    def output_written(self, text):
        """
        Append most recent text to the end of the display, place cursor at end.

        This function also tries to mimick the behavior of a carriage
        return in the output text. At the position of a carriage return
        the current line is deleted and replaced by the new text.
        """
        if len(text) > 20000:
            # if receiving very long print statements, limit display to 20k
            # symbols. This is necessary because performance of QTextEdit is
            # insufficient to handle very large texts
            prefix = "Received very long print statement, first 20k symbols:\n"
            text = prefix + text[:20000]
        self.status_preview.moveCursor(QTextCursor.MoveOperation.End)
        if "\r" in text:
            before, after = text.split("\r", maxsplit=1)
            self.status_preview.insertPlainText(before)
            # make sure cursor is at the end of the inserted text (required
            # if there is a \n in `before`).
            self.status_preview.moveCursor(QTextCursor.MoveOperation.End)
            # return cursor to beginning of line by deleting its content
            cursor = self.status_preview.textCursor()
            # select the content of the last line and clear the text
            self.status_preview.moveCursor(
                QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.MoveAnchor
            )
            self.status_preview.moveCursor(
                QTextCursor.MoveOperation.StartOfLine, QTextCursor.MoveMode.KeepAnchor
            )
            cursor.removeSelectedText()
            if "\r" in after:
                # recursion for long strings
                self.output_written(after)
            else:
                # insert text after \r at the cursor location
                self.status_preview.insertPlainText(after)
        else:
            self.status_preview.insertPlainText(text)
            self.status_preview.moveCursor(QTextCursor.MoveOperation.End)
        sb = self.status_preview.verticalScrollBar()
        sb.setValue(sb.maximum())

    def update_filename(self, path: str) -> None:
        """
        Update the current measurement filename.

        Parameters
        ----------
        path: str
            Path to current measurement file
        """
        self.measurement_file = Path(path)
        self.preview_action.setEnabled(True)

    def enable_buttons(self, flag):
        """
        Switch the buttons from thread running to thread stopped mode.

        Parameters
        ----------
            flag : bool
                True means script is running
        """
        self.is_running = flag

        if flag:
            self.start_pause_action.setIcon(get_matrix_icon("CUSTOM_Pause"))
            self.start_pause_action.setText("Pause")
            self.start_pause_action.setToolTip("Pause the currently running script.")
            self.start_pause_action.triggered.disconnect(self.start_process)
            self.start_pause_action.triggered.connect(self.pause_thread)
        else:
            self.script_edit.removeHighlight()
            self.start_pause_action.setIcon(get_matrix_icon("CUSTOM_Play"))
            self.start_pause_action.setText("Start")
            self.start_pause_action.setToolTip("Execute the script.")
            self.start_pause_action.triggered.disconnect(self.pause_thread)
            self.start_pause_action.triggered.connect(self.start_process)

        self.start_pause_action.setChecked(False)
        self.stop_action.setEnabled(flag)
        self.abort_action.setEnabled(flag)
        self.finish_action.setEnabled(flag)
        self.kill_action.setEnabled(flag)
        self.script_edit.setReadOnly(flag)
        self.new_file_action.setEnabled(not flag)
        self.load_action.setEnabled(not flag)
        self.help_system_action.setEnabled(not flag)
        self.add_system_action.setEnabled(not flag)
        self.remove_system_action.setEnabled(not flag)
        self.metadata.setEnabled(not flag)

    def process_finished(self):
        """
        Handle GUI changes and clean up thread after it has finished.

        Return buttons to original state, delete the finished process.
        """
        self.enable_buttons(False)
        self.print_colored("\nExecution finished")
        del self.measurement_thread

    def run_linter(self):
        """Call the linter for the editor view."""
        self.script_edit.setSettables(self.get_settables())
        return self.script_edit.returnIssues()

    def start_process(self):
        """
        Start the matrix_script process.

        Disable/enable buttons to reflect run state and get selected
        systems. Then runs the script defined in the edit.
        """
        if 0 == len(self.systems):
            self.start_pause_action.setChecked(False)
            self.print_colored("No system selected")
            return
        # avoid script execution for empty scripts?
        # if self.script_edit.text().strip() == "":
        #    print("No script to execute")
        #    print("==========")
        #    return
        # run linter to make sure there are no errors
        if self.run_linter() > 0:
            self.print_colored("Script execution was halted because of linter errors")
            qApp = get_application_instance()
            qApp.processEvents()
            # open a popup window to inform about the error
            a = QMessageBox(parent=self)
            a.setText("Linter error")
            a.setInformativeText("Error found in script, continue anyway?")
            a.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            a.setDefaultButton(QMessageBox.StandardButton.Ok)
            ret = a.exec()
            if ret == QMessageBox.StandardButton.Cancel:
                self.start_pause_action.setChecked(False)
                return

        self.print_colored("### Running script now")
        # define basic part of script, imports relevant commands
        user_script = self.script_edit.toPlainText()
        script = generate_script(user_script)
        meta_data = self.metadata.get_metadata()
        temp_config = self.config_editor.write_config()
        self.measurement_thread = ScriptThread(
            meta_data, script, self.scriptname, temp_config, self.systems
        )
        self.measurement_thread.lineno_signal.connect(self.script_edit.highlight)
        self.measurement_thread.input_signal.connect(self.get_script_input)
        self.measurement_thread.filename_signal.connect(self.update_filename)
        self.measurement_thread.finished.connect(self.process_finished)
        logger.info("The following user script was run:\n%s", user_script)
        self.measurement_thread.start()
        self.enable_buttons(True)

    def update_systems(self, update_config=True):
        """
        Update the systems list and config editor.

        Parameters
        ----------
        update_config (bool): Whether to update the config editor.
        """
        new_systems = [
            # use normpath here since there is no pathlib equivalent
            normpath(self.system_list.item(j).text())
            for j in range(self.system_list.count())
        ]

        # Clear cache if systems changed
        if not hasattr(self, "systems") or self.systems != new_systems:
            self._cached_system_info = None

        self.systems = new_systems

        # Get system information using subprocess (cache for reuse)
        if self._cached_system_info is None and self.systems:
            try:
                self._cached_system_info = get_system_info(self.systems)
                if not self._cached_system_info:
                    print("Warning: subprocess returned empty system info")
                    self._cached_system_info = {}
            except Exception as e:
                print(f"Warning: Could not get system info for config editor: {e}")
                self._cached_system_info = {}

        # only systems that are part of matrix or ifwlib can be configured via files
        configurable = [system for system in self.systems if not Path(system).exists()]
        matr1x.reload_config()
        if update_config:
            self.config_editor.set_systemfile(configurable)
            self.config_editor.set_full_system_list(self.systems)
            self.config_editor.set_system_info(self._cached_system_info or {})
            self.config_editor.update_data()

        # Update system commands with cached info
        self.update_system_commands(self._cached_system_info)
        self.run_linter()

    def get_settable_info(self):
        """Verify that the systems match the ones from the loaded script."""
        # Use cached system info if available
        if hasattr(self, "_cached_system_info") and self._cached_system_info:
            try:
                return self._extract_settable_info(self._cached_system_info)
            except Exception:
                pass

        # Fallback to fresh system info
        try:
            system_info = get_system_info(self.systems)
            if system_info:
                self._cached_system_info = system_info
                return self._extract_settable_info(system_info)
        except Exception:
            pass

        return None

    def _extract_settable_info(self, system_info):
        """Extract settable information from system info."""
        if not system_info or "parameters" not in system_info:
            return None

        indexes = []
        columns = []
        units = []

        for param_key, param_info in system_info["parameters"].items():
            if isinstance(param_info, dict) and "name" in param_info:
                # Extract index from param_key (e.g., "param_0" -> 0)
                try:
                    index = int(param_key.split("_")[1])
                    param_name = param_info["name"]
                    param_unit = param_info.get("unit", "")

                    # Handle compound columns (names/units joined with ", ")
                    if ", " in param_name:
                        # Split compound columns back into individual columns
                        name_parts = [name.strip() for name in param_name.split(", ")]
                        unit_parts = [unit.strip() for unit in param_unit.split(", ")]

                        # Ensure we have the same number of names and units
                        if len(unit_parts) != len(name_parts):
                            unit_parts = [""] * len(name_parts)

                        for name, unit in zip(name_parts, unit_parts):
                            indexes.append(index)
                            columns.append(name)
                            units.append(unit)
                    else:
                        indexes.append(index)
                        columns.append(param_name)
                        units.append(param_unit)
                except (ValueError, IndexError):
                    continue

        return (indexes, columns, units)

    def save_file_as(self):
        """Ask for the filename and calls write_file()."""
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

    def save_file(self):
        """
        Try to save under the last name and call write_file().

        if no last filename exists calls save_file_as().
        """
        if not self.last_filename:
            return self.save_file_as()
        else:
            return self.write_file(self.last_filename)

    def write_file(self, filename: Path):
        """Save script to file and write system information to header."""
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
        self.script_edit.setPlainText(newscript)
        output_file.write(newscript)
        output_file.close()
        self.last_filename = filename
        self.script_edit.setModified(False)
        self.systems_dirty = False
        self.update_window_title()
        return 0

    def generate_save_content(self):
        """Add the systems in the header of a script."""
        header = ""
        if 0 < len(self.systems):
            # only attempt generating a header if a system is selected
            try:
                # get settable information to put into the header
                # (columns/units)
                settable_info = self.get_settable_info()

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
        script = self.script_edit.toPlainText().rstrip()
        newscript = header
        for i, line in enumerate(script.splitlines()):
            if i < 4 and (line.startswith("# system ") or line.startswith("# file v")):
                # if there are already definitions of the system, skip them
                continue
            newscript += line + "\n"
        return newscript

    def load_from_filename(self, filename: Path):
        """
        Load the script from file denoted by filename.

        Also, make sure that header information specified still agree
        with the corresponding system.
        """
        try:
            input_file = filename.open()
        except OSError:
            self.print_colored("File cannot be opened")
            return
        self.scriptname = filename
        self.script_edit.setPlainText("")
        self.system_list.clear()
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
                    self.system_list.addItem(syst)
                    self.update_systems()
                    settable_info = self.get_settable_info()
                except KeyError:
                    self.print_colored(
                        "System that was used to generate the "
                        "script was not found in installed systems."
                        " Please check .matrix.conf file."
                    )
                    return
        else:
            self.print_colored("No system defined in script, please choose system(s)")
        self.script_edit.insertText(line)
        #
        # system columns definiton
        #
        line = input_file.readline()
        self.script_edit.insertText(line)
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
        self.script_edit.insertText(line)
        # make sure that system unit definition agrees with
        # current system
        if "# system units : " in line and settable_info is not None and len(settable_info) >= 3:
            system_units = line.strip().replace("# system units : ", "")
            current_units = [str(unit).strip() for unit in settable_info[2]]
            # Handle both "," and ", " as separators since compound columns use ", "
            loaded_units = []
            for unit in system_units.split(","):
                unit = unit.strip()
                if unit:
                    loaded_units.append(unit)
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
            self.script_edit.insertText(line)
        input_file.close()
        self.script_edit.setModified(False)
        self.systems_dirty = False
        self.last_filename = filename
        self.update_window_title()
        if self.system_list.count() > 0:
            self.remove_system_action.setEnabled(True)
        self.run_linter()

    def load_from_file(self) -> None:
        """Open file dialog and call load_from_filename."""
        # First, check if unsaved changes exist
        if self.script_edit.isModified() or self.systems_dirty:
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
        if self.script_edit.isModified() or self.systems_dirty:
            qApp = get_application_instance()
            qApp.processEvents()
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
        self.script_edit.setPlainText("")
        self.script_edit.setModified(False)


def main():
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
