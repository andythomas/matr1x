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
"""Provide a graphical user interface for matrix measurements."""

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import shiboken6
from pydantic import ValidationError
from PySide6.QtCore import QByteArray, QDateTime, QPoint, QSize, Qt, QThread, Signal
from PySide6.QtGui import QAction, QCloseEvent, QColor, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QSizePolicy,
    QTableWidgetItem,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import matr1x
from matr1x.error_handling import Error, install_error_handler
from matr1x.gui_util import (
    AboutBox,
    ConfigEditWidget,
    FileDropMixin,
    LoggingWindow,
    MApplication,
    MetaDataDialog,
    ReadOnlyTable,
    SaferQSettings,
    check_config,
    detect_shortcut,
    get_matrix_icon,
    get_system_info,
    open_matrix_toml,
    protected_restore,
)
from matr1x.models import (
    Datafile,
    Envelope,
    ErrorMessage,
    Header,
    MeasuredValues,
    Message,
    SetValues,
    SystemInfo,
    Telemetry,
)
from matr1x.post_install import (
    check_desktop_integration,
    post_installation,
    remove_desktop_integration,
)
from matr1x.scripts import (
    sweep_generator,
)
from matr1x.system import MergedSystem
from matr1x.util import get_matrix_binary, open_and_error

logger = logging.getLogger(Path(__file__).name)

if sys.platform == "win32":
    try:
        from ctypes import windll

        myappid = "python.matr1x.matrix-gui.version"
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass


class LabelWithSignal(QLabel):
    """A QLabel that emits a signal if the text changes."""

    textChanged = Signal(str)

    def setText(self, a0: str) -> None:
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

    def __init__(self) -> None:
        """Initialize the list widget with an empty list."""
        super().__init__()
        self.data_list = []
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setAlternatingRowColors(True)
        self.model().rowsMoved.connect(self.update_data_order)

    def add_parameters(self, parameters: tuple) -> None:
        """
        Add a set of parameters.

        Parameters
        ----------
        parameters : tuple
            The tuple to be added:
            (inputFile, outputFile, metadata_dict, config_dict).
        """
        output = Path(parameters[1]).name if parameters[1] else "<use input>"
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
        list_item = QListWidgetItem(list_entry)
        super().addItem(list_item)

    def takeItem(self, row: int) -> QListWidgetItem:
        """
        Delete the item.

        Parameters
        ----------
        row : int
            The row to be deleted.
        """
        self.data_list.pop(row)
        return super().takeItem(row)

    def update_data_order(self) -> None:
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


class GuiThread(QThread):
    """Execute the measurement thread."""

    filename_received = Signal(str)
    telemetry_received = Signal(Telemetry)
    tabledata_received = Signal(Envelope)

    def __init__(self) -> None:
        """Initialize the thread."""
        QThread.__init__(self)
        self.proc: subprocess.Popen | None = None

    def set_parameters(self, params: tuple, config_editor: ConfigEditWidget) -> None:
        """Set measurement parameters and meta-data."""
        self.inputFile, self.outputFile, self.meta_data, self.config_dict = params
        self.config_editor: ConfigEditWidget = config_editor

    def run(self) -> None:
        """Start the command line thread."""
        tmp_config_file = None
        if hasattr(self, "config_dict") and self.config_dict:
            tmp_config_file = self.config_editor.write_config(self.config_dict)
        cmd = [get_matrix_binary(), "-i", self.inputFile, "-pj"]
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
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
            )
            if self.proc.stdout is not None:
                for line in self.proc.stdout:
                    self.process_received_data(line)
            self.proc.wait()
            logger.info("matrix ended with returncode: %s", self.proc.returncode)
        finally:
            if tmp_config_file and tmp_config_file.exists():
                tmp_config_file.unlink()

    def process_received_data(self, line: str) -> None:
        """
        Process the data from the measurement thread.

        Parameters
        ----------
        line: str
            The line that was received.
        """
        try:
            env = Envelope.model_validate_json(line)
        except ValidationError:
            logger.warning("Corrupted or unknown data received: %s", line)
            return
        data = env.payload
        if isinstance(data, Message):
            logger.info(data.message)
        elif isinstance(data, Datafile):
            self.filename_received.emit(data.datafile)
        elif isinstance(data, Telemetry):
            self.telemetry_received.emit(data)
        elif isinstance(data, (SetValues, MeasuredValues, Header)):
            self.tabledata_received.emit(env)
        elif isinstance(data, ErrorMessage):
            logger.error(data.error)

    def _send_stdin(self, cmd: str) -> None:
        """
        Write a non-blocking command to the subprocess stdin.

        Parameters
        ----------
        cmd : str
            The command string to send.
        """
        if self.proc is not None and self.proc.stdin is not None:
            self.proc.stdin.write(cmd)
            self.proc.stdin.flush()

    def pause(self) -> None:
        """Pause the thread."""
        self._send_stdin("p\n")

    def abort(self) -> None:
        """Send abort to the thread."""
        self._send_stdin("a\n")

    def finish(self) -> None:
        """Send finish to the thread."""
        self._send_stdin("f\n")

    def kill(self) -> None:
        """Kill the thread."""
        if self.proc is not None:
            self.proc.kill()
            logger.warning("Measurement thread was manually killed.")


