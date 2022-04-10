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
from PyQt5.QtWidgets import (QApplication, QMainWindow, QCheckBox, QComboBox, QWidget, QSizePolicy, QLayout,
                             QFileDialog, QHBoxLayout, QGridLayout, QLabel, QPushButton,
                             QToolButton, QSlider, QGroupBox)


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
        self.slider.setRange(0,0)
        self.slider.setValue(0)
        self.inc = QToolButton()
        self.inc.setArrowType(Qt.RightArrow)
        self.dec = QToolButton()
        self.dec.setArrowType(Qt.LeftArrow)
        grid.addWidget(self.label)
        grid.addWidget(self.dec)
        grid.addWidget(self.slider, stretch=1)
        grid.addWidget(self.inc)
        grid.setContentsMargins(0,0,0,0)
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
    def __init__(self, layout, index, indexX, indexY):
        self.index = index
        self.desig = [indexX, indexY]
        self.layout = layout
        self.vb = gu.CustomViewBox()
        self.pw = self.layout.addPlot(row=self.index, col=0, viewBox=self.vb)
        self.plt = self.pw.plot([])
        self.plt.setPen(None)
        self.labels = ["", ""]
        self.units = ["", ""]

    def remove_plot(self):
        self.layout.removeItem(self.layout.getItem(row=self.index, col=0))

    def set_designator(self, desig):
        self.desig = desig

    def set_labels(self, labels):
        self.labels = labels

    def set_units(self, units):
        self.units = units

    def plot(self, *args, **kwargs):
        self.pw.getAxis("left").textWidth = 0
        self.pw.setLabel("bottom", self.labels[0],
                         self.units[0])
        self.pw.setLabel("left", self.labels[1],
                         self.units[1])
        self.plt.setData(*args, **kwargs)


