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
"""Display data and allow simple data manipulation."""

import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, no_type_check

import numpy as np
import pyqtgraph
import pyqtgraph.exporters
from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QKeyCombination,
    QPoint,
    QSize,
    Qt,
    QThread,
    Signal,
)
from PySide6.QtGui import QAction, QColor, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QGridLayout,
    QLabel,
    QLayout,
    QMainWindow,
    QMenuBar,
    QMessageBox,
    QSizePolicy,
    QToolBar,
    QWidget,
)

import matr1x
from matr1x.error_handling import expect_not_none, install_error_handler
from matr1x.eval import HeaderDict, _create_empty_header, loadmatrix
from matr1x.gui_util import (
    AboutBox,
    FileDropMixin,
    LoggingWindow,
    LogWindowMixin,
    MApplication,
    MetaViewerWidget,
    SimplePlotWidget,
    check_config,
    clear_layout,
    create_matrix_settings_action,
    get_matrix_icon,
    open_matrix_toml,
)
from matr1x.post_install import (
    check_desktop_integration,
    post_installation,
    remove_desktop_integration,
)
from matr1x.scripts.shared_classes import SaferQSettings

logger = logging.getLogger(__name__)

if sys.platform == "win32":
    try:
        from ctypes import windll

        myappid = "python.matr1x.matrix-preview.version"
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass

# A sentinel value for when there is no data
NO_DATA = None


class PlotData(TypedDict):
    """Data structure for plotting with type information."""

    label: str
    desig: int
    unit: str
    data: np.ndarray | None  # data can be an ndarray or None
    shape: tuple[int, ...]  # Specifies a tuple of integers
    dim: int


class UpdateThread(QThread):
    """Handle the thread."""

    update_now = Signal()

    def __init__(self, interval):
        """Init thread and set sleep interval."""
        QThread.__init__(self)
        self.stopFlag = False
        self.interval = interval

    def run(self):
        """Run thread and sleep in intervals."""
        while not self.stopFlag:
            time.sleep(self.interval)
            self.update_now.emit()

    def terminate(self):
        """Terminate the thread."""
        self.stopFlag = True
        self.wait()


@dataclass
class ActionGroup:
    """Actions to be utilized in the GUI."""

    new: QAction
    load: QAction
    previous: QAction
    next: QAction
    export_png: QAction
    export_data: QAction
    auto_update: QAction
    update: QAction
    quit: QAction
    matrix_settings: QAction
    about: QAction
    toggle_toolbar: QAction
    meta: QAction
    show_log: QAction
    post_install: QAction
    remove_desktop_integration: QAction