@dataclass(frozen=True)
class ActionGroup:
    """Actions to be utilized in the GUI."""

    remove: QAction
    preview: QAction
    matrix_settings: QAction
    about: QAction
    config: QAction
    sweep: QAction
    auto_filename: QAction
    save_as: QAction
    queue: QAction
    start: QAction
    pause: QAction
    abort: QAction
    finish: QAction
    kill: QAction
    toggle_toolbar: QAction
    show_log: QAction
    load: QAction
    quit: QAction
    post_install: QAction
    remove_desktop_integration: QAction


@dataclass(frozen=True)
class WidgetGroup:
    """UI widgets to be utilized in the GUI."""

    meas_list: QueueListWidget
    config_editor: ConfigEditWidget
    output_edit: QLineEdit
    dockable_metadata: QDockWidget
    meta_view: MetaDataDialog
    input_file: LabelWithSignal
    current_file: QLabel
    progress: QLabel
    progressbar: QProgressBar
    table: ReadOnlyTable


class UIBuilder:
    """Build the GUI and provide widgets and actions."""

    def __init__(self, window: QMainWindow) -> None:
        self.window: QMainWindow = window
        self.actions: ActionGroup = self._create_actions()
        self.widgets: WidgetGroup = self._create_widgets()
        self.toolbar: QToolBar = self._create_toolbar()
        self._create_gui()
        self._create_menu()

    def _create_widgets(self) -> WidgetGroup:
        """Create all UI widgets of this application."""
        self.measurements_container = QWidget()
        meas_list = QueueListWidget()
        config_editor = ConfigEditWidget()
        config_editor.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        output_edit = QLineEdit()
        input_file = LabelWithSignal()
        current_file = QLabel()
        dockable_metadata = QDockWidget("Metadata", self.window)
        meta_view = MetaDataDialog()
        dockable_metadata.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        dockable_metadata.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        dockable_metadata.setWidget(meta_view)
        self.central_widget = QWidget()
        self.input_label = QLabel("Input: ")
        self.output_label = QLabel("Output: ")
        self.queue_label = QLabel("Queue")
        self.file_label = QLabel("Current file: ")
        table = ReadOnlyTable()
        table.setColumnCount(4)
        table.setRowCount(1)
        table.setHorizontalHeaderLabels(["Parameter", "Set value", "Readout value", "unit"])
        width = (table.verticalHeader().width() + table.horizontalHeader().length()) * 1.04
        table.setFixedWidth(int(width))
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        progress = QLabel("Measurement idle.")
        progressbar = QProgressBar()
        return WidgetGroup(
            meas_list=meas_list,
            config_editor=config_editor,
            output_edit=output_edit,
            dockable_metadata=dockable_metadata,
            meta_view=meta_view,
            input_file=input_file,
            current_file=current_file,
            progressbar=progressbar,
            progress=progress,
            table=table,
        )

    def _create_gui(self) -> None:
        """Create and set up all GUI layouts."""
        measurement = QVBoxLayout()
        measurement.addWidget(self.widgets.table)
        measurement.addWidget(self.widgets.progress)
        measurement.addWidget(self.widgets.progressbar)
        queue_n_measurement = QHBoxLayout()
        queue_n_measurement.setContentsMargins(0, 0, 0, 0)
        queue_n_measurement.addWidget(self.widgets.meas_list, 1)
        queue_n_measurement.addWidget(self.remove_button)
        queue_n_measurement.addLayout(measurement, 0)
        self.measurements_container.setLayout(queue_n_measurement)
        self.window.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.widgets.config_editor)
        self.widgets.config_editor.setFloating(True)
        self.widgets.config_editor.close()
        central_layout = QVBoxLayout()
        input_line = QHBoxLayout()
        input_line.addWidget(self.input_label)
        input_line.addWidget(self.widgets.input_file)
        input_line.addStretch()
        central_layout.addLayout(input_line)
        output_line = QHBoxLayout()
        output_line.addWidget(self.output_label)
        output_line.addWidget(self.widgets.output_edit)
        central_layout.addLayout(output_line)
        central_layout.addWidget(self.queue_label)
        central_layout.addWidget(self.measurements_container)
        current_line = QHBoxLayout()
        current_line.addWidget(self.file_label)
        current_line.addWidget(self.widgets.current_file)
        current_line.addStretch()
        central_layout.addLayout(current_line)
        self.central_widget.setLayout(central_layout)
        self.window.setCentralWidget(self.central_widget)
        self.window.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self.widgets.dockable_metadata
        )

    def _create_actions(self) -> ActionGroup:
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
        remove = QAction(get_matrix_icon("CHAR_-"), "Remove\nQueue\nItem", self.window)
        self.remove_button.setDefaultAction(remove)
        load = QAction(get_matrix_icon("SP_DialogOpenButton"), "Open", self.window)
        load.setShortcut(QKeySequence.StandardKey.Open)
        quit_app = QAction("Quit", self.window)
        if os.name == "nt":
            quit_app.setShortcut(QKeySequence.StandardKey.Close)
        else:
            quit_app.setShortcut(QKeySequence.StandardKey.Quit)
        preview = QAction(
            get_matrix_icon("matr1x-matrix-preview.png", QColor("RoyalBlue")),
            "Preview",
            self.window,
        )
        preview.setEnabled(False)
        matrix_settings = QAction("Show matrix toml", self.window)
        matrix_settings.setMenuRole(QAction.MenuRole.PreferencesRole)
        matrix_settings.setShortcut(QKeySequence.StandardKey.Preferences)
        matrix_settings.triggered.connect(open_matrix_toml)
        about = QAction("About", self.window)
        about.setMenuRole(QAction.MenuRole.AboutRole)
        config = QAction(get_matrix_icon("CHAR_≡"), "Device config", self.window)
        config.setCheckable(True)
        sweep = QAction(
            get_matrix_icon("matr1x-sweep-generator.png", QColor("RoyalBlue")),
            "Generator",
            self.window,
        )
        auto_filename = QAction(get_matrix_icon("SP_DriveHDIcon"), "Auto-filename", self.window)
        auto_filename.setCheckable(True)
        save_as = QAction(get_matrix_icon("SP_DialogSaveButton"), "Save As...", self.window)
        save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        queue = QAction(get_matrix_icon("CHAR_+"), "Queue", self.window)
        queue.setEnabled(False)
        start = QAction(get_matrix_icon("CUSTOM_Play"), "Start", self.window)
        start.setEnabled(False)
        pause = QAction(get_matrix_icon("CUSTOM_Pause"), "Pause", self.window)
        pause.setCheckable(True)
        pause.setChecked(False)
        pause.setEnabled(False)
        abort = QAction(
            get_matrix_icon("CUSTOM_Stop", color=QColor("#B71C1C")), "Abort", self.window
        )
        abort.setEnabled(False)
        finish = QAction(
            get_matrix_icon("CUSTOM_Stop", color=QColor("#388E3C")), "Finish", self.window
        )
        finish.setEnabled(False)
        kill = QAction(get_matrix_icon("SP_DialogCancelButton"), "Kill", self.window)
        kill.setEnabled(False)
        toggle_toolbar = QAction("Show Toolbar", self.window)
        toggle_toolbar.setShortcut(QKeySequence("Ctrl+1"))
        toggle_toolbar.setCheckable(True)
        toggle_toolbar.setChecked(True)
        show_log = QAction("Show Log Window", self.window)
        show_log.setCheckable(True)
        post_install = QAction("Install Desktop Integration", self.window)
        remove_desktop_integration = QAction("Remove Desktop Integration", self.window)
        return ActionGroup(
            remove=remove,
            preview=preview,
            matrix_settings=matrix_settings,
            about=about,
            config=config,
            sweep=sweep,
            auto_filename=auto_filename,
            save_as=save_as,
            queue=queue,
            start=start,
            pause=pause,
            abort=abort,
            finish=finish,
            kill=kill,
            toggle_toolbar=toggle_toolbar,
            show_log=show_log,
            load=load,
            quit=quit_app,
            post_install=post_install,
            remove_desktop_integration=remove_desktop_integration,
        )

    def _create_toolbar(self) -> QToolBar:
        """Create the Toolbar."""
        toolbar = QToolBar("Toolbar")
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        toolbar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        toolbar.setFloatable(False)
        icon_size = MApplication.instance().toolbar_icon_size()
        empty = QWidget()
        empty.setFixedWidth(icon_size)
        empty2 = QWidget()
        empty2.setFixedWidth(icon_size)
        toolbar.setIconSize(QSize(icon_size, icon_size))
        toolbar.addAction(self.actions.load)
        toolbar.addAction(self.actions.sweep)
        toolbar.addSeparator()
        toolbar.addAction(self.actions.auto_filename)
        toolbar.addAction(self.actions.save_as)
        toolbar.addWidget(empty)
        toolbar.addAction(self.actions.queue)
        toolbar.addAction(self.actions.start)
        toolbar.addAction(self.actions.pause)
        toolbar.addAction(self.actions.abort)
        toolbar.addAction(self.actions.finish)
        toolbar.visibilityChanged.connect(self.actions.toggle_toolbar.setChecked)
        toolbar.addWidget(empty2)
        toolbar.addAction(self.actions.preview)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        toolbar.addWidget(spacer)
        toolbar.addAction(self.actions.config)
        self.window.addToolBar(toolbar)
        return toolbar

    def _create_menu(self) -> None:
        """Create the menu."""
        menu = self.window.menuBar()
        file_menu = menu.addMenu("&File")
        file_menu.addAction(self.actions.load)
        file_menu.addAction(self.actions.sweep)
        file_menu.addSeparator()
        file_menu.addAction(self.actions.auto_filename)
        file_menu.addAction(self.actions.save_as)
        file_menu.addSeparator()
        file_menu.addAction(self.actions.remove)
        file_menu.addSeparator()
        file_menu.addAction(self.actions.quit)  # This gets auto-moved on a Mac
        control_menu = menu.addMenu("&Control")
        control_menu.addAction(self.actions.queue)
        control_menu.addAction(self.actions.start)
        control_menu.addAction(self.actions.pause)
        control_menu.addAction(self.actions.abort)
        control_menu.addAction(self.actions.finish)
        control_menu.addAction(self.actions.kill)
        control_menu.addSeparator()
        control_menu.addAction(self.actions.preview)
        view_menu = menu.addMenu("&View")
        view_menu.addAction(self.actions.toggle_toolbar)
        view_menu.addAction(self.actions.matrix_settings)
        view_menu.addAction(self.actions.config)
        help_menu = menu.addMenu("&Help")
        help_menu.addAction(self.actions.about)
        help_menu.addAction(self.actions.show_log)
        help_menu.addSeparator()
        help_menu.addAction(self.actions.post_install)
        help_menu.addAction(self.actions.remove_desktop_integration)