class SweepPreview(QMainWindow):
    """
    Data viewer for matrix files

    Arguments:
        filename -- name of matrix file (.maX)
    """

    def __init__(self, parent=None, filename=""):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.filename = filename
        self.udthread = None
        self.lu_time = time.time()
        self.fetch_data()
        self.init_ui()

    def init_ui(self):
        """
        Initialize GUI for popup
        """
        grid = QGridLayout()

        w_close = QPushButton("close preview")
        w_close.clicked.connect(self.close)

        w_update = QPushButton("update plot")
        w_update.clicked.connect(lambda : self.conditional_fetch_data(True))

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

        self.comboBoxCalc = QComboBox()
        self.comboBoxCalc.addItems(["None", "Delta-", "Delta+"])
        self.dMode = 0

        self.w_2dplot = QCheckBox("2d plotting")
        #self.w_2dplot.setVisible(False)
        #self.w_2dplot.toggled.connect(self.transpose_toggled)

        self.w_transpose = QCheckBox("transpose array")
        self.w_transpose.setVisible(False)
        self.w_transpose.toggled.connect(self.transpose_toggled)

        self.xslider = QRangeWidget("x data")
        self.xslider.setRange(0, 0)
        self.xslider.value_changed.connect(self.slider_moved)
        self.xslider.setVisible(False)
        self.yslider = QRangeWidget("y data")
        self.yslider.setRange(0, 0)
        self.yslider.value_changed.connect(self.slider_moved)
        self.yslider.setVisible(False)

        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        self.gl = pg.GraphicsLayoutWidget()
        self.plots = [PlotObject(self.gl, 0, 0, 0),]

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

        grid.addWidget(w_file, 14, 0, 1, -1)
        grid.addWidget(self.w_status, 15, 0, 1, -1)
        grid.addWidget(w_close, 0, 0)
        grid.addWidget(w_update, 4, 0)
        grid.addWidget(self.autoupdateBox, 5, 0)
        grid.addWidget(self.plotlineBox, 6, 0)
        grid.addWidget(self.comboBoxX, 1, 0)
        grid.addWidget(self.comboBoxY, 2, 0)
        grid.addWidget(self.comboBoxCalc, 3, 0)
        grid.addWidget(self.w_plots, 7, 0, 1, 1)
        grid.addWidget(self.w_2dplot, 9, 0, 1, 1)
        grid.addWidget(self.w_transpose, 10, 0, 1, 1)
        grid.addWidget(self.w_delete, 8, 0, 1, 1)
        grid.addWidget(w_save, 0, 1, 1, 4)
        grid.addWidget(self.posLabel, 0, 5, 1, 1)
        grid.addWidget(self.gl, 1, 1, 11, 5)
        grid.addWidget(self.xslider, 12, 1, 1, 5)
        grid.addWidget(self.yslider, 13, 1, 1, 5)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(11, 1)
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

    def slider_moved(self, newValue):
        """
        If slider has been moved, plot different data
        """
        self.update_plot()

    def transpose_toggled(self, check_state):
        """
        transpose has been toggled, reload data
        """
        self.reload_data()

    def plot_2nd_toggled(self, check_state):
        if check_state is True:
            index = 1
            if len(self.plots) < 2:
                self.plots.append(PlotObject(self.gl, index, 0, 0))
        else:
            index = 0
        self.comboBoxX.setCurrentIndex(self.plots[index].desig[0])
        self.comboBoxY.setCurrentIndex(self.plots[index].desig[1])

    def add_wplot(self):
        taken_indices = [plot.index for plot in self.plots]
        index = max(taken_indices) + 1
        self.plots.append(PlotObject(self.gl, index, 0, 0))
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

    def update_wplots(self, index):
        cnt = self.w_plots.count()
        if index == cnt-1 and cnt > 1:
            self.add_wplot()
            cnt += 1
        if cnt > 2 and self.w_delete.isVisible() is False:
            # something can be deleted, make button visible
            self.w_delete.setVisible(True)
        for i, plot in enumerate(self.plots):
            name = f"p{i} - {plot.labels[0]} vs {plot.labels[1]}"
            self.w_plots.setItemText(i, name)
        self.comboBoxX.setCurrentIndex(self.plots[index].desig[0])
        self.comboBoxY.setCurrentIndex(self.plots[index].desig[1])


    def conditional_fetch_data(self, force=False):
        if getsize(self.filename) > 300000 and time.time() - self.lu_time < 20:
            # skip updates if delta is below 20s and filesize is > 300kB
            # to avoid overloading the system with read queries
            updated = False
        elif self.lu_time < getmtime(self.filename) or force is True:
			# file has changed after last update, reload
            self.fetch_data()
            updated = True
        if (self.dMode != self.comboBoxCalc.currentIndex() or
                updated is True):
            # reload the data into the file structure
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
        if ".h5." in self.filename:
            self.header, self.data = loadh5matrix(self.filename)
            self.names, self.units = self.header[:2]
        else:
            self.header, self.data = loadmatrix(
                self.filename, structured=True)
            self.names, self.units = self.data.dtype.names, self.header[1]
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

    def handle_error(self, ret):
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
        else:
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

        # initialize slider ranges and visibility if reuqired
        self.multidim = False
        self.xslider.setVisible(False)
        self.yslider.setVisible(False)
        if len(self.xdata.shape) > 1 and all(np.array(self.xdata.shape) > 1):
            self.multidim = True
            self.xslider.setVisible(True)
            self.xslider.setRange(0, self.xdata.shape[1]-1)
            self.xslider.setValue(0)
        if len(self.ydata.shape) > 1 and all(np.array(self.ydata.shape) > 1):
            self.multidim = True
            self.yslider.setVisible(True)
            self.yslider.setRange(0, self.ydata.shape[1]-1)
            self.yslider.setValue(0)

        # update the plotted data
        self.update_plot()

    def update_plot(self):
        """
        Updates the plot to show sweep[index] against its range
        """
        self.dMode = self.comboBoxCalc.currentIndex()
        if self.multidim is True:
            x = self.xdata[:, self.xslider.value()]
            y = self.ydata[:, self.yslider.value()]
        else:
            x = self.xdata
            y = self.ydata
        if 0 == self.dMode:
            # no calculus to be done
            pass
        elif 1 == self.dMode:
            x = delta(x)[0]
            y = delta(y)[1]
        elif 2 == self.dMode:
            x = delta(x)[0]
            y = delta(y)[0]
        """
        # if 3pt delta is wished for...
        elif 3 == self.dMode:
            self.xdata = delta3p(x)[0]
            self.ydata = delta3p(y)[1]
        elif 4 == self.dMode:
            self.xdata = delta3p(x)[0]
            self.ydata = delta3p(y)[0]
        """
        # update labels on plot
        index = self.w_plots.currentIndex()
        self.plots[index].plot(x=x, y=y, symbol="o")
        self.update_wplots(index)


def main():
    if len(sys.argv) < 2:
        print("no filename provided, exiting")
        sys.exit(0, )
    app = QApplication(sys.argv)
    # we need to ignore this signal here otherwise we are kicked into
    # background when matrix returns. see run_as_fg_process
    if 'SIGTTOU' in dir(signal):  # signal only on POSIX compliant systems
        signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    with QtGracefulKiller():
        ex = SweepPreview(None, sys.argv[1])
        ex.show()
        ret = app.exec()
    sys.exit(ret)
