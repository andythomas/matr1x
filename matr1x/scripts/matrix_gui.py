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
"""Provide a graphical user interface for matrix measurements."""

import hashlib
import json
import os
import re
import signal
import socket
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QByteArray, QSettings, QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QKeyEvent, QKeySequence
from PyQt6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import matr1x
from matr1x.control.util import QtGracefulKiller
from matr1x.gui_util import (
    AboutBox,
    ConfigEditWidget,
    MApplication,
    MetaDataDialog,
    check_config,
    detect_shortcut,
    get_application_instance,
    get_matrix_icon,
    get_system_info,
    open_matrix_toml,
)
from matr1x.scripts import (
    MATRIX_GUI_PORT,
    matrix_preview,
    sweep_generator,
)
from matr1x.system import MergedSystem
from matr1x.util import get_matrix_binary, open_and_error, set_correct_mac_appname


def signal_handler(signal, frame):
    """Take any keyboard interrupt in the GUI."""
    return


# Connect keyboard interrupt with above signal handler
signal.signal(signal.SIGINT, signal_handler)

if sys.platform == "win32":
    try:
        from ctypes import windll

        myappid = "python.matr1x.matrix-gui.version"
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass


class LabelWithSignal(QLabel):
    """A QLabel that emits a signal if the text changes."""

    textChanged = pyqtSignal(str)

    def setText(self, a0):
        """
        Set label text and emit signal.

        Parameters
        ----------
        a0 : str
            The new label text.
        """
        super().setText(a0)
        self.textChanged.emit(a0)


class QueueListWidget(QListWidget):
    """
    A list widget that stores a dictionary for each row.

    This list of dict is used to handle the measurement queue and store
    the line to show in the list view.
    """

    def __init__(self):
        """Initialize the list widget with an empty list."""
        super().__init__()
        self.data_list = []
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setAlternatingRowColors(True)
        model = self.model()
        assert model is not None
        model.rowsMoved.connect(self.update_data_order)

    def add_parameters(self, parameters: tuple) -> None:
        """
        Add a set of parameters.

        Parameters
        ----------
        parameters : tuple
            The tuple to be added: (inputFile, outputFile, metadata_dict, config_dict).
        """
        output = Path(parameters[1]).name if parameters[1] else ""
        if output == "":
            output = "<use input>"
        dict_str = (
            parameters[0]
            + parameters[1]
            + json.dumps(parameters[2], sort_keys=True)
            + json.dumps(parameters[3], sort_keys=True)
        )
        hash_value = hashlib.sha256(dict_str.encode()).hexdigest()[:6]
        list_entry = f"Input: {Path(parameters[0]).name} - Output: {output} - Id: {hash_value}"
        param_dict = {"parameters": parameters, "listview": list_entry}
        self.data_list.append(param_dict)
        list_item = QListWidgetItem(param_dict["listview"])
        super().addItem(list_item)

    def takeItem(self, row: int):
        """
        Delete the item.

        Parameters
        ----------
        row : int
            The row to be deleted.
        """
        self.data_list.pop(row)
        super().takeItem(row)

    def update_data_order(self):
        """Update the list of dicts based on the list widget."""
        new_order = []
        for i in range(self.count()):
            item = self.item(i)
            assert item is not None
            new_order.append(item.text())
        self.data_list.sort(key=lambda x: new_order.index(x["listview"]))

    def parameters(self, row: int) -> tuple:
        """
        Get the parameters for a matrix run.

        Parameters
        ----------
        row : int
            The row to query.

        Returns
        -------
        The input parameters for the thread.
        """
        return self.data_list[row]["parameters"]