class UIBuilder:
    """Create the GUI elements."""

    def __init__(self):
        self.actions: ActionGroup = self._create_actions()
        # widgets
        self.toolbar: QToolBar = self._create_toolbar()
        # gui
        self.file_selector: QComboBox
        self.menubar: QMenuBar = self._create_menu()

    def _create_actions(self) -> ActionGroup:
        """Create all required actions."""
        new = QAction(get_matrix_icon("SP_FileIcon"), "New window")
        new.setShortcut(QKeySequence.StandardKey.New)
        load = QAction(get_matrix_icon("SP_DialogOpenButton"), "Open")
        load.setShortcut(QKeySequence.StandardKey.Open)
        previous = QAction(get_matrix_icon("SP_ArrowLeft"), "Previous")
        cmd_left_shortcut = QKeySequence(
            QKeyCombination(Qt.KeyboardModifier.ControlModifier, Qt.Key.Key_Left)
        )
        previous.setShortcut(cmd_left_shortcut)
        previous.setEnabled(False)
        next_file = QAction(get_matrix_icon("SP_ArrowRight"), "Next")
        cmd_right_shortcut = QKeySequence(
            QKeyCombination(Qt.KeyboardModifier.ControlModifier, Qt.Key.Key_Right)
        )
        next_file.setShortcut(cmd_right_shortcut)
        next_file.setEnabled(False)
        export_png = QAction(get_matrix_icon("SP_DialogSaveButton"), "Save png")
        export_png.setEnabled(False)
        export_png.setShortcut(QKeySequence.StandardKey.Save)
        export_data = QAction(get_matrix_icon("SP_FileDialogDetailedView"), "Save txt")
        export_data.setEnabled(False)
        auto_update = QAction(get_matrix_icon("SP_BrowserReload"), "Auto Update")
        auto_update.setEnabled(False)
        auto_update.setCheckable(True)
        update = QAction(get_matrix_icon("CHAR_U", QColor("RoyalBlue")), "Update")
        update.setEnabled(False)
        quit_app = QAction("Quit")
        if os.name == "nt":
            quit_app.setShortcut(QKeySequence.StandardKey.Close)
        else:
            quit_app.setShortcut(QKeySequence.StandardKey.Quit)
        toggle_toolbar = QAction("Show Toolbar")
        toggle_toolbar.setShortcut(QKeySequence("Ctrl+1"))
        toggle_toolbar.setCheckable(True)
        toggle_toolbar.setChecked(True)
        meta = QAction(get_matrix_icon("SP_FileDialogListView"), "Metadata")
        meta.setShortcut(QKeySequence("Ctrl+2"))
        meta.setEnabled(False)
        meta.setCheckable(True)
        return ActionGroup(
            new=new,
            load=load,
            previous=previous,
            next=next_file,
            export_png=export_png,
            export_data=export_data,
            auto_update=auto_update,
            update=update,
            quit=quit_app,
            matrix_settings=create_matrix_settings_action(),
            about=LogWindowMixin.create_about_action(),
            toggle_toolbar=toggle_toolbar,
            meta=meta,
            show_log=LogWindowMixin.create_show_log_action(),
            post_install=LogWindowMixin.create_post_install_action(),
            remove_desktop_integration=LogWindowMixin.create_remove_desktop_integration_action(),
        )

    def _create_toolbar(self) -> QToolBar:
        """Create the main toolbar."""
        toolbar = QToolBar("Toolbar")
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        toolbar.setFloatable(False)
        toolbar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        icon_size = MApplication.instance().toolbar_icon_size()
        toolbar.setIconSize(QSize(icon_size, icon_size))
        toolbar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea | Qt.ToolBarArea.BottomToolBarArea)
        toolbar.addAction(self.actions.load)
        toolbar.visibilityChanged.connect(self.actions.toggle_toolbar.setChecked)
        toolbar.addAction(self.actions.export_png)
        toolbar.addAction(self.actions.export_data)
        toolbar.addSeparator()
        toolbar.addAction(self.actions.update)
        toolbar.addAction(self.actions.auto_update)
        empty = QWidget()
        empty.setFixedWidth(icon_size)
        toolbar.addWidget(empty)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        toolbar.addWidget(spacer)
        toolbar.addSeparator()
        toolbar.addAction(self.actions.previous)
        self.file_selector = QComboBox()
        self.file_selector.setEnabled(False)
        self.file_selector.setMinimumContentsLength(50)
        toolbar.addWidget(self.file_selector)
        toolbar.addAction(self.actions.next)
        toolbar.addSeparator()
        toolbar.addAction(self.actions.meta)
        return toolbar

    def _create_menu(self) -> QMenuBar:
        """Create the main menu."""
        menu = QMenuBar()
        file_menu = menu.addMenu("&File")
        file_menu.addAction(self.actions.new)
        file_menu.addSeparator()
        file_menu.addAction(self.actions.load)
        file_menu.addAction(self.actions.quit)
        file_menu.addAction(self.actions.export_png)
        file_menu.addAction(self.actions.export_data)
        file_menu.addSeparator()
        file_menu.addAction(self.actions.update)
        file_menu.addAction(self.actions.auto_update)
        if sys.platform != "darwin":
            file_menu.addSeparator()
            file_menu.addAction(self.actions.quit)
        control_menu = menu.addMenu("&Control")
        control_menu.addAction(self.actions.previous)
        control_menu.addAction(self.actions.next)
        view_menu = menu.addMenu("&View")
        view_menu.addAction(self.actions.toggle_toolbar)
        view_menu.addAction(self.actions.meta)
        view_menu.addSeparator()
        view_menu.addAction(self.actions.matrix_settings)
        help_menu = menu.addMenu("&Help")
        LogWindowMixin.add_common_help_actions(help_menu, self.actions)
        return menu


