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
"""
Generate sweeps for matrix via a straightforward GUI.

It heavily relies on numpy.linspace for the creation of the sweep
segments.
"""

import os
import re
import sys
import time
import traceback
from ast import literal_eval
from math import floor
from os.path import basename, splitext

import pyqtgraph as pg
from numpy import linspace, uint
from PyQt6.QtCore import QByteArray, QEvent, QSettings, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QKeySequence, QPalette
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import matr1x
from matr1x import datetimefmt, system_directories, system_names, usersfolder
from matr1x.control.util import QtGracefulKiller
from matr1x.gui_util import (
    AboutBox,
    CustomViewBox,
    MApplication,
    SystemListWidget,
    check_config,
    create_tray_notification,
    get_application_instance,
    get_matrix_icon,
    open_matrix_toml,
    save_messagebox,
    validator,
)
from matr1x.system import MergedSystem
from matr1x.util import (
    calculate_sweep,
    create_temp_dir_with_symlinks,
    generate_col_index,
    get_importable_module_name,
    set_correct_mac_appname,
)

if sys.platform == "win32":
    try:
        from ctypes import windll

        myappid = "python.matr1x.sweep-generator.version"
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass


def add_focusInEvent(cls):
    """Add a focusIn signal and focusInEvent handling."""

    class decorated_class(cls):
        """The class shell."""

        focusIn = pyqtSignal()

        def focusInEvent(self, e: QEvent, parent=None):
            super().focusInEvent(e)
            self.focusIn.emit()

    return decorated_class


@add_focusInEvent
class CheckBoxFocus(QCheckBox):
    """Reimplement CheckBox with focusInEvent."""


@add_focusInEvent
class LineEditFocus(QLineEdit):
    """Reimplement LineEdit with focusInEvent."""


@add_focusInEvent
class SpinBoxFocus(QSpinBox):
    """Reimplement QSpinBox with focusInEvent."""


class QLabelWithColor(QLabel):
    """Allow QLabel with highlight color and mouseclick reaction."""

    clicked = pyqtSignal(int)

    def __init__(self):
        """Init with colored background for bright and dark mode."""
        super().__init__()
        self.color_bright = "#DCF5D4"
        self.color_dark = "#325725"
        self._update_colors()

    def _update_colors(self) -> None:
        """Change color while avoiding recursion."""
        self.updating_stylesheet = True
        self.stylesheet_bright = f"""
                     QLabel {{
                         background-color: {self.color_bright};
                         color: black;
                     }}
                 """
        self.stylesheet_dark = f"""
                     QLabel {{
                         background-color: {self.color_dark};
                         color: #DBDBDB;
                     }}
                 """
        if QTextEdit().palette().color(QPalette.ColorRole.Text).value() > 128:
            self.setStyleSheet(self.stylesheet_dark)
        else:
            self.setStyleSheet(self.stylesheet_bright)
        self.updating_stylesheet = False

    def changeEvent(self, a0):
        """Detect palette changes such as dark and bright mode desktops."""
        if a0 is not None:
            if a0.type() == QEvent.Type.PaletteChange and not self.updating_stylesheet:
                self._update_colors()
        return super().changeEvent(a0)

    def mousePressEvent(self, ev):
        """
        Detect mouse-click for proper column highlighting.

        The column of the click is emitted as a pyqtSignal.
        """
        if ev is not None:
            if ev.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit(ev)
                active_window = MApplication.activeWindow()
                if active_window is not None:
                    active_window.setFocus()
        return super().mousePressEvent(ev)

    def setColors(self, color_bright: str, color_dark: str) -> None:
        """
        Change the colors for both modes.

        Parameters
        ----------
        color_bright : str
            The six digit hex code for the bright mode color (e.g. #DCF5D4).
        color_dark : str
            The six digit hex code for the dark mode color
        """
        self.color_bright = color_bright
        self.color_dark = color_dark
        self._update_colors()


class SweepPreviewPopup(QDialog):
    """
    Show the sweep as list and as plot in a pop-up.

    Parameters
    ----------
    index : int
      index of column in sweep to be displayed on startup
    sweep : list
      list of sweeps for each column
    cols : list
      list of column names
    units :list
      list of column units
    csign : list
      list of corresponding parameter identifiers
    """

    def __init__(self, parent, index, sweep, cols, units, csign):
        super().__init__(parent)
        self.sweep = sweep
        self.cols = cols
        self.units = units
        self.csign = csign
        self.canvas = None

        # initialize ui
        main_layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        self.data_table = QTableWidget()
        self.data_table.setColumnCount(1)
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setHorizontalHeaderLabels(["Value"])
        header = self.data_table.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.Stretch)

        # add label to show cursor position
        self.posLabel = QLabel("x: {:e}\ny: {:e}".format(0, 0))

        # populate combo box with column names and identifiers
        comboBox = QComboBox()
        columns = []
        for c, cs in zip(self.cols, self.csign):
            columns.append(cs + " - " + c.strip())
        comboBox.addItems(columns)
        comboBox.setCurrentIndex(index)
        comboBox.currentIndexChanged.connect(self.indexChanged)

        pg.setConfigOption("background", "w")
        pg.setConfigOption("foreground", "k")
        self.vb = CustomViewBox()
        self.pw = pg.PlotWidget(viewBox=self.vb, name="plot1", enableMenu=False)
        self.plt = self.pw.plot()
        self.plt.setPen((0, 0, 153), width=3)

        self.proxy = pg.SignalProxy(
            self.pw.scene().sigMouseMoved, rateLimit=30, slot=self.mouseMoved
        )

        self.plotListRangeX(index)
        self.update_data_table(index)

        left_layout.addWidget(comboBox)
        left_layout.addWidget(self.data_table)
        right_layout.addWidget(self.posLabel)
        right_layout.addWidget(self.pw)
        main_layout.addLayout(left_layout)
        main_layout.addLayout(right_layout)

        self.setLayout(main_layout)
        self.show()

    def indexChanged(self, newIndex: int) -> None:
        """
        Show the interface for new index if index is changed.

        Parameters
        ----------
        newIndex : int
            The updated index.
        """
        self.plotListRangeX(newIndex)
        self.update_data_table(newIndex)

    def update_data_table(self, index: int) -> None:
        """
        Update the table to show the current sweep.

        Parameters
        ----------
        index : int
            The index of the sweep to be displayed.
        """
        self.data_table.setRowCount(len(self.sweep[index]))
        for index, item in zip(range(len(self.sweep[index])), self.sweep[index]):
            value = QTableWidgetItem(str(item))
            value.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.data_table.setItem(index, 0, value)
        self.data_table.update()

    def mouseMoved(self, ev):
        """Implement event to update cursor position while pointer is in plot."""
        mousePoint = self.vb.mapSceneToView(ev[0])
        self.posLabel.setText("x: {:e}\ny: {:e}".format(mousePoint.x(), mousePoint.y()))

    def plotListRangeX(self, index):
        """Update the plot to show sweep[index] against its range."""
        self.pw.getAxis("left").textWidth = 0
        length = len(self.sweep[index])
        self.plt.setData(x=linspace(0, length, length), y=self.sweep[index], symbol="o")

        self.pw.setLabel("bottom", "index")
        self.pw.setLabel(
            "left", (self.cols[index].strip() + " [" + self.units[index].strip() + "]")
        )