class MainWindow(FileDropMixin, QMainWindow):
    """Runs the logical code."""

    def __init__(self) -> None:
        super().__init__()
        self.log_window = LoggingWindow(parent=self)
        self.log_window.hide()
        logger.info("matrix-gui starting")
        self.setWindowTitle("Matrix GUI")
        self.setWindowIcon(get_matrix_icon("matr1x-matrix-gui.png"))
        self.ui = UIBuilder(self)
        self.ui.actions.remove.triggered.connect(self.remove_measurement)
        self.ui.actions.preview.triggered.connect(self.open_preview)
        self.ui.actions.about.triggered.connect(self.info_box)
        self.ui.actions.config.toggled.connect(self.toggle_preferences)
        self.ui.widgets.config_editor.visibilityChanged.connect(self.ui.actions.config.setChecked)
        self.ui.actions.sweep.triggered.connect(self.start_sweep_generator)
        self.ui.actions.auto_filename.toggled.connect(self.update_auto_gen_filename)
        self.ui.actions.save_as.triggered.connect(self.show_output_dialog)
        self.ui.actions.queue.triggered.connect(self.queue_measurement)
        self.ui.actions.start.triggered.connect(self.run_matrix)
        self.ui.actions.toggle_toolbar.triggered.connect(self.toggle_toolbar_view)
        self.ui.actions.show_log.triggered.connect(self.toggle_log_window)
        self.log_window.visibility_changed.connect(self._on_log_window_visibility_changed)
        self._on_log_window_visibility_changed(self.log_window.isVisible())
        self.ui.actions.load.triggered.connect(self.show_input_dialog)
        self.ui.actions.quit.triggered.connect(self.close)
        self.ui.actions.post_install.triggered.connect(post_installation)
        self.ui.actions.remove_desktop_integration.triggered.connect(remove_desktop_integration)
        self.ui.widgets.input_file.textChanged.connect(self.parse_system_from_inputfile)
        check_config(matr1x.config)
        self.sg: QMainWindow | None = None
        self.running = False
        self.sys_meta_data = {}
        self.measurement_thread = GuiThread()
        self.measurement_thread.filename_received.connect(self.process_filename)
        self.measurement_thread.telemetry_received.connect(self.process_telemetry)
        self.measurement_thread.tabledata_received.connect(self.process_tabledata)
        self.measurement_thread.finished.connect(self.process_finished)
        self.ui.actions.pause.triggered.connect(self.measurement_thread.pause)
        self.ui.actions.abort.triggered.connect(self.measurement_thread.abort)
        self.ui.actions.finish.triggered.connect(self.measurement_thread.finish)
        self.ui.actions.kill.triggered.connect(self.measurement_thread.kill)
        self.setAcceptDrops(True)
        self.setValidExtensions([".sw8", re.compile(r"\.\d+t$")])
        self.file_dropped.connect(lambda file: self.ui.widgets.input_file.setText(file))
        self.settings = SaferQSettings("matr1x", "gui")
        self._cached_system_info: SystemInfo | None = None
        check_desktop_integration()

    def process_filename(self, filename: str) -> None:
        """
        Handle the filename from the measurement thread.

        Parameters
        ----------
        filename : str
            The filename given to the measurement file.
        """
        self.ui.widgets.current_file.setText(filename)
        self.ui.actions.preview.setEnabled(True)

    def process_telemetry(self, telemetry: Telemetry) -> None:
        """
        Show the progress data.

        Parameters
        ----------
        telemetry : TelemetryContent
            The telemetry data received from the measurement thread.
        """
        self.ui.widgets.progressbar.setMaximum(telemetry.points)
        self.ui.widgets.progressbar.setValue(telemetry.point)
        if telemetry.remaining is not None:
            self.ui.widgets.progress.setText(str(telemetry))

    def process_tabledata(self, env: Envelope) -> None:
        """
        Show the data in the table view.

        Parameters
        ----------
        env: Envelope
            The table data received from the measurement thread.
        """
        data = env.payload
        if isinstance(data, Header):
            count = len(data.columns)
            self.ui.widgets.table.setRowCount(count)
            for index, item in enumerate(data.columns):
                column = QTableWidgetItem(str(item))
                unit = QTableWidgetItem(str(data.units[index]))
                column.setTextAlignment(
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                )
                unit.setTextAlignment(
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                )
                self.ui.widgets.table.setItem(index, 0, column)
                self.ui.widgets.table.setItem(index, 3, unit)
        elif isinstance(data, SetValues):
            for index, item in enumerate(data.set):
                if item is not None:
                    value = QTableWidgetItem(str(item))
                else:
                    value = QTableWidgetItem("")
                value.setTextAlignment(
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                )
                self.ui.widgets.table.setItem(index, 1, value)
        elif isinstance(data, MeasuredValues):
            for index, item in enumerate(data.measured):
                if item is not None:
                    value = QTableWidgetItem(str(item))
                else:
                    value = QTableWidgetItem("")
                value.setTextAlignment(
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                )
                self.ui.widgets.table.setItem(index, 2, value)
            try:
                utc = QDateTime.fromSecsSinceEpoch(int(item), Qt.TimeSpec.UTC)
                local = utc.toLocalTime()
                value = QTableWidgetItem(local.toString("HH:mm:ss"))
                value.setTextAlignment(
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                )
                value.setToolTip("Converted to local time.")
                self.ui.widgets.table.setItem(index, 2, value)
            except Exception:
                logger.debug("Could not convert timestamp to local time.")

    def closeEvent(self, a0: QCloseEvent) -> None:
        """Close app properly."""
        if self.running:
            QMessageBox.warning(
                QWidget(),
                "Measurement running!",
                """Please wait for the measurement to finish.""",
            )
            a0.ignore()
            return
        if self.sg is not None:
            self.sg.close()
        while self.ui.widgets.meas_list.count() > 0:
            self.remove_measurement()
        self.save_window_state()
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.log_window.log_handler)
        self.log_window.deleteLater()
        a0.accept()

    def info_box(self) -> None:
        """Display an 'about this app' widget."""
        box = AboutBox(
            "Matrix GUI", get_matrix_icon("matr1x-matrix-gui.png"), matr1x, matr1x.datetimefmt
        )
        box.exec()

    def save_window_state(self) -> None:
        """Save application configuration until next startup."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("toolbar_position", self.toolBarArea(self.ui.toolbar).value)
        self.settings.setValue("metadata_size", self.ui.widgets.dockable_metadata.size())
        self.settings.setValue("config_position", self.ui.widgets.config_editor.pos())
        self.settings.setValue("config_size", self.ui.widgets.config_editor.size())
        if shiboken6.isValid(self.log_window):
            self.settings.setValue("log_window/position", self.log_window.pos())
            self.settings.setValue("log_window/size", self.log_window.size())

    def restore_window_state(self) -> None:
        """Restore application configuration from the previous use."""
        toolbar_pos = self.settings.safer_value(
            "toolbar_position", Qt.ToolBarArea.TopToolBarArea.value, type=int
        )
        self.addToolBar(Qt.ToolBarArea(toolbar_pos), self.ui.toolbar)
        # Just in case it is the first start
        self.resize(self.sizeHint())
        self.restoreGeometry(self.settings.safer_value("geometry", QByteArray(), type=QByteArray))
        self.resizeDocks(
            [self.ui.widgets.dockable_metadata],
            [
                self.settings.safer_value(
                    "metadata_size", self.ui.widgets.dockable_metadata.size(), type=QSize
                ).width()
            ],
            Qt.Orientation.Horizontal,
        )
        self.ui.widgets.config_editor.move(
            self.settings.safer_value(
                "config_position", self.ui.widgets.config_editor.pos(), type=QPoint
            )
        )
        self.ui.widgets.config_editor.resize(
            self.settings.safer_value(
                "config_size", self.ui.widgets.config_editor.size(), type=QSize
            )
        )
        self.log_window.move(
            self.settings.safer_value("log_window/position", self.log_window.pos(), type=QPoint)
        )
        self.log_window.resize(
            self.settings.safer_value("log_window/size", self.log_window.size(), type=QSize)
        )

    def toggle_log_window(self) -> None:
        """Toggle the visibility of the logging window."""
        if self.log_window.isVisible():
            self.log_window.hide()
        else:
            self.log_window.show()
            self.log_window.raise_()
            self.log_window.activateWindow()

    def _on_log_window_visibility_changed(self, visible: bool) -> None:
        """Keep 'Show Log Window' action label/checked state in sync."""
        action = self.ui.actions.show_log
        action.setChecked(visible)
        action.setText("Hide Log Window" if visible else "Show Log Window")

    def toggle_preferences(self, checked: bool) -> None:
        """
        Toggle the preferences pane.

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

    def toggle_toolbar_view(self, checked: bool) -> None:
        """
        Toogles the visibility of the toolbar.

        Parameters
        ----------
        checked: bool
            Show (True) or hide (False) the toolbar.
        """
        if checked:
            self.ui.toolbar.show()
        else:
            self.ui.toolbar.hide()

    def update_auto_gen_filename(self, state: bool) -> None:
        """Fill in output filename if required."""
        if state:
            input_path = Path(self.ui.widgets.input_file.text())
            self.ui.widgets.output_edit.setText(str(input_path.with_suffix("")))

    def show_input_dialog(self) -> None:
        """Open a QFileDialog with filter for input files."""
        folder = self.ui.widgets.input_file.text()
        if folder == "":
            folder = self.ui.widgets.output_edit.text()
            if folder == "":
                folder = matr1x.usersfolder
        # remove old pattern with next major update
        filename = QFileDialog.getOpenFileName(
            self, "Select input file", str(folder), "Sweep 8 files (*.sw8);;t files (*.*t)"
        )
        if filename[0] != "":
            self.ui.widgets.input_file.setText(filename[0])
            if self.ui.actions.auto_filename.isChecked():
                input_path = Path(self.ui.widgets.input_file.text())
                self.ui.widgets.output_edit.setText(str(input_path.with_suffix("")))

    def show_output_dialog(self) -> None:
        """Open a QFileDialog with filter for output files."""
        folder = self.ui.widgets.output_edit.text()
        if folder == "":
            folder = self.ui.widgets.input_file.text()
            if folder == "":
                folder = matr1x.usersfolder
        filename = QFileDialog.getSaveFileName(
            self,
            "Select ma file",
            str(folder),
            "Output files (*.ma8);; Old output files (*.ma7 *.ma6)",
            options=QFileDialog.Option.DontConfirmOverwrite,
        )
        if filename[0] != "":
            self.ui.widgets.output_edit.setText(filename[0])

    def start_sweep_generator(self) -> None:
        """Run sweep Generator already initialized with system."""
        if self.sg is None:
            self.sg = sweep_generator.MainWindow(
                filename=Path(self.ui.widgets.input_file.text()),
                inputcb=self.ui.widgets.input_file.setText,
                log_window=self.log_window,
            )
            self.sg.show()
        elif self.sg.isVisible() is False:
            self.sg.show()
        elif self.sg.isMinimized() is True:
            self.sg.showNormal()
        else:
            self.sg.raise_()

    def parse_system_from_inputfile(self, input_file_path: str) -> None:
        """Parse the system from an input file."""
        input_path = Path(input_file_path)
        if not input_path.exists():
            return
        with open_and_error(input_file_path, "r") as f:
            if isinstance(f, Error):
                QMessageBox.warning(
                    self, "Input file error!", f"Input file cannot be parsed: {f.error}."
                )
                return
            for line in f.value:
                system_pattern = r"^# [Ss]ystem filename : (.+)"
                if match := re.match(system_pattern, line.strip()):
                    systemfile: list[str] = match.group(1).split(",")
                    break
                if line.strip() and not line.strip().startswith("#"):
                    # should not occur
                    QMessageBox.warning(
                        self,
                        "System file error!",
                        "No system specified in input file.",
                    )
                    return
            else:
                QMessageBox.warning(
                    self,
                    "System file error!",
                    "No system specified in input file.",
                )
                return
        try:
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
            system_info = get_system_info(systemfile)
            if isinstance(system_info, Error):
                print(system_info.error)  # noqa: T201
                self._cached_system_info = None
            else:
                self._cached_system_info = system_info.value
        matr1x.reload_config()
        self.ui.widgets.config_editor.set_systemfile(configurable)
        if systemfile != self.ui.widgets.config_editor.full_system_list:
            self.ui.widgets.config_editor.set_full_system_list(systemfile)
            self.ui.widgets.config_editor.set_system_info(self._cached_system_info)
            self.ui.widgets.config_editor.update_data()
        self.ui.actions.queue.setEnabled(True)

    def queue_measurement(self) -> None:
        """Queue a measurement into the measurement menu."""
        inputFile = self.ui.widgets.input_file.text()
        outputFile = self.ui.widgets.output_edit.text()
        if not Path(inputFile).exists():
            QMessageBox.warning(self, "Input file error!", "Input file does not exist.")
            return
        metadata = self.ui.widgets.meta_view.get_metadata()
        for key in metadata.keys():
            self.sys_meta_data[key] = metadata[key]
        # create parameter set for measurement, make sure to copy the meta data
        config_dict = self.ui.widgets.config_editor.get_config_dict()
        parameters = (
            inputFile,
            outputFile,
            self.sys_meta_data.copy(),
            config_dict,
        )
        self.ui.widgets.meas_list.add_parameters(parameters)
        if not self.running:
            self.ui.actions.start.setEnabled(True)

    def run_matrix(self) -> None:
        """Start running the queued measurements."""
        self.running = True
        self.ui.actions.preview.setEnabled(False)
        self.ui.actions.start.setEnabled(False)
        self.run_next_measurement()

    def keyPressEvent(self, a0: QKeyEvent) -> None:
        """Allow to modify systems list with keyboard shortcuts."""
        if self.ui.widgets.meas_list.hasFocus():
            if detect_shortcut(a0, QKeySequence(QKeySequence.StandardKey.Delete)):
                self.remove_measurement()
            if detect_shortcut(a0, QKeySequence(Qt.Key.Key_Backspace)):
                self.remove_measurement()
        super().keyPressEvent(a0)

    def remove_measurement(self) -> None:
        """Remove selected or last item from measurement list."""
        selected = self.ui.widgets.meas_list.selectedItems()
        if len(selected) > 0:
            self.ui.widgets.meas_list.takeItem(self.ui.widgets.meas_list.row(selected[0]))
        elif self.ui.widgets.meas_list.count() > 0:  # remove last item
            self.ui.widgets.meas_list.takeItem(self.ui.widgets.meas_list.count() - 1)
            self.ui.actions.start.setEnabled(False)

    def run_next_measurement(self) -> None:
        """Run the next queued measurement."""
        self.measurement_thread.set_parameters(
            self.ui.widgets.meas_list.parameters(0),
            self.ui.widgets.config_editor,
        )
        self.measurement_thread.start()
        self.ui.actions.pause.setEnabled(True)
        self.ui.actions.abort.setEnabled(True)
        self.ui.actions.finish.setEnabled(True)
        self.ui.actions.kill.setEnabled(True)

    def process_finished(self) -> None:
        """
        Properly finish a mesurement.

        Called when the current measurement is finished, checks whether
        there are further measurements in the queue and runs them in
        case.
        """
        self.ui.widgets.progressbar.setValue(0)
        self.ui.widgets.progress.setText("Measurement idle.")
        self.ui.widgets.table.setRowCount(1)
        for i in range(self.ui.widgets.table.columnCount()):
            self.ui.widgets.table.setItem(0, i, QTableWidgetItem(""))
        self.ui.widgets.meas_list.takeItem(0)
        self.ui.actions.pause.setEnabled(False)
        self.ui.actions.pause.setChecked(False)
        self.ui.actions.abort.setEnabled(False)
        self.ui.actions.finish.setEnabled(False)
        self.ui.actions.kill.setEnabled(False)
        if self.ui.widgets.meas_list.count() > 0 and self.running is True:
            self.run_next_measurement()
        else:
            self.ui.actions.start.setEnabled(False)
            self.running = False

    def open_preview(self) -> None:
        """Spawn a preview for the (running) measurement."""
        output = Path(self.ui.widgets.current_file.text())
        if not output.exists():
            QMessageBox.warning(self, "Preview error!", f"File does not exist ({output})")
        else:
            preview = [
                sys.executable,
                "-c",
                f"from matr1x.scripts import matrix_preview; matrix_preview.main(file=r'{output}')",
            ]
            subprocess.Popen(preview)


def main() -> None:
    """Set the basic GUI parameters and run."""
    install_error_handler()
    app = MApplication(sys.argv)
    app.setDesktopFileName("matrix-gui")
    ex = MainWindow()
    ex.show()
    protected_restore(ex.restore_window_state)
    ret = app.exec()
    logger.info("matrix-gui exiting")
    sys.exit(ret)