class SweepPreview(FileDropMixin, LogWindowMixin, QMainWindow):
    """
    Data viewer for matrix files.

    Parameters
    ----------
    filename: Path
      name of matrix file (.ma6, .ma7, .ma8)
    parent: widget or None
      parent widget
    """

    openfile_dialog = Signal()
    allowed_extensions = (".ma6", ".ma7", ".ma8")

    def __init__(self, parent: QWidget | None = None, filename: Path | None = None):
        super().__init__(parent)
        self.log_window = LoggingWindow(parent=self)
        self.log_window.hide()
        logger.info("matrix-preview starting")
        # File-related properties
        self.filename: Path | None = filename
        self.file_dir: Path = Path()
        self.file_index: int = 0
        self.data_files: list[str] = []

        # State properties
        self.closing_allowed = True
        self.multidim = False
        self.error = False
        self.ui_initialized = False
        self.lu_time = 0.0

        # Thread and update properties
        self.update_thread: UpdateThread | None = None

        # UI components that are recreated for each file in init_ui()
        self.w_l: list = []  # Labels for axes
        self.column_selector: list[QComboBox]
        self.w_plot2d: QCheckBox  # 2D plotting checkbox
        self.w_plot2d_comp: QCheckBox  # 2D complex plotting checkbox
        self.w_transpose: QCheckBox  # Transpose checkbox
        self.spw: SimplePlotWidget
        self.iv: pyqtgraph.ImageView | None = None  # Image view widget
        self.column_items: list[str] = []  # Column descriptions for current file

        # Data properties
        self.names: list[str] = []
        self.units: list[str] = []
        self.shapes: list[tuple[int, ...]] = []
        self.header: HeaderDict = _create_empty_header()
        self.data: np.ndarray | dict[str, np.ndarray] = np.array([])
        # initialize basic GUI
        self.init_basic_ui()
        # allow to store the settings
        self.settings = SaferQSettings("matr1x", "preview")
        self.meta_viewer = MetaViewerWidget(self.header)
        self.setup_meta_viewer()
        # signal from delayed file open
        self.openfile_dialog.connect(self.load_button_pressed)
        # Only connect for root windows (parent=None) to avoid duplicate connections
        application = MApplication.instance()
        if parent is None:
            application.connect_file_handler(self._open_file_from_signal)
        # initialize filename if available
        if filename:
            self.open_file(filename)
        self.setAcceptDrops(True)
        self.setValidExtensions(list(self.allowed_extensions))
        self.file_dropped.connect(lambda file: self.open_file(Path(file)))
        check_desktop_integration()

    def _get_maximum_screen_width(self):
        """Determine width of the biggest available screen."""
        width = 0
        for screen in MApplication.instance().screens():
            width = max(width, screen.geometry().width())
        return width

    def eventFilter(self, a0, a1):
        """Update the file view if required."""
        if a0 == self.ui.file_selector:
            if a1 is not None and a1.type() == QEvent.Type.MouseButtonPress:
                self.update_file_combo()
            return False
        return False

    def load_button_pressed(self):
        """Open file dialog to chose the input file."""
        self.closing_allowed = False
        filename = QFileDialog.getOpenFileName(
            self, "Select ma file", "", "matrix data files (*.ma8 *.ma7 *.ma6)"
        )[0]
        self.closing_allowed = True
        if filename:
            self.open_file(Path(filename))

    def _open_file_from_signal(self, filename: str):
        """Convert string to Path for opening file.

        This method is needed to handle file opening from signals on MacOS.
        """
        self.open_file(Path(filename))

    def open_file(self, filename: Path):
        """Read the data from the file."""
        logger.info("opening %s", filename)
        self.filename = filename
        # get all files
        self.file_dir = self.filename.absolute().parent
        self.setWindowTitle(f"Matrix Preview: {self.file_dir}")
        self.file_list_refresh()
        self.file_index = self.data_files.index(self.filename.name)
        self.update_thread = None
        self.lu_time = time.time()
        self.fetch_data()
        self.multidim = False
        self.error = False
        self.clear_ui()
        self.init_ui()
        self.ui.file_selector.installEventFilter(self)

    def file_list_refresh(self):
        """Refresh all files with the correct extension in the selected directory."""
        files = self.file_dir.iterdir()
        self.data_files = [file.name for file in files if file.suffix in self.allowed_extensions]
        self.data_files = sorted(
            self.data_files,
            key=lambda t: (self.file_dir / t).stat().st_mtime,
        )

    def update_file_combo(self):
        """Update the combo box that displays the file names."""
        self.file_list_refresh()
        ctext = self.ui.file_selector.currentText()
        self.ui.file_selector.setToolTip(str(self.file_dir))
        self.ui.file_selector.currentIndexChanged.disconnect()
        self.ui.file_selector.clear()
        self.ui.file_selector.addItems(self.data_files)
        index = self.data_files.index(ctext)
        self.ui.file_selector.setCurrentIndex(index)  # current index can differ from
        # self.file_index, problem?
        self.ui.file_selector.currentIndexChanged.connect(self.file_index_changed)

    def closeEvent(self, a0):
        """Store toolbar position on close."""
        if self.closing_allowed:
            if self.update_thread is not None:
                self.update_thread.terminate()
            self.save_window_state()
            self.cleanup_log_window()
            a0.accept()
        else:
            a0.ignore()

    def save_window_state(self) -> None:
        """
        Save application configuration until next startup.

        For convenience, main window geometry, the toolbar placement,
        and the size and position of the metadata pane are saved.
        """
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("toolbar_position", self.toolBarArea(self.ui.toolbar).value)
        self.settings.setValue("meta_position_area", self.dockWidgetArea(self.meta_viewer).value)
        self.settings.setValue("meta_floating", self.meta_viewer.isFloating())
        self.settings.setValue("meta_position", self.meta_viewer.pos())
        self.settings.setValue("meta_size", self.meta_viewer.size())
        self.save_log_window_state(self.settings)

    def restore_window_state(self) -> None:
        """
        Restore application configuration to look similar to the previous use.

        Main window geometry and the toolbar placement are restored.
        """
        toolbar_pos = self.settings.safer_value(
            "toolbar_position", Qt.ToolBarArea.TopToolBarArea.value, type=int
        )
        self.addToolBar(Qt.ToolBarArea(toolbar_pos), self.ui.toolbar)
        # Just in case it is the first start
        self.resize(self.sizeHint())
        self.restoreGeometry(self.settings.safer_value("geometry", QByteArray(), type=QByteArray))
        self.restore_log_window_state(self.settings)

    def info_box(self):
        """Display an 'about this app' widget."""
        box = AboutBox(
            "Matrix Preview",
            get_matrix_icon("matr1x-matrix-preview.png"),
            matr1x,
            matr1x.datetimefmt,
        )
        box.exec()
        return

    def create_new_preview(self) -> None:
        """Create a new preview window."""
        preview = [
            sys.executable,
            "-c",
            "from matr1x.scripts import matrix_preview; matrix_preview.main()",
        ]
        subprocess.Popen(preview)

    def toggle_toolbar_view(self, checked):
        """Toogles the visibility of the toolbar on and off."""
        if checked:
            self.ui.toolbar.show()
        else:
            self.ui.toolbar.hide()

    def init_basic_ui(self):
        """Initialize basic GUI that works without chosen filename."""
        self.setWindowTitle("Matrix Preview")
        self.setWindowIcon(get_matrix_icon("matr1x-matrix-preview.png"))
        pyqtgraph.setConfigOption("background", "w")
        pyqtgraph.setConfigOption("foreground", "k")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.grid: QGridLayout = QGridLayout()
        self.widget = QWidget()
        self.w_status = QLabel("")
        self.w_status.setStyleSheet("QLabel { color : red; }")
        self.grid.addWidget(self.w_status, 6, 0, 1, -1)
        self.widget.setLayout(self.grid)
        self.setCentralWidget(self.widget)
        self.ui = UIBuilder()
        self.setMenuBar(self.ui.menubar)
        self.addToolBar(self.ui.toolbar)
        self.show()
        check_config(matr1x.config)
        self._create_connections()

    def _create_connections(self):
        """Connect actions with application logic."""
        self.ui.actions.new.triggered.connect(self.create_new_preview)
        self.ui.actions.load.triggered.connect(self.load_button_pressed)
        self.ui.actions.previous.triggered.connect(self.previous_file)
        self.ui.actions.next.triggered.connect(self.next_file)
        self.ui.actions.export_png.triggered.connect(self.save_plot)
        self.ui.actions.export_data.triggered.connect(self.save_data)
        self.ui.actions.auto_update.toggled.connect(self.updatethread)
        self.ui.actions.update.triggered.connect(lambda: self.conditional_fetch_data(True))
        self.ui.actions.quit.triggered.connect(self.close)
        self.ui.actions.matrix_settings.triggered.connect(open_matrix_toml)
        self.ui.actions.about.triggered.connect(self.info_box)
        self.ui.actions.toggle_toolbar.triggered.connect(self.toggle_toolbar_view)
        self.ui.actions.meta.triggered.connect(self.toggle_meta)
        self.ui.actions.post_install.triggered.connect(post_installation)
        self.ui.actions.remove_desktop_integration.triggered.connect(remove_desktop_integration)
        self.ui.actions.show_log.triggered.connect(self.toggle_log_window)
        self.log_window.visibility_changed.connect(
            lambda visible: self._on_log_window_visibility_changed(visible, self.ui.actions)
        )
        self._on_log_window_visibility_changed(self.log_window.isVisible(), self.ui.actions)

    def setup_meta_viewer(self) -> None:
        """Configure the metadata view dock widget."""
        self.meta_viewer.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
        )
        self.meta_viewer.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.meta_viewer.setVisible(False)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.meta_viewer)
        self.restore_meta_viewer()
        self.meta_viewer.visibilityChanged.connect(self.ui.actions.meta.setChecked)

    def restore_meta_viewer(self) -> None:
        """Restore viewer position ans size from settings."""
        meta_pos = self.settings.safer_value(
            "meta_position_area", Qt.DockWidgetArea.RightDockWidgetArea.value, type=int
        )

        self.addDockWidget(Qt.DockWidgetArea(meta_pos), self.meta_viewer)
        self.meta_viewer.setFloating(self.settings.safer_value("meta_floating", False, type=bool))
        if self.meta_viewer.isFloating():
            self.meta_viewer.move(
                self.settings.safer_value("meta_position", self.meta_viewer.pos(), type=QPoint)
            )
            self.meta_viewer.resize(
                self.settings.safer_value("meta_size", self.meta_viewer.size(), type=QSize)
            )
        else:
            self.resizeDocks(
                [self.meta_viewer],
                [
                    self.settings.safer_value(
                        "meta_size", self.meta_viewer.size(), type=QSize
                    ).width()
                ],
                Qt.Orientation.Horizontal,
            )

    def init_ui(self):
        """Initialize GUI for popup."""
        # File list
        self.ui.file_selector.addItems(self.data_files)
        self.ui.file_selector.setCurrentIndex(self.file_index)
        self.ui.file_selector.currentIndexChanged.connect(self.file_index_changed)

        # Update
        auinit = False
        self.ui.actions.auto_update.setChecked(auinit)
        self.updatethread(auinit)

        self.w_l = [QLabel("y"), QLabel("x"), QLabel("y")]
        self.w_l[2].setVisible(False)

        self.column_selector = [QComboBox(), QComboBox(), QComboBox()]
        self.column_selector[1].setEnabled(False)
        self.column_selector[2].setVisible(False)

        self.column_items = [
            f"{name} ({unit}), shape: {shape}"
            for name, unit, shape in zip(self.names, self.units, self.shapes)
        ]

        for i in range(3):
            self.column_selector[i].addItems([""] + self.column_items)
            self.column_selector[i].currentIndexChanged.connect(self.index_changed)

        self.w_plot2d = QCheckBox("2d plotting")
        self.w_plot2d.toggled.connect(self.plotting_toggled)

        self.w_plot2d_comp = QCheckBox("2d complex")
        self.w_plot2d_comp.toggled.connect(self.plotting_complex)
        self.w_plot2d_comp.setVisible(False)

        self.w_transpose = QCheckBox("transpose")
        self.w_transpose.setVisible(False)
        self.w_transpose.toggled.connect(self.transpose_toggled)

        self.spw = SimplePlotWidget(self.raise_error, self.index_callback)
        # minimum height of plot widget, could be removed but then
        # window always needs to be resized
        self.spw.setMinimumHeight(350)
        self.iv = None

        self.grid.addWidget(self.w_plot2d, 2, 3, 1, 1)
        for i in range(3):
            self.grid.addWidget(self.w_l[i], i + 1, 0)
            self.grid.addWidget(self.column_selector[i], i + 1, 1)
        self.grid.addWidget(self.w_plot2d_comp, 2, 4, 1, 1)
        self.grid.addWidget(self.w_transpose, 2, 2, 1, 1)
        self.grid.addWidget(self.spw, 4, 0, 1, -1)
        # set rescaling behavior
        self.grid.setColumnStretch(1, 1)
        self.grid.setRowStretch(4, 1)
        self.grid.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        # although this seems counter intuitive. setting the minimum width
        # limits the maximum window size in case long filenames are used.
        # see #328
        self.setMinimumWidth(800)
        self.setMaximumWidth(self._get_maximum_screen_width())

        if not self.ui_initialized:
            self.ui.actions.export_png.setEnabled(True)
            self.ui.actions.export_data.setEnabled(True)
            self.ui.actions.update.setEnabled(True)
            self.ui.actions.auto_update.setEnabled(True)
            self.ui.actions.previous.setEnabled(True)
            self.ui.file_selector.setEnabled(True)
            self.ui.actions.next.setEnabled(True)
            self.ui.actions.meta.setEnabled(True)
            # do not duplicate the items next time
            self.ui_initialized = True

    def clear_ui(self) -> None:
        """Clear the UI."""
        for i in reversed(range(2, self.grid.count())):
            item = self.grid.takeAt(i)
            if item is None:
                continue
            if widget := item.widget():
                widget.deleteLater()
            elif layout := item.layout():
                clear_layout(layout)

    def toggle_meta(self, state):
        """Toggle the meta data view."""
        if state is True:
            self.meta_viewer.setVisible(True)
        else:
            self.meta_viewer.setVisible(False)

    def get_filename_without_extension(self) -> str:
        """Return the actual filename without extension."""
        if self.filename is None:
            return ""
        if self.filename.suffix in self.allowed_extensions:
            return str(self.filename.with_suffix(""))
        return str(self.filename)

    def save_plot(self) -> None:
        """Ask for filename and save the displayed data in a png file."""
        filename = QFileDialog.getSaveFileName(
            self,
            "Select output png file",
            self.get_filename_without_extension() + ".png",
            "png files (*.png)",
        )[0]
        if filename:
            filename_path = Path(filename)
            if filename_path.suffix.lower() != ".png":
                filename_path = filename_path.with_suffix(".png")
            if self.iv is not None:
                exporter = pyqtgraph.exporters.ImageExporter(self.iv.view)
                exporter.export(str(filename_path))
            else:
                self.spw.save_plot(str(filename_path))

    def save_data(self) -> None:
        """Ask for filename and save the displayed data in an text file."""
        columns = self.spw.get_columns()
        suggested_filename = (
            self.get_filename_without_extension() + "_" + columns[1] + "_" + columns[0]
        )
        filename = QFileDialog.getSaveFileName(
            self,
            "Select output text file",
            suggested_filename,
            "text files (*.txt)",
        )[0]
        if filename:
            filename_path = Path(filename)
            if filename_path.suffix.lower() != ".txt":
                filename_path = filename_path.with_suffix(".txt")
            self.spw.save_data(str(filename_path))

    def previous_file(self):
        """Determine the previous file."""
        self.update_file_combo()
        if self.file_index > 0:
            self.ui.file_selector.setCurrentIndex(self.file_index - 1)

    def next_file(self):
        """Determine the next file."""
        self.update_file_combo()
        if self.file_index < len(self.data_files) - 1:
            self.ui.file_selector.setCurrentIndex(self.file_index + 1)

    def file_index_changed(self, index):
        """Update info when index changes."""
        self.file_index = index
        self.filename = self.file_dir / self.data_files[self.file_index]
        check = self.conditional_fetch_data(True, check=True)
        if check != 0:
            self.column_items = [
                f"{name} ({unit}), shape: {shape}"
                for name, unit, shape in zip(self.names, self.units, self.shapes)
            ]
            if check == -2:
                # file has same columns but different shapes, only change
                # names to reflect the dimensions
                for i in range(3):
                    for j, item in enumerate(self.column_items):
                        self.column_selector[i].setItemText(j + 1, item)
            elif check == -1:
                # file has different columns
                # reload interface
                for i in range(3):
                    self.column_selector[i].clear()
                    self.column_selector[i].addItems([""] + self.column_items)
                self.reset()
                self.spw.reset()
        else:
            self.spw.refresh_all_plots()
        self.meta_viewer.update_data(self.header)

    def index_changed(self, newIndex):
        """If index changed, reload the new data and handle the gui interaction."""
        if self.column_selector[0] == self.sender():
            if newIndex == 0:
                self.column_selector[1].setEnabled(False)
                self.column_selector[1].setCurrentIndex(0)
            else:
                self.column_selector[1].setEnabled(True)
        self.reload_data()

    def transpose_toggled(self, check_state):
        """Transpose has been toggled, reload data."""
        if self.w_plot2d.isChecked() is True and self.w_plot2d_comp.isChecked() is False:
            if len(self.shapes[self.column_selector[0].currentIndex() - 1]) < 3:
                # toggle index for 2d data, since x and y invert role
                dummy = self.column_selector[2].currentIndex()
                self.column_selector[2].blockSignals(True)
                self.column_selector[2].setCurrentIndex(self.column_selector[1].currentIndex())
                self.column_selector[1].setCurrentIndex(dummy)
                self.column_selector[2].blockSignals(False)
        self.reload_data()

    def plotting_toggled(self, check_state):
        """Switch the currently selected plotting view to 2D."""
        self.w_l[0].setText("z" if check_state is True else "y")
        self.w_plot2d_comp.setVisible(check_state)
        if self.w_plot2d_comp.isChecked() is True and not check_state:
            self.w_plot2d_comp.setChecked(False)
        if self.w_plot2d_comp.isChecked() is True:
            check_state = not check_state
        self.w_l[2].setVisible(check_state)
        self.column_selector[2].setVisible(check_state)
        self.ui.actions.export_data.setEnabled(not check_state)
        self.reload_data()

    def plotting_complex(self, check_state):
        """
        Turn on the more complex 2D plotting widget.

        This is provided by pyqtgraph instead of using the
        SimplePlotWidget.
        """
        if check_state is True:
            self.spw.setVisible(False)
            if self.iv is None:
                # set up image view on first initialization
                self.iv = pyqtgraph.ImageView()
                self.grid.addWidget(self.iv, 4, 0, 1, -1)
            else:
                self.iv.setVisible(True)
        elif check_state is False and self.iv is not None:
            self.grid.removeWidget(self.iv)
            del self.iv
            self.iv = None
            self.spw.setVisible(True)
        # reload data and set widget labels
        self.plotting_toggled(check_state or self.w_plot2d.isChecked())

    def raise_error(self, error):
        """
        Raise the error flag.

        This can be used as callback function to set
        errors from the SimplePlotWidget.
        """
        if error != "":
            self.w_status.setVisible(True)
            self.w_status.setText(error)
            self.error = True
        elif error == "" and self.error is True:
            self.error = False
            self.w_status.setVisible(False)

    def index_callback(self, plot_object):
        """
        Handle a change of the ploted index.

        This is acieved via the plot selector of the
        SimplePlotWidget (callback).
        """
        self.w_plot2d.blockSignals(True)
        self.w_plot2d.setChecked(plot_object.plot2d)
        self.w_plot2d.blockSignals(False)
        for i in range(3):
            self.column_selector[i].blockSignals(True)
            self.column_selector[i].setCurrentIndex(plot_object.desig[i])
            self.column_selector[i].blockSignals(False)
        self.reload_data()

    def updatethread(self, state):
        """
        Run and terminate a thread that reloads the data from the file.

        RUn if the filename has changed.
        """
        if state is True:
            # start updatethread with 2s refresh time
            self.update_thread = UpdateThread(2)
            self.update_thread.update_now.connect(self.conditional_fetch_data)
            self.update_thread.start()
        if state is False and self.update_thread is not None:
            self.update_thread.terminate()
            self.update_thread = None

    def conditional_fetch_data(self, force=False, check=False) -> int:
        """
        Fetch data from the file.

        Fetches data from the file if force is True, or if the
        modification time is past the time of the latest update (stored
        in self.lu_time). If force is false, this function was called
        from the updatethread, therefore make it update all windows.
        """
        filename = expect_not_none(self.filename, "Trying to fetch data, but filename is None!")
        ret = 0
        if force is True:
            # file has changed after last update,
            # reload the data into the file structure
            ret = self.fetch_data(check=check)
            self.reload_data()
            self.spw.refresh_all_plots()
            self.refresh_columns_size()
        elif filename.stat().st_size > 300000 and time.time() - self.lu_time < 20:
            # skip updates if delta is below 20s and filesize is > 300kB
            # to avoid overloading the system with read queries
            pass
        elif self.lu_time < filename.stat().st_mtime:
            # file has changed after last update,
            # reload the data into the file structure
            ret = self.fetch_data(check=check)
            self.reload_data()
            self.spw.refresh_all_plots()
            self.refresh_columns_size()
        return ret

    def refresh_columns_size(self):
        """Refresh size of all columns."""
        self.column_items = [
            f"{name} ({unit}), shape: {shape}"
            for name, unit, shape in zip(self.names, self.units, self.shapes)
        ]
        # change names to reflect the dimensions
        for i in range(3):
            for j, item in enumerate(self.column_items):
                self.column_selector[i].setItemText(j + 1, item)

    def reset(self):
        """Reset the actual data view."""
        self.w_plot2d.setChecked(False)
        self.w_plot2d_comp.setChecked(False)
        self.w_transpose.setChecked(False)
        if self.iv is not None:
            self.grid.removeWidget(self.iv)
            del self.iv
            self.iv = None

    def fetch_data(self, check=False) -> int:
        """Handle the data operations."""
        try:
            ret = 0
            self.header, self.data = loadmatrix(str(self.filename), replace_None=True)
            names = self.header["columns"]
            units = self.header["units"]
            shapes = [self.data[col].shape for col in names]
            if check is True:
                if self.names != names:
                    ret = -1
                elif shapes != self.shapes:
                    ret = -2
                elif units != self.units:
                    # TODO: Discuss whether this should reset
                    # or just regenerate names
                    ret = -2
            self.names = names
            self.units = units
            self.shapes = shapes
            # update meta data info
            self.meta_viewer.update_data(self.header)
        except Exception:
            # file could not be opened
            exc_type, exc_value, exc_traceback = sys.exc_info()
            _ = QMessageBox.critical(
                self,
                "Error when opening file",
                f"""
The following error was raised when opening the file:
{repr(exc_value)}
Please investigate the error and eventually restart matrix-preview""",
            )
            sys.exit(-1)

        # update timer
        self.lu_time = time.time()
        return ret

    def reload_data(self):
        """
        Wrap the 1d and 2d plotting functions.

        Also, decide which one is appropriate from the state of the gui.
        """
        if self.w_plot2d.isChecked() is True or self.w_plot2d_comp.isChecked() is True:
            ret = self.reload_data_2d()
        else:
            ret = self.reload_data_curve()
        # handle the error if there is any
        self.handle_error(ret)

    def handle_error(self, ret):
        """Handle a possible dimension error of the reload_data function."""
        if ret == -1:
            self.raise_error("data axis cannot be reshaped, lengths not multiples")
        elif ret == -2:
            self.raise_error("data has too high dimension for 1d slicing")
        elif ret == -3:
            self.raise_error("no data selected")
        elif ret == -4:
            self.raise_error("data shapes complicated, do not know what to do")
        elif ret == -5:
            self.raise_error("data has too low or too high dimension for 2d plot")
        elif ret == -6:
            self.raise_error("data has too high dimension for 2d slicing")
        elif ret == -7:
            self.raise_error("data in x does not have correct dimension")
        elif ret == -8:
            self.raise_error("data in y does not have correct dimension")
        elif ret == -9:
            self.raise_error("data array with zero length dimension is present")
        if ret > 0 and self.error is True:
            self.error = False
            self.w_status.setVisible(False)

    def reload_data_2d(self):
        """Reload the data in the 2d case."""
        indexZ, indexX, indexY = [self.column_selector[i].currentIndex() - 1 for i in range(3)]

        # Declare the dictionaries as Optional[PlotData]
        x: PlotData | None = None
        y: PlotData | None = None
        z: PlotData | None = None

        if indexZ == -1:
            # empty index selected
            return -3

        data_vars: list[PlotData | None] = [z, x, y]
        indices = [indexZ, indexX, indexY]

        for i, index in enumerate(indices):
            if index == -1:
                dim = 0
                data_vars[i] = {
                    "label": "",
                    "desig": 0,
                    "unit": "",
                    "data": NO_DATA,
                    "shape": (0,),
                    "dim": 0,
                }
            else:
                dim = len(self.shapes[index])
                name = self.names[index]
                data = self.data[name]

                if data.size == 0:
                    return -9

                data_vars[i] = {
                    "label": name,
                    "desig": index + 1,
                    "unit": self.units[index],
                    "data": data,
                    "shape": data.shape,
                    "dim": dim,
                }
            if dim > 2 and i == 0 and self.w_plot2d_comp.isChecked() is True:
                self.column_selector[1].setEnabled(True)
            elif i == 0 and self.w_plot2d_comp.isChecked() is True:
                self.column_selector[1].setEnabled(False)
                self.column_selector[1].setCurrentIndex(0)
            elif i == 0 and self.column_selector[1].isEnabled() is False:
                # if coming from complex view and x was disabled, enable now
                self.column_selector[1].setEnabled(True)
            if dim > 2 and i == 0 and self.w_plot2d_comp.isChecked() is False:
                # 3D plotting, disable y since it is not meaningful here
                # x gives the plotting axis (i.e. value corresponding to index)
                self.w_l[2].setVisible(False)
                self.column_selector[2].setVisible(False)
                self.column_selector[2].setCurrentIndex(0)
            elif i == 0 and self.w_plot2d_comp.isChecked() is False:
                self.w_l[2].setVisible(True)
                self.column_selector[2].setVisible(True)
            if (dim < 2 and i == 0) or dim > 3:
                # dimensions not compatible
                # <1D or >3D data cannot be 2d plotted.
                return -5

        z, x, y = data_vars

        # Check for the sentinel value
        if x is None or y is None or z is None or z["data"] is NO_DATA:
            return -9
        # data in a 2d plot can always be transposed
        self.w_transpose.setVisible(True)

        # data is loaded, now try to combine the data so that it becomes
        # plottable in a 2d plot
        transpose = False
        if self.w_transpose.isChecked() is True:
            transpose = True
            if z["dim"] == 3:
                z["data"] = z["data"].transpose(0, 2, 1)
            else:
                z["data"] = z["data"].T
        z["shape"] = z["data"].shape
        if x["data"] is NO_DATA:
            x = PlotData(
                label="array index",
                unit="",
                dim=1,
                data=np.arange(z["shape"][0]),
                desig=0,
                shape=(z["shape"][0],),
            )
        else:
            index = 1 if (transpose is True and x["dim"] > 1) else 0
            lenx = x["shape"][index]
            if lenx != z["shape"][0]:
                return -7
            if x["dim"] < 2:
                x["data"] = np.linspace(x["data"][0], x["data"][-1], lenx)
            else:
                if transpose is False:
                    x["data"] = np.linspace(x["data"][0, 0], x["data"][-1, 0], lenx)
                else:
                    x["data"] = np.linspace(x["data"][0, 0], x["data"][0, -1], lenx)
            x["shape"] = (lenx,)
            x["dim"] = 1

        if y["data"] is NO_DATA:
            y = PlotData(
                label="array index",
                unit="",
                dim=1,
                data=np.arange(z["shape"][1]),
                desig=0,
                shape=(z["shape"][1],),
            )
        else:
            index = 1 if transpose is False and y["dim"] > 1 else 0
            leny = y["shape"][index]
            if leny != z["shape"][1]:
                return -8
            if y["dim"] < 2:
                y["data"] = np.linspace(y["data"][0], y["data"][-1], leny)
            else:
                if transpose is False:
                    y["data"] = np.linspace(y["data"][0, 0], y["data"][0, -1], leny)
                else:
                    y["data"] = np.linspace(y["data"][0, 0], y["data"][-1, 0], leny)
            y["shape"] = (leny,)
            y["dim"] = 1

        if self.w_plot2d_comp.isChecked() is True:
            if z["dim"] > 2:
                axes = {"t": 0, "x": 1, "y": 2}
            else:
                axes = {"x": 0, "y": 1}
            if self.iv is not None:
                self.iv.setImage(z["data"], axes=axes, xvals=x["data"])
                self.iv.getView().invertY(False)
                self.iv.getView().setAspectLocked(False)
                self.iv.getHistogramWidget().axis.setLabel(z["label"])
        else:
            self.spw.plot(z, x, y, plot2d=self.w_plot2d.isChecked())
        return 0

    @no_type_check
    def reload_data_curve(self):
        """
        Reload the data.

        Try to make the dimensions suitable for a 1D curve plot by smart
        guessing from the data dimension.
        """
        indexY, indexX = [self.column_selector[i].currentIndex() - 1 for i in range(2)]

        # disable transpose widget
        self.w_transpose.setVisible(False)

        y: PlotData | None = None
        x: PlotData | None = None

        if indexY == -1:
            # empty index selected
            return -3
        elif indexX == -1:
            # set up axis labels and units according to index
            dim = len(self.shapes[indexY])
            if dim >= 3:
                return -2
            if dim == 2:
                self.w_transpose.setVisible(True)

            yname = self.names[indexY]

            y_data = self.data[yname]
            if self.w_transpose.isChecked() is True and dim == 2:
                y_data = y_data.T

            y = {
                "label": yname,
                "desig": indexY + 1,
                "unit": self.units[indexY],
                "data": y_data,
                "shape": y_data.shape,
                "dim": dim,
            }

            x_shape = (y["shape"][0],)
            x = {
                "label": "array index",
                "unit": "",
                "dim": 1,
                "data": np.arange(y["shape"][0]),
                "desig": 0,
                "shape": x_shape,
            }
        else:
            # both axes are defined, set up x and y dictionary
            yname = self.names[indexY]
            y = {
                "label": yname,
                "desig": indexY + 1,
                "unit": self.units[indexY],
                "data": self.data[yname],
                "shape": self.shapes[indexY],
                "dim": len(self.shapes[indexY]),
            }
            xname = self.names[indexX]
            x = {
                "label": xname,
                "desig": indexX + 1,
                "unit": self.units[indexX],
                "data": self.data[xname],
                "shape": self.shapes[indexX],
                "dim": len(self.shapes[indexX]),
            }

        if y["data"].size == 0 or x["data"].size == 0:
            return -9

        # data is loaded, now try to combine the data so that it becomes
        # plottable in a curve/scatter plot
        if x["shape"] != y["shape"]:
            # data has uneqal shape, so we need to think about format
            if x["dim"] == 1 and y["dim"] == 1:
                # one dimensional data but of uneven length
                # attempt to reshape
                small_axis = min(x["shape"][0], y["shape"][0])
                large_axis = max(x["shape"][0], y["shape"][0])
                if large_axis % small_axis == 0:
                    # data can be reshaped
                    x["data"] = x["data"].reshape(small_axis, -1)
                    y["data"] = y["data"].reshape(small_axis, -1)
                else:
                    # data cannot be reshaped, abort
                    return -1
            elif x["shape"][0] == y["shape"][0]:
                # same length on first axis, reshape into sets of curves
                # with the length given by the identical axis.
                x["data"] = x["data"].reshape(x["shape"][0], -1)
                y["data"] = y["data"].reshape(x["shape"][0], -1)
                # This will flatten 3D arrays into something that can be
                # previewed as curve, although it does not make too
                # much sense.
            elif x["data"].size == y["data"].size:
                # data has same size, try to reshape to the one with higher
                # dimension
                reshape_dim = x["shape"] if x["dim"] > y["dim"] else y["shape"]
                x["data"] = x["data"].reshape(reshape_dim)
                y["data"] = y["data"].reshape(reshape_dim)
                # Might be smarter to flatten?
            else:
                # data multidimensional but with different dimensions, so
                # we do not know how to handle this
                return -4
        else:
            # data identical with single or multiple dimension, no reshaping
            # required
            if x["dim"] < 3:
                # data is has lower dimension than three
                if x["dim"] == 2:
                    # identidcal 2D data on both axes,
                    # allow and handle transposition
                    self.w_transpose.setVisible(True)
                    if self.w_transpose.isChecked() is True:
                        x["data"] = x["data"].T
                        y["data"] = y["data"].T
            else:
                # data has too many dimensions to display, one can possibly
                # reshape for the first axis to match and flatten the data
                # to two dimensions, but this will be horrible for the meaning
                # of 3D data. I see no use case in implementing this
                return -2

        # update meta information and data
        self.spw.plot(y, x, plot2d=self.w_plot2d.isChecked())
        return 0


def main(file: str | None = None):
    """Set the basic GUI parameters and run."""
    install_error_handler()
    app = MApplication(sys.argv)
    app.setDesktopFileName("matrix-preview")
    # we need to ignore this signal here otherwise we are kicked into
    # background when matrix returns. see run_as_fg_process
    if hasattr(signal, "SIGTTOU"):  # signal only on POSIX compliant systems
        signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    if file is not None:
        ex = SweepPreview(None, Path(file))
    elif len(sys.argv) < 2:
        ex = SweepPreview(None, None)
    else:
        ex = SweepPreview(None, Path(sys.argv[1]))
    ex.show()
    ex.restore_window_state()
    ret = app.exec()
    sys.exit(ret)
