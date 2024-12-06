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

"""Display data and allow simple data manipulation."""
import logging
import os
import signal
import sys
import threading
import time
from os.path import abspath, getmtime, getsize

import numpy as np
import pyqtgraph
import pyqtgraph.exporters
from PyQt6.QtCore import QEvent, QSettings, QSize, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QGridLayout,
    QLabel,
    QLayout,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QStyle,
    QToolBar,
    QWidget,
)

import matr1x
from matr1x import gui_util
from matr1x.control.util import QtGracefulKiller
from matr1x.eval import loadmatrix
from matr1x.gui_util import AboutBox, MApplication, MIcon
from matr1x.util import set_correct_mac_appname

logger = logging.getLogger(os.path.split(__file__)[-1])

if os.name == 'nt':
    try:
        from ctypes import windll  # Only exists on Windows.
        myappid = 'python.matr1x.matrix-preview.version'
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass


class Matr1xApplication(MApplication):
    """Allow double-click file open on a Mac."""

    openfile = pyqtSignal(str)

    def event(self, event):
        """Catch file open on a Mac."""
        if event.type() == QEvent.Type.FileOpen:
            filename = event.file()
            self.openfile.emit(filename)
        return QApplication.event(self, event)


class UpdateThread(QThread):
    """Handle the thread."""

    update_now = pyqtSignal()

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


