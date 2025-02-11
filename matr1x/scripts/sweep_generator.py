# This file is part of a software collection for data aquisition (matr1x).
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

It heavily relies on numpy.linspace for the creation of the sweep segments.
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
from PyQt6.QtCore import QEvent, QSettings, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QKeySequence, QPalette
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
    MIcon,
    MTextEdit,
    SystemListWidget,
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

if os.name == 'nt':
    try:
        from ctypes import windll  # Only exists on Windows.
        myappid = 'python.matr1x.sweep-generator.version'
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass


class LineEditFocus(QLineEdit):
    """Reimplement LineEdit with focusInEvent."""

    focusIn = pyqtSignal()

    def __init__(self, parent=None, string=None):
        """Init QLineEdit."""
        if string is not None:
            super().__init__(string)
        else:
            super().__init__(None)

    def focusInEvent(self, e, parent=None):
        """Reimplement LineEdit with focusInEvent."""
        super().focusInEvent(e)
        self.focusIn.emit()


class QLabelWithColor(QLabel):
    """Allow QLabel with highlight color."""

    def __init__(self, string=None, color1="#DCF5D4", color2="#325725"):
        """Init with colored background.

        Provide two colors for bright and dark mode.

        Parameters
        ----------
        string: str or None
            Text of the QLabel
        color1: str
            Hex code of the color for bright mode
        color2: str
            Hex code of the color for dark mode
        """
        super().__init__(string)
        self.bright = f"""
                     QLabel {{
                         background-color: {color1};
                         color: black;
                     }}
                 """
        self.dark = f"""
                     QLabel {{
                         background-color: {color2};
                         color: #DBDBDB;
                     }}
                 """
        self._update_colors()

    def _update_colors(self):
        """Change color while avoiding recursion."""
        self.updating_stylesheet = True
        if QTextEdit().palette().color(QPalette.ColorRole.Text).value() > 128:
            self.setStyleSheet(self.dark)
        else:
            self.setStyleSheet(self.bright)
        self.updating_stylesheet = False

    def changeEvent(self, event: QEvent):
        """Detect palette changes such as dark and bright mode desktops."""
        if event.type() == QEvent.Type.PaletteChange and not self.updating_stylesheet:
            self._update_colors()
        return super().changeEvent(event)

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
        grid = QGridLayout()

        closeButton = QPushButton("Close preview")
        closeButton.clicked.connect(self.closePopup)

        self.textEdit = MTextEdit()
        self.textEdit.setReadOnly(True)
        self.textEdit.setMinimumHeight(100)

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
        self.pw = pg.PlotWidget(viewBox=self.vb, name="plot1",
                                enableMenu=False)
        self.plt = self.pw.plot()
        self.plt.setPen((0, 0, 153), width=3)

        self.proxy = pg.SignalProxy(self.pw.scene().sigMouseMoved,
                                    rateLimit=30,
                                    slot=self.mouseMoved)

        self.plotListRangeX(index)
        self.updateTextEdit(index)

        grid.addWidget(closeButton, 0, 0)
        grid.addWidget(comboBox, 1, 0)
        grid.addWidget(self.textEdit, 2, 0, 4, 1)

        grid.addWidget(self.posLabel, 0, 1, 1, 5)
        grid.addWidget(self.pw, 1, 1, 5, 5)

        self.setLayout(grid)
        self.show()

    def indexChanged(self, newIndex):
        """Show the interface for new index if index is changed."""
        self.plotListRangeX(newIndex)
        self.updateTextEdit(newIndex)

    def updateTextEdit(self, index):
        """Update the textEdit to show the current sweep[index]."""
        self.textEdit.clear()
        for index, item in zip(range(len(self.sweep[index])),
                               self.sweep[index]):
            self.textEdit.append(str(index) + "\t| " + str(item))

    def mouseMoved(self, ev):
        """Implement event to update cursor position while pointer is in plot."""
        mousePoint = self.vb.mapSceneToView(ev[0])
        self.posLabel.setText("x: {:e}\ny: {:e}".format(mousePoint.x(),
                                                        mousePoint.y()))

    def plotListRangeX(self, index):
        """Update the plot to show sweep[index] against its range."""
        self.pw.getAxis("left").textWidth = 0
        length = len(self.sweep[index])
        self.plt.setData(x=linspace(0, length, length),
                         y=self.sweep[index], symbol="o")

        self.pw.setLabel("bottom", "index")
        self.pw.setLabel("left", (self.cols[index].strip() + " [" +
                                  self.units[index].strip() + "]"))

    def closePopup(self):
        """Close the pop-up."""
        self.close()


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

    def __init__(self, filename=None, system=None, inputcb=None):
        super().__init__()
        self.setWindowIcon(MIcon("matr1x-sweep-generator.png"))

        self.system = system
        self.inputcb = inputcb
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
        self.functions = []
        self.sweepParams = []
        self.systemFilename = ""
        self.last_loaded_file = None

        # gui variables
        self.nRowPreview = 3
        self.labels = (("Column", "label"), ("Name", "label"),
                       ("Unit", "label"), ("Start value", "float"),
                       ("End value", "float"), ("Point count", "int"),
                       ("Append sweep", "buttonA"), ("Repeat", "int"),
                       ("Up- and down", "boolean"),
                       ("Loop over column", "combo"),
                       ("Function", "comboF"),
                       ("Preview column", "buttonP"))

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

    def closeEvent(self, event):
        """Store settings before closing app."""
        self.saveCurrentState()
        event.accept()

    def saveCurrentState(self):
        """Save window and toolbar placement."""
        self.settings.setValue("position", self.pos())
        self.settings.setValue("size", self.size())
        self.settings.setValue("toolbar_placement", self.toolBarArea(self.toolbar))

    def restoreState(self):
        """Restore window and toolbar placement."""
        recommended_size = self.sizeHint()
        self.move(self.settings.value("position", self.pos()))
        self.resize(self.settings.value("size", recommended_size))
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
        # About
        self.about_action = QAction("About", self)
        self.about_action.setMenuRole(QAction.MenuRole.AboutRole)
        self.about_action.triggered.connect(self.info_box)
        # Open
        self.load_action = QAction(MIcon("SP_DialogOpenButton"), "Open", self)
        self.load_action.triggered.connect(self.gui_from_sweep)
        self.load_action.setShortcut(QKeySequence.StandardKey.Open)
        # Add System
        self.add_system_action = QAction(
            MIcon("CHAR_+", QColor("RoyalBlue")), "Add System", self
        )
        self.add_system_action.triggered.connect(self.add_system)
        # Remove System
        self.remove_system_action = QAction(
            MIcon("CHAR_-", QColor("RoyalBlue")), "Remove System", self
        )
        self.remove_system_action.setEnabled(False)
        self.remove_system_action.triggered.connect(self.delete_selected_system)
        # System list
        self.systemList = SystemListWidget(self)
        self.systemList.orderChanged.connect(self.filename_changed)
        self.systemList.setMinimumHeight(50)
        self.systemList.setMaximumHeight(50)
        # Save
        self.save_action = QAction(MIcon("SP_DialogSaveButton"), "Save", self)
        self.save_action.triggered.connect(self.output_to_file)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.setEnabled(False)
        # Save As...
        self.save_as_action = QAction(MIcon("SP_DialogSaveButton"), "Save As...", self)
        self.save_as_action.triggered.connect(self.save_file_as)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        # Append
        self.append_action = QAction(MIcon("SP_DialogSaveButton"), "Append", self)
        self.append_action.triggered.connect(self.append_to_file)
        self.appendflag = 0
        # Generate Pulldown
        self.save_button = QToolButton()
        self.save_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.save_button.setIcon(MIcon("SP_DialogSaveButton"))
        self.save_button.setText("Save")
        self.save_button.setDefaultAction(self.save_action)
        self.save_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        save_pulldown = QMenu(self)
        save_pulldown.addAction(self.save_as_action)
        save_pulldown.addAction(self.append_action)
        self.save_button.setMenu(save_pulldown)
        # Quit
        self.quit_action = QAction("Quit", self)
        if os.name == "nt":
            self.quit_action.setShortcut(QKeySequence.StandardKey.Close)
        else:
            self.quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.quit_action.triggered.connect(self.close)
        # Generate sweep
        self.sweep_action = QAction(MIcon("SP_BrowserReload"), "Generate Sweep", self)
        self.sweep_action.triggered.connect(self.print_sweep_to_preview)
        self.sweep_action.setEnabled(False)
        # View: Toolbar
        self.toggle_toolbar_action = QAction("Show Toolbar", self)
        self.toggle_toolbar_action.setShortcut(QKeySequence("Ctrl+1"))
        self.toggle_toolbar_action.setCheckable(True)
        self.toggle_toolbar_action.setChecked(True)
        self.toggle_toolbar_action.triggered.connect(self.toggle_toolbar_view)

        # Start the layout
        fGrid = QGridLayout()

        self.grid = QGridLayout()
        self.grid.setSpacing(5)

        self.gridUtility = QGridLayout()
        self.gridUtility.setSpacing(5)

        self.statusBar = MTextEdit()
        self.statusBar.setReadOnly(True)
        self.statusBar.setMinimumHeight(80)

        sGrid = QGridLayout()

        sGrid.addWidget(QLabel("Status"), 0, 0)
        sGrid.addWidget(self.statusBar, 0, 1, 1, 10)

        vBox = QVBoxLayout()
        vBox.addLayout(fGrid)
        vBox.addLayout(self.grid)
        vBox.addLayout(self.gridUtility)
        vBox.addLayout(sGrid)

        self.widget = QWidget()
        self.widget.setSizePolicy(QSizePolicy.Policy.Expanding,
                                  QSizePolicy.Policy.Fixed)
        self.widget.setLayout(vBox)
        self.setCentralWidget(self.widget)

        self.create_toolbar()
        self.create_menu()

    def create_toolbar(self) -> None:
        """Create the Toolbar."""
        self.toolbar = QToolBar("Toolbar")
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.toolbar.setFloatable(False)
        self.toolbar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        icon_size = MApplication.instance().toolbar_icon_size()
        self.toolbar.setIconSize(QSize(icon_size, icon_size))
        self.toolbar.setAllowedAreas(
            Qt.ToolBarArea.TopToolBarArea | Qt.ToolBarArea.BottomToolBarArea
        )
        self.toolbar.addAction(self.load_action)
        self.toolbar.addWidget(self.save_button)
        self.toolbar.addAction(self.sweep_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.add_system_action)
        self.toolbar.addWidget(self.systemList)
        self.toolbar.addAction(self.remove_system_action)
        self.toolbar.visibilityChanged.connect(self.toggle_toolbar_action.setChecked)
        self.addToolBar(self.toolbar)

    def create_menu(self) -> None:
        """Create the main menu."""
        menu = self.menuBar()
        file_menu = menu.addMenu("&File")
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
        control_menu.addAction(self.sweep_action)
        #
        view_menu = menu.addMenu("&View")
        view_menu.addAction(self.toggle_toolbar_action)
        #
        help_menu = menu.addMenu("&Help")
        help_menu.addAction(self.about_action)

    def info_box(self):
        """Display an 'about this app' widget."""
        box = AboutBox(
            "Sweep Generator",
            MIcon("matr1x-sweep-generator.png"),
            matr1x,
            matr1x.datetimefmt,
        )
        box.exec()
        return

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
        """Enable drag and drop (2)."""
        urls = event.mimeData().urls()
        if len(urls) == 1:
            file_path = urls[0].toLocalFile()
            if self.is_valid_extension(file_path):
                self.open_file(file_path)
            else:
                QMessageBox.warning(
                    self,
                    "Invalid File",
                    # remove old pattern with next major update
                    "Only files with extensions matching .<number>t or .sw8 are supported.",
                )
        else:
            QMessageBox.warning(self, "Multiple Files",
                                "Please drop only a single file.")

    def reset_layout(self):
        """Reset layout to clean state."""
        if self.populated:
            self.clear_layout(self.grid)
            self.clear_layout(self.gridUtility)
            for i in range(self.nParmsUsed):
                self.grid.setColumnStretch(i+1, 0)
        self.widget.adjustSize()
        self.adjustSize()

    def filename_changed(self):
        """Import new system on changed filename."""
        # get new system filename
        filenames = [self.systemList.item(j).text()
                     for j in range(self.systemList.count())]
        if 0 == len(filenames):
            self.reset_layout()
            self.save_action.setEnabled(False)
            self.sweep_action.setEnabled(False)
            return
        self.save_action.setEnabled(True)
        self.sweep_action.setEnabled(True)
        modulestr = ""
        # update entries in GUI list
        for j, systemfile in enumerate(filenames):
            self.systemList.item(j).setText(systemfile)
        self.systemFilename = ",".join(filenames)
        try:
            self.system = MergedSystem.from_files(filenames)
            for file in filenames:
                modulestr += basename(splitext(file)[0]) + ","
            self.statusBar.append("Successfully imported -- " + modulestr)
            # update gui using the system specifications
            self.import_system()
        except Exception as e:
            if isinstance(e, ModuleNotFoundError):
                self.statusBar.append("ModuleNotFoundError was raised," +
                                      "Check path to module")
            else:
                self.statusBar.append(
                    "The following error was raised during system " +
                    "import, please check system for errors")
            tbinfo = traceback.format_exception(e)
            tbstr = "".join(tbinfo[7:])
            self.statusBar.append(tbstr)

    def import_system(self):
        """Import specified system and populate layout."""
        if len(self.system.columns) != len(self.system.units):
            # simple sanity check
            self.statusBar.append("Lists with columns, units and settable" +
                                  "not of equal length, check system file!")
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
        color1 = False
        last_letter = ""
        for pos in range(self.nParmsUsed):
            if pos in save_sweep_params.keys():
                # if parameter was already defined before, keep sweep params
                self.sweep_params.append(save_sweep_params[pos])
            else:
                # otherwise, set empty list
                self.sweep_params.append([])
            # for each used parameter generate labels according to system
            # specifications
            self.grid.setColumnStretch(pos+1, 1)
            # color corresponding columns
            letter = self.col_sign[pos][0]
            if last_letter == "":
                last_letter = letter
            if letter != last_letter:
                last_letter = letter
                color1 = not color1
            if color1:
                col_sign_label = QLabelWithColor(self.col_sign[pos])
                flat_col_label = QLabelWithColor(self.flat_col[pos].strip())
                flat_unit_label = QLabelWithColor(self.flat_unit[pos].strip())
            else:
                col_sign_label = QLabelWithColor(
                    self.col_sign[pos], "#D0EBFE", "#1E4962"
                )
                flat_col_label = QLabelWithColor(
                    self.flat_col[pos].strip(), "#D0EBFE", "#1E4962"
                )
                flat_unit_label = QLabelWithColor(
                    self.flat_unit[pos].strip(), "#D0EBFE", "#1E4962"
                )
            col_sign_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            flat_col_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            flat_unit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.grid.addWidget(col_sign_label, 1, pos + 1)
            self.grid.addWidget(flat_col_label, 2, pos + 1)
            self.grid.addWidget(flat_unit_label, 3, pos + 1)
        self.populate_layout()
        if not self.populated:
            self.populated = True
        self.statusBar.append("Initialization of sweep generator completed"
                              " - enjoy!")

    def populate_layout(self):
        """Populate sweep controls dynamically from specifications in self.labels."""
        for col in range(self.nParmsUsed):
            for label, row in zip(self.labels, range(len(self.labels))):
                if 0 == col:
                    # first column is labels only
                    self.grid.addWidget(QLabel(label[0]), row+1, 0)
                if label[1] == "float":
                    # float entry add lineedit with double validator
                    lineEdit = LineEditFocus()
                    lineEdit.setValidator(validator[float])
                    lineEdit.focusIn.connect(self.populate_sweep_grid)
                    self.grid.addWidget(lineEdit, row+1, col+1)
                elif label[1] == "buttonA":
                    # adds append button
                    appendButton = QPushButton("Append")
                    appendButton.clicked.connect(self.append_sweep_col)
                    self.grid.addWidget(appendButton, row+1, col+1)
                elif label[1] == "int":
                    # int entry with int validator
                    lineEdit = LineEditFocus()
                    lineEdit.setValidator(validator[uint])
                    lineEdit.focusIn.connect(self.populate_sweep_grid)
                    self.grid.addWidget(lineEdit, row+1, col+1)
                elif label[1] == "boolean":
                    # boolean entry generates checkbox
                    checkBox = QCheckBox(self)
                    checkBox.pressed.connect(self.populate_sweep_grid)
                    self.grid.addWidget(checkBox, row+1, col+1)
                elif label[1] == "combo":
                    # combobox/dropdown menu
                    comboBox = QComboBox(self)
                    columns = ["None"]
                    for i in range(self.nParmsUsed):
                        columns.append(self.col_sign[i] +
                                       " - " +
                                       self.flat_col[i].strip())
                    comboBox.addItems(columns)
                    self.grid.addWidget(comboBox, row+1, col+1)
                elif label[1] == "comboF":
                    # function dropdown menu
                    comboBox = QComboBox(self)
                    columns = ["None", "sqrt", "x^2",
                               "exp", "ln", "log10", "10^x"]
                    comboBox.addItems(columns)
                    self.grid.addWidget(comboBox, row+1, col+1)
                elif label[1] == "buttonP":
                    previewButton = QPushButton("Preview")
                    previewButton.clicked.connect(self.preview_sweep)
                    self.grid.addWidget(previewButton, row+1, col+1)

        # generate sweep grid labels and layout
        self.currentCol = QLabel("Selected Column - \nStart - Stop - Points")

        self.sweepGrid = QGridLayout()

        # set layout and box containing sweep grid, required for
        # straightforward deletion/reinitialization
        self.baseBox = QVBoxLayout()
        self.baseBox.addLayout(self.sweepGrid)
        self.baseBox.addStretch(1)

        baseArea = QWidget(self)
        baseArea.setLayout(self.baseBox)

        scrollArea = QScrollArea(self)
        scrollArea.setWidget(baseArea)
        scrollArea.setWidgetResizable(True)

        self.sweepBox = QVBoxLayout()
        self.sweepBox.addWidget(self.currentCol)
        self.sweepBox.addWidget(scrollArea)

        self.sweepPreview = MTextEdit()
        self.sweepPreview.setReadOnly(True)

        self.fileEditOutput = QLineEdit(self)

        self.gridUtility.addWidget(QLabel("Generated Sweep:"), 0, 0)
        self.gridUtility.addWidget(QLabel("Output filename:"), 6, 0, 1, 1)
        self.gridUtility.addWidget(self.fileEditOutput, 6, 1, 1, 5)

        self.gridUtility.addLayout(self.sweepBox, 0, 5, 6, 2)
        self.gridUtility.addWidget(self.sweepPreview, 0, 1, 6, 4)
        # make the column with the preview and the textedit to take all
        # available space
        self.gridUtility.setColumnStretch(1, 1)
        self.gridUtility.setColumnStretch(5, 1)

    def preview_sweep(self):
        """Display a popup with the sweep given in the column (as plot and list)."""
        col = self.grid.getItemPosition(self.grid.indexOf(self.sender()))[1]
        sweep = self.generate_sweep()
        if sweep is None:
            return
        elif isinstance(sweep, str):
            # if an error is encountered during the generation of the sweep
            # lists from the parameter, a helpful error message should be
            # provided here
            self.statusBar.append(sweep)
            return
        popup = SweepPreviewPopup(self, col-1, sweep, self.flat_col,
                                  self.flat_unit, self.col_sign)
        popup.show()

    def print_sweep_to_preview(self):
        """Print the complete set of sweeps to self.sweepPreview."""
        sweep = self.generate_sweep()
        if sweep is None:
            # sweep generation failed
            return
        elif isinstance(sweep, str):
            # if an error is encountered during the generation of the sweep
            # lists from the parameter, a helpful error message should be
            # provided here
            self.statusBar.append(sweep)
            return
        # get length of longest sweep and
        # make sure all sweeps in a group are of equal length
        # this is how the looping over different column is implemented here
        maxLen = []
        for i in range(len(sweep)):
            # make sure that values that belong to the same parameter have the
            # same length
            if ((self.col_sign[i] == self.col_sign[i-1] and
                 len(sweep[i]) != len(sweep[i-1]))):
                self.statusBar.append("Not all parameters for that " +
                                      "instrument have the same length\n" +
                                      "Please correct your sweep params " +
                                      "in instrument " + self.col_sign[i] +
                                      " -> " + self.flat_col[i] +
                                      "\nIf a parameter accepts multiple "
                                      "values, the different values for that "
                                      "parameter must have the same length")
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
                self.statusBar.append("sweep_params seem unsuitable for "
                                      "measurements, lengths not multiples. "
                                      "Check that loops are set correctly.")
                return
            else:
                mult.append(maxLen/len(sweep[i]))

        self.sweepPreview.clear()
        # initialize outputList, here the strings for the lines will be input
        # this is equivalent to what goes into the file
        self.outputList = []
        for i in range(maxLen):
            string = []
            for j, swp in enumerate(sweep):
                if 0 != mult[j] and not i % mult[j]:
                    # here the values are stretched to the correct "length" if
                    # the loop_over parameter is considered
                    if self.col_sign[j] == self.col_sign[j-1] and len(sweep) > 1:
                        # Parameter has multiple values
                        string.append(str(swp[floor(i/mult[j])]))
                    else:
                        # Parameter has single value
                        string.append(
                            "-" + self.col_sign[j] +
                            " " + str(swp[floor(i/mult[j])]))
                string.append("   ")
            # add everything into a single string
            string = "".join(string)
            # add at most 1000 characters per line
            self.sweepPreview.append(string[:1000])
            # replace excess spaces from file and print, could be removed
            self.outputList.append(string.replace("   ", " ") + "\n")
        return 1

    def append_to_file(self):
        """Append the contents of self.outputList to the file specified for output."""
        self.appendflag = 2
        self.output_to_file()
        self.appendflag = 0

    def output_to_file(self):
        """Write the contents of self.outputList to the file specified for output."""
        append = self.appendflag
        filename = self.fileEditOutput.text()
        if "" == filename:
            self.save_file_as()
            return
        elif "" == self.systemFilename:
            self.statusBar.append("System undefined")
            return
        else:
            if self.print_sweep_to_preview() is None:
                return
            # append .sw8 if not already in filename and update textEdit
            match = ".sw8"
            if match not in filename:
                filename += match
                self.fileEditOutput.setText(filename)
            try:
                outputFile = open(filename, 'r')
            except (OSError, IOError):
                self.statusBar.append("File does not exist yet, adding header")
                append = 0
            try:
                if 2 == append:
                    # user wants to append
                    outputFile = open(filename, 'a')
                else:
                    outputFile = open(filename, 'w')
            except (OSError, IOError):
                self.statusBar.append("File can not be opened")
                return
        # get telemtry and append to file
        timestamp = time.strftime(f"{datetimefmt} \n", time.localtime())
        if 2 != append:
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
            outputFile.write("\n# functions : ")
            outputFile.write(str(self.functions))
            outputFile.write("\n# up_down : ")
            outputFile.write(str(self.up_down))
            outputFile.write("\n# repeat : ")
            outputFile.write(str(self.repeat))
            outputFile.write("\n# time stamp : ")
            outputFile.write(timestamp)
        for line in self.outputList:
            outputFile.write(line)
        outputFile.close()
        if self.inputcb is not None:
            self.inputcb(filename)
        if 2 == append:
            self.statusBar.append("Output appended to " + filename + " at " +
                                  timestamp)
        else:
            self.statusBar.append("Output written to " + filename + " at " +
                                  timestamp)

    def append_sweep_col(self):
        """Add defined sweep parameters to self.sweep_params and populate sweepGrid.

        Take care that whenever adressing the list (i.e. sweep_params) that
        those are shifted by 1 (layout starts at col 1, lists at 0)
        """
        position = self.grid.getItemPosition(self.grid.indexOf(self.sender()))
        param_set = []

        for i in range(3):
            # get set of values for linspace -> linspace(p1, p2, p3)
            param_set.append(self.grid.itemAtPosition(
                position[0]-(3-i), position[1]).widget().text())

        if "" in param_set:
            self.statusBar.append("Missing value, " +
                                  "please specify all three parameters")
            return
        else:
            # add the list of three parameters to the sweep_params for the
            # given column
            self.sweep_params[position[1]-1].append(param_set)
            for i in range(3):
                # clear widgets with the original values, as these are now
                # appended to the sweep_params
                self.grid.itemAtPosition(position[0]-(3-i),
                                         position[1]).widget().setText("")
            # update the sweep grid for the active column (should now display
            # the new parameter set)
            self.populate_sweep_grid(position[1])

    def remove_sweep_param(self, col):
        """Remove a set of linspace parameters from sweep_params at the correct position."""
        row = self.sweepGrid.getItemPosition(
            self.sweepGrid.indexOf(self.sender()))[0]
        del self.sweep_params[col-1][row]
        self.populate_sweep_grid(col)

    def populate_sweep_grid(self, col=None):
        """Display the actual sweep parameters."""
        if col is None:
            try:
                col = self.grid.getItemPosition(
                    self.grid.indexOf(self.sender()))[1]
            except AttributeError:
                self.statusBar("No sender could be found, check function calls"
                               "in source code, populate_sweep_grid got probably"
                               "called without col parameter by a direct"
                               "function call")
                return
        self.currentCol.setText("Selected Column:\t" +
                                self.col_sign[col-1] + " -- " +
                                str(self.flat_col[col-1]).strip() +
                                "\nStart - Stop - Points")

        # Clear Widget
        self.clear_layout(self.sweepGrid)

        row = 0
        for param_set in self.sweep_params[col-1]:
            for i in range(3):
                le = QLineEdit(self)
                le.setText(str(param_set[i]))
                if 3 == i:
                    le.setValidator(validator[uint])
                else:
                    le.setValidator(validator[float])
                le.editingFinished.connect(
                    lambda: self.change_sweep_param(col))
                self.sweepGrid.addWidget(le, row, i)
            qpb = QPushButton("Delete")
            # Fun Function :), parameter calls lambda, which calls
            # self.remove_sweep_param(col), because connect can pass no parameters
            # directly, feels quite dirty but seems to work
            qpb.clicked.connect(lambda: self.remove_sweep_param(col))
            self.sweepGrid.addWidget(qpb, row, 3)
            row += 1

    def change_sweep_param(self, col):
        """Change the sweep param if it is manipulated within the sweepGrid."""
        text = self.sender().text()
        position = self.sweepGrid.getItemPosition(
            self.sweepGrid.indexOf(self.sender()))
        self.sweep_params[col-1][position[0]][position[1]] = text

    def clear_layout(self, layout):
        """Clear all child widgets from layout."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            else:
                self.clear_layout(item)

    def add_system(self) -> None:
        """
        Add a system file to the system list.

        Opens a QFileDialog with filter system*.py.
        """
        directory = system_directories[-1]
        if not self.shortcut_dir and len(system_names) > 1:
            self.shortcut_dir = create_temp_dir_with_symlinks(
                system_names, system_directories)
        if self.shortcut_dir:
            directory = os.path.join(self.shortcut_dir.name, system_names[-1])
        if self.last_loaded_file:
            directory = os.path.dirname(self.last_loaded_file)
        # get filenames from dialog
        filenames = QFileDialog.getOpenFileNames(
            self, 'Select system file', directory,
            "system files (system*.py)")[0]
        if filenames == []:
            return
        for filename in filenames:
            self.last_loaded_file = filename
            filename = os.path.realpath(filename)
            module_name = get_importable_module_name(filename)
            if module_name:
                self.systemList.addItem(module_name)
            else:
                self.systemList.addItem(filename)
        self.remove_system_action.setEnabled(True)
        self.filename_changed()

    def delete_selected_system(self) -> None:
        """Remove selected or last system from the system list."""
        selected = self.systemList.selectedItems()
        if len(selected) > 0:
            self.systemList.takeItem(self.systemList.row(selected[0]))
        elif 0 < self.systemList.count():
            self.systemList.takeItem(self.systemList.count()-1)
        else:
            return
        if self.systemList.count() == 0:
            self.remove_system_action.setEnabled(False)
        self.filename_changed()

    def save_file_as(self):
        """Open a QFileDialog to receive save file name."""
        filename = QFileDialog.getSaveFileName(
            self, "Select output file", usersfolder, "All files (*)"
        )
        if filename[0] != "":
            self.fileEditOutput.setText(filename[0])
            self.output_to_file()

    def generate_sweep(self):
        """
        GUI functionality to populate all lists necessary for sweep generation.

        After that generates the sweep from the parameters (still needs to be
        stretched)
        """
        self.loop_over = []
        self.functions = []
        self.up_down = []
        self.repeat = []
        for row, label in zip(range(len(self.labels)), self.labels):
            for col in range(self.nParmsUsed):
                currentWidget = self.grid.itemAtPosition(row+1, col+1).widget()
                if "combo" == label[1] and "Loop" in label[0]:
                    self.loop_over.append(currentWidget.currentIndex()-1)
                elif "comboF" == label[1] and "Function" in label[0]:
                    self.functions.append(currentWidget.currentText())
                elif "boolean" == label[1] and "Up" in label[0]:
                    if currentWidget.checkState() == Qt.CheckState.Checked:
                        self.up_down.append(2)
                    else:
                        self.up_down.append(0)
                elif "int" == label[1] and "Repeat" in label[0]:
                    try:
                        text = currentWidget.text()
                        if "" == text:
                            self.repeat.append(1)
                        else:
                            self.repeat.append(int(text))
                    except TypeError:
                        self.statusBar.append("Type Error called by repeat," +
                                              "should not happen")
                        return

        # all lists are up to date, now generate sweep lists
        sweep = calculate_sweep(self.sweep_params, self.loop_over.copy(),
                                self.up_down, self.repeat, self.functions)
        if sweep is None:
            self.statusBar.append("Error during sweep generation, " +
                                  "check that all loops are set correctly")
            return
        return sweep

    def gui_from_sweep(self):
        """Open a QFileDialog to open an existing sweep file."""
        # get filename from dialog
        filename = QFileDialog.getOpenFileName(
            self,
            "Select input file",
            usersfolder,
            "Sweep 8 files (*.sw8);;t files (*.*t)",
        )[0]
        if filename:
            self.open_file(filename)

    def open_file(self, filename):
        """Load system from file, define read out parameters to parse."""
        params = {"# params : ": None, "# loop_over : ": None,
                  "# functions : ": None, "# up_down : ": None,
                  "# repeat : ": None}
        self.systemList.clear()
        with open(filename, "r") as infile:
            for line in infile:
                regex = r"^# [Ss]ystem filename : (.+)"
                if match := re.match(regex, line.strip()):
                    self.systemList.addItems(match.group(1).split(","))
                    self.filename_changed()
                for key in params.keys():
                    if key in line:
                        # read the parameters from the corresponding line
                        line = line.strip().replace(key, "")
                        params[key] = literal_eval(line)

        if None in params.values():
            # not all parameters could be read from the file
            return
        else:
            (self.sweep_params, self.loop_over, self.functions, self.up_down,
             self.repeat) = params.values()

        # initialize layout with values specified in file
        for row, label in zip(range(len(self.labels)), self.labels):
            for col in range(self.nParmsUsed):
                currentWidget = self.grid.itemAtPosition(row+1, col+1).widget()
                if "combo" == label[1] and "Loop" in label[0]:
                    currentWidget.setCurrentIndex(self.loop_over[col]+1)
                elif "comboF" == label[1] and "Function" in label[0]:
                    currentWidget.setCurrentText(self.functions[col])
                elif "boolean" == label[1] and "Up" in label[0]:
                    currentWidget.setCheckState(
                        Qt.CheckState(self.up_down[col]))
                elif "int" == label[1] and "Repeat" in label[0]:
                    if 1 == self.repeat[col]:
                        currentWidget.setText("")
                    else:
                        currentWidget.setText(str(self.repeat[col]))


def main():
    """Set the basic GUI parameters and run."""
    app = MApplication(sys.argv)
    if os.name == 'nt':
        # enable modern mode on windows which allows for darkmode
        app.setStyle('fusion')
    elif sys.platform == "darwin":
        set_correct_mac_appname("Sweep Generator")
    with QtGracefulKiller():
        if len(sys.argv) < 2:
            mw = MainWindow()
        else:
            mw = MainWindow(filename=sys.argv[1])
        mw.show()
        mw.restoreState()
        ret = app.exec()
    sys.exit(ret)
