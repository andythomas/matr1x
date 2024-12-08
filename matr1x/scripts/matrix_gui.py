# This file is part of a software collection for data aquisition (matr1x).
# Copyright (C) 2024 matr1x developers
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
import os
import re
import signal
import socket
import subprocess
import sys
from os.path import exists

from PyQt6.QtCore import QSettings, QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QKeyEvent, QKeySequence
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QSpacerItem,
    QStyle,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import matr1x
from matr1x.control.util import QtGracefulKiller
from matr1x.eval import get_latest_datafile
from matr1x.gui_util import (
    AboutBox,
    ConfigEditWidget,
    MApplication,
    MetaDataDialog,
    MIcon,
    MLineEdit,
    detect_shortcut,
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

if os.name == 'nt':
    try:
        from ctypes import windll  # Only exists on Windows.
        myappid = 'python.matr1x.matrix-gui.version'
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass


class ExecThread(QThread):
    """execute the measurement thread."""

    filename_received = pyqtSignal(str)

    def __init__(self):
        """Initialize the thread."""
        QThread.__init__(self)

    def set_param(self, inputFile, outputFile, meta_data):
        """Set mearument parameters and meta-data."""
        self.inputFile = inputFile
        self.outputFile = outputFile
        self.meta_data = meta_data

    def receive_filename(self):
        """Receive filename from command line.

        Matrix checks if the file already exists and subsequently changes its name.
        This way, no existing measurement can be accidently overwritten. The name
        is reported back to the GUI
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('127.0.0.1', MATRIX_GUI_PORT))
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

    def run(self):
        """Start the command line process."""
        cmd = [get_matrix_binary(), "-i", self.inputFile]
        if self.outputFile != "":
            cmd += ["-o", self.outputFile]
        for key, val in self.meta_data.items():
            if key in matr1x.VALID_META_KEYS.keys() and val:
                if matr1x.VALID_META_KEYS[key]:
                    # only pass on allowed (editable) meta keys and only if
                    # data is not None
                    cmd += [f"--dc_{key.lower()}", val]
        print(subprocess.list2cmdline(cmd))
        ret = self.run_as_fg_process(cmd)
        print(f"matrix ended with returncode: {ret}")

    def run_as_fg_process(self, *args, **kwargs):
        # Code of this function was adapted from
        # https://stackoverflow.com/a/66727983/3504203,
        # it was published under CC BY-SA 4.0,
        # https://creativecommons.org/licenses/by-sa/4.0/
        # Modifications were made to use a primitive fallback on MS Windows.
        """Catch signals correctly.

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
        if os.name == 'nt':
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
                child = subprocess.Popen(*args, preexec_fn=new_pgid,
                                         **kwargs)

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
                termios.tcsetattr(sys.stdin.fileno(),
                                  termios.TCSADRAIN, old_attr)

        return ret


class MainWindow(QMainWindow):
    """Define layout, runs everything."""

    def __init__(self):
        super().__init__()
        self.color_palette = QApplication.instance().palette()
        self.initUI()
        self.sg = None
        self.running = False
        self.meas_queue = {}
        self.sys_meta_data = {}
        self.thread = ExecThread()
        self.thread.filename_received.connect(self.outputEdit.setText)
        self.thread.finished.connect(self.processFinished)

        # allow to store the settings
        self.settings = QSettings("matr1x", "gui")

        # Define the allowed extension pattern
        self.allowed_extension_pattern = re.compile(r'\.\d+t$')
        # Enable dragging and dropping onto the widget
        self.setAcceptDrops(True)

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

    def dragEnterEvent(self, event):
        """Enable drag and drop (1)."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Enable drag and drop(2)."""
        urls = event.mimeData().urls()
        if len(urls) == 1:
            file_path = urls[0].toLocalFile()
            if self.is_valid_extension(file_path):
                self.inputEdit.setText(file_path)
            else:
                QMessageBox.warning(
                    self,
                    "Invalid File",
                    "Only files with extensions matching .<number>t are supported.")
        else:
            QMessageBox.warning(self, "Multiple Files",
                                "Please drop only a single file.")

    def closeEvent(self, event):
        """Close app properly."""
        # only close if no measurement is running.
        if self.running:
            QMessageBox.critical(
                QWidget(),
                "Measurement running!",
                """Please wait for the measurement to finish. Alternatively,
                stop the measurement in the terminal before exiting 'Matrix GUI'!""",
            )
            event.ignore()
            return
        # close sweep generator as well
        if self.sg is not None:
            self.sg.close()
        self.saveCurrentState()
        event.accept()

    def info_box(self):
        """Display an 'about this app' widget."""
        box = AboutBox(
            "Matrix GUI", MIcon("matr1x-matrix-gui.png"), matr1x, matr1x.datetimefmt
        )
        box.exec()
        return

    def saveCurrentState(self) -> None:
        """
        Save application configuration until next startup.

        For convenience, main window size, position and layout, the toolbar placement,
        and the size and position of metadata and configuration pane are saved.
        """
        self.settings.setValue("position", self.pos())
        self.settings.setValue("size", self.size())
        self.settings.setValue("toolbar_placement", self.toolBarArea(self.toolbar))
        self.settings.setValue("metadata_size", self.w_dockable_metadata.size())
        self.settings.setValue("config_position", self.config_editor.pos())
        self.settings.setValue("config_size", self.config_editor.size())

    def restoreState(self) -> None:
        """
        Restore application configuration to look similar to the previous use.

        Main window size, position and layout, the toolbar placement, and the size and
        position of metadata and configuration pane are restored.
        """
        self.addToolBar(
            self.settings.value("toolbar_placement", Qt.ToolBarArea.TopToolBarArea),
            self.toolbar,
        )
        recommended_size = self.sizeHint()
        self.move(self.settings.value("position", self.pos()))
        self.resize(self.settings.value("size", recommended_size))
        self.resizeDocks(
            [self.w_dockable_metadata],
            [
                self.settings.value(
                    "metadata_size", self.w_dockable_metadata.size()
                ).width()
            ],
            Qt.Orientation.Horizontal,
        )
        self.config_editor.move(
            self.settings.value("config_position", self.config_editor.pos())
        )
        self.config_editor.resize(
            self.settings.value("config_size", self.config_editor.size())
        )

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
        self.setWindowIcon(MIcon("matr1x-matrix-gui.png"))
        self.inputEdit = MLineEdit()
        self.inputEdit.setReadOnly(True)
        self.inputEdit.textChanged.connect(self.parseSystemFromInputFile)
        # About
        self.about_action = QAction("About", self)
        self.about_action.setMenuRole(QAction.MenuRole.AboutRole)
        self.about_action.triggered.connect(self.info_box)
        # Preferences
        self.config_editor = ConfigEditWidget()
        self.config_editor.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.config_editor)
        self.config_editor.setFloating(True)
        self.config_editor.close()
        self.config_action = QAction(MIcon("CHAR_≡"), "Preferences", self)
        self.config_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        self.config_action.setShortcut(QKeySequence.StandardKey.Preferences)
        self.config_action.setCheckable(True)
        self.config_action.toggled.connect(self.toggle_preferences)
        self.config_editor.visibilityChanged.connect(self.config_action.setChecked)
        # File: Load a recipe
        self.load_action = QAction(MIcon("SP_DialogOpenButton"), "Open", self)
        self.load_action.triggered.connect(self.showInputDialog)
        self.load_action.setShortcut(QKeySequence.StandardKey.Open)
        # File: Open sweep generator
        self.sweep_action = QAction(
            MIcon("matr1x-sweep-generator.png", QColor("RoyalBlue")),
            "Generator",
            self,
        )
        self.sweep_action.triggered.connect(self.startSweepGenerator)
        # File: Autosave
        self.outputEdit = MLineEdit()
        self.outputEdit.setReadOnly(True)
        self.outputAutoGen = QAction(MIcon("SP_DriveHDIcon"), "Autosave", self)
        self.outputAutoGen.setCheckable(True)
        autogen = True
        self.outputAutoGen.setChecked(autogen)
        self.outputAutoGen.setText("Auto-filename")
        # File: Save as...
        self.save_as_action = QAction(MIcon("SP_DialogSaveButton"), "Save As...", self)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.save_as_action.triggered.connect(self.showOutputDialog)
        self.outputAutoGen.toggled.connect(self.updateAutoGenFilename)
        self.updateAutoGenFilename(autogen)
        # Quit
        self.quit_action = QAction("Quit", self)
        if os.name == "nt":
            self.quit_action.setShortcut(QKeySequence.StandardKey.Close)
        else:
            self.quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.quit_action.triggered.connect(self.close)
        # Control: Start
        self.start_action = QAction(MIcon("CUSTOM_Play"), "Start", self)
        self.start_action.triggered.connect(self.queueMeasurement)

        self.w_dockable_metadata = QDockWidget("Metadata", self)
        self.w_meta_view = MetaDataDialog()
        self.w_dockable_metadata.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.w_dockable_metadata.setFeatures(
            QDockWidget.DockWidgetFeature.NoDockWidgetFeatures
        )
        self.w_dockable_metadata.setWidget(self.w_meta_view)
        # View: Toolbar
        self.toggle_toolbar_action = QAction("Show Toolbar", self)
        self.toggle_toolbar_action.setShortcut(QKeySequence("Ctrl+1"))
        self.toggle_toolbar_action.setCheckable(True)
        self.toggle_toolbar_action.setChecked(True)
        self.toggle_toolbar_action.triggered.connect(self.toggle_toolbar_view)

        self.measurements_container = QWidget()
        inner_measurement_layout = QHBoxLayout()
        inner_measurement_layout.setContentsMargins(0, 0, 0, 0)

        self.meas_list = QListWidget()
        self.meas_list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection)
        self.meas_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove)
        self.meas_list.itemClicked.connect(self.selectionChanged)

        self.remove_button = QToolButton()
        self.remove_button.setStyleSheet(
            """
                    QToolButton {
                        border: none;
                        background: none;
                    }
                """
        )
        self.remove_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextUnderIcon
        )
        self.remove_action = QAction(MIcon("CHAR_-"), "Remove", self)
        self.remove_action.triggered.connect(self.removeMeasurement)
        self.remove_button.setDefaultAction(self.remove_action)

        inner_measurement_layout.addWidget(self.meas_list)
        inner_measurement_layout.addWidget(self.remove_button)

        self.measurements_container.setLayout(inner_measurement_layout)

        self.preview_action = QAction(
            MIcon("matr1x-matrix-preview.png", QColor("RoyalBlue")), "Preview", self
        )
        self.preview_action.triggered.connect(self.openPreview)

        self.create_menu()
        self.create_toolbar()

        # Build the main elements
        fGrid = QVBoxLayout()
        fGrid.addWidget(QLabel("Input"))
        fGrid.addWidget(self.inputEdit)
        fGrid.addWidget(QLabel("Queue"))
        fGrid.addWidget(self.measurements_container)
        fGrid.addWidget(QLabel("Output"))
        fGrid.addWidget(self.outputEdit)

        vBox = QVBoxLayout()
        vBox.addLayout(fGrid)
        vertical_stretch = QSpacerItem(
            1, 1, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )
        vBox.addItem(vertical_stretch)
        self.widget = QWidget()
        self.widget.setLayout(vBox)
        self.setCentralWidget(self.widget)

        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self.w_dockable_metadata
        )

    def create_toolbar(self) -> None:
        """Create the Toolbar."""
        self.toolbar = QToolBar("Toolbar")
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.toolbar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.toolbar.setFloatable(False)
        small = QApplication.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize)
        standard = QApplication.style().pixelMetric(
            QStyle.PixelMetric.PM_ToolBarIconSize
        )
        intermediate = int((small + standard) / 2)
        empty = QWidget()
        empty.setFixedWidth(intermediate)
        empty2 = QWidget()
        empty2.setFixedWidth(intermediate)
        self.toolbar.setIconSize(QSize(intermediate, intermediate))
        self.toolbar.addAction(self.load_action)
        self.toolbar.addAction(self.sweep_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.outputAutoGen)
        self.toolbar.addAction(self.save_as_action)
        self.toolbar.addWidget(empty)
        self.toolbar.addAction(self.start_action)
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
        # Populate the actions
        file_menu = menu.addMenu("&File")
        file_menu.addAction(self.load_action)
        file_menu.addAction(self.sweep_action)
        file_menu.addSeparator()
        file_menu.addAction(self.outputAutoGen)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.remove_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)  # This gets auto-moved on a Mac
        #
        control_menu = menu.addMenu("&Control")
        control_menu.addAction(self.start_action)
        control_menu.addSeparator()
        control_menu.addAction(self.preview_action)
        #
        view_menu = menu.addMenu("&View")
        view_menu.addAction(self.toggle_toolbar_action)
        view_menu.addAction(self.config_action)
        #
        help_menu = menu.addMenu("&Help")
        help_menu.addAction(self.about_action)

    def updateAutoGenFilename(self, state):
        """Disable output filename field while running."""
        if state is True:
            # disable output filename fields
            self.outputEdit.setEnabled(False)
            self.save_as_action.setEnabled(False)
        if state is False:
            self.outputEdit.setEnabled(True)
            self.save_as_action.setEnabled(True)
        if self.outputAutoGen.isChecked():
            self.outputEdit.setReadOnly(True)
        else:
            self.outputEdit.setReadOnly(False)

    def showInputDialog(self):
        """Open a QFileDialog with filter for input files."""
        folder = self.inputEdit.text()
        if "" == folder:
            folder = self.outputEdit.text()
            if "" == folder:
                folder = matr1x.usersfolder
        # remove old pattern with next major update
        filename = QFileDialog.getOpenFileName(
            self, "Select input file", folder, "Sweep 8 files (*.sw8);;t files (*.*t)"
        )
        if "" != filename[0]:
            self.inputEdit.setText(filename[0])

    def showOutputDialog(self):
        """Open a QFileDialog with filter for output files."""
        folder = self.outputEdit.text()
        if "" == folder:
            folder = self.inputEdit.text()
            if "" == folder:
                folder = matr1x.usersfolder
        filename = QFileDialog.getSaveFileName(
            self, 'Select ma file', folder,
            "Output files (*.ma8);; Old output files (*.ma7 *.ma6)",
            options=QFileDialog.Option.DontConfirmOverwrite)
        if "" != filename[0]:
            self.outputEdit.setText(filename[0])

    def startSweepGenerator(self):
        """Run sweep Generator already initialized with system."""
        if self.sg is None:
            self.sg = sweep_generator.MainWindow(
                filename=self.inputEdit.text(), inputcb=self.sGsetInputFile
            )
            self.sg.show()
        elif self.sg.isVisible() is False:
            self.sg.show()
        elif self.sg.isMinimized() is True:
            self.sg.showNormal()
        else:
            self.sg.raise_()

    def sGsetInputFile(self, filename):
        """Can be called externally for setting the input file."""
        self.inputEdit.setText(filename)

    def selectionChanged(self, item):
        """Display correct information from measurement queue."""
        item_index = int(item.text().split("-")[0])
        elem = self.meas_queue[item_index]
        self.inputEdit.setText(elem[0])
        if elem[1] != "":
            self.outputEdit.setText(elem[1])
        self.w_meta_view.load_initial_values(elem[2])

    def parseSystemFromInputFile(self, text):
        """Parse the system from an input file."""
        systemfile = None
        if not os.path.exists(text):
            # no file, ignore
            return
        with open_and_error(text, "r") as (f, err):
            if err:
                QMessageBox.warning(
                    self, "Input file error!", f"Input file cannot be parsed: {err}."
                )
            else:
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
        try:
            system = MergedSystem.from_files(systemfile)
        except ModuleNotFoundError:
            QMessageBox.warning(
                self, "System file error!", "System file does not exist."
            )
            return
        except PermissionError:
            QMessageBox.warning(
                self, "System file error!", "Insufficient permissions for system file."
            )
            return

        self.sys_meta_data = system.dcdata
        configurable = [
            system for system in systemfile if not os.path.exists(system.strip())
        ]
        self.config_editor.update_data(configurable)

    def queueMeasurement(self):
        """Queue a measurement into the measurement menu."""
        inputFile = self.inputEdit.text()
        if self.outputAutoGen.isChecked():
            outputFile = ""
        else:
            outputFile = self.outputEdit.text()
        if "" == inputFile:
            QMessageBox.warning(self, "Input file error!", "No input file specified.")
            return
        if not exists(inputFile):
            QMessageBox.warning(self, "Input file error!", "Input file does not exist.")
            return
        metadata = self.w_meta_view.get_metadata()
        for key in metadata.keys():
            self.sys_meta_data[key] = metadata[key]
        # create parameter set for measurement, make sure to copy the meta data
        param = (inputFile, outputFile, self.sys_meta_data.copy())
        index = len(self.meas_queue)
        self.meas_queue[index] = param
        self.meas_list.addItem(f"{index} - {os.path.basename(inputFile)} - "
                               f"{os.path.basename(outputFile)} -")
        if self.meas_list.count() > 0:
            last_item = self.meas_list.item(self.meas_list.count() - 1)
            self.meas_list.scrollToItem(last_item)
        if self.running is True:
            pass
        else:
            self.runMatrix()

    def stopQueue(self):
        """Reset the queue button and reconnects to running functionality."""
        self.running = False

    def runMatrix(self):
        """Start running the queued measurements."""
        self.running = True
        self.start_action.setIcon(MIcon("CHAR_+"))
        self.start_action.setText("Queue")
        self.runNextMeasurement()

    def keyPressEvent(self, event: QKeyEvent):
        """Allow to modify systems list with keyboard shortcuts."""
        if self.meas_list.hasFocus():
            if detect_shortcut(event, QKeySequence(QKeySequence.StandardKey.Delete)):
                self.removeMeasurement()
            if detect_shortcut(event, QKeySequence(Qt.Key.Key_Backspace)):
                self.removeMeasurement()
        super().keyPressEvent(event)

    def removeMeasurement(self):
        """Remove selected or last item from meas_list."""
        selected = self.meas_list.selectedItems()
        if len(selected) > 0:
            self.meas_list.takeItem(self.meas_list.row(selected[0]))
        elif 0 < self.meas_list.count():  # remove last item
            self.meas_list.takeItem(self.meas_list.count()-1)

    def runNextMeasurement(self):
        """Run the next queued measurement."""
        item = int(self.meas_list.takeItem(0).text().split("-")[0])
        self.thread.set_param(*self.meas_queue[item])
        self.thread.start()

    def processFinished(self):
        """Properly finish a mesurement.

        Called when the current measurement is finished, checks whether
        there are further measurements in the queue and runs them in case
        After all measurements have been run, resets the queue.
        """
        if self.meas_list.count() > 0 and self.running is True:
            self.runNextMeasurement()
        else:
            self.start_action.setIcon(MIcon("CUSTOM_Play"))
            self.start_action.setText("Start")
            self.running = False
        # if all measurements were run, reset the measurement counter
        if self.meas_list.count() == 0:
            self.meas_queue = {}

    def openPreview(self):
        """Open a window and preview the (running) measurement."""
        output = self.outputEdit.text()
        if "" == output:  # try to obtain last filename from input file
            infile = self.inputEdit.text()
            if "" == infile:
                QMessageBox.warning(
                    self, "Preview error!", "Please specify a filename."
                )
                return
            output = get_latest_datafile(basename=infile)
        if output is None:
            QMessageBox.warning(
                self, "Preview error!", f"File does not exist ({output})"
            )
        elif not exists(output):
            QMessageBox.warning(
                self, "Preview error!", f"File does not exist ({output})"
            )
        a = matrix_preview.SweepPreview(self, output)
        a.show()


def main():
    """Set the basic GUI parameters and run."""
    app = MApplication(sys.argv)
    if os.name == 'nt':
        # enable modern mode on windows which allows for darkmode
        app.setStyle('fusion')
    elif sys.platform == "darwin":
        set_correct_mac_appname("Matrix GUI")
    app.setDesktopFileName("matrix-gui")
    # we need to ignore this signal here otherwise we are kicked into
    # background when matrix returns. see run_as_fg_process
    if 'SIGTTOU' in dir(signal):  # signal only on POSIX compliant systems
        signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    with QtGracefulKiller():
        ex = MainWindow()
        ex.show()
        ex.restoreState()
        ret = app.exec()
    sys.exit(ret)