class SweepPreview(QMainWindow):
    """
    Data viewer for matrix files.

    Parameters
    ----------
    filename: str
      name of matrix file (.ma6, .ma7, .ma8)
    parent: widget or None
      parent widget
    """

    openfile_dialog = pyqtSignal()
    allowed_extensions = (".ma6", ".ma7", ".ma8")

    def __init__(self, parent=None, filename=""):
        super().__init__(parent)
        self.filename = ""
        self.closing_allowed = True
        self.w_meta_view = None
        # initialize basic GUI
        self.init_basic_ui()
        # allow to store the settings
        self.settings = QSettings("matr1x", "preview")
        # signal from delayed file open
        self.openfile_dialog.connect(self.load_button_pressed)
        # handle MacOS specific FileOpenEvent from Matr1xApplication
        if hasattr(QApplication.instance(), 'openfile'):
            QApplication.instance().openfile.connect(self.open_file)
        # initialize filename if available
        if filename:
            self.open_file(filename)
        else:
            self.file_open_thread = threading.Thread(
                target=self._delayed_file_load_attempt)
            logger.info("start delayed")
            self.file_open_thread.start()

    def is_valid_extension(self, file_path):
        """Return True if extension is valid."""
        return file_path.endswith(self.allowed_extensions)

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
                    f"Only files with extensions {', '.join(self.allowed_extensions)} are supported.")
        else:
            QMessageBox.warning(self, "Multiple Files",
                                "Please drop only a single file.")

    def _get_maximum_screen_width(self):
        """Determine width of the biggest available screen."""
        width = 0
        for screen in QApplication.instance().screens():
            width = max(width, screen.geometry().width())
        return width

    def _delayed_file_load_attempt(self):
        """
        Trigger opening the file open dialog.

        On Linux/Windows the file open dialog opens immediately.
        On MacOS only in case no FileOpen Event is generated in the meantime.
        """
        if sys.platform == "darwin":
            # the mac uses an openfile event to signal the filename
            # a 2020 intel machine required 100ms, 300ms seems like a save
            # margin
            time.sleep(0.3)
        if sys.platform == "linux":
            # The sleep is needed to allow time to set up the GUI,
            # otherwise the default window size determination fails
            time.sleep(0.02)
        if not self.filename:
            self.openfile_dialog.emit()

    def eventFilter(self, f_object, f_event):
        """Update the file view if required."""
        if f_object == self.w_file:
            if f_event.type() == QEvent.Type.MouseButtonPress:
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
            self.open_file(filename)
        else:
            if not self.filename:
                self.w_status.setText("Please open a file")

    def open_file(self, filename):
        """Read the data from the file."""
        logger.info(f"opening {filename}")
        self.filename = filename
        # get all files
        self.file_dir = os.path.dirname(abspath(filename))
        self.setWindowTitle(f"Matrix Preview: {self.file_dir}")
        self.file_list_refresh()
        self.file_index = self.data_files.index(os.path.basename(filename))
        self.udthread = None
        self.lu_time = time.time()
        self.fetch_data()
        self.multidim = False
        self.error = False
        self.clear_ui()
        self.init_ui()
        self.w_file.installEventFilter(self)

    def file_list_refresh(self):
        """Refresh all files with the correct extension in the selected directory."""
        files = os.listdir(self.file_dir)
        self.data_files = [file for file in files if self.is_valid_extension(file)]
        self.data_files = sorted(
            self.data_files,
            key=lambda t: os.stat(os.path.join(self.file_dir, t)).st_mtime,
        )

    def update_file_combo(self):
        """Update the combo box that displays the file names."""
        self.file_list_refresh()
        ctext = self.w_file.currentText()
        self.w_file.setToolTip(self.file_dir)
        self.w_file.currentIndexChanged.disconnect()
        self.w_file.clear()
        self.w_file.addItems(self.data_files)
        index = self.data_files.index(ctext)
        self.w_file.setCurrentIndex(index)  # current index can differ from
        # self.file_index, problem?
        self.w_file.currentIndexChanged.connect(self.file_index_changed)

    def closeEvent(self, event):
        """Store toolbar position on close."""
        if self.closing_allowed:
            self.saveCurrentState()
            event.accept()
        else:
            event.ignore()

    def saveCurrentState(self):
        """Save preferences for toolbar and window placement."""
        self.settings.setValue("position", self.pos())
        self.settings.setValue("size", self.size())
        self.settings.setValue("toolbar_placement", self.toolBarArea(self.toolbar))
        if self.w_meta_view:
            self.settings.setValue(
                "meta_placement", self.dockWidgetArea(self.w_meta_view)
            )
            self.settings.setValue("meta_floating", self.w_meta_view.isFloating())
            self.settings.setValue("meta_position", self.w_meta_view.pos())
            self.settings.setValue("meta_size", self.w_meta_view.size())

    def restoreState(self):
        """Restore window and toolbar placement."""
        self.addToolBar(
            self.settings.value("toolbar_placement", Qt.ToolBarArea.TopToolBarArea),
            self.toolbar,
        )
        recommended_size = self.sizeHint()
        self.move(self.settings.value("position", self.pos()))
        self.resize(self.settings.value("size", recommended_size))

    def info_box(self):
        """Display an 'about this app' widget."""
        box = AboutBox(
            "Matrix Preview",
            MIcon("matr1x-matrix-preview.png"),
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

    def init_basic_ui(self):
        """Initialize basic GUI that works without chosen filename."""
        self.setWindowTitle("Matrix Preview")
        self.setWindowIcon(MIcon("matr1x-matrix-preview.png"))

        pyqtgraph.setConfigOption("background", "w")
        pyqtgraph.setConfigOption("foreground", "k")

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.grid = QGridLayout()
        self.widget = QWidget()

        # Open
        self.load_action = QAction(MIcon("SP_DialogOpenButton"), "Open", self)
        self.load_action.triggered.connect(self.load_button_pressed)
        self.load_action.setShortcut(QKeySequence.StandardKey.Open)
        # Previous
        self.previous_action = QAction(MIcon("SP_ArrowLeft"), "Previous", self)
        cmd_left_shortcut = QKeySequence(
            Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_Left
        )
        self.previous_action.setShortcut(cmd_left_shortcut)
        self.previous_action.setEnabled(False)
        self.previous_action.triggered.connect(self.previous_file)
        # Next
        self.next_action = QAction(MIcon("SP_ArrowRight"), "Next", self)
        cmd_right_shortcut = QKeySequence(
            Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_Right
        )
        self.next_action.setShortcut(cmd_right_shortcut)
        self.next_action.setEnabled(False)
        self.next_action.triggered.connect(self.next_file)
        # Export plot
        self.export_png_action = QAction(MIcon("SP_DialogSaveButton"), "Save png", self)
        self.export_png_action.setEnabled(False)
        self.export_png_action.setShortcut(QKeySequence.StandardKey.Save)
        self.export_png_action.triggered.connect(self.save_plot)
        # Save data as as text file
        self.export_data_action = QAction(
            MIcon("SP_FileDialogDetailedView"), "Save txt", self
        )
        self.export_data_action.setEnabled(False)
        self.export_data_action.triggered.connect(self.save_data)
        # Update
        self.auto_update_action = QAction(
            MIcon("SP_BrowserReload"), "Auto Update", self
        )
        self.auto_update_action.setEnabled(False)
        self.auto_update_action.setCheckable(True)
        self.auto_update_action.toggled.connect(self.updatethread)
        self.update_action = QAction(
            MIcon("CHAR_U", QColor("RoyalBlue")), "Update", self
        )
        self.update_action.setEnabled(False)
        self.update_action.triggered.connect(lambda: self.conditional_fetch_data(True))
        # Quit
        self.quit_action = QAction("Quit", self)
        if os.name == "nt":
            self.quit_action.setShortcut(QKeySequence.StandardKey.Close)
        else:
            self.quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.quit_action.triggered.connect(self.close)
        # File List
        self.w_file = QComboBox()
        self.w_file.setEnabled(False)
        self.w_file.setMinimumContentsLength(50)
        # About
        self.about_action = QAction("About", self)
        self.about_action.setMenuRole(QAction.MenuRole.AboutRole)
        self.about_action.triggered.connect(self.info_box)
        # View: Toolbar
        self.toggle_toolbar_action = QAction("Show Toolbar", self)
        self.toggle_toolbar_action.setShortcut(QKeySequence("Ctrl+1"))
        self.toggle_toolbar_action.setCheckable(True)
        self.toggle_toolbar_action.setChecked(True)
        self.toggle_toolbar_action.triggered.connect(self.toggle_toolbar_view)
        # Meta Data
        self.meta_action = QAction(MIcon("SP_FileDialogListView"), "Metadata", self)
        self.meta_action.setShortcut(QKeySequence("Ctrl+2"))
        self.meta_action.setEnabled(False)
        self.meta_action.setCheckable(True)
        self.meta_action.triggered.connect(self.toggle_meta)

        self.w_status = QLabel("")
        self.w_status.setStyleSheet("QLabel { color : red; }")

        self.grid.addWidget(self.w_status, 6, 0, 1, -1)

        self.widget.setLayout(self.grid)
        self.setCentralWidget(self.widget)

        # Enable dragging and dropping onto the widget
        self.setAcceptDrops(True)
        self.create_toolbar()
        self.create_menu()

        self.ui_initialized = False
        self.show()

    def create_toolbar(self) -> None:
        """Create the toolbar."""
        self.toolbar = QToolBar("Toolbar")
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.toolbar.setFloatable(False)
        self.toolbar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        small = QApplication.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize)
        standard = QApplication.style().pixelMetric(
            QStyle.PixelMetric.PM_ToolBarIconSize
        )
        intermediate = int((small + standard) / 2)
        self.toolbar.setIconSize(QSize(intermediate, intermediate))
        self.toolbar.setAllowedAreas(
            Qt.ToolBarArea.TopToolBarArea | Qt.ToolBarArea.BottomToolBarArea
        )
        # add the toolbar items
        self.toolbar.addAction(self.load_action)
        self.addToolBar(self.toolbar)
        self.toolbar.visibilityChanged.connect(self.toggle_toolbar_action.setChecked)
        self.toolbar.addAction(self.export_png_action)
        self.toolbar.addAction(self.export_data_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.update_action)
        self.toolbar.addAction(self.auto_update_action)
        empty = QWidget()
        empty.setFixedWidth(intermediate)
        self.toolbar.addWidget(empty)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.toolbar.addWidget(spacer)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.previous_action)
        self.toolbar.addWidget(self.w_file)
        self.toolbar.addAction(self.next_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.meta_action)

    def create_menu(self) -> None:
        """Create the main menu."""
        menu = self.menuBar()
        #
        self.file_menu = menu.addMenu("&File")
        self.file_menu.addAction(self.load_action)
        self.file_menu.addAction(self.quit_action)
        self.file_menu.addAction(self.export_png_action)
        self.file_menu.addAction(self.export_data_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.update_action)
        self.file_menu.addAction(self.auto_update_action)
        if sys.platform != "darwin":
            self.file_menu.addSeparator()
            self.file_menu.addAction(self.quit_action)
        #
        self.control_menu = menu.addMenu("&Control")
        self.control_menu.addAction(self.previous_action)
        self.control_menu.addAction(self.next_action)
        #
        self.view_menu = menu.addMenu("&View")
        self.view_menu.addAction(self.toggle_toolbar_action)
        self.view_menu.addAction(self.meta_action)
        #
        self.help_menu = menu.addMenu("&Help")
        self.help_menu.addAction(self.about_action)

    def init_ui(self):
        """Initialize GUI for popup."""
        # File list
        self.w_file.addItems(self.data_files)
        self.w_file.setCurrentIndex(self.file_index)
        self.w_file.currentIndexChanged.connect(self.file_index_changed)

        if not self.w_meta_view:
            self.w_meta_view = gui_util.MetaViewerWidget(self.header)
            self.w_meta_view.setFeatures(
                QDockWidget.DockWidgetFeature.DockWidgetClosable
                | QDockWidget.DockWidgetFeature.DockWidgetFloatable
                | QDockWidget.DockWidgetFeature.DockWidgetMovable
            )
            self.w_meta_view.setAllowedAreas(
                Qt.DockWidgetArea.LeftDockWidgetArea
                | Qt.DockWidgetArea.RightDockWidgetArea
            )
            self.w_meta_view.setVisible(False)
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.w_meta_view)
            # restore settings
            self.addDockWidget(
                self.settings.value(
                    "meta_placement", Qt.DockWidgetArea.RightDockWidgetArea
                ),
                self.w_meta_view,
            )
            self.w_meta_view.setFloating(
                self.settings.value("meta_floating", False, type=bool)
            )
            if self.w_meta_view.isFloating():
                self.w_meta_view.move(
                    self.settings.value("meta_position", self.w_meta_view.pos())
                )
                self.w_meta_view.resize(
                    self.settings.value("meta_size", self.w_meta_view.size())
                )
            else:
                self.resizeDocks(
                    [self.w_meta_view],
                    [self.settings.value("meta_size", self.w_meta_view.size()).width()],
                    Qt.Orientation.Horizontal,
                )
        else:
            # meta view already exists, replace and ensure w_meta button
            # has right check state
            self.meta_action.setChecked(self.w_meta_view.isVisible())

        self.w_meta_view.visibilityChanged.connect(self.meta_action.setChecked)
        # Update
        auinit = False
        self.auto_update_action.setChecked(auinit)
        self.updatethread(auinit)

        self.w_l = [QLabel("y"), QLabel("x"), QLabel("y")]
        self.w_l[2].setVisible(False)

        self.w_index = [QComboBox(), QComboBox(), QComboBox()]
        self.w_index[1].setEnabled(False)
        self.w_index[2].setVisible(False)

        self.column_items = [
            f"{name} ({unit}), shape: {shape}" for name, unit, shape
            in zip(self.names, self.units, self.shapes)]

        for i in range(3):
            self.w_index[i].addItems([""] + self.column_items)
            self.w_index[i].currentIndexChanged.connect(self.index_changed)

        self.w_plot2d = QCheckBox("2d plotting")
        self.w_plot2d.toggled.connect(self.plotting_toggled)

        self.w_plot2d_comp = QCheckBox("2d complex")
        self.w_plot2d_comp.toggled.connect(self.plotting_complex)
        self.w_plot2d_comp.setVisible(False)

        self.w_transpose = QCheckBox("transpose")
        self.w_transpose.setVisible(False)
        self.w_transpose.toggled.connect(self.transpose_toggled)

        self.spw = gui_util.SimplePlotWidget(self.raise_error, self.index_callback)
        # minimum height of plot widget, could be removed but then
        # window always needs to be resized
        self.spw.setMinimumHeight(350)
        self.iv = None

        self.grid.addWidget(self.w_plot2d, 2, 3, 1, 1)
        for i in range(3):
            self.grid.addWidget(self.w_l[i], i+1, 0)
            self.grid.addWidget(self.w_index[i], i+1, 1)
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
            self.export_png_action.setEnabled(True)
            self.export_data_action.setEnabled(True)
            self.update_action.setEnabled(True)
            self.auto_update_action.setEnabled(True)
            self.previous_action.setEnabled(True)
            self.w_file.setEnabled(True)
            self.next_action.setEnabled(True)
            self.meta_action.setEnabled(True)
            # do not duplicate the items next time
            self.ui_initialized = True

    def clear_ui(self):
        """Clear the UI."""
        for i in reversed(range(2, self.grid.count())):
            item = self.grid.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                for j in range(item.layout().count()):
                    item.layout().takeAt(0).widget().deleteLater()

    def toggle_meta(self, state):
        """Toggle the meta data view."""
        if state is True:
            self.w_meta_view.setVisible(True)
        else:
            self.w_meta_view.setVisible(False)

    def get_filename_without_extension(self) -> str:
        """Return the actual filename without extension."""
        for extension in self.allowed_extensions:
            if self.filename.endswith(extension):
                return self.filename[: -len(extension)]
        return self.filename

    def save_plot(self) -> None:
        """Ask for filename and save the displayed data in a png file."""
        filename = QFileDialog.getSaveFileName(
            self,
            "Select output png file",
            self.get_filename_without_extension() + ".png",
            "png files (*.png)",
        )[0]
        if filename:
            if ".png" != filename[-4:].lower():
                filename += ".png"
            if self.iv is not None:
                exporter = pyqtgraph.exporters.ImageExporter(self.iv.view)
                exporter.export(filename)
            else:
                self.spw.save_plot(filename)

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
            if ".txt" != filename[-4:].lower():
                filename += ".txt"
            self.spw.save_data(filename)

    def previous_file(self):
        """Determine the previous file."""
        self.update_file_combo()
        if self.file_index > 0:
            self.w_file.setCurrentIndex(self.file_index-1)

    def next_file(self):
        """Determine the next file."""
        self.update_file_combo()
        if self.file_index < len(self.data_files) - 1:
            self.w_file.setCurrentIndex(self.file_index+1)

    def file_index_changed(self, index):
        """Update info when index changes."""
        self.file_index = index
        self.filename = os.path.join(self.file_dir, self.data_files[self.file_index])
        check = self.conditional_fetch_data(True, check=True)
        if 0 != check:
            self.column_items = [
                f"{name} ({unit}), shape: {shape}" for name, unit, shape
                in zip(self.names, self.units, self.shapes)]
            if -2 == check:
                # file has same columns but different shapes, only change
                # names to reflect the dimensions
                for i in range(3):
                    for j, item in enumerate(self.column_items):
                        self.w_index[i].setItemText(j+1, item)
            elif -1 == check:
                # file has different columns
                # reload interface
                for i in range(3):
                    self.w_index[i].clear()
                    self.w_index[i].addItems([""] + self.column_items)
                self.reset()
                self.spw.reset()
        else:
            ci = self.spw.w_plots.currentIndex()
            for i in range(self.spw.w_plots.count()-1):
                if i == ci:
                    # skip plot that will remain selected
                    continue
                self.spw.w_plots.setCurrentIndex(i)
            # reset active plot
            self.spw.w_plots.setCurrentIndex(ci)
        self.w_meta_view.update_data(self.header)

    def index_changed(self, newIndex):
        """If index changed, reload the new data and handle the gui interaction."""
        if self.w_index[0] == self.sender():
            if newIndex == 0:
                self.w_index[1].setEnabled(False)
                self.w_index[1].setCurrentIndex(0)
            else:
                self.w_index[1].setEnabled(True)
        self.reload_data()

    def transpose_toggled(self, check_state):
        """Transpose has been toggled, reload data."""
        if (self.w_plot2d.isChecked() is True and
                self.w_plot2d_comp.isChecked() is False):
            if len(self.shapes[self.w_index[0].currentIndex()-1]) < 3:
                # toggle index for 2d data, since x and y invert role
                dummy = self.w_index[2].currentIndex()
                self.w_index[2].blockSignals(True)
                self.w_index[2].setCurrentIndex(self.w_index[1].currentIndex())
                self.w_index[1].setCurrentIndex(dummy)
                self.w_index[2].blockSignals(False)
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
        self.w_index[2].setVisible(check_state)
        self.export_data_action.setEnabled(not check_state)
        self.reload_data()

    def plotting_complex(self, check_state):
        """Turn on the more complex 2D plotting widget provided by pyqtgraph instead of using the SimplePlotWidget."""
        if check_state is True:
            self.spw.setVisible(False)
            if self.iv is None:
                # set up image view on first initialization
                self.iv = pyqtgraph.ImageView()
                self.widget.layout().addWidget(self.iv, 4, 0, 1, -1)
            else:
                self.iv.setVisible(True)
        elif check_state is False and self.iv is not None:
            self.widget.layout().removeWidget(self.iv)
            del self.iv
            self.iv = None
            self.spw.setVisible(True)
        # reload data and set widget labels
        self.plotting_toggled(check_state or self.w_plot2d.isChecked())

    def raise_error(self, error):
        """Raise the error flag, can be used as callback function to set errors from the SimplePlotWidget."""
        if error != "":
            self.w_status.setVisible(True)
            self.w_status.setText(error)
            self.error = True
        elif error == "" and self.error is True:
            self.error = False
            self.w_status.setVisible(False)

    def index_callback(self, plot_object):
        """Handle a change of the ploted index via the plot selector of the SimplePlotWidget (callback)."""
        self.w_plot2d.blockSignals(True)
        self.w_plot2d.setChecked(plot_object.plot2d)
        self.w_plot2d.blockSignals(False)
        for i in range(3):
            self.w_index[i].blockSignals(True)
            self.w_index[i].setCurrentIndex(plot_object.desig[i])
            self.w_index[i].blockSignals(False)
        self.reload_data()

    def updatethread(self, state):
        """Run and terminate a thread that reloads the data from the file if the filename has changed."""
        if state is True:
            # start updatethread with 2s refresh time
            self.udthread = UpdateThread(2)
            self.udthread.update_now.connect(self.conditional_fetch_data)
            self.udthread.start()
        if state is False and self.udthread is not None:
            self.udthread.terminate()
            self.udthread = None

    def conditional_fetch_data(self, force=False, check=False):
        """
        Fetch data from the file.

        Fetches data from the file if force is True, or if the modification
        time is past the time of the latest update (stored in self.lu_time).
        If force is false, this function was called from the updatethread,
        therefore make it update all windows.
        """
        ret = 0
        if force is True:
            # file has changed after last update,
            # reload the data into the file structure
            ret = self.fetch_data(check=check)
            self.reload_data()
            self.refresh_all_plots()
            self.refresh_columns_size()
        elif getsize(self.filename) > 300000 and time.time() - self.lu_time < 20:
            # skip updates if delta is below 20s and filesize is > 300kB
            # to avoid overloading the system with read queries
            pass
        elif self.lu_time < getmtime(self.filename):
            # file has changed after last update,
            # reload the data into the file structure
            ret = self.fetch_data(check=check)
            self.reload_data()
            self.refresh_all_plots()
            self.refresh_columns_size()
        return ret

    def refresh_columns_size(self):
        """Refresh size of all columns."""
        self.column_items = [
            f"{name} ({unit}), shape: {shape}" for name, unit, shape
            in zip(self.names, self.units, self.shapes)]
        # change names to reflect the dimensions
        for i in range(3):
            for j, item in enumerate(self.column_items):
                self.w_index[i].setItemText(j+1, item)

    def refresh_all_plots(self):
        """Refresh all subplots by selecting each individually."""
        ci = self.spw.w_plots.currentIndex()
        for i in range(self.spw.w_plots.count()-1):
            if ci == i:
                # skip current index as this one will be done last
                pass
            self.spw.w_plots.setCurrentIndex(i)
        self.spw.w_plots.setCurrentIndex(ci)

    def reset(self):
        """Reset the actual data view."""
        self.w_plot2d.setChecked(False)
        self.w_plot2d_comp.setChecked(False)
        self.w_transpose.setChecked(False)
        if self.iv is not None:
            self.widget.layout().removeWidget(self.iv)
            del self.iv
            self.iv = None

    def fetch_data(self, check=False):
        """Handle the data operations."""
        try:
            ret = 0
            self.header, self.data = loadmatrix(self.filename,
                                                replace_None=True)
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
        except Exception:
            # file could not be opened
            exc_type, exc_value, exc_traceback = sys.exc_info()
            _ = QMessageBox.critical(
                self, "Error when opening file",
                f"""
The following error was raised when opening the file:
{repr(exc_value)}
Please investigate the error and eventually restart matrix-preview""")
            sys.exit(-1)

        # update timer
        self.lu_time = time.time()
        return ret

    def reload_data(self):
        """Wrap the 1d and 2d plotting functions and decide which one is appropriate from the state of the gui."""
        if (self.w_plot2d.isChecked() is True or
                self.w_plot2d_comp.isChecked() is True):
            ret = self.reload_data_2d()
        else:
            ret = self.reload_data_curve()
        # handle the error if there is any
        self.handle_error(ret)

    def handle_error(self, ret):
        """Handle a possible dimension error of the reload_data function."""
        if ret < 0:
            if ret == -3:
                self.raise_error("no data selected")
            elif ret == -2:
                self.raise_error(
                    "data has too high dimension for 1d slicing")
            elif ret == -1:
                self.raise_error(
                    "data axis cannot be reshaped, lengths not multiples")
            elif ret == -4:
                self.raise_error(
                    "data shapes complicated, do not know what to do")
            elif ret == -5:
                self.raise_error(
                    "data has too low or too high dimension for 2d plot")
            elif ret == -6:
                self.raise_error(
                    "data has too high dimension for 2d slicing")
            elif ret == -7:
                self.raise_error(
                    "data in x does not have correct dimension")
            elif ret == -8:
                self.raise_error(
                    "data in y does not have correct dimension")
            elif ret == -9:
                self.raise_error(
                    "data array with zero length dimension is present")
        elif self.error is True:
            self.error = False
            self.w_status.setVisible(False)

    def reload_data_2d(self):
        """Reload the data in the 2d case."""
        indexZ, indexX, indexY = [
            self.w_index[i].currentIndex() - 1 for i in range(3)]
        x = {}
        y = {}
        z = {}
        if indexZ == -1:
            # empty index selected
            return -3
        for i, (index, dat) in enumerate(zip([indexZ, indexX, indexY],
                                             [z, x, y])):
            if index == -1:
                dat["data"] = False
                continue
            else:
                dim = len(self.shapes[index])
                name = self.names[index]
                dat["label"] = name
                dat["desig"] = index+1
                dat["unit"] = self.units[index]
                data = self.data[name]
                if data.size > 0:
                    dat["data"] = data
                else:
                    return -9
                dat["shape"] = dat["data"].shape
                dat["dim"] = dim
            if dim > 2 and i == 0 and self.w_plot2d_comp.isChecked() is True:
                self.w_index[1].setEnabled(True)
            elif i == 0 and self.w_plot2d_comp.isChecked() is True:
                self.w_index[1].setEnabled(False)
                self.w_index[1].setCurrentIndex(0)
            elif i == 0 and self.w_index[1].isEnabled() is False:
                # if coming from complex view and x was disabled, enable now
                self.w_index[1].setEnabled(True)
            if dim > 2 and i == 0 and self.w_plot2d_comp.isChecked() is False:
                # 3D plotting, disable y since it is not meaningful here
                # x gives the plotting axis (i.e. value corresponding to index)
                self.w_l[2].setVisible(False)
                self.w_index[2].setVisible(False)
                self.w_index[2].setCurrentIndex(0)
            elif i == 0 and self.w_plot2d_comp.isChecked() is False:
                self.w_l[2].setVisible(True)
                self.w_index[2].setVisible(True)
            if (dim < 2 and i == 0) or dim > 3:
                # dimensions not compatible
                # <1D or >3D data cannot be 2d plotted.
                return -5

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
        if x["data"] is False:
            x = dict(label="array index", unit="", dim=1,
                     data=np.arange(z["shape"][0]), desig=0,
                     shape=(z["shape"][0],))
        else:
            index = 1 if (transpose is True and x["dim"] > 1) else 0
            lenx = x["shape"][index]
            # verify length matches dimension z
            if lenx != z["shape"][0]:
                return -7
            if x["dim"] < 2:
                x["data"] = np.linspace(x["data"][0], x["data"][-1], lenx)
            else:
                if transpose is False:
                    x["data"] = np.linspace(x["data"][0, 0],
                                            x["data"][-1, 0],
                                            lenx)
                else:
                    x["data"] = np.linspace(x["data"][0, 0],
                                            x["data"][0, -1],
                                            lenx)
            x["shape"] = lenx
            x["dim"] = 1

        if y["data"] is False:
            y = dict(label="array index", unit="", dim=1,
                     data=np.arange(z["shape"][1]), desig=0,
                     shape=(z["shape"][1],))
        else:
            index = 1 if transpose is False and y["dim"] > 1 else 0
            leny = y["shape"][index]
            # verify length matches dimension z
            if leny != z["shape"][1]:
                return -8
            if y["dim"] < 2:
                y["data"] = np.linspace(y["data"][0], y["data"][-1], leny)
            else:
                if transpose is False:
                    y["data"] = np.linspace(y["data"][0, 0],
                                            y["data"][0, -1],
                                            leny)
                else:
                    y["data"] = np.linspace(y["data"][0, 0],
                                            y["data"][-1, 0],
                                            leny)
            y["shape"] = leny
            y["dim"] = 1

        if self.w_plot2d_comp.isChecked() is True:
            if z["dim"] > 2:
                axes = {"t": 0, "x": 1, "y": 2}
            else:
                axes = {"x": 0, "y": 1}
            self.iv.setImage(z["data"], axes=axes, xvals=x["data"])
            self.iv.getView().invertY(False)
            self.iv.getView().setAspectLocked(False)
            self.iv.getHistogramWidget().axis.setLabel(z["label"])

        else:
            self.spw.plot(z, x, y,
                          plot2d=self.w_plot2d.isChecked())
        return 0

    def reload_data_curve(self):
        """
        Reload the data.

        Try to make the dimensions suitable for a 1D curve plot by smart guessing from the data dimension.
        """
        indexY, indexX = [self.w_index[i].currentIndex() - 1 for i in range(2)]
        x = {}
        y = {}
        # disable transpose widget
        self.w_transpose.setVisible(False)
        if indexY == -1:
            # empty index selected
            return -3
        elif indexX == -1:
            # set up axis labels and units according to index
            # only have y data, so make x array index
            dim = len(self.shapes[indexY])
            if dim < 3:
                # 1D or 2D data can be plotted without second data set
                # against column index
                yname = self.names[indexY]
                if 2 == dim:
                    # 2D data can be transposed
                    self.w_transpose.setVisible(True)
                if self.w_transpose.isChecked() is True and 2 == dim:
                    y["data"] = self.data[yname].T
                else:
                    y["data"] = self.data[yname]
                y["shape"] = y["data"].shape
                x = dict(label="array index", unit="", dim=1,
                         data=np.arange(y["shape"][0]), desig=0,
                         shape=(y["shape"][0],))
                y["label"] = yname
                y["desig"] = indexY+1
                y["unit"] = self.units[indexY]
                y["dim"] = dim
            else:
                return -2
        else:
            # both axes are define, set up x and y dictionary
            yname = self.names[indexY]
            y = dict(label=yname, desig=indexY+1, unit=self.units[indexY],
                     data=self.data[yname], shape=self.shapes[indexY],
                     dim=len(self.shapes[indexY]))
            xname = self.names[indexX]
            x = dict(label=xname, desig=indexX+1, unit=self.units[indexX],
                     data=self.data[xname], shape=self.shapes[indexX],
                     dim=len(self.shapes[indexX]))

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
                if 0 == large_axis % small_axis:
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


def main():
    """Set the basic GUI parameters and run."""
    app = Matr1xApplication(sys.argv)
    if os.name == 'nt':
        # enable modern mode on windows which allows for darkmode
        app.setStyle('fusion')
    elif sys.platform == "darwin":
        set_correct_mac_appname("Matrix Preview")
    app.setDesktopFileName("matrix-preview")
    # we need to ignore this signal here otherwise we are kicked into
    # background when matrix returns. see run_as_fg_process
    if 'SIGTTOU' in dir(signal):  # signal only on POSIX compliant systems
        signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    with QtGracefulKiller():
        if len(sys.argv) < 2:
            ex = SweepPreview(None, "")
        else:
            ex = SweepPreview(None, sys.argv[1])
        ex.show()
        ex.restoreState()
        ret = app.exec()
    sys.exit(ret)
