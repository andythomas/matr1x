# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
import os
import signal
import sys
import time
from os.path import getmtime, getsize

import matr1x
import numpy as np
import pyqtgraph as pg
import pyqtgraph.exporters
from matr1x import gui_util as gu
from matr1x.control.util import QtGracefulKiller
from matr1x.eval import delta, loadh5matrix, loadmatrix
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog,
                             QGridLayout, QGroupBox, QHBoxLayout, QFrame, QLabel,
                             QLayout, QLineEdit, QMainWindow, QMessageBox, QPushButton,
                             QSizePolicy, QSlider, QToolButton, QVBoxLayout, QWidget)


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


class QRangeWidget(QGroupBox):
    value_changed = pyqtSignal(int)

    def __init__(self, title, parent=None):
        super().__init__("", parent)
        self.setMinimumHeight(30)
        self.setFixedHeight(30)
        self.base_title = title
        grid = QHBoxLayout()
        self.label = QLabel(title)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.setValue(0)
        self.inc = QToolButton()
        self.inc.setArrowType(Qt.RightArrow)
        self.dec = QToolButton()
        self.dec.setArrowType(Qt.LeftArrow)
        grid.addWidget(self.label)
        grid.addWidget(self.dec)
        grid.addWidget(self.slider, stretch=1)
        grid.addWidget(self.inc)
        grid.setContentsMargins(0, 0, 0, 0)
        self.setLayout(grid)

        self.slider.valueChanged.connect(self._value_changed)
        self.inc.clicked.connect(self._increment)
        self.dec.clicked.connect(self._decrement)

    def _increment(self):
        val = self.value() + 1
        if val <= self.maximum():
            self.slider.setValue(val)

    def _decrement(self):
        val = self.value() - 1
        if val >= 0:
            self.slider.setValue(val)

    def _updateText(self):
        self.label.setText(
            f"{self.base_title} - {self.value()} ({self.maximum()+1})")

    def _value_changed(self, val):
        self._updateText()
        self.value_changed.emit(val)

    def setValue(self, val):
        self.slider.setValue(val)
        self._updateText()

    def value(self):
        return self.slider.value()

    def setRange(self, minimum, maximum):
        self.slider.setRange(minimum, maximum)
        self._updateText()

    def maximum(self):
        return self.slider.maximum()


