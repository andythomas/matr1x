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

import logging
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import (
    QDateTime,
    QPoint,
    Qt,
    QTimer,
    QTimeZone,
    Signal,
)
from PySide6.QtGui import QAction, QCloseEvent, QColor, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QProgressBar,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import matr1x
from matr1x.error_handling import Error, InternalInvariantError, install_error_handler
from matr1x.gui_util import (
    AboutBox,
    AutoSlot,
    ConfigEditWidget,
    FileDropMixin,
    LoggingWindow,
    LogWindowMixin,
    MApplication,
    ReadOnlyTable,
    check_config,
    create_matr1x_quit_action,
    create_matrix_settings_action,
    detect_shortcut,
    get_matrix_icon,
    get_system_info,
    open_matrix_toml,
)
from matr1x.models import (
    Datafile,
    Envelope,
    ErrorMessage,
    Header,
    MeasuredValues,
    Message,
    SetValues,
    Telemetry,
)
from matr1x.post_install import (
    check_desktop_integration,
    post_installation,
    remove_desktop_integration,
)
from matr1x.scripts import sweep_generator
from matr1x.scripts.shared_classes import (
    MeasurementItem,
    MeasurementThread,
    MeasurementUI,
    MetaDataDialog,
    MetadataDockWidget,
    MMainWindow,
    MToolBar,
    SaferQSettings,
)
from matr1x.system import MergedSystem
from matr1x.util import open_and_error

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
    """A widget that stores the parameters for each row."""

    changed: Signal = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setAlternatingRowColors(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.active: bool = False

    def show_context_menu(self, pos: QPoint):
        """Allow to change output and delete items."""
        item = self.itemAt(pos)
        if not item:
            return
        row = self.row(item)
        self.active = True
        try:
            menu = QMenu(self)
            change_output = menu.addAction("Change Output")
            change_metadata = menu.addAction("Change Metadata")
            change_config = menu.addAction("Change Config")
            menu.addSeparator()
            remove = menu.addAction("Remove")
            action = menu.exec(self.mapToGlobal(pos))  # ty: ignore[invalid-argument-type]
            if action == remove:
                self.takeItem(row)
            elif action == change_output:
                self.change_output(row)
            elif action == change_metadata:
                self.change_metadata(row)
            elif action == change_config:
                self.change_config(row)
        finally:
            self.active = False

    def change_config(self, row: int) -> None:
        """Change the config of the item."""
        parameters = self.item(row).data(Qt.ItemDataRole.UserRole)
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Device Config")
        editor = ConfigEditWidget(popup=True)
        editor.set_systemfile(self.parameters(row).systems)
        editor.set_system_info(self.parameters(row).system_info)
        editor.update_data()
        editor.apply_config_dict(parameters.config)
        layout = QVBoxLayout(dialog)
        layout.addWidget(editor)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec():
            parameters.config = editor.get_config_dict()
            self.item(row).setData(Qt.ItemDataRole.UserRole, parameters)
            self.item(row).setToolTip(parameters.tooltip)

    def change_metadata(self, row: int) -> None:
        """Change the metadata of the item."""
        parameters = self.item(row).data(Qt.ItemDataRole.UserRole)
        dialog = MetaDataDialog(popup=True)
        dialog.set_metadata(parameters.metadata)
        if dialog.exec():
            parameters.metadata.update(dialog.metadata)
            self.item(row).setData(Qt.ItemDataRole.UserRole, parameters)
            self.item(row).setToolTip(parameters.tooltip)

    def change_output(self, row: int) -> None:
        """Change the output file location."""
        parameters = self.item(row).data(Qt.ItemDataRole.UserRole)
        folder = Path(parameters.input_file).with_suffix(".ma8")
        filename = QFileDialog.getSaveFileName(
            self,
            "Select ma file",
            str(folder),
            "Output files (*.ma8)",
            options=QFileDialog.Option.DontConfirmOverwrite,  # this is often ignored
            # and native dialog is not an option
        )
        if filename[0] != "":
            parameters.output_file = filename[0]
            self.item(row).setData(Qt.ItemDataRole.UserRole, parameters)
            self.item(row).setText(parameters.list_entry)
            self.item(row).setToolTip(parameters.tooltip)

    def add_parameters(self, parameters: MeasurementItem) -> None:
        """Add a set of parameters."""
        item = QListWidgetItem(parameters.list_entry)
        item.setData(Qt.ItemDataRole.UserRole, parameters)
        item.setToolTip(parameters.tooltip)
        self.addItem(item)

    def addItem(self, item: QListWidgetItem | str) -> None:
        """Add an item to the list widget."""
        super().addItem(item)
        self.changed.emit()

    def takeItem(self, row: int) -> QListWidgetItem:
        """Delete the item."""
        item = super().takeItem(row)
        self.changed.emit()
        return item

    def parameters(self, row: int) -> MeasurementItem:
        """Get the parameters for a matrix run of the given row."""
        item = self.item(row)
        return item.data(Qt.ItemDataRole.UserRole)

    def keyPressEvent(self, a0: QKeyEvent) -> None:
        """Allow to modify systems list with keyboard shortcuts."""
        if detect_shortcut(a0, QKeySequence(QKeySequence.StandardKey.Delete)):
            self.remove_measurement()
        elif detect_shortcut(a0, QKeySequence(Qt.Key.Key_Backspace)):
            self.remove_measurement()
        super().keyPressEvent(a0)

    def remove_measurement(self) -> None:
        """Remove selected or last item from measurement list."""
        selected = self.selectedItems()
        if selected:
            self.takeItem(self.row(selected[0]))
        elif self.count():
            self.takeItem(self.count() - 1)


@dataclass(frozen=True)
class ActionGroup:
    """Actions to be utilized in the GUI."""

    preview: QAction
    matrix_settings: QAction
    config: QAction
    sweep: QAction
    queue: QAction
    start: QAction
    pause: QAction
    abort: QAction
    finish: QAction
    kill: QAction
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
    dockable_metadata: MetadataDockWidget
    meta_view: MetaDataDialog
    input_file: LabelWithSignal
    current_file: QLabel
    progress: QLabel
    progressbar: QProgressBar
    table: ReadOnlyTable
    central_widget: QWidget
    current_measurement: QLineEdit
    about_box: AboutBox
    measurement_thread: MeasurementThread
    measurement_ui: MeasurementUI


class UIBuilder:
    """Create the GUI elements."""

    def __init__(self) -> None:
        self.widgets: WidgetGroup = self._create_widgets()
        self.actions: ActionGroup = self._create_actions()
        self.toolbar: MToolBar = self._create_toolbar()
        self._create_gui()
        self.menubar = self._create_menubar()

    def _create_widgets(self) -> WidgetGroup:
        """Create all UI widgets of this application."""
        meas_list = QueueListWidget()
        input_file = LabelWithSignal()
        current_file = QLabel()
        dockable_metadata = MetadataDockWidget()
        table = ReadOnlyTable()
        table.setColumnCount(4)
        table.setRowCount(1)
        table.setHorizontalHeaderLabels(["Parameter", "Set value", "Readout value", "unit"])
        width = (table.verticalHeader().width() + table.horizontalHeader().length()) * 1.04
        table.setFixedWidth(int(width))
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        progress = QLabel("Measurement idle.")
        progressbar = QProgressBar()
        central_widget = QWidget()
        current_measurement = QLineEdit()
        current_measurement.setReadOnly(True)
        return WidgetGroup(
            meas_list=meas_list,
            config_editor=ConfigEditWidget(),
            dockable_metadata=dockable_metadata,
            meta_view=dockable_metadata.meta_view,
            input_file=input_file,
            current_file=current_file,
            progressbar=progressbar,
            progress=progress,
            table=table,
            central_widget=central_widget,
            current_measurement=current_measurement,
            about_box=AboutBox(
                "Matrix GUI", get_matrix_icon("matr1x-matrix-gui.png"), matr1x, matr1x.datetimefmt
            ),
            measurement_thread=MeasurementThread(),
            measurement_ui=MeasurementUI(),
        )

    def _create_gui(self) -> None:
        """Create and set up all GUI layouts."""
        measurement = QVBoxLayout()
        measurement.addWidget(self.widgets.table)
        measurement.addWidget(self.widgets.progress)
        measurement.addWidget(self.widgets.progressbar)
        queue_n_current_measurement = QVBoxLayout()
        queue_n_current_measurement.addWidget(self.widgets.current_measurement)
        queue_n_current_measurement.addWidget(self.widgets.meas_list, 1)
        queue_n_measurement = QHBoxLayout()
        queue_n_measurement.setContentsMargins(0, 0, 0, 0)
        queue_n_measurement.addLayout(queue_n_current_measurement, 1)
        queue_n_measurement.addLayout(measurement, 0)
        measurements_container = QWidget()
        measurements_container.setLayout(queue_n_measurement)
        central_layout = QVBoxLayout()
        input_line = QHBoxLayout()
        input_line.addWidget(QLabel("Input: "))
        input_line.addWidget(self.widgets.input_file)
        input_line.addStretch()
        central_layout.addLayout(input_line)
        central_layout.addWidget(QLabel("Queue"))
        central_layout.addWidget(measurements_container)
        current_line = QHBoxLayout()
        current_line.addWidget(QLabel("Current file: "))
        current_line.addWidget(self.widgets.current_file)
        current_line.addStretch()
        central_layout.addLayout(current_line)
        self.widgets.central_widget.setLayout(central_layout)

    def _create_actions(self) -> ActionGroup:
        """Create all QActions of this application."""
        load = QAction(get_matrix_icon("SP_DialogOpenButton"), "Open")
        load.setShortcut(QKeySequence.StandardKey.Open)
        preview = QAction(
            get_matrix_icon("matr1x-matrix-preview.png", QColor("RoyalBlue")), "Preview"
        )
        preview.setEnabled(False)
        sweep = QAction(
            get_matrix_icon("matr1x-sweep-generator.png", QColor("RoyalBlue")), "Generator"
        )
        queue = QAction(get_matrix_icon("CHAR_+"), "Queue")
        queue.setEnabled(False)
        return ActionGroup(
            preview=preview,
            matrix_settings=create_matrix_settings_action(),
            config=self.widgets.config_editor.action,
            sweep=sweep,
            queue=queue,
            start=self.widgets.measurement_ui.start,
            pause=self.widgets.measurement_ui.pause,
            abort=self.widgets.measurement_ui.abort,
            finish=self.widgets.measurement_ui.finish,
            kill=self.widgets.measurement_ui.kill,
            show_log=LogWindowMixin.create_show_log_action(),
            load=load,
            quit=create_matr1x_quit_action(),
            post_install=LogWindowMixin.create_post_install_action(),
            remove_desktop_integration=LogWindowMixin.create_remove_desktop_integration_action(),
        )

    def _create_toolbar(self) -> MToolBar:
        """Create the Toolbar."""
        toolbar = MToolBar("Toolbar")
        toolbar.addAction(self.actions.load)
        toolbar.addAction(self.actions.sweep)
        toolbar.addSeparator()
        toolbar.addWidget(toolbar.empty)
        toolbar.addAction(self.actions.queue)
        self.widgets.measurement_ui.add_to_toolbar(toolbar)
        toolbar.addWidget(toolbar.empty)
        toolbar.addAction(self.actions.preview)
        toolbar.addWidget(toolbar.spacer)
        toolbar.addAction(self.widgets.dockable_metadata.action)
        toolbar.addAction(self.actions.config)
        return toolbar

    def _create_menubar(self) -> QMenuBar:
        """Create the menubar."""
        menubar = QMenuBar()
        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self.actions.load)
        file_menu.addAction(self.actions.sweep)
        file_menu.addSeparator()
        file_menu.addAction(self.actions.quit)  # This gets auto-moved on a Mac
        control_menu = menubar.addMenu("&Control")
        control_menu.addAction(self.actions.queue)
        self.widgets.measurement_ui.add_to_menu(control_menu)
        control_menu.addSeparator()
        control_menu.addAction(self.actions.preview)
        view_menu = menubar.addMenu("&View")
        view_menu.addAction(self.toolbar.action)
        view_menu.addAction(self.widgets.dockable_metadata.action)
        view_menu.addAction(self.actions.config)
        view_menu.addSeparator()
        view_menu.addAction(self.actions.matrix_settings)
        help_menu = menubar.addMenu("&Help")
        LogWindowMixin.add_common_help_actions(help_menu, self.actions)
        help_menu.addAction(self.widgets.about_box.action)
        return menubar