class MainWindow(QMainWindow):
    """
    Define main layout, run everything.

    Parameters
    ----------
    filename : str
      Sweep file to load for editing
    system : str
      path to system(s) for which an input file should be generated
    inputcb : function handle
      callback function used to return the filename of the generated file
    """

    extension = ".sw8"

    def __init__(self, filename=None, system=None, inputcb=None):
        super().__init__()
        self.setWindowIcon(get_matrix_icon("matr1x-sweep-generator.png"))

        # file handling helpers
        self.system = system
        self.inputcb = inputcb
        self.last_loaded_system = None
        self.last_filename = ""
        self.dirty = False
        self.shortcut_dir = None

        # allow to store the settings
        self.settings = QSettings("matr1x", "sweep-generator")

        # column variables
        self.flat_col = []
        self.flat_unit = []
        self.col_sign = []

        # sweep variables
        self.loop_over = []
        self.up_down = []
        self.repeat = []
        self.sweep_params = []
        self.systemFilename = ""

        # gui variables
        self.preview_column = 1
        self.labels = (
            ("column", "Column"),
            ("nameunit", "Name (Unit)"),
            ("start", "Start value"),
            ("end", "End value"),
            ("points", "Point count"),
            ("append", "Append sweep"),
            ("repeat", "Repeat"),
            ("updown", "Up-down"),
            ("loopover", "Loop over"),
        )
        # initialize generic (system independent) part of ui
        self.outputList = None
        self.populated = False

        # Enable dragging and dropping onto the widget
        self.setAcceptDrops(True)
        self.init_ui()
        # If filename is passed as command line argument
        if filename is not None:
            if self.is_valid_extension(filename):
                self.open_file(filename)
                self.last_filename = filename

    def closeEvent(self, a0):
        """
        Store settings before closing app.

        If the script was modified without saving, a dialog asks how to
        proceed.
        """
        if a0 is not None:
            if self.dirty:
                ret = save_messagebox(self)
                if ret == QMessageBox.StandardButton.Cancel:
                    a0.ignore()
                    return
                if ret == QMessageBox.StandardButton.Save:
                    if not self.save_file():
                        # if save fails, ignore message
                        a0.ignore()
                        return
            self.save_window_state()
            a0.accept()

    def save_window_state(self) -> None:
        """
        Save application configuration until next startup.

        For convenience, main window geometry and toolbar placement are
        saved.
        """
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("toolbar_placement", self.toolBarArea(self.toolbar))

    def restore_window_state(self) -> None:
        """
        Restore application configuration to look similar to the previous use.

        Main window geometry and toolbar placement are restored.
        """
        # Just in case it is the first start
        self.resize(self.sizeHint())
        self.restoreGeometry(self.settings.value("geometry", QByteArray()))
        self.addToolBar(
            self.settings.value("toolbar_placement", Qt.ToolBarArea.TopToolBarArea),
            self.toolbar,
        )

    def toggle_toolbar_view(self, checked):
        """Toogles the visibility of the toolbar on and off."""
        if checked:
            self.toolbar.show()
        else:
            self.toolbar.hide()

    def init_ui(self) -> None:
        """Generate the main GUI."""
        self.setWindowTitle("Sweep Generator")
        # Start the layout
        self.grid = QGridLayout()
        self.grid.setVerticalSpacing(5)
        self.grid.setHorizontalSpacing(10)
        main_layout = QVBoxLayout()
        main_layout.addLayout(self.grid)
        self.utility_layout = QVBoxLayout()
        main_layout.addLayout(self.utility_layout)
        self.main_widget = QWidget()
        self.main_widget.setLayout(main_layout)
        self.setCentralWidget(self.main_widget)
        # generate sweep grid labels and layout
        self.sweep_table = QTableWidget()
        self.sweep_table.setColumnCount(4)
        self.sweep_table.setHorizontalHeaderLabels(["Start", "Stop", "Points", "Delete"])
        header = self.sweep_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.sweep_table.verticalHeader().hide()
        self.sweep_preview = QTableWidget()
        self.sweep_preview.setColumnCount(1)
        self.sweep_preview.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sweep_preview.setAlternatingRowColors(True)
        self.sweep_preview.setHorizontalHeaderLabels(["Preview of the generated sweep-parameters"])
        header = self.sweep_preview.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.Stretch)
        table_width = self.sweep_preview.viewport().width()
        self.sweep_preview.setColumnWidth(0, table_width)
        central_view = QHBoxLayout()
        central_view.addWidget(self.sweep_preview)
        central_view.addWidget(self.sweep_table)
        self.utility_layout.addLayout(central_view)
        self.create_actions()
        self.create_toolbar()
        self.create_menu()
        check_config(matr1x.config)

    def create_actions(self) -> None:
        """Create all QActions of this application."""
        self.matrix_settings_action = QAction("Show matrix toml", self)
        self.matrix_settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        self.matrix_settings_action.setShortcut(QKeySequence.StandardKey.Preferences)
        self.matrix_settings_action.triggered.connect(open_matrix_toml)
        self.about_action = QAction("About", self)
        self.about_action.setMenuRole(QAction.MenuRole.AboutRole)
        self.about_action.triggered.connect(self.info_box)
        self.new_file_action = QAction(get_matrix_icon("SP_FileIcon"), "New", self)
        self.new_file_action.triggered.connect(self.new_file)
        self.new_file_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_file_action.setEnabled(False)
        self.load_action = QAction(get_matrix_icon("SP_DialogOpenButton"), "Open", self)
        self.load_action.triggered.connect(self.gui_from_sweep)
        self.load_action.setShortcut(QKeySequence.StandardKey.Open)
        self.add_system_action = QAction(
            get_matrix_icon("CHAR_+", QColor("RoyalBlue")), "Add System", self
        )
        self.add_system_action.triggered.connect(self.add_system)
        self.remove_system_action = QAction(
            get_matrix_icon("CHAR_-", QColor("RoyalBlue")), "Remove System", self
        )
        self.remove_system_action.setEnabled(False)
        self.remove_system_action.triggered.connect(self.delete_selected_system)
        self.systemList = SystemListWidget(self)
        self.systemList.orderChanged.connect(self.filename_changed)
        self.systemList.setMinimumHeight(50)
        self.systemList.setMaximumHeight(50)
        self.save_action = QAction(get_matrix_icon("SP_DialogSaveButton"), "Save", self)
        self.save_action.triggered.connect(self.save_file)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.setEnabled(False)
        self.save_as_action = QAction(get_matrix_icon("SP_DialogSaveButton"), "Save As...", self)
        self.save_as_action.triggered.connect(lambda: self.save_file(dialog=True))
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.append_action = QAction(get_matrix_icon("SP_DialogSaveButton"), "Append", self)
        self.append_action.triggered.connect(lambda: self.save_file(append=True))
        self.append_to_action = QAction(
            get_matrix_icon("SP_DialogSaveButton"), "Append To...", self
        )
        self.append_to_action.triggered.connect(lambda: self.save_file(append=True, dialog=True))
        self.save_button = QToolButton()
        self.save_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.save_button.setIcon(get_matrix_icon("SP_DialogSaveButton"))
        self.save_button.setText("Save")
        self.save_button.setDefaultAction(self.save_action)
        self.save_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        save_pulldown = QMenu(self)
        save_pulldown.addAction(self.save_as_action)
        save_pulldown.addAction(self.append_action)
        save_pulldown.addAction(self.append_to_action)
        self.save_button.setMenu(save_pulldown)
        self.quit_action = QAction("Quit", self)
        if os.name == "nt":
            self.quit_action.setShortcut(QKeySequence.StandardKey.Close)
        else:
            self.quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.quit_action.triggered.connect(self.close)
        self.sweep_action = QAction(get_matrix_icon("SP_BrowserReload"), "Draft Sweep", self)
        self.sweep_action.triggered.connect(self.print_sweep_to_preview)
        self.sweep_action.setEnabled(False)
        self.toggle_toolbar_action = QAction("Show Toolbar", self)
        self.toggle_toolbar_action.setShortcut(QKeySequence("Ctrl+1"))
        self.toggle_toolbar_action.setCheckable(True)
        self.toggle_toolbar_action.setChecked(True)
        self.toggle_toolbar_action.triggered.connect(self.toggle_toolbar_view)
        self.preview_action = QAction(
            get_matrix_icon("matr1x-matrix-preview.png", QColor("RoyalBlue")), "Preview", self
        )
        self.preview_action.triggered.connect(self.preview_sweep)
        self.preview_action.setEnabled(False)

    def create_toolbar(self) -> None:
        """Create the Toolbar."""
        self.toolbar = QToolBar("Toolbar")
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.toolbar.setFloatable(False)
        self.toolbar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        icon_size = get_application_instance().toolbar_icon_size()
        self.toolbar.setIconSize(QSize(icon_size, icon_size))
        self.toolbar.setAllowedAreas(
            Qt.ToolBarArea.TopToolBarArea | Qt.ToolBarArea.BottomToolBarArea
        )
        self.toolbar.addAction(self.new_file_action)
        self.toolbar.addAction(self.load_action)
        self.toolbar.addWidget(self.save_button)
        self.toolbar.addAction(self.sweep_action)
        empty = QWidget()
        empty.setFixedWidth(icon_size)
        empty2 = QWidget()
        empty2.setFixedWidth(icon_size)
        self.toolbar.addWidget(empty)
        self.toolbar.addAction(self.preview_action)
        self.toolbar.addWidget(empty2)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.add_system_action)
        self.toolbar.addWidget(self.systemList)
        self.toolbar.addAction(self.remove_system_action)
        self.toolbar.visibilityChanged.connect(self.toggle_toolbar_action.setChecked)
        self.addToolBar(self.toolbar)

    def create_menu(self) -> None:
        """Create the main menu."""
        menu = self.menuBar()
        assert menu is not None
        file_menu = menu.addMenu("&File")
        assert file_menu is not None
        file_menu.addAction(self.new_file_action)
        file_menu.addAction(self.load_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addAction(self.append_action)
        file_menu.addSeparator()
        file_menu.addAction(self.add_system_action)
        file_menu.addAction(self.remove_system_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)  # This gets auto-moved on a Mac
        #
        control_menu = menu.addMenu("&Control")
        assert control_menu is not None
        control_menu.addAction(self.sweep_action)
        #
        view_menu = menu.addMenu("&View")
        assert view_menu is not None
        view_menu.addAction(self.toggle_toolbar_action)
        view_menu.addAction(self.matrix_settings_action)
        #
        help_menu = menu.addMenu("&Help")
        assert help_menu is not None
        help_menu.addAction(self.about_action)

    def info_box(self) -> None:
        """Display an 'about this app' widget."""
        box = AboutBox(
            "Sweep Generator",
            get_matrix_icon("matr1x-sweep-generator.png"),
            matr1x,
            matr1x.datetimefmt,
        )
        box.exec()

    def is_valid_extension(self, file_path):
        """Return True if extension is valid."""
        pattern = re.compile(r"\.\d+t$")
        # remove old pattern with next major update, i.e. Matrix v9
        if pattern.search(file_path) is not None:
            return True
        elif self.extension in file_path:
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
        """Enable drag and drop (2)."""
        urls = event.mimeData().urls()
        if len(urls) == 1:
            file_path = urls[0].toLocalFile()
            if self.is_valid_extension(file_path):
                self.open_file(file_path)
            else:
                warning_text = (
                    "Only files with extensions matching .<number>t "
                    f"or {self.extension} are supported."
                )
                QMessageBox.warning(
                    self,
                    "Invalid File",
                    # remove old pattern with next major update
                    warning_text,
                )
        else:
            QMessageBox.warning(self, "Multiple Files", "Please drop only a single file.")

    def reset_layout(self) -> None:
        """Reset layout to clean state."""
        if self.populated:
            self.sweep_params = []
            self.flat_col = []
            self.clear_layout(self.grid)
            self.sweep_table.setRowCount(0)
            self.sweep_preview.setRowCount(0)

    def filename_changed(self) -> bool:
        """
        Import new system because a filename changed.

        Returns
        -------
        bool
            True on success and False on error during import.
        """
        if any(sublist for sublist in self.sweep_params):
            create_tray_notification(
                "Sweep reset", "All previous sweep parameters have been cleared.", self
            )
        filenames = [self.systemList.item(j).text() for j in range(self.systemList.count())]
        if 0 == len(filenames):
            self.reset_layout()
            self.new_file_action.setEnabled(False)
            self.save_action.setEnabled(False)
            self.save_as_action.setEnabled(False)
            self.append_action.setEnabled(False)
            self.sweep_action.setEnabled(False)
            self.preview_action.setEnabled(False)
            self.remove_system_action.setEnabled(False)
            return False
        self.new_file_action.setEnabled(True)
        self.save_action.setEnabled(True)
        self.save_as_action.setEnabled(True)
        self.append_action.setEnabled(True)
        self.sweep_action.setEnabled(True)
        self.preview_action.setEnabled(True)
        self.remove_system_action.setEnabled(True)
        modulestr = ""
        # update entries in GUI list
        for j, systemfile in enumerate(filenames):
            self.systemList.item(j).setText(systemfile)
        self.systemFilename = ",".join(filenames)
        try:
            self.system = MergedSystem.from_files(filenames)
        except Exception as e:
            if isinstance(e, ModuleNotFoundError):
                error_text = '<p style="color:red">Please check the path to the system files and '
                error_text += "whether all required dependencies are present.</p>"
            else:
                error_text = "The following error was raised during system "
                error_text += "import, please check the system for errors.\n\n"
            tbinfo = traceback.format_exception(type(e), e, e.__traceback__)
            tbstr = "".join(tbinfo)
            error_text += "" + tbstr
            QMessageBox.warning(self, "Import error.", error_text.replace("\n", "<br>"))
            return False
        for file in filenames:
            modulestr += basename(splitext(file)[0]) + ","
        # update gui using the system specifications
        self.process_system_import()
        return True

    def process_system_import(self) -> None:
        """Process specified system imports and populate layout."""
        if len(self.system.columns) != len(self.system.units):
            # simple sanity check
            QMessageBox.warning(
                self,
                "Import error!",
                "Lists with columns, units and settables of unequal length, check system file.",
            )
            return
        self.reset_layout()
        # store old columns
        old_cols = self.flat_col
        # Initalize sweep lists
        self.col_sign = []
        # generate list of settable parameters
        settables, self.flat_col, self.flat_unit = self.system.settable_columns()
        for i, (settable, col) in enumerate(zip(settables, self.system.columns)):
            # add a column for each settable parameter in the system
            if settable is True:
                if isinstance(col, (tuple, list)):
                    # if parameter has multiple values, add multiple columns
                    for c in col:
                        self.col_sign.append(generate_col_index(i))
                else:
                    self.col_sign.append(generate_col_index(i))
        # columns are initialized, get already available columns from
        # the old columns, save the sweep params and their new location
        save_sweep_params = {}
        for index, old_col in enumerate(old_cols):
            if old_col in self.flat_col:
                newloc = self.flat_col.index(old_col)
                save_sweep_params[newloc] = self.sweep_params[index]
        # populate the actual number of used parameters (fully flattened)
        self.nParmsUsed = len(self.flat_col)
        # generate empty list of list for the sweep parameters
        self.sweep_params = []
        for pos in range(self.nParmsUsed):
            if pos in save_sweep_params.keys():
                # if parameter was already defined before, keep sweep params
                self.sweep_params.append(save_sweep_params[pos])
            else:
                # otherwise, set empty list
                self.sweep_params.append([])
        self.populate_layout()
        self.populated = True

    def get_custom_widget(self, name: str, column: int = 0) -> QWidget:
        """
        Receive a custom widget for use in the GUI.

        We need a new istance of a widget every time, otherwise Qt moves it
        to the last position.

        Parameters
        ----------
        name : str
            The custom name of the widget to receive.
        column : int
            The column of the widget.

        Returns
        -------
        QWidget
            The widget.
        """
        if name == "column" or name == "nameunit":
            widget = QLabelWithColor()
            widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            widget.clicked.connect(lambda: self.populate_sweep_grid(column))
        elif name == "start" or name == "end" or name == "points":
            widget = LineEditFocus()
            widget.setAlignment(Qt.AlignmentFlag.AlignRight)
            widget.focusIn.connect(lambda: self.populate_sweep_grid(column))  # ty: ignore [unresolved-attribute] issue #143
            widget.textChanged.connect(
                lambda text, column=column - 1: self.update_append(text, column)
            )
            if name == "points":
                widget.setValidator(validator[int])
            else:
                widget.setValidator(validator[float])
        elif name == "repeat":
            widget = SpinBoxFocus()
            widget.setRange(1, 999)
            widget.setAlignment(Qt.AlignmentFlag.AlignRight)
            widget.focusIn.connect(lambda: self.populate_sweep_grid(column))  # ty: ignore [unresolved-attribute] issue #143
            widget.valueChanged.connect(lambda: self.update_window_title(dirty=True))
        elif name == "append":
            widget = QPushButton("+")
            temp_widget = QLineEdit(None)
            size = temp_widget.sizeHint().height()
            temp_widget.deleteLater()
            # A vertical button that almost spans the three lines it appends looks nice
            widget.setFixedSize(size, int(2.9 * size))
            widget.clicked.connect(lambda: self.append_sweep_col(column))
            widget.clicked.connect(lambda: self.update_window_title(dirty=True))
        elif name == "updown":
            widget = CheckBoxFocus(self)
            widget.focusIn.connect(lambda: self.populate_sweep_grid(column))  # ty: ignore [unresolved-attribute] issue #143
            widget.stateChanged.connect(lambda: self.update_window_title(dirty=True))
        elif name == "loopover":
            widget = QComboBox(self)
            widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            font = widget.font()
            font.setPointSize(font.pointSize() - 1)
            widget.setFont(font)
            columns = ["None"]
            for i in range(self.nParmsUsed):
                columns.append(self.flat_col[i].strip())
            widget.addItems(columns)
            widget.activated.connect(lambda: self.populate_sweep_grid(column))
            widget.currentIndexChanged.connect(lambda: self.update_window_title(dirty=True))
        else:
            raise ValueError(f"Unknown widget {name}.")
        return widget

    def populate_layout(self) -> None:
        """Populate sweep control and data fields."""
        self.grid_widgets = []
        color1 = True
        last_letter = self.col_sign[0][0]
        for column in range(self.nParmsUsed):
            sweep_widgets = {}
            for label in self.labels:
                sweep_widgets[label[0]] = self.get_custom_widget(label[0], column=column + 1)
            sweep_widgets["column"].setText(self.col_sign[column])
            nameunit = f"{self.flat_col[column].strip()} ({self.flat_unit[column].strip()})"
            sweep_widgets["nameunit"].setText(nameunit)
            # alternate the column label colors
            letter = self.col_sign[column][0]
            if letter != last_letter:
                last_letter = letter
                color1 = not color1
            if not color1:
                sweep_widgets["column"].setColors("#D0EBFE", "#1E4962")
                sweep_widgets["nameunit"].setColors("#D0EBFE", "#1E4962")
            self.grid_widgets.append(sweep_widgets)

        self.grid.addWidget(QLabel(self.labels[0][1]), 0, 0)
        self.grid.addWidget(QLabel(self.labels[1][1]), 1, 0)
        parameters = QVBoxLayout()
        parameters.addWidget(QLabel(self.labels[2][1]))
        parameters.addWidget(QLabel(self.labels[3][1]))
        parameters.addWidget(QLabel(self.labels[4][1]))
        self.grid.addLayout(parameters, 2, 0)
        modifiers = f"{self.labels[6][1]}/ {self.labels[7][1]}"
        self.grid.addWidget(QLabel(modifiers), 3, 0)
        combolabel = f"{self.labels[8][1]}\n "
        self.grid.addWidget(QLabel(combolabel), 4, 0)
        # determine how many columns can fit
        combobox = self.get_custom_widget("loopover")
        max_width = combobox.minimumSizeHint().width() + self.grid.horizontalSpacing()
        combobox.deleteLater()
        left, top, right, bottom = self.grid.getContentsMargins()
        screen_width = self.screen().availableGeometry().width() - left - right
        # The first column fits one column less because of the labels.
        column_fit = screen_width // max_width - 1
        row = 0
        for column in range(self.nParmsUsed):
            # Fit the calculated number of columns in the first row and
            # one more in the subsequent ones.
            # The grid requires 5 rows for every parameter set:
            # column, nameunit, parameters, modifiers and combobox.
            if column >= column_fit:
                row = ((column - column_fit) // (column_fit + 1) + 1) * 5
            grid_column = (column + 1) % (column_fit + 1)
            self.grid.addWidget(self.grid_widgets[column]["column"], 0 + row, grid_column)
            self.grid.addWidget(self.grid_widgets[column]["nameunit"], 1 + row, grid_column)
            parameters = QVBoxLayout()
            parameters.setSpacing(3)
            parameters.addWidget(self.grid_widgets[column]["start"])
            parameters.addWidget(self.grid_widgets[column]["end"])
            parameters.addWidget(self.grid_widgets[column]["points"])
            quart = QHBoxLayout()
            quart.setSpacing(8)
            quart.addLayout(parameters)
            quart.addWidget(self.grid_widgets[column]["append"])
            self.grid_widgets[column]["append"].setDisabled(True)
            self.grid.addLayout(quart, 2 + row, grid_column)
            modifiers = QHBoxLayout()
            modifiers.setSpacing(5)
            modifiers.addWidget(self.grid_widgets[column]["repeat"], stretch=1)
            temp_widget = QLineEdit(None)
            size = temp_widget.sizeHint().height()
            temp_widget.deleteLater()
            arrow_icon = get_matrix_icon(
                "CUSTOM_Updown",
                color=QColor("transparent"),
                pencolor=QColor("darkgray"),
            )
            arrow_label = QLabel()
            arrow_label.setPixmap(arrow_icon.pixmap(size, size))
            modifiers.addWidget(arrow_label)
            modifiers.addWidget(self.grid_widgets[column]["updown"])
            self.grid.addLayout(modifiers, 3 + row, grid_column)
            combobox = QVBoxLayout()
            combobox.addWidget(self.grid_widgets[column]["loopover"])
            combobox.addWidget(QLabel(" "))
            self.grid.addLayout(combobox, 4 + row, grid_column)

    def update_append(self, text: str, column: int) -> None:
        """
        Update the append button if all 3 required fields are filled.

        Parameters
        ----------
        column : int
            The column of the append button.
        """
        if (
            self.grid_widgets[column]["start"].text().strip()
            and self.grid_widgets[column]["end"].text().strip()
            and self.grid_widgets[column]["points"].text().strip()
        ):
            #
            self.grid_widgets[column]["append"].setEnabled(True)
        else:
            self.grid_widgets[column]["append"].setEnabled(False)

    def preview_sweep(self) -> None:
        """Display a popup with the sweep given in the column (as plot and list)."""
        sweep = self.generate_sweep()
        if sweep is None:
            return
        elif isinstance(sweep, str):
            # if an error is encountered during the generation of the sweep
            # lists from the parameter, a helpful error message should be
            # provided here
            QMessageBox.warning(self, "Error during sweep generation!", sweep)
            return
        popup = SweepPreviewPopup(
            self,
            self.preview_column - 1,
            sweep,
            self.flat_col,
            self.flat_unit,
            self.col_sign,
        )
        popup.show()

    def print_sweep_to_preview(self) -> None:
        """Print the complete set of sweeps to self.sweep_preview."""
        sweep = self.generate_sweep()
        if sweep is None:
            # sweep generation failed
            return
        elif isinstance(sweep, str):
            # if an error is encountered during the generation of the sweep
            # lists from the parameter, a helpful error message should be
            # provided here
            QMessageBox.warning(self, "Error during sweep generation!", sweep)
            return
        # get length of longest sweep and
        # make sure all sweeps in a group are of equal length
        # this is how the looping over different column is implemented here
        maxLen = []
        for i in range(len(sweep)):
            # make sure that values that belong to the same parameter have the
            # same length
            if self.col_sign[i] == self.col_sign[i - 1] and len(sweep[i]) != len(sweep[i - 1]):
                error_text = "Not all parameters for that instrument have the same length."
                error_text += (
                    f"Please correct your sweep parameters in instrument {self.col_sign[i]} "
                )
                error_text += f" -> {self.flat_col[i]}. If a parameter accepts multiple "
                error_text += (
                    "values, the different values for that parameter must have the same length."
                )
                QMessageBox.warning(self, "Parameter error!", error_text)
                return
            maxLen.append(len(sweep[i]))

        # get the maximum length
        maxLen = max(maxLen)

        # calculate necessary multiplicators to stretch the sweeps
        # if sweep lenghts are not multiples of each other something is wrong
        mult = []
        for i in range(len(sweep)):
            if [] == sweep[i]:
                mult.append(0)
            elif maxLen % len(sweep[i]):
                error_text = (
                    "Sweep_parameters seem unsuitable for measurements, lengths not multiples. "
                )
                error_text += "Check that loops are set correctly."
                QMessageBox.warning(self, "Sweep parameters incompatible!", error_text)
                return
            else:
                mult.append(maxLen / len(sweep[i]))

        # initialize outputList, here the strings for the lines will be input
        # this is equivalent to what goes into the file
        self.outputList = []
        self.sweep_preview.setRowCount(maxLen)
        for i in range(maxLen):
            string = []
            for j, swp in enumerate(sweep):
                if 0 != mult[j] and not i % mult[j]:
                    # here the values are stretched to the correct "length" if
                    # the loop_over parameter is considered
                    if self.col_sign[j] == self.col_sign[j - 1] and len(sweep) > 1:
                        # Parameter has multiple values
                        string.append(str(swp[floor(i / mult[j])]))
                    else:
                        # Parameter has single value
                        string.append("-" + self.col_sign[j] + " " + str(swp[floor(i / mult[j])]))
                string.append("   ")
            # add everything into a single string
            string = "".join(string)
            # add at most 1000 characters per line
            value = QTableWidgetItem(string[:1000])
            self.sweep_preview.setItem(i, 0, value)
            # replace excess spaces from file and print, could be removed
            self.outputList.append(string.replace("   ", " ") + "\n")
        self.sweep_preview.update()

    def update_window_title(self, dirty: bool = False) -> None:
        """
        Indicate if the file was edited with an asterisk.

        Parameters
        ----------
        dirty : bool
            The file was edited (True) or, e.g., recently saved (False).
        """
        self.dirty = dirty
        text = "Sweep Generator"
        if dirty:
            text += ": *"
        elif self.last_filename:
            text += ": "
        if self.last_filename:
            text += basename(self.last_filename)
        elif dirty:
            text += "<unsaved>"
        self.setWindowTitle(text)

    def save_file(self, append: bool = False, dialog: bool = False) -> bool:
        """
        Save the generated sweep to a file.

        Parameters
        ----------
        append : bool, optional
            Append the file (True) or create/ overwrite the file (False).
        dialog : bool, optional
            Do (True) or do not (False) show a dialog to chose a filename.

        Returns
        -------
        bool
            Saved (True) or cancelled (False)
        """
        if dialog or self.last_filename == "":
            prefilled_file = self.last_filename if self.last_filename != "" else usersfolder
            if append:
                filename = QFileDialog.getOpenFileName(
                    self,
                    "Select file to append to",
                    prefilled_file,
                    f"Sweep 8 files (*{self.extension})",
                )
            else:
                filename = QFileDialog.getSaveFileName(
                    self,
                    "Select output file",
                    prefilled_file,
                    f"Sweep 8 files (*{self.extension})",
                )
            if filename[0] != "":
                self.last_filename = filename[0]
                filename = filename[0]
            else:
                return False
        else:
            filename = self.last_filename
        self.print_sweep_to_preview()
        if filename[-len(self.extension) :] != self.extension:
            filename += self.extension
        try:
            if append:
                outputFile = open(filename, "a")
            else:
                outputFile = open(filename, "w")
        except (OSError, IOError):
            QMessageBox.warning(self, "Error!", "File can not be opened.")
            return False
        # get telemetry and append to file
        timestamp = time.strftime(f"{datetimefmt} \n", time.localtime())
        if not append:
            outputFile.write(
                "# v8 input file for matrix program generated" + " by sweep-generator"
            )
            outputFile.write("\n# system filename : ")
            outputFile.write(self.systemFilename)
            outputFile.write("\n# settable columns : ")
            outputFile.write(",".join(self.flat_col))
            outputFile.write("\n# settable units : ")
            outputFile.write(",".join(self.flat_unit))
            outputFile.write("\n# settable column label : ")
            outputFile.write(",".join(self.col_sign))
            outputFile.write("\n# params : ")
            outputFile.write(str(self.sweep_params))
            outputFile.write("\n# loop_over : ")
            outputFile.write(str(self.loop_over))
            outputFile.write("\n# up_down : ")
            outputFile.write(str(self.up_down))
            outputFile.write("\n# repeat : ")
            outputFile.write(str(self.repeat))
            outputFile.write("\n# time stamp : ")
            outputFile.write(timestamp)
        for line in self.outputList:
            outputFile.write(line)
        outputFile.close()
        self.last_filename = filename
        self.update_window_title(dirty=False)
        if self.inputcb is not None:
            self.inputcb(filename)
        return True

    def append_sweep_col(self, column: int) -> None:
        """
        Add defined sweep parameters to self.sweep_params and populate sweep table.

        Take care that whenever adressing the list (i.e. sweep_params)
        that those are shifted by 1 (layout starts at col 1, lists at
        0).
        """
        param_set = []
        param_set.append(self.grid_widgets[column - 1]["start"].text())
        param_set.append(self.grid_widgets[column - 1]["end"].text())
        param_set.append(self.grid_widgets[column - 1]["points"].text())
        self.sweep_params[column - 1].append(param_set)
        self.grid_widgets[column - 1]["start"].setText("")
        self.grid_widgets[column - 1]["end"].setText("")
        self.grid_widgets[column - 1]["points"].setText("")
        # update the sweep grid for the active column (should now display
        # the new parameter set)
        self.populate_sweep_grid(column)

    def populate_sweep_grid(self, actual_column: int) -> None:
        """
        Display the actual sweep parameters.

        Parameters
        ----------
        actual_column : int
            The column that is selected.
        """
        self.preview_column = actual_column
        for column in range(self.nParmsUsed + 1):
            col_sign_label = self.grid_widgets[column - 1]["column"]
            flat_col_nameunit = self.grid_widgets[column - 1]["nameunit"]
            if column == actual_column:
                col_sign_label.setFrameStyle(QLabel.Shape.Panel | QLabel.Shadow.Sunken)
                col_sign_label.setLineWidth(2)
                flat_col_nameunit.setFrameStyle(QLabel.Shape.Panel | QLabel.Shadow.Sunken)
                flat_col_nameunit.setLineWidth(2)
            else:
                col_sign_label.setFrameStyle(QLabel.Shape.NoFrame)
                flat_col_nameunit.setFrameStyle(QLabel.Shape.NoFrame)
        self.sweep_table.setRowCount(len(self.sweep_params[actual_column - 1]))

        for row, param_set in enumerate(self.sweep_params[actual_column - 1]):
            for i in range(3):
                line_edit = QLineEdit(self)
                line_edit.setText(str(param_set[i]))
                if 3 == i:
                    line_edit.setValidator(validator[uint])
                else:
                    line_edit.setValidator(validator[float])
                line_edit.editingFinished.connect(
                    lambda actual_column=actual_column, row=row, i=i: self.change_sweep_param(
                        actual_column, row, i
                    )
                )
                line_edit.textChanged.connect(lambda: self.update_window_title(dirty=True))
                line_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
                self.sweep_table.setCellWidget(row, i, line_edit)
            delete_button = QPushButton("-")
            delete_button.clicked.connect(
                lambda _, actual_column=actual_column, row=row: self.remove_sweep_param(
                    actual_column, row
                )
            )
            delete_button.clicked.connect(lambda: self.update_window_title(dirty=True))
            wrapper = QWidget()
            layout = QHBoxLayout(wrapper)
            layout.addWidget(delete_button)
            layout.setContentsMargins(5, 5, 5, 5)
            layout.setAlignment(delete_button, Qt.AlignmentFlag.AlignCenter)
            self.sweep_table.setCellWidget(row, 3, wrapper)

    def remove_sweep_param(self, col: int, row: int) -> None:
        """
        Remove a set of linspace parameters from sweep_params at the correct position.

        Parameters
        ----------
        col : int
            The currently selected matrix column, e.g. a/field.
        row : int
            The row of the table to be deleted.
        """
        del self.sweep_params[col - 1][row]
        self.populate_sweep_grid(col)

    def change_sweep_param(self, col: int, row: int, field) -> None:
        """
        Change the sweep param if it is manipulated within the sweep table.

        Parameters
        ----------
        col : int
            The currently selected matrix column, e.g., a/field.
        row : int
            The row that of the table that is edited.
        field : int
            The text field that is edited, i.e. the column of the table.
        """
        text = self.sender().text()
        self.sweep_params[col - 1][row][field] = text

    def clear_layout(self, layout):
        """Clear all child widgets from layout."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.spacerItem():
                pass
            else:
                self.clear_layout(item)

    def add_system(self) -> None:
        """
        Add a system file to the system list and initiate import.

        Opens a QFileDialog with filter system*.py.
        """
        directory = system_directories[-1]
        if not self.shortcut_dir and len(system_names) > 1:
            self.shortcut_dir = create_temp_dir_with_symlinks(system_names, system_directories)
        if self.shortcut_dir:
            directory = os.path.join(self.shortcut_dir.name, system_names[-1])
        if self.last_loaded_system:
            directory = os.path.dirname(self.last_loaded_system)
        # get filenames from dialog
        filenames = QFileDialog.getOpenFileNames(
            self, "Select system file", directory, "system files (system*.py)"
        )[0]
        if filenames == []:
            return
        for filename in filenames:
            self.last_loaded_system = filename
            filename = os.path.realpath(filename)
            module_name = get_importable_module_name(filename)
            if module_name:
                self.systemList.addItem(module_name)
            else:
                self.systemList.addItem(filename)
        self.update_window_title(dirty=True)
        if not self.filename_changed():
            for filename in filenames:
                self.systemList.takeItem(self.systemList.count() - 1)
        if self.systemList.count() != 0:
            self.remove_system_action.setEnabled(True)

    def delete_selected_system(self) -> None:
        """Remove selected or last system from the system list."""
        selected = self.systemList.selectedItems()
        if len(selected) > 0:
            self.systemList.takeItem(self.systemList.row(selected[0]))
        elif 0 < self.systemList.count():
            self.systemList.takeItem(self.systemList.count() - 1)
        else:
            return
        if self.systemList.count() == 0:
            self.remove_system_action.setEnabled(False)
        self.filename_changed()
        self.update_window_title(dirty=True)

    def generate_sweep(self):
        """
        GUI functionality to populate all lists necessary for sweep generation.

        After that generates the sweep from the parameters (still needs
        to be stretched)
        """
        self.loop_over = []
        self.up_down = []
        self.repeat = []

        for col in range(self.nParmsUsed):
            self.loop_over.append(self.grid_widgets[col]["loopover"].currentIndex() - 1)
            updownstate = self.grid_widgets[col]["updown"].checkState()
            if updownstate == Qt.CheckState.Checked:
                self.up_down.append(2)
            else:
                self.up_down.append(0)
            self.repeat.append(self.grid_widgets[col]["repeat"].value())

        # all lists are up to date, now generate sweep lists
        sweep = calculate_sweep(
            self.sweep_params, self.loop_over.copy(), self.up_down, self.repeat
        )
        if sweep is None:
            QMessageBox.warning(
                self,
                "Sweep generation failed",
                "Please check that all loops are set correctly.",
            )
            return
        return sweep

    def gui_from_sweep(self):
        """Open a QFileDialog to open an existing sweep file."""
        # get filename from dialog
        prefilled_file = self.last_filename if self.last_filename != "" else usersfolder
        filename = QFileDialog.getOpenFileName(
            self,
            "Select input file",
            prefilled_file,
            f"Sweep 8 files (*{self.extension});;t files (*.*t)",  # Delete old extension in MA9
        )[0]
        if filename:
            self.open_file(filename)

    def open_file(self, filename: str) -> None:
        """
        Load a sweep file.

        Load system from file, define read out parameters to parse and
        display the sweep in the corresponding preview.

        Parameters
        ----------
        filename : str
            Sweep file to open.
        """
        params = {
            "# params : ": None,
            "# loop_over : ": None,
            "# functions : ": None,
            "# up_down : ": None,
            "# repeat : ": None,
        }
        self.systemList.clear()
        with open(filename, "r") as infile:
            for line in infile:
                regex = r"^# [Ss]ystem filename : (.+)"
                if match := re.match(regex, line.strip()):
                    self.systemList.addItems(match.group(1).split(","))
                    if not self.filename_changed():
                        return
                for key in params.keys():
                    if key in line:
                        # read the parameters from the corresponding line
                        line = line.strip().replace(key, "")
                        params[key] = literal_eval(line)
        # 'Functions' is depracated. Old files read and issue a warning if the functionality
        # is used. Otherwise they just load. Delete the this backward compatibility for Matrix v9.
        # Andy 20250306
        if len(params.values()) == 5:  # old filename
            (
                self.sweep_params,
                self.loop_over,
                functions,
                self.up_down,
                self.repeat,
            ) = params.values()
        else:
            (self.sweep_params, self.loop_over, self.up_down, self.repeat) = params.values()
            functions = None
        if functions and any(function != "None" for function in functions):
            warning_text = (
                "This file uses the removed 'function' functionality."
                "Please use matrix-script. File did not load!"
            )
            QMessageBox.warning(
                self,
                "Open file error.",
                warning_text,
            )
            return
        # initialize layout with values specified in file
        for col in range(self.nParmsUsed):
            self.grid_widgets[col]["loopover"].setCurrentIndex(self.loop_over[col] + 1)
            self.grid_widgets[col]["updown"].setCheckState(Qt.CheckState(self.up_down[col]))
            self.grid_widgets[col]["repeat"].setValue(self.repeat[col])
        self.last_filename = filename
        self.update_window_title()
        self.print_sweep_to_preview()

    def new_file(self) -> None:
        """
        Prepare a completely new sweep.

        Delete all existing sweep parameters, update the sweep grid
        accordingly and empty the sweep preview. Also reset all input
        fields to their original states.
        """
        if self.dirty:
            ret = save_messagebox(self)
            if ret == QMessageBox.StandardButton.Cancel:
                return
            if ret == QMessageBox.StandardButton.Save:
                saved = self.save_file()
                if not saved:
                    return
        self.sweep_params = []
        for col in range(self.nParmsUsed):
            self.sweep_params.append([])
            self.grid_widgets[col]["start"].setText("")
            self.grid_widgets[col]["end"].setText("")
            self.grid_widgets[col]["points"].setText("")
            self.grid_widgets[col]["repeat"].setValue(1)
            self.grid_widgets[col]["updown"].setChecked(False)
            self.grid_widgets[col]["loopover"].setCurrentIndex(0)
            self.populate_sweep_grid(col + 1)
        self.print_sweep_to_preview()
        self.grid_widgets[0]["start"].setFocus()
        self.last_filename = ""
        self.update_window_title(dirty=False)


def main():
    """Set the basic GUI parameters and run."""
    app = MApplication(sys.argv)
    if os.name == "nt":
        # enable modern mode on windows which allows for darkmode
        app.setStyle("fusion")
    elif sys.platform == "darwin":
        set_correct_mac_appname("Sweep Generator")
    with QtGracefulKiller():
        if len(sys.argv) < 2:
            mw = MainWindow()
        else:
            mw = MainWindow(filename=sys.argv[1])
        mw.show()
        mw.restore_window_state()
        ret = app.exec()
    sys.exit(ret)