class PlotObject():
    """
    object that contains the plot and remembers what is plotted
    """
    exposed_functions = {"np": np, "sqrt": np.sqrt, "e": np.e, "pi": np.pi,
                         "power": np.power, "log": np.log, "log10": np.log10,
                         "exp": np.exp}

    def __init__(self, l_plot, status, error, l_slider,
                 index, indexX, indexY):
        self.index = index
        self.desig = [indexX, indexY]
        self.l_plot = l_plot
        self.l_slider = l_slider
        self.status = status
        self.error = error
        self.vb = gu.CustomViewBox()
        self.pw = self.l_plot.addPlot(row=self.index, col=0,
                                      viewBox=self.vb, title=f"p{index}")
        self.plt = self.pw.plot([])
        self.plt.setPen(None)
        self.labels = ["", ""]
        self.units = ["", ""]
        self.math_mode = 0
        self.math_texts = ["x", "y"]
        self.x = np.zeros(0)
        self.y = np.zeros(0)
        self.fx = None

        self.w_hline = QFrame()
        self.w_hline.setFrameShape(QFrame.HLine)
        self.w_hline.setFixedHeight(2)
        self.w_hline.setVisible(False)
        self.w_xslider = QRangeWidget(f"p{index} - x")
        self.w_xslider.setRange(0, 0)
        self.w_xslider.value_changed.connect(self._slider_event)
        self.w_xslider.setVisible(False)
        self.w_yslider = QRangeWidget(f"p{index} - y")
        self.w_yslider.setRange(0, 0)
        self.w_yslider.value_changed.connect(self._slider_event)
        self.w_yslider.setVisible(False)
        self.l_slider.addWidget(self.w_hline)
        self.l_slider.addWidget(self.w_xslider)
        self.l_slider.addWidget(self.w_yslider)

    def _slider_moved(self, newValue):
        """
        If slider has been moved, plot different data
        """
        self.update_plot()

    def _raise_error(self, error):
        self.error()
        self.status.setText(error)

    def _get_math(self, x, y):
        if 0 == self.math_mode:
            pass
            # no calculus to be done
        elif 1 == self.math_mode:
            x = delta(x)[0]
            y = delta(y)[1]
        elif 2 == self.math_mode:
            x = delta(x)[0]
            y = delta(y)[0]
        elif 3 == self.math_mode:
            xc = None
            yc = None
            try:
                def fx(xf,yf):
                    return eval(self.math_texts[0],
                                {"x":xf, "y":yf} | self.exposed_functions)
                xc = fx(x,y)
            except Exception as e:
                self._raise_error(
                    "error in math function (x): " + str(e))
            try:
                def fy(xf,yf):
                    return eval(self.math_texts[1],
                                {"x":xf, "y":yf} | self.exposed_functions)
                yc = fy(x,y)
            except Exception as e:
                self._raise_error(
                    "error in math function (y): " + str(e))
            if xc is not None and yc is not None:
                if len(xc) != len(yc):
                    self._raise_error(
                        "error in math results: arrays have different length")
                else:
                    x, y = xc, yc
        return x, y

    def _handle_multidim_and_sliders(self):
        self.md = False
        for slider, dshape in zip([self.w_xslider, self.w_yslider],
                                  [self.xdata.shape, self.ydata.shape]):
            slider.setVisible(False)
            if len(dshape) > 1 and all(np.array(dshape) > 1):
                self.md = True
                slider.setVisible(True)
                slider.setRange(0, dshape[1]-1)
            else:
                # reset hidden slider to zero to avoid intereference
                # with new data
                slider.setValue(0)

        if self.md is True:
            self.w_hline.setVisible(True)
            self._handle_multidim_data()
        else:
            self.w_hline.setVisible(False)
            self.x = self.xdata
            self.y = self.ydata

    def _handle_multidim_data(self):
        if self.md is True:
            self.x = self.xdata[:, self.w_xslider.value()]
            self.y = self.ydata[:, self.w_yslider.value()]

    def _slider_event(self, val):
        self._handle_multidim_data()
        self.plot(symbol="o")

    def remove_plot(self):
        self.l_plot.removeItem(self.l_plot.getItem(row=self.index, col=0))
        self.l_slider.removeWidget(self.w_hline)
        self.l_slider.removeWidget(self.w_xslider)
        self.l_slider.removeWidget(self.w_yslider)

    def set_designator(self, desig):
        self.desig = desig

    def set_labels(self, labels):
        self.labels = labels

    def set_units(self, units):
        self.units = units

    def set_math_mode(self, mode, math_texts):
        self.math_mode = mode
        self.math_texts = math_texts

    def set_data(self, x, y):
        self.xdata = x
        self.ydata = y
        self._handle_multidim_and_sliders()

    def plot(self, *args, **kwargs):
        x, y = self._get_math(self.x, self.y)
        self.pw.getAxis("left").textWidth = 0
        self.pw.setLabel("bottom", self.labels[0],
                         self.units[0])
        self.pw.setLabel("left", self.labels[1],
                         self.units[1])
        self.plt.setData(x=x, y=y, *args, **kwargs)