class MainWindow(FileDropMixin, LogWindowMixin, MMainWindow):
    """Runs the logical code."""

    def __init__(self) -> None:
        super().__init__()
        self.settings = SaferQSettings("matr1x", "gui")
        self.log_window = LoggingWindow(parent=self)
        self.log_window.hide()
        logger.info("matrix-gui starting")
        self.setWindowTitle("Matrix GUI")
        self.setWindowIcon(get_matrix_icon("matr1x-matrix-gui.png"))
        self.ui = UIBuilder()
        self.setMenuBar(self.ui.menubar)
        self.addToolBar(self.ui.toolbar)
        self.install_metadata_config_docks(
            self.ui.widgets.dockable_metadata,
            self.ui.widgets.config_editor,
        )
        self.setCentralWidget(self.ui.widgets.central_widget)
        check_config(matr1x.config)
        self.sg: QMainWindow | None = None
        self.running = False
        self.sys_meta_data = {}
        self._create_connections()
        self.setAcceptDrops(True)
        self.setValidExtensions([".sw8", re.compile(r"\.\d+t$")])
        self.file_dropped.connect(lambda file: self.ui.widgets.input_file.setText(file))
        check_desktop_integration()

    def _create_connections(self) -> None:
        """Connect actions and widgets with application logic."""
        self.ui.actions.preview.triggered.connect(self.open_preview)
        self.ui.actions.matrix_settings.triggered.connect(open_matrix_toml)
        self.ui.actions.sweep.triggered.connect(self.start_sweep_generator)
        self.ui.actions.queue.triggered.connect(self.queue_measurement)
        self.ui.actions.start.triggered.connect(self.run_matrix)
        self.ui.actions.post_install.triggered.connect(post_installation)
        self.ui.actions.remove_desktop_integration.triggered.connect(remove_desktop_integration)
        self.ui.actions.show_log.triggered.connect(self.toggle_log_window)
        self.log_window.visibility_changed.connect(
            lambda visible: self._on_log_window_visibility_changed(visible, self.ui.actions)
        )
        self._on_log_window_visibility_changed(self.log_window.isVisible(), self.ui.actions)
        self.ui.actions.load.triggered.connect(self.show_input_dialog)
        self.ui.actions.quit.triggered.connect(self.close)
        self.ui.widgets.input_file.textChanged.connect(self.parse_system_from_inputfile)
        self.ui.widgets.measurement_ui.connect_to_thread(self.ui.widgets.measurement_thread)
        self.ui.widgets.measurement_thread.data_received.connect(self.process_data)
        self.ui.widgets.measurement_thread.finished.connect(self.process_finished)
        self.ui.widgets.meas_list.changed.connect(self.measurement_list_changed)

    @AutoSlot
    def process_data(self, env: Envelope) -> None:
        """Process the data from the measurement thread."""
        data = env.payload
        if isinstance(data, Message):
            logger.info(data.message)
        elif isinstance(data, Datafile):
            self.ui.widgets.current_file.setText(data.datafile)
            self.ui.actions.preview.setEnabled(True)
        elif isinstance(data, Telemetry):
            self.ui.widgets.progressbar.setMaximum(data.points)
            self.ui.widgets.progressbar.setValue(data.point)
            if data.remaining is not None:
                self.ui.widgets.progress.setText(str(data))
        elif isinstance(data, (SetValues, MeasuredValues, Header)):
            self._process_tabledata(env)
        elif isinstance(data, ErrorMessage):
            logger.error(data.error)

    def measurement_list_changed(self) -> None:
        """Update the data order when the measurement list is changed."""
        if not self.running:
            if self.ui.widgets.meas_list.count() > 0:
                self.ui.actions.start.setEnabled(True)
            else:
                self.ui.actions.start.setEnabled(False)

    def _process_tabledata(self, env: Envelope) -> None:
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
            for index, item in enumerate(data.set_values):
                if item is not None:
                    value = QTableWidgetItem(str(item))
                else:
                    value = QTableWidgetItem("")
                value.setTextAlignment(
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                )
                self.ui.widgets.table.setItem(index, 1, value)
        elif isinstance(data, MeasuredValues):
            for index, item in enumerate(data.measured_values):
                if item is not None:
                    value = QTableWidgetItem(str(item))
                else:
                    value = QTableWidgetItem("")
                value.setTextAlignment(
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                )
                self.ui.widgets.table.setItem(index, 2, value)
            try:
                utc = QDateTime.fromSecsSinceEpoch(int(item), QTimeZone.utc())
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
            self.ui.widgets.meas_list.remove_measurement()
        self.save_window_state()
        self.cleanup_log_window()
        a0.accept()

    def save_window_state(self) -> None:
        """Save application configuration until next startup."""
        self.save_layout_state(self.settings)
        self.save_log_window_state(self.settings)

    def restore_window_state(self) -> None:
        """Restore application configuration from the previous use."""
        self.restore_layout_state(self.settings)
        self.restore_log_window_state(self.settings)

    def show_input_dialog(self) -> None:
        """Open a QFileDialog with filter for input files."""
        folder = self.ui.widgets.input_file.text() or matr1x.usersfolder
        # remove old pattern with next major update
        filename = QFileDialog.getOpenFileName(
            self, "Select input file", str(folder), "Sweep 8 files (*.sw8);;t files (*.*t)"
        )
        if filename[0] != "":
            self.ui.widgets.input_file.setText(filename[0])

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
                        self, "System file error!", "No system specified in input file."
                    )
                    return
            else:
                QMessageBox.warning(
                    self, "System file error!", "No system specified in input file."
                )
                return
        system = MergedSystem.from_files(systemfile)
        if isinstance(system, Error):
            QMessageBox.warning(self, "System file error!", system.error)
            return
        system = system.value
        self.sys_meta_data = system.dcdata
        configurable = [system for system in systemfile if not Path(system.strip()).exists()]
        # Get system information using subprocess (cache for reuse)
        if systemfile:
            system_info = get_system_info(systemfile)
            if isinstance(system_info, Error):
                print(system_info.error)  # noqa: T201
                system_info = None
            else:
                system_info = system_info.value
        matr1x.reload_config()
        self.ui.widgets.config_editor.set_systemfile(configurable)
        if systemfile != self.ui.widgets.config_editor.full_system_list:
            self.ui.widgets.config_editor.set_full_system_list(systemfile)
            self.ui.widgets.config_editor.set_system_info(system_info)
            self.ui.widgets.config_editor.update_data()
        self.ui.actions.queue.setEnabled(True)

    def queue_measurement(self) -> None:
        """Queue a measurement into the measurement menu."""
        inputFile = self.ui.widgets.input_file.text()
        if not Path(inputFile).exists():
            QMessageBox.warning(self, "Input file error!", "Input file does not exist.")
            return
        self.sys_meta_data.update(self.ui.widgets.meta_view.metadata)
        # create parameter set for measurement, make sure to copy the meta data
        if not self.ui.widgets.config_editor.system_info:
            raise InternalInvariantError("System info should not be None at this point.")
        parameters = MeasurementItem(
            kind="sweep",
            input_file=inputFile,
            output_file="",
            metadata=self.sys_meta_data.copy(),
            config=self.ui.widgets.config_editor.get_config_dict(),
            systems=self.ui.widgets.config_editor.full_system_list.copy(),
            system_info=self.ui.widgets.config_editor.system_info.model_copy(deep=True),
        )
        self.ui.widgets.meas_list.add_parameters(parameters)
        if not self.running:
            self.ui.actions.start.setEnabled(True)

    def run_matrix(self) -> None:
        """Start running the queued measurements."""
        self.running = True
        self.ui.actions.preview.setEnabled(False)
        self.ui.actions.start.setEnabled(False)
        self.ui.widgets.progress.setText("Measurement started.")
        self.run_next_measurement()

    def run_next_measurement(self) -> None:
        """Run the next queued measurement."""
        if self.ui.widgets.meas_list.active:
            self.ui.widgets.progress.setText("Waiting for queue edit to finish.")
            QTimer.singleShot(200, self.run_next_measurement)
            return
        self.ui.widgets.measurement_thread.set_parameters(self.ui.widgets.meas_list.parameters(0))
        self.ui.widgets.current_measurement.setText(
            self.ui.widgets.meas_list.parameters(0).list_entry
        )
        self.ui.widgets.current_measurement.setToolTip(
            self.ui.widgets.meas_list.parameters(0).tooltip
        )
        self.ui.widgets.meas_list.takeItem(0)
        self.ui.widgets.measurement_thread.start()
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
        self.ui.widgets.current_measurement.setText("")
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
    ex.restore_window_state()
    ret = app.exec()
    logger.info("matrix-gui exiting")
    sys.exit(ret)
