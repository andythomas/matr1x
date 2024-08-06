# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2024 matr1x developers. All rights reserved.
# ---
import logging
import os
import signal
import sys
import threading
import time
import warnings
from os.path import abspath, dirname, getmtime, getsize, join

import numpy as np

# Try to import Qt6 and fallback to Qt5 if not available
try:
    from PyQt6.QtCore import QEvent, Qt, QThread, pyqtSignal
    from PyQt6.QtGui import QIcon
    from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox,
                                 QDockWidget, QFileDialog, QGridLayout,
                                 QHBoxLayout, QLabel, QLayout, QMainWindow,
                                 QMessageBox, QPushButton, QToolButton, QWidget)
except ImportError:
    warnings.warn("PyQt5 support will be removed in 2024. Switch to PyQt6",
                  DeprecationWarning)
    from PyQt5.QtCore import QEvent, Qt, QThread, pyqtSignal
    from PyQt5.QtGui import QIcon
    from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox,
                                 QDockWidget, QFileDialog, QGridLayout,
                                 QHBoxLayout, QLabel, QLayout, QMainWindow,
                                 QMessageBox, QPushButton, QToolButton, QWidget)

import pyqtgraph as pg
import pyqtgraph.exporters
from matr1x import gui_util as gu
from matr1x.control.util import QtGracefulKiller
from matr1x.eval import loadmatrix

logger = logging.getLogger(os.path.split(__file__)[-1])

if os.name == 'nt':
    try:
        from ctypes import windll  # Only exists on Windows.
        myappid = 'python.matr1x.matrix-preview.version'
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass


class Matr1xApplication (QApplication):
    openfile = pyqtSignal(str)

    def event(self, event):
        if event.type() == QEvent.Type.FileOpen:
            filename = event.file()
            self.openfile.emit(filename)
        return QApplication.event(self, event)


class UpdateThread(QThread):
    update_now = pyqtSignal()

    def __init__(self, interval):
        QThread.__init__(self)
        self.stopFlag = False
        self.interval = interval

    def run(self):
        while not self.stopFlag:
            time.sleep(self.interval)
            self.update_now.emit()

    def terminate(self):
        self.stopFlag = True