class SweepPreview(QMainWindow):
    """
    Data viewer for matrix files

    Arguments:
        filename -- name of matrix file (.maX)
    """

    def __init__(self, parent=None, filename=""):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        if filename == "":
            filename = QFileDialog.getOpenFileName(
                self, "Select ma file", "",
                "matrix files (*.ma7);;old matrix files (*.ma6)",)[0]
            if "" != filename:
                self.filename = filename
            else:
                # no file was provided, terminate
                sys.exit()
        else:
            self.filename = filename
        self.udthread = None
        self.lu_time = time.time()
        self.fetch_data()
        self.multidim = False
        self.error = False
        self.init_ui()

    def init_ui(self):
        """
        Initialize GUI for popup
        """
        grid = QGridLayout()

        w_close = QPushButton("close preview")
        w_close.clicked.connect(self.close)

        w_update = QPushButton("update plot")
        w_update.clicked.connect(lambda: self.conditional_fetch_data(True))

        w_save = QPushButton("save plot")
        w_save.clicked.connect(self.save_plot)

        self.w_delete = QPushButton("delete plot")
        self.w_delete.clicked.connect(self.remove_wplot)
        self.w_delete.setVisible(False)

        self.autoupdateBox = QCheckBox("auto update data")
        auinit = False
        self.autoupdateBox.setChecked(auinit)
        self.autoupdateBox.toggled.connect(self.updatethread)
        self.updatethread(auinit)

        self.posLabel = QLabel("x: 0.0e-0\ny: 0.0e-0")
        w_file = QLabel(self.filename)
        self.w_status = QLabel("")
        self.w_status.setStyleSheet("QLabel { color : red; }")

        self.setWindowTitle(os.path.basename(self.filename))

        self.comboBoxX = QComboBox()
        self.comboBoxY = QComboBox()
        self.comboBoxY.setEnabled(False)

        column_items = [f"{name}, {len(shape)}D data" for name, shape
                        in zip(self.names, self.shapes)]
        self.comboBoxX.addItems([""] + column_items)
        self.comboBoxY.addItems([""] + column_items)
        self.comboBoxX.currentIndexChanged.connect(self.index_changed)
        self.comboBoxY.currentIndexChanged.connect(self.index_changed)

        self.w_calc = QComboBox()
        self.w_calc.addItems(["None", "delta-", "delta+", "custom"])
        self.w_calc.currentIndexChanged.connect(self.calc_or_data_changed)
        self.w_lxmath = QLabel("lambda x : ")
        self.w_xmath = QLineEdit("x")
        self.w_xmath.setToolTip("You can use power,sqrt,exp,log,log10 and "
                                "numpy is defined as np.\nThe dimensions on "
                                "x and y need to be equal after any opeartion")
        self.w_xmath.returnPressed.connect(self.calc_or_data_changed)
        self.w_lymath = QLabel("lambda y : ")
        self.w_ymath = QLineEdit("y")
        self.w_ymath.setToolTip("You can use power,sqrt,exp,log,log10 and "
                                "numpy is defined as np.\nThe dimensions on "
                                "x and y need to be equal after any opeartion")
        self.w_ymath.returnPressed.connect(self.calc_or_data_changed)
        for widget in [self.w_lxmath, self.w_xmath,
                       self.w_ymath, self.w_lymath]:
            widget.setVisible(False)

        self.w_2dplot = QCheckBox("2d plotting")
        # self.w_2dplot.setVisible(False)
        # self.w_2dplot.toggled.connect(self.transpose_toggled)

        self.w_transpose = QCheckBox("transpose array")
        self.w_transpose.setVisible(False)
        self.w_transpose.toggled.connect(self.transpose_toggled)

        self.l_slider = QVBoxLayout()
        #self.l_slider.setMargins(0, 0, 0, 0)
        self.l_slider.setSpacing(0)
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        self.gl = pg.GraphicsLayoutWidget()
        self.plots = [PlotObject(self.gl, self.w_status,
                                 self.raise_error, self.l_slider,
                                 0, 0, 0), ]

        self.w_plots = QComboBox()
        self.w_plots.addItem("")
        self.w_plots.addItem("add plot")
        self.update_wplots(0)
        self.w_plots.currentIndexChanged.connect(self.update_wplots)

        self.plotlineBox = QCheckBox("show plot line")
        lineinit = False

        self.plotlineBox.setChecked(auinit)
        self.plotlineBox.toggled.connect(self.update_linesetting)
        self.update_linesetting(lineinit)

        self.proxy = pg.SignalProxy(self.gl.scene().sigMouseMoved,
                                    rateLimit=30,
                                    slot=self.mouse_moved)

        self.gl.setSizePolicy(QSizePolicy.Expanding,
                              QSizePolicy.Expanding)

        grid.addWidget(w_file, 19, 0, 1, -1)
        grid.addWidget(self.w_status, 20, 0, 1, -1)
        grid.addWidget(w_close, 0, 0)
        grid.addWidget(w_update, 4, 0)
        grid.addWidget(self.autoupdateBox, 5, 0)
        grid.addWidget(self.plotlineBox, 6, 0)
        grid.addWidget(self.comboBoxX, 1, 0)
        grid.addWidget(self.comboBoxY, 2, 0)
        grid.addWidget(self.w_calc, 3, 0)
        grid.addWidget(self.w_lxmath, 8, 0)
        grid.addWidget(self.w_xmath, 9, 0)
        grid.addWidget(self.w_lymath, 10, 0)
        grid.addWidget(self.w_ymath, 11, 0)
        grid.addWidget(self.w_plots, 12, 0, 1, 1)
        grid.addWidget(self.w_2dplot, 14, 0, 1, 1)
        grid.addWidget(self.w_transpose, 15, 0, 1, 1)
        grid.addWidget(self.w_delete, 13, 0, 1, 1)
        grid.addWidget(w_save, 0, 1, 1, 4)
        grid.addWidget(self.posLabel, 0, 5, 1, 1)
        grid.addWidget(self.gl, 1, 1, 16, 5)
        grid.addLayout(self.l_slider, 17, 1, 1, 5)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(16, 1)
        grid.setSizeConstraint(QLayout.SetNoConstraint)

        self.widget = QWidget()
        self.widget.setLayout(grid)
        self.setCentralWidget(self.widget)
        self.show()

    def index_changed(self, newIndex):
        """
        If index is changed, show the interface for new index
        """
        if self.comboBoxX == self.sender():
            if newIndex == 0:
                self.comboBoxY.setEnabled(False)
                self.comboBoxY.setCurrentIndex(0)
            else:
                self.comboBoxY.setEnabled(True)
        self.reload_data()

    def calc_or_data_changed(self):
        index = self.w_calc.currentIndex()
        current_plot = self.w_plots.currentIndex()
        if index == 3 and self.w_lxmath.isVisible() is False:
            for widget in [self.w_lxmath, self.w_xmath,
                           self.w_ymath, self.w_lymath]:
                widget.setVisible(True)
        elif index != 3 and self.w_lxmath.isVisible() is True:
            for widget in [self.w_lxmath, self.w_xmath,
                           self.w_ymath, self.w_lymath]:
                widget.setVisible(False)
        self.handle_error(0)

        self.plots[current_plot].set_math_mode(
            index, [self.w_xmath.text(), self.w_ymath.text()])
        self.plots[current_plot].plot(symbol="o")

    def transpose_toggled(self, check_state):
        """
        transpose has been toggled, reload data
        """
        self.reload_data()

    def raise_error(self):
        """
        raise the error flag
        """
        self.error = True

    def add_wplot(self):
        taken_indices = [plot.index for plot in self.plots]
        index = max(taken_indices) + 1
        self.plots.append(PlotObject(self.gl, self.w_status,
                                     self.raise_error, self.l_slider,
                                     index, 0, 0))
        self.w_plots.addItem("add plot")

    def remove_wplot(self):
        if len(self.plots) == 1:
            # only single plot present
            return
        index = self.w_plots.currentIndex()
        # pop plot container from list, remove widget and delete object
        plot = self.plots.pop(index)
        plot.remove_plot()
        del plot
        # change index to previous plot and remove the deleted one
        if index != 0:
            self.w_plots.setCurrentIndex(index-1)
        self.w_plots.removeItem(index)
        if self.w_plots.count() == 2:
            # nothing else to be deleted, hide button
            self.w_delete.setVisible(False)

    def update_wplot_label(self):
        for i, plot in enumerate(self.plots):
            name = f"p{plot.index} - {plot.labels[0]} vs {plot.labels[1]}"
            self.w_plots.setItemText(i, name)

    def update_wplots(self, index):
        cnt = self.w_plots.count()
        if index == cnt-1 and cnt > 1:
            self.add_wplot()
            cnt += 1
        if cnt > 2 and self.w_delete.isVisible() is False:
            # something can be deleted, make button visible
            self.w_delete.setVisible(True)

        # update the labels
        #self.update_wplot_label()

        # update widgets according to specifications in currently selected plot
        self.w_xmath.setText(self.plots[index].math_texts[0])
        self.w_ymath.setText(self.plots[index].math_texts[1])
        self.w_calc.setCurrentIndex(self.plots[index].math_mode)
        self.comboBoxX.setCurrentIndex(self.plots[index].desig[0])
        self.comboBoxY.setCurrentIndex(self.plots[index].desig[1])

    def conditional_fetch_data(self, force=False):
        if getsize(self.filename) > 300000 and time.time() - self.lu_time < 20:
            # skip updates if delta is below 20s and filesize is > 300kB
            # to avoid overloading the system with read queries
            updated = False
        elif self.lu_time < getmtime(self.filename) or force is True:
            # file has changed after last update,
            # reload the data into the file structure
            self.fetch_data()
            self.reload_data()

    def mouse_moved(self, ev):
        vb = self.plots[0].vb
        mousePoint = vb.mapSceneToView(ev[0])
        self.posLabel.setText("x: {:e}\ny: {:e}".format(mousePoint.x(),
                                                        mousePoint.y()))

    def save_plot(self):
        exporter = pg.exporters.ImageExporter(self.gl.scene())
        filename = QFileDialog.getSaveFileName(
            self, 'Select output png file', matr1x.usersfolder,
            "png files (*.png)")[0]
        if ".png" != filename[-4:].lower():
            filename += ".png"
        exporter.export(filename)
        # exporter.parameters()["height"] = 1200
        # exporter.parameters()["width"] = 1920

    def fetch_data(self):
        try:
            if ".h5." in self.filename:
                self.header, self.data = loadh5matrix(self.filename)
                self.names, self.units = self.header[:2]
            else:
                self.header, self.data = loadmatrix(
                    self.filename, structured=True)
                self.names, self.units = self.data.dtype.names, self.header[1]
        except Exception:
            # file could not be opened
            exc_type, exc_value, exc_traceback = sys.exc_info()
            a = QMessageBox.critical(
                self, f"Error when opening file",
                f"""
The following error was raised when opening the file:
{repr(exc_value)}
Please investigate the error and eventually restart matrix_preview""")
            sys.exit(-1)

        self.shapes = [self.data[col].shape for col in self.names]
        # update timer
        self.lu_time = time.time()

    def updatethread(self, state):
        if state is True:
            # start updatethread with 2s refresh time
            self.udthread = UpdateThread(2)
            self.udthread.update_now.connect(self.conditional_fetch_data)
            self.udthread.start()
        if state is False and self.udthread is not None:
            self.udthread.terminate()
            self.udthread = None

    def update_linesetting(self, state):
        if state is True:
            for plot in self.plots:
                plot.plt.setPen((0, 0, 153), width=3)
        if state is False:
            for plot in self.plots:
                plot.plt.setPen(None)

    def reload_data(self):
        if self.w_2dplot.isChecked() is True:
            self.reload_data_2d()
        else:
            ret = self.reload_data_curve()
            self.handle_error(ret)
        self.update_wplot_label()

    def handle_error(self, ret):
        if ret < 0:
            self.error = True
            if ret == -3:
                self.w_status.setText("no data selected")
            elif ret == -2:
                self.w_status.setText(
                    "data has too high dimension for 1d slicing")
            elif ret == -1:
                self.w_status.setText(
                    "data axis cannot be reshaped, lengths not multiples")
            elif ret == -4:
                self.w_status.setText(
                    "data shapes complicated, do not know what to do")
        elif self.error is True:
            self.error = False
            self.w_status.setText("")

    def reload_data_2d(self):
        pass

    def reload_data_curve(self):
        """
        Updates the data to match the index of the edits, stays in 1D curves
        """
        indexX = self.comboBoxX.currentIndex() - 1
        indexY = self.comboBoxY.currentIndex() - 1
        # disable transpose widget
        self.w_transpose.setVisible(False)
        if indexX == -1:
            # empty index selected
            return -3
        elif indexY == -1:
            # set up axis labels and units according to index
            # only have x data
            dim = len(self.shapes[indexX])
            if dim < 3:
                # 1D or 2D data can be plotted without second data set
                # against column index
                xname = self.names[indexX]
                if 2 == dim:
                    # 2D data can be transposed
                    self.w_transpose.setVisible(True)
                if self.w_transpose.isChecked() is True and 2 == dim:
                    x = np.arange(self.shapes[indexX][1])
                    y = self.data[xname].T
                else:
                    x = np.arange(self.shapes[indexX][0])
                    y = self.data[xname]
                xlabel = "array index"
                xunit = ""
                ylabel = xname
                yunit = self.units[indexX]
            else:
                return -2
        else:
            xname = self.names[indexX]
            yname = self.names[indexY]
            x = self.data[xname]
            y = self.data[yname]
            xlabel = xname
            ylabel = yname
            xunit = self.units[indexX]
            yunit = self.units[indexY]

        index = self.w_plots.currentIndex()
        self.plots[index].set_designator([indexX+1, indexY+1])
        self.plots[index].set_labels([xlabel, ylabel])
        self.plots[index].set_units([xunit, yunit])
        # data is loaded, now try to combine the data so that it becomes
        # plottable in a curve/scatter plot
        if not x.shape == y.shape:
            if len(x.shape) == 1 and len(y.shape) == 1:
                # one dimensional data but of uneven length
                # attempt to reshape
                small_axis = min(x.shape[0], y.shape[0])
                large_axis = max(x.shape[0], y.shape[0])
                if 0 == large_axis % small_axis:
                    # data can be reshaped
                    self.xdata = x.reshape(small_axis, -1)
                    self.ydata = y.reshape(small_axis, -1)
                else:
                    # data cannot be reshaped, abort
                    return -1
            elif x.shape[0] == y.shape[0]:
                # same length on first axis, reshape into sets of curves
                # with the length given by the identical axis.
                # This will flatten 3D arrays into something that can be
                # previewed as curve, although it does not make too
                # much sense.
                self.xdata = x.reshape(x.shape[0], -1)
                self.ydata = y.reshape(x.shape[0], -1)
            else:
                # data multidimensional but with different dimensions, so
                # we do not know how to handle this
                return -4
        else:
            # data identical with single or multiple dimension, no reshaping
            # required
            if len(x.shape) < 3:
                # data is has lower dimension than three
                if len(x.shape) == 2:
                    # identidcal 2D data on both axes,
                    # allow and handle transposition
                    self.w_transpose.setVisible(True)
                    if self.w_transpose.isChecked() is True:
                        x = x.T
                        y = y.T
                self.xdata = x
                self.ydata = y
            else:
                # data has too many dimensions to display, one can possibly
                # reshape for the first axis to match and flatten the data
                # to two dimensions, but this will be horrible for the meaning
                # of 3D data. I see no use case in implementing this
                return -2

        # update the plotted data
        self.update_plot()
        return 0

    def update_plot(self):
        """
        Updates the plot to show sweep[index] against its range
        """
        # update labels on plot
        index = self.w_plots.currentIndex()
        self.plots[index].set_data(self.xdata, self.ydata)
        self.calc_or_data_changed()


def main():
    app = QApplication(sys.argv)
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