class ExecThread(QThread):
    """Execute the measurement thread."""

    filename_received = pyqtSignal(str)

    def __init__(self):
        """Initialize the thread."""
        QThread.__init__(self)

    def set_param(self, params, config_editor):
        """Set measurement parameters and meta-data from a parameter tuple."""
        self.inputFile, self.outputFile, self.meta_data, self.config_dict = params
        self.config_editor = config_editor

    def receive_filename(self):
        """
        Receive filename from command line.

        Matrix checks if the file already exists and subsequently
        changes its name. This way, no existing measurement can be
        accidently overwritten. The name is reported back to the GUI
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", MATRIX_GUI_PORT))
        s.listen(1)
        conn, address = s.accept()  # will block until a new client connects

        # get filename which is sent by matrix
        data = ""
        while True:
            datachunk = conn.recv(1024)
            if not datachunk:
                break
            data += datachunk.decode()

        conn.close()
        self.filename_received.emit(data)

    def run(self) -> None:
        """Start the command line process."""
        # Create temporary config file from dictionary
        tmp_config_file = None
        if hasattr(self, "config_dict") and self.config_dict:
            # Use ConfigEditWidget's write_config method to write the dictionary
            tmp_config_file = self.config_editor.write_config(self.config_dict)

        try:
            cmd = [get_matrix_binary(), "-i", self.inputFile]
            if self.outputFile != "":
                cmd += ["-o", self.outputFile]
            for key, val in self.meta_data.items():
                if key in matr1x.VALID_META_KEYS.keys() and val:
                    if matr1x.VALID_META_KEYS[key]:
                        # only pass on allowed (editable) meta keys and only if
                        # data is not None
                        cmd += [f"--dc_{key.lower()}", val]
            if tmp_config_file:
                cmd += ["--optional-config", str(tmp_config_file)]
            print(subprocess.list2cmdline(cmd))
            ret = self.run_as_fg_process(cmd)
            print(f"matrix ended with returncode: {ret}")
        finally:
            # Clean up temporary config file
            if tmp_config_file and tmp_config_file.exists():
                tmp_config_file.unlink()

    def run_as_fg_process(self, *args, **kwargs):
        # Code of this function was adapted from
        # https://stackoverflow.com/a/66727983/3504203,
        # it was published under CC BY-SA 4.0,
        # https://creativecommons.org/licenses/by-sa/4.0/
        # Modifications were made to use a primitive fallback on MS Windows.
        """
        Catch signals correctly.

        The "correct" way of spawning a new subprocess:
        signals like C-c must only go
        to the child process, and not to this python.

        the args are the same as subprocess.Popen

        returns Popen().wait() value

        Some side-info about "how ctrl-c works":
        https://unix.stackexchange.com/a/149756/1321

        fun fact: this function took a whole night
                  to be figured out.
        """
        if sys.platform == "win32":
            # fork the child
            child = subprocess.Popen(*args, **kwargs)
            # get filename back
            self.receive_filename()
            # wait for the child to terminate
            ret = child.wait()
        else:
            import termios

            old_pgrp = os.tcgetpgrp(sys.stdin.fileno())
            old_attr = termios.tcgetattr(sys.stdin.fileno())

            user_preexec_fn = kwargs.pop("preexec_fn", None)

            def new_pgid():
                if user_preexec_fn:
                    user_preexec_fn()

                # set a new process group id
                os.setpgid(os.getpid(), os.getpid())

                # generally, the child process should stop itself
                # before exec so the parent can set its new pgid.
                # (setting pgid has to be done before the child execs).
                # however, Python 'guarantee' that `preexec_fn`
                # is run before `Popen` returns.
                # this is because `Popen` waits for the closure of
                # the error relay pipe '`errpipe_write`',
                # which happens at child's exec.
                # this is also the reason the child can't stop itself
                # in Python's `Popen`, since the `Popen` call would never
                # terminate then.
                # `os.kill(os.getpid(), signal.SIGSTOP)`

            try:
                # fork the child
                child = subprocess.Popen(*args, preexec_fn=new_pgid, **kwargs)  # ty: ignore [no-matching-overload] issue #247

                # we can't set the process group id from the parent since the
                # child will already have exec'd. and we can't SIGSTOP it before
                # exec, see above.
                # `os.setpgid(child.pid, child.pid)`

                # set the child's process group as new foreground
                os.tcsetpgrp(sys.stdin.fileno(), child.pid)
                # revive the child,
                # because it may have been stopped due to SIGTTOU or
                # SIGTTIN when it tried using stdout/stdin
                # after setpgid was called, and before we made it
                # forward process by tcsetpgrp.
                os.kill(child.pid, signal.SIGCONT)

                # get filename back
                self.receive_filename()

                # wait for the child to terminate
                ret = child.wait()

            finally:
                # we have to mask SIGTTOU because tcsetpgrp
                # raises SIGTTOU to all current background
                # process group members (i.e. us) when switching tty's pgrp
                # it we didn't do that, we'd get SIGSTOP'd
                # hdlr = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
                # signal library only works in the main thread
                # make us tty's foreground again
                os.tcsetpgrp(sys.stdin.fileno(), old_pgrp)
                # now restore the handler
                # signal.signal(signal.SIGTTOU, hdlr)
                # restore terminal attributes
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_attr)

        return ret


class MainWindow(QMainWindow):
    """Define layout, runs everything."""

    def __init__(self):
        super().__init__()
        self.initUI()
        self.sg = None
        self.running = False
        self.sys_meta_data = {}
        self.measurement_thread = ExecThread()
        self.measurement_thread.filename_received.connect(self.handle_received_filename)
        self.measurement_thread.finished.connect(self.processFinished)

        # allow to store the settings
        self.settings = QSettings("matr1x", "gui")

        # Define the allowed extension pattern
        self.allowed_extension_pattern = re.compile(r"\.\d+t$")
        # Enable dragging and dropping onto the widget
        self.setAcceptDrops(True)

        # Initialize cache for system information
        self._cached_system_info = None

    def handle_received_filename(self, filename: str) -> None:
        """
        Handle the filename from the measurement thread.

        Parameters
        ----------
        filename : str
            The filename given to the measurement file.
        """
        self.current_file.setText(filename)
        self.preview_action.setEnabled(True)

    def is_valid_extension(self, file_path):
        """Return True if extension is valid."""
        pattern = re.compile(r"\.\d+t$")
        # remove old pattern with next major update
        if pattern.search(file_path) is not None:
            return True
        elif ".sw8" in file_path:
            return True
        else:
            return False

    def dragEnterEvent(self, a0):
        """Enable drag and drop (1)."""
        if a0 is not None:
            mimedata = a0.mimeData()
            if mimedata is not None:
                if mimedata.hasUrls():
                    a0.acceptProposedAction()
                else:
                    a0.ignore()

    def dropEvent(self, a0):
        """Enable drag and drop(2)."""
        if a0 is not None:
            mimedata = a0.mimeData()
            if mimedata is not None:
                urls = mimedata.urls()
                if len(urls) == 1:
                    file_path = urls[0].toLocalFile()
                    if self.is_valid_extension(file_path):
                        self.input_file.setText(file_path)
                    else:
                        QMessageBox.warning(
                            self,
                            "Invalid File",
                            "Only files with extensions matching .<number>t are supported.",
                        )
                else:
                    QMessageBox.warning(self, "Multiple Files", "Please drop only a single file.")

    def closeEvent(self, a0):
        """Close app properly."""
        if a0 is not None:
            if self.running:
                QMessageBox.critical(
                    QWidget(),
                    "Measurement running!",
                    """Please wait for the measurement to finish. Alternatively,
                    stop the measurement in the terminal before exiting 'Matrix GUI'!""",
                )
                a0.ignore()
                return
            # close sweep generator as well
            if self.sg is not None:
                self.sg.close()
            # clean up measurement list
            while self.meas_list.count() > 0:
                self.removeMeasurement()
            self.save_window_state()
            a0.accept()

    def info_box(self):
        """Display an 'about this app' widget."""
        box = AboutBox(
            "Matrix GUI", get_matrix_icon("matr1x-matrix-gui.png"), matr1x, matr1x.datetimefmt
        )
        box.exec()
        return

    def save_window_state(self) -> None:
        """
        Save application configuration until next startup.

        For convenience, main window geometry, the toolbar placement,
        and the size and position of metadata and configuration pane are
        saved.
        """
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("toolbar_placement", self.toolBarArea(self.toolbar))
        self.settings.setValue("metadata_size", self.w_dockable_metadata.size())
        self.settings.setValue("config_position", self.config_editor.pos())
        self.settings.setValue("config_size", self.config_editor.size())

    def restore_window_state(self) -> None:
        """
        Restore application configuration to look similar to the previous use.

        Main window geometry, the toolbar placement, and the size and
        position of metadata and configuration pane are restored.
        """
        self.addToolBar(
            self.settings.value("toolbar_placement", Qt.ToolBarArea.TopToolBarArea),
            self.toolbar,
        )
        # Just in case it is the first start
        self.resize(self.sizeHint())
        self.restoreGeometry(self.settings.value("geometry", QByteArray()))
        self.resizeDocks(
            [self.w_dockable_metadata],
            [self.settings.value("metadata_size", self.w_dockable_metadata.size()).width()],
            Qt.Orientation.Horizontal,
        )
        self.config_editor.move(self.settings.value("config_position", self.config_editor.pos()))
        self.config_editor.resize(self.settings.value("config_size", self.config_editor.size()))

    def toggle_preferences(self, checked):
        """Open the preferences pane."""
        if checked:
            self.config_editor.show()
            self.config_editor.raise_()
            self.config_editor.activateWindow()
        else:
            self.config_editor.hide()

    def toggle_toolbar_view(self, checked):
        """Toogles the visibility of the toolbar on and off."""
        if checked:
            self.toolbar.show()
        else:
            self.toolbar.hide()

    def initUI(self):
        """Initialize the basic GUI for the graphical version of matrix."""
        self.setWindowTitle("Matrix GUI")
        self.setWindowIcon(get_matrix_icon("matr1x-matrix-gui.png"))
        self.measurements_container = QWidget()
        inner_measurement_layout = QHBoxLayout()
        inner_measurement_layout.setContentsMargins(0, 0, 0, 0)
        self.meas_list = QueueListWidget()
        self.create_actions()
        inner_measurement_layout.addWidget(self.meas_list)
        inner_measurement_layout.addWidget(self.remove_button)
        self.measurements_container.setLayout(inner_measurement_layout)
        self.create_menu()
        self.create_toolbar()
        central_layout = QVBoxLayout()
        self.input_file = LabelWithSignal()
        self.input_file.textChanged.connect(self.parseSystemFromInputFile)
        input_line = QHBoxLayout()
        input_line.addWidget(QLabel("<b>Input: </b>"))
        input_line.addWidget(self.input_file)
        input_line.addStretch()
        central_layout.addLayout(input_line)
        output_line = QHBoxLayout()
        output_line.addWidget(QLabel("<b>Output: </b>"))
        output_line.addWidget(self.outputEdit)
        central_layout.addLayout(output_line)
        central_layout.addWidget(QLabel("Queue"))
        central_layout.addWidget(self.measurements_container)
        current_line = QHBoxLayout()
        current_line.addWidget(QLabel("<b>Current: </b>"))
        self.current_file = QLabel()
        current_line.addWidget(self.current_file)
        current_line.addStretch()
        central_layout.addLayout(current_line)
        self.widget = QWidget()
        self.widget.setLayout(central_layout)
        self.setCentralWidget(self.widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.w_dockable_metadata)
        check_config(matr1x.config)

    def create_actions(self) -> None:
        """Create all QActions of this application."""
        self.remove_button = QToolButton()
        self.remove_button.setStyleSheet(
            """
                    QToolButton {
                        border: none;
                        background: none;
                    }
                """
        )
        self.remove_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.remove_action = QAction(get_matrix_icon("CHAR_-"), "Remove", self)
        self.remove_action.triggered.connect(self.removeMeasurement)
        self.remove_button.setDefaultAction(self.remove_action)
        self.preview_action = QAction(
            get_matrix_icon("matr1x-matrix-preview.png", QColor("RoyalBlue")), "Preview", self
        )
        self.preview_action.triggered.connect(self.openPreview)
        self.preview_action.setEnabled(False)
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
        self.config_action.setCheckable(True)
        self.config_action.toggled.connect(self.toggle_preferences)
        self.config_editor.visibilityChanged.connect(self.config_action.setChecked)
        self.load_action = QAction(get_matrix_icon("SP_DialogOpenButton"), "Open", self)
        self.load_action.triggered.connect(self.showInputDialog)
        self.load_action.setShortcut(QKeySequence.StandardKey.Open)
        self.sweep_action = QAction(
            get_matrix_icon("matr1x-sweep-generator.png", QColor("RoyalBlue")),
            "Generator",
            self,
        )
        self.sweep_action.triggered.connect(self.startSweepGenerator)
        self.auto_filename_action = QAction(
            get_matrix_icon("SP_DriveHDIcon"), "Auto-filename", self
        )
        self.auto_filename_action.setCheckable(True)
        self.auto_filename_action.toggled.connect(self.updateAutoGenFilename)
        self.save_as_action = QAction(get_matrix_icon("SP_DialogSaveButton"), "Save As...", self)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.save_as_action.triggered.connect(self.showOutputDialog)
        self.outputEdit = QLineEdit()
        self.quit_action = QAction("Quit", self)
        if os.name == "nt":
            self.quit_action.setShortcut(QKeySequence.StandardKey.Close)
        else:
            self.quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.quit_action.triggered.connect(self.close)
        self.queue_action = QAction(get_matrix_icon("CHAR_+"), "Queue", self)
        self.queue_action.triggered.connect(self.queueMeasurement)
        self.queue_action.setEnabled(False)
        self.start_action = QAction(get_matrix_icon("CUSTOM_Play"), "Start", self)
        self.start_action.triggered.connect(self.runMatrix)
        self.start_action.setEnabled(False)
        self.w_dockable_metadata = QDockWidget("Metadata", self)
        self.w_meta_view = MetaDataDialog()
        self.w_dockable_metadata.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.w_dockable_metadata.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.w_dockable_metadata.setWidget(self.w_meta_view)
        self.toggle_toolbar_action = QAction("Show Toolbar", self)
        self.toggle_toolbar_action.setShortcut(QKeySequence("Ctrl+1"))
        self.toggle_toolbar_action.setCheckable(True)
        self.toggle_toolbar_action.setChecked(True)
        self.toggle_toolbar_action.triggered.connect(self.toggle_toolbar_view)

    def create_toolbar(self) -> None:
        """Create the Toolbar."""
        self.toolbar = QToolBar("Toolbar")
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.toolbar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.toolbar.setFloatable(False)
        icon_size = get_application_instance().toolbar_icon_size()
        empty = QWidget()
        empty.setFixedWidth(icon_size)
        empty2 = QWidget()
        empty2.setFixedWidth(icon_size)
        self.toolbar.setIconSize(QSize(icon_size, icon_size))
        self.toolbar.addAction(self.load_action)
        self.toolbar.addAction(self.sweep_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.auto_filename_action)
        self.toolbar.addAction(self.save_as_action)
        self.toolbar.addWidget(empty)
        self.toolbar.addAction(self.start_action)
        self.toolbar.addAction(self.queue_action)
        self.toolbar.visibilityChanged.connect(self.toggle_toolbar_action.setChecked)
        self.toolbar.addWidget(empty2)
        self.toolbar.addAction(self.preview_action)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.toolbar.addWidget(spacer)
        self.toolbar.addAction(self.config_action)
        self.addToolBar(self.toolbar)

    def create_menu(self) -> None:
        """Create the menu."""
        menu = self.menuBar()
        assert menu is not None
        # Populate the actions
        file_menu = menu.addMenu("&File")
        assert file_menu is not None
        file_menu.addAction(self.load_action)
        file_menu.addAction(self.sweep_action)
        file_menu.addSeparator()
        file_menu.addAction(self.auto_filename_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.remove_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)  # This gets auto-moved on a Mac
        #
        control_menu = menu.addMenu("&Control")
        assert control_menu is not None
        control_menu.addAction(self.start_action)
        control_menu.addAction(self.queue_action)
        control_menu.addSeparator()
        control_menu.addAction(self.preview_action)
        #
        view_menu = menu.addMenu("&View")
        assert view_menu is not None
        view_menu.addAction(self.toggle_toolbar_action)
        view_menu.addAction(self.matrix_settings_action)
        view_menu.addAction(self.config_action)
        #
        help_menu = menu.addMenu("&Help")
        assert help_menu is not None
        help_menu.addAction(self.about_action)

    def updateAutoGenFilename(self, state):
        """Fill in output filename if required."""
        if state is True:
            input_path = Path(self.input_file.text())
            self.outputEdit.setText(str(input_path.with_suffix("")))

    def showInputDialog(self):
        """Open a QFileDialog with filter for input files."""
        folder = self.input_file.text()
        if "" == folder:
            folder = self.outputEdit.text()
            if "" == folder:
                folder = matr1x.usersfolder
        # remove old pattern with next major update
        filename = QFileDialog.getOpenFileName(
            self, "Select input file", str(folder), "Sweep 8 files (*.sw8);;t files (*.*t)"
        )
        if "" != filename[0]:
            self.input_file.setText(filename[0])
            if self.auto_filename_action.isChecked():
                input_path = Path(self.input_file.text())
                self.outputEdit.setText(str(input_path.with_suffix("")))

    def showOutputDialog(self):
        """Open a QFileDialog with filter for output files."""
        folder = self.outputEdit.text()
        if "" == folder:
            folder = self.input_file.text()
            if "" == folder:
                folder = matr1x.usersfolder
        filename = QFileDialog.getSaveFileName(
            self,
            "Select ma file",
            str(folder),
            "Output files (*.ma8);; Old output files (*.ma7 *.ma6)",
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if "" != filename[0]:
            self.outputEdit.setText(filename[0])

    def startSweepGenerator(self):
        """Run sweep Generator already initialized with system."""
        if self.sg is None:
            self.sg = sweep_generator.MainWindow(
                filename=Path(self.input_file.text()), inputcb=self.input_file.setText
            )
            self.sg.show()
        elif self.sg.isVisible() is False:
            self.sg.show()
        elif self.sg.isMinimized() is True:
            self.sg.showNormal()
        else:
            self.sg.raise_()

    def parseSystemFromInputFile(self, input_file_path: str) -> None:
        """Parse the system from an input file."""
        systemfile: list[str] | None = None
        input_path = Path(input_file_path)
        if not input_path.exists():
            # no file, ignore
            return
        with open_and_error(input_file_path, "r") as (f, err):
            if err:
                QMessageBox.warning(
                    self, "Input file error!", f"Input file cannot be parsed: {err}."
                )
            else:
                assert f is not None
                for line in f:
                    system_pattern = r"^# [Ss]ystem filename : (.+)"
                    if match := re.match(system_pattern, line.strip()):
                        systemfile = match.group(1).split(",")
                        break
                    if "#" != line[0]:
                        # should not occur
                        QMessageBox.warning(
                            self,
                            "System file error!",
                            "No system specified in input file.",
                        )
                        return

                # Check if systemfile was found
                if systemfile is None:
                    QMessageBox.warning(
                        self,
                        "System file error!",
                        "No system specified in input file.",
                    )
                    return
        try:
            # Type assertion to help type checker
            assert systemfile is not None
            system = MergedSystem.from_files(systemfile)
        except ModuleNotFoundError:
            QMessageBox.warning(self, "System file error!", "System file does not exist.")
            return
        except PermissionError:
            QMessageBox.warning(
                self, "System file error!", "Insufficient permissions for system file."
            )
            return

        self.sys_meta_data = system.dcdata

        configurable = [system for system in systemfile if not Path(system.strip()).exists()]

        # Get system information using subprocess (cache for reuse)
        self._cached_system_info = None
        if systemfile:
            try:
                self._cached_system_info = get_system_info(systemfile)
                if not self._cached_system_info:
                    print("Warning: subprocess returned empty system info")
                    self._cached_system_info = {}
            except Exception as e:
                print(f"Warning: Could not get system info for config editor: {e}")
                self._cached_system_info = {}

        matr1x.reload_config()
        self.config_editor.set_systemfile(configurable)
        if systemfile != self.config_editor.full_system_list:
            self.config_editor.set_full_system_list(systemfile)
            self.config_editor.set_system_info(self._cached_system_info or {})
            self.config_editor.update_data()
        self.queue_action.setEnabled(True)

    def queueMeasurement(self):
        """Queue a measurement into the measurement menu."""
        inputFile = self.input_file.text()
        outputFile = self.outputEdit.text()
        if not Path(inputFile).exists():
            QMessageBox.warning(self, "Input file error!", "Input file does not exist.")
            return
        metadata = self.w_meta_view.get_metadata()
        for key in metadata.keys():
            self.sys_meta_data[key] = metadata[key]
        # create parameter set for measurement, make sure to copy the meta data
        config_dict = self.config_editor.get_config_dict()
        parameters = (
            inputFile,
            outputFile,
            self.sys_meta_data.copy(),
            config_dict,
        )
        self.meas_list.add_parameters(parameters)
        if not self.running:
            self.start_action.setEnabled(True)

    def runMatrix(self):
        """Start running the queued measurements."""
        self.running = True
        self.preview_action.setEnabled(False)
        self.start_action.setEnabled(False)
        self.runNextMeasurement()

    def keyPressEvent(self, a0: QKeyEvent | None):
        """Allow to modify systems list with keyboard shortcuts."""
        if self.meas_list.hasFocus():
            if detect_shortcut(a0, QKeySequence(QKeySequence.StandardKey.Delete)):
                self.removeMeasurement()
            if detect_shortcut(a0, QKeySequence(Qt.Key.Key_Backspace)):
                self.removeMeasurement()
        super().keyPressEvent(a0)

    def removeMeasurement(self):
        """Remove selected or last item from measurement list."""
        selected = self.meas_list.selectedItems()
        if len(selected) > 0:
            self.meas_list.takeItem(self.meas_list.row(selected[0]))
        elif 0 < self.meas_list.count():  # remove last item
            self.meas_list.takeItem(self.meas_list.count() - 1)
            self.start_action.setEnabled(False)

    def runNextMeasurement(self):
        """Run the next queued measurement."""
        self.measurement_thread.set_param(self.meas_list.parameters(0), self.config_editor)
        self.measurement_thread.start()

    def processFinished(self):
        """
        Properly finish a mesurement.

        Called when the current measurement is finished, checks whether
        there are further measurements in the queue and runs them in
        case.
        """
        self.meas_list.takeItem(0)
        if self.meas_list.count() > 0 and self.running is True:
            self.runNextMeasurement()
        else:
            self.start_action.setEnabled(False)
            self.running = False

    def openPreview(self):
        """Open a window and preview the (running) measurement."""
        output = Path(self.current_file.text())
        if not output.exists():
            QMessageBox.warning(self, "Preview error!", f"File does not exist ({output})")
        else:
            a = matrix_preview.SweepPreview(self, output)
            a.show()


def main():
    """Set the basic GUI parameters and run."""
    app = MApplication(sys.argv)
    if os.name == "nt":
        # enable modern mode on windows which allows for darkmode
        app.setStyle("fusion")
    elif sys.platform == "darwin":
        set_correct_mac_appname("Matrix GUI")
    app.setDesktopFileName("matrix-gui")
    # we need to ignore this signal here otherwise we are kicked into
    # background when matrix returns. see run_as_fg_process
    if hasattr(signal, "SIGTTOU"):  # signal only on POSIX compliant systems
        signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    with QtGracefulKiller():
        ex = MainWindow()
        ex.show()
        ex.restore_window_state()
        ret = app.exec()
    sys.exit(ret)