class SweepPreview(QMainWindow):
    """
    Data viewer for matrix files

    Parameters
    ----------
    filename: str
      name of matrix file (.ma6 or .ma7)
    parent: widget or None
      parent widget
    """
    openfile_dialog = pyqtSignal()
    allowed_extensions = ('.ma6', '.ma7')

    def __init__(self, parent=None, filename=""):
        super().__init__(parent)
        self.filename = ""
        # initialize basic GUI
        self.init_basic_ui()

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
        return file_path.endswith(self.allowed_extensions)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
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
        """
        determine width of the biggest available screen.
        """
        width = 0
        for screen in QApplication.instance().screens():
            width = max(width, screen.geometry().width())
        return width

    def _delayed_file_load_attempt(self):
        """
        Function to trigger opening the file open dialog.
        On Linux/Windows the file open dialog opens immediately.
        On MacOS only in case no FileOpen Event is generated in the meantime.
        """
        if sys.platform == "darwin":
            # the mac uses an openfile event to signal the filename
            # a 2020 intel machine required 100ms, 300ms seems like a save
            # margin
            time.sleep(0.3)
        if not self.filename:
            self.openfile_dialog.emit()

    def eventFilter(self, f_object, f_event):
        if f_object == self.w_file:
            if f_event.type() == QEvent.Type.MouseButtonPress:
                self.update_file_combo()
            return False
        return False

    def load_button_pressed(self):
        filename = QFileDialog.getOpenFileName(
            self, "Select ma file", "",
            "matrix files (*.ma7);;old matrix files (*.ma6)",)[0]
        if filename:
            self.open_file(filename)
        else:
            if not self.filename:
                self.w_status.setText("Please open a file")

    def open_file(self, filename):
        logger.info(f"opening {filename}")
        self.filename = filename
        # get all files
        self.file_dir = os.path.dirname(abspath(filename))
        self.file_list_refresh()
        self.file_index = self.data_files.index(
            os.path.join(self.file_dir, os.path.basename(filename)))
        self.udthread = None
        self.lu_time = time.time()
        self.fetch_data()
        self.multidim = False
        self.error = False
        self.clear_ui()
        self.init_ui()
        self.w_file.installEventFilter(self)

    def file_list_refresh(self):
        files = os.listdir(self.file_dir)
        self.data_files = (
            [os.path.join(self.file_dir, file)
             for file in files if self.is_valid_extension(file)])
        self.data_files = sorted(
            self.data_files, key=lambda t: os.stat(t).st_mtime)

    def update_file_combo(self):
        self.file_list_refresh()
        ctext = self.w_file.currentText()
        self.w_file.currentIndexChanged.disconnect()
        self.w_file.clear()
        self.w_file.addItems(self.data_files)
        index = self.data_files.index(ctext)
        self.w_file.setCurrentIndex(index)  # current index can differ from
        # self.file_index, problem?
        self.w_file.currentIndexChanged.connect(self.file_index_changed)

    def init_basic_ui(self):
        """
        initialize basic GUI that works without chosen filename
        """
        self.setWindowTitle("Matrix Preview")

        # initialize empty window
        icondir = join(dirname(__file__), 'icons')
        self.setWindowIcon(QIcon(join(icondir, 'matr1x-matrix-preview.png')))

        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.grid = QGridLayout()
        self.widget = QWidget()

        w_load = QPushButton("load file")
        w_load.clicked.connect(self.load_button_pressed)
        self.w_status = QLabel("")
        self.w_status.setStyleSheet("QLabel { color : red; }")

        self.grid.addWidget(w_load, 0, 0, 1, 1)
        self.grid.addWidget(self.w_status, 6, 0, 1, -1)

        self.widget.setLayout(self.grid)
        self.setCentralWidget(self.widget)

        # Enable dragging and dropping onto the widget
        self.setAcceptDrops(True)
        self.show()

    def init_ui(self):
        """
        Initialize GUI for popup
        """
        l_file = QHBoxLayout()

        w_prev = QToolButton()
        w_prev.setArrowType(Qt.ArrowType.LeftArrow)
        w_prev.clicked.connect(self.previous_file)

        w_next = QToolButton()
        w_next.setArrowType(Qt.ArrowType.RightArrow)
        w_next.clicked.connect(self.next_file)

        self.w_file = QComboBox()
        self.w_file.addItems(self.data_files)
        self.w_file.setCurrentIndex(self.file_index)
        self.w_file.currentIndexChanged.connect(self.file_index_changed)

        w_meta = QPushButton("show meta data")
        w_meta.setCheckable(True)
        w_meta.toggled.connect(self.toggle_meta)

        l_file.addWidget(w_prev)
        l_file.addWidget(self.w_file, stretch=1)
        l_file.addWidget(w_next)
        l_file.addWidget(w_meta)

        self.w_meta_view = gu.MetaViewerWidget(self.header)
        self.w_meta_view.setFeatures(
            QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)

        w_save = QPushButton("export plot")
        w_save.clicked.connect(self.save_plot)

        w_update = QPushButton("update data")
        w_update.clicked.connect(lambda: self.conditional_fetch_data(True))

        self.autoupdateBox = QCheckBox("auto update")
        auinit = False
        self.autoupdateBox.setChecked(auinit)
        self.autoupdateBox.toggled.connect(self.updatethread)
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

        self.spw = gu.SimplePlotWidget(self.raise_error, self.index_callback)
        # minimum height of plot widget, could be removed but then
        # window always needs to be resized
        self.spw.setMinimumHeight(350)
        self.iv = None

        self.grid.addLayout(l_file, 0, 1, 1, -1)
        self.grid.addWidget(self.w_plot2d, 2, 3, 1, 1)
        self.grid.addWidget(w_save, 1, 4)
        self.grid.addWidget(w_update, 1, 2)
        self.grid.addWidget(self.autoupdateBox, 1, 3)
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

        self.w_meta_view.setVisible(False)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea,
                           self.w_meta_view)

    def clear_ui(self):
        for i in reversed(range(2, self.grid.count())):
            item = self.grid.takeAt(i)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                for j in range(item.layout().count()):
                    item.layout().takeAt(0).widget().deleteLater()

    def toggle_meta(self, state):
        if state is True:
            self.w_meta_view.setVisible(True)
        else:
            self.w_meta_view.setVisible(False)

    def save_plot(self):
        filename = QFileDialog.getSaveFileName(
            self, 'Select output png file', self.file_dir,
            "png files (*.png)")[0]
        if ".png" != filename[-4:].lower():
            filename += ".png"
        if self.iv is not None:
            exporter = pg.exporters.ImageExporter(self.iv.view)
            exporter.export(filename)
        else:
            self.spw.save_plot(filename)

    def previous_file(self):
        self.update_file_combo()
        if self.file_index > 0:
            self.w_file.setCurrentIndex(self.file_index-1)

    def next_file(self):
        self.update_file_combo()
        if self.file_index < len(self.data_files) - 1:
            self.w_file.setCurrentIndex(self.file_index+1)

    def file_index_changed(self, index):
        self.file_index = index
        self.filename = self.data_files[self.file_index]
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
        """
        If index is changed, reload the new data and handle the gui interaction
        """
        if self.w_index[0] == self.sender():
            if newIndex == 0:
                self.w_index[1].setEnabled(False)
                self.w_index[1].setCurrentIndex(0)
            else:
                self.w_index[1].setEnabled(True)
        self.reload_data()

    def transpose_toggled(self, check_state):
        """
        transpose has been toggled, reload data
        """
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
        """
        Switch the currently selected plotting view to 2D
        """
        self.w_l[0].setText("z" if check_state is True else "y")
        self.w_plot2d_comp.setVisible(check_state)
        if self.w_plot2d_comp.isChecked() is True and not check_state:
            self.w_plot2d_comp.setChecked(False)
        if self.w_plot2d_comp.isChecked() is True:
            check_state = not check_state
        self.w_l[2].setVisible(check_state)
        self.w_index[2].setVisible(check_state)
        self.reload_data()

    def plotting_complex(self, check_state):
        """
        Turn on the more complex 2D plotting widget provided by pyqtgraph
        instead of using the SimplePlotWidget
        """
        if check_state is True:
            self.spw.setVisible(False)
            if self.iv is None:
                # set up image view on first initialization
                self.iv = pg.ImageView()
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
        """
        raise the error flag, can be used as callback function to set errors
        from the SimplePlotWidget
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
        callback function that handles a change of the ploted index via the
        plot selector of the SimplePlotWidget
        """
        self.w_plot2d.blockSignals(True)
        self.w_plot2d.setChecked(plot_object.plot2d)
        self.w_plot2d.blockSignals(False)
        for i in range(3):
            self.w_index[i].blockSignals(True)
            self.w_index[i].setCurrentIndex(plot_object.desig[i])
            self.w_index[i].blockSignals(False)
        self.reload_data()

    def updatethread(self, state):
        """
        Function that runs and terminates a thread that reloads the data from
        the file if the filename has changed.
        """
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
        Fetches data from the file if force is True, or if the modification
        time is past the time of the latest update (stored in self.lu_time).
        If force is false, this function was called from the updatethread,
        therefore make it update all windows
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
        self.column_items = [
            f"{name} ({unit}), shape: {shape}" for name, unit, shape
            in zip(self.names, self.units, self.shapes)]
        # change names to reflect the dimensions
        for i in range(3):
            for j, item in enumerate(self.column_items):
                self.w_index[i].setItemText(j+1, item)

    def refresh_all_plots(self):
        """
        refresh all subplots by selecting each individually
        """
        ci = self.spw.w_plots.currentIndex()
        for i in range(self.spw.w_plots.count()-1):
            if ci == i:
                # skip current index as this one will be done last
                pass
            self.spw.w_plots.setCurrentIndex(i)
        self.spw.w_plots.setCurrentIndex(ci)

    def reset(self):
        self.w_plot2d.setChecked(False)
        self.w_plot2d_comp.setChecked(False)
        self.w_transpose.setChecked(False)
        if self.iv is not None:
            self.widget.layout().removeWidget(self.iv)
            del self.iv
            self.iv = None

    def fetch_data(self, check=False):
        """
        Function that actually handles the data operations
        """
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
        """
        wraps the 1d and 2d plotting functions and decides which one is
        appropriate from the state of the gui
        """
        if (self.w_plot2d.isChecked() is True or
                self.w_plot2d_comp.isChecked() is True):
            ret = self.reload_data_2d()
        else:
            ret = self.reload_data_curve()
        # handle the error if there is any
        self.handle_error(ret)

    def handle_error(self, ret):
        """
        Handles a possible dimension error of the reload_data function
        """
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
        Reloads the data and tries to make the dimensions suitable for a 1D
        curve plot by smart guessing from the data dimension.
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
    if "_" in os.path.basename(sys.argv[0]):
        warnings.warn(
            "The executable name 'matrix_preview' is deprecated. Use 'matrix-preview' instead.",
            FutureWarning)
    app = Matr1xApplication(sys.argv)
    if os.name == 'nt':
        # enable modern mode on windows which allows for darkmode
        app.setStyle('fusion')
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
        ret = app.exec()
    sys.exit(ret)
