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
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                             QFileDialog, QGridLayout, QLabel, QPushButton,
                             QSlider)


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


class SweepPreview(QDialog):
    """
    Data viewer for matrix files

    Arguments:
        filename -- name of matrix file (.maX)
    """

    def __init__(self, parent=None, filename=""):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.filename = filename
        if ".h5" in filename:
            self.h5 = True
            self.header, self.data = loadh5matrix(self.filename)
        else:
            self.h5 = False
            self.header, self.data = loadmatrix(self.filename,
                                                structured=True)
        self.names, self.units = self.header[:2]
        self.udthread = None
        self.lu_time = time.time()
        self.init_ui()

    def init_ui(self):
        """
        Initialize GUI for popup
        """
        grid = QGridLayout()

        closeButton = QPushButton("Close preview")
        closeButton.clicked.connect(self.close)

        updateButton = QPushButton("Update plot")
        updateButton.clicked.connect(self.refresh_lists)

        saveButton = QPushButton("Save plot")
        saveButton.clicked.connect(self.save_plot)

        self.autoupdateBox = QCheckBox("Auto update data")
        auinit = False
        self.autoupdateBox.setChecked(auinit)
        self.autoupdateBox.toggled.connect(self.updatethread)
        self.updatethread(auinit)

        self.posLabel = QLabel("x: 0.0e-0\ny: 0.0e-0")
        fileLabel = QLabel(self.filename)
        self.setWindowTitle(os.path.basename(self.filename))

        self.comboBoxX = QComboBox()
        self.comboBoxY = QComboBox()
        self.comboBoxCalc = QComboBox()

        self.comboBoxCalc.addItems(["None", "Delta-", "Delta+"])
        self.dMode = 0

        self.comboBoxX.addItems(self.names)
        self.comboBoxY.addItems(self.names)
        self.comboBoxX.currentIndexChanged.connect(self.index_changed)
        self.comboBoxY.currentIndexChanged.connect(self.index_changed)

        self.xslabel = QLabel("x-axis - index")
        self.yslabel = QLabel("y-axis - index")
        self.xslider = QSlider(Qt.Horizontal)
        self.xslider.setRange(0, 0)
        self.xslider.valueChanged.connect(self.slider_moved)
        self.xslider.setEnabled(False)
        self.yslider = QSlider(Qt.Horizontal)
        self.yslider.setRange(0, 0)
        self.yslider.valueChanged.connect(self.slider_moved)
        self.yslider.setEnabled(False)

        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        self.vb = gu.CustomViewBox()
        self.pw = pg.PlotWidget(
            viewBox=self.vb, name="Plot1", enableMenu=False)
        self.plt = self.pw.plot()
        self.refresh_lists()

        self.plotlineBox = QCheckBox("show plot line")
        lineinit = False
        self.plt.setPen(None)
        self.plotlineBox.setChecked(auinit)
        self.plotlineBox.toggled.connect(self.update_linesetting)
        self.update_linesetting(lineinit)

        self.proxy = pg.SignalProxy(self.pw.scene().sigMouseMoved,
                                    rateLimit=30,
                                    slot=self.mouse_moved)

        grid.addWidget(fileLabel, 12, 0, 1, -1)
        grid.addWidget(closeButton, 0, 0)
        grid.addWidget(updateButton, 4, 0)
        grid.addWidget(self.autoupdateBox, 5, 0)
        grid.addWidget(self.plotlineBox, 6, 0)
        grid.addWidget(self.comboBoxX, 1, 0)
        grid.addWidget(self.comboBoxY, 2, 0)
        grid.addWidget(self.comboBoxCalc, 3, 0)
        grid.addWidget(self.xslabel, 7, 0, 1, 1)
        grid.addWidget(self.xslider, 8, 0, 1, 1)
        grid.addWidget(self.yslabel, 9, 0, 1, 1)
        grid.addWidget(self.yslider, 10, 0, 1, 1)
        grid.addWidget(saveButton, 0, 1, 1, 4)
        grid.addWidget(self.posLabel, 0, 5, 1, 1)
        grid.addWidget(self.pw, 1, 1, 11, 5)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(11, 1)

        self.setLayout(grid)
        self.show()

    def index_changed(self, newIndex):
        """
        If index is changed, show the interface for new index
        """
        self.reload_data()

    def slider_moved(self, newValue):
        """
        If slider has been moved, plot different data
        """
        self.update_plot()

    def refresh_lists(self):
        updated = self.open_file_and_update_data()
        if (self.dMode != self.comboBoxCalc.currentIndex() or
                updated is True):
            self.update_plot()

    def mouse_moved(self, ev):
        mousePoint = self.vb.mapSceneToView(ev[0])
        self.posLabel.setText("x: {:e}\ny: {:e}".format(mousePoint.x(),
                                                        mousePoint.y()))

    def save_plot(self):
        exporter = pg.exporters.ImageExporter(self.vb.scene())
        filename = QFileDialog.getSaveFileName(
            self, 'Select output png file', matr1x.usersfolder,
            "png files (*.png)")[0]
        if ".png" != filename[-4:].lower():
            filename += ".png"
        exporter.export(filename)
        # exporter.parameters()["height"] = 1200
        # exporter.parameters()["width"] = 1920

    def open_file_and_update_data(self):
        if getsize(self.filename) > 300000 and time.time() - self.lu_time < 20:
            # skip updates if delta is below 10s and filesize is > 300kB
            # this will depend on the system!
            return False
        if self.lu_time < getmtime(self.filename):
            if self.h5 is True:
                self.header, self.data = loadh5matrix(self.filename)
            else:
                self.header, self.data = loadmatrix(
                    self.filename, structured=True)
            self.names, self.units = self.header[:2]
            self.lu_time = time.time()
            return True

    def updatethread(self, state):
        if state is True:
            # start updatethread with 2s refresh time
            self.udthread = UpdateThread(2)
            self.udthread.update_now.connect(self.refresh_lists)
            self.udthread.start()
        if state is False and self.udthread is not None:
            self.udthread.terminate()
            self.udthread = None

    def update_linesetting(self, state):
        if state is True:
            self.plt.setPen((0, 0, 153), width=3)
        if state is False:
            self.plt.setPen(None)

    def reload_data(self):
        """
        Updates the data to match the index of the edits, stays in 1D curves
        """
        indexX = self.comboBoxX.currentIndex()
        indexY = self.comboBoxY.currentIndex()
        if self.h5 is True:
            xname = self.names[indexX]
            yname = self.names[indexY]
        else:
            # get name from data, as genfromtxt sanitizes the array names
            names = self.data.dtype.names
            xname = names[indexX]
            yname = names[indexY]
        x = self.data[xname]
        y = self.data[yname]
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
                    self.xdata = []
                    self.ydata = []
                    return
            elif x.shape[0] == y.shape[0]:
                # same length on first axis, reshape into sets of curves
                # with the length given by the identical axis
                self.xdata = x.reshape(x.shape[0], -1)
                self.ydata = y.reshape(x.shape[0], -1)
            else:
                # data multidimensional but with different dimensions, so
                # we do not know how to handle this
                self.xdata = []
                self.ydata = []
                return
        else:
            # data identical with single or multiple dimension, no reshaping
            # required
            if len(xshape) < 2 or len(yshape) < 2:
                # data is only two dimensional
                self.xdata = x
                self.ydata = y
            else:
                # data has too many dimensions to display, one can possibly
                # reshape for the first axis to match and flatten the data
                # to two dimensions, but this will be horrible for the meaning
                # of 3D data. I see no use case in implementing this
                self.xdata = []
                self.ydata = []
                return
        self.multidim = False
        if len(self.xdata.shape) > 1:
            self.multidim = True
            self.xslider.setRange(0, self.xdata.shape[1]-1)
            self.xslider.setValue(0)
        if len(self.ydata.shape) > 1:
            self.multidim = True
            self.yslider.setRange(0, self.ydata.shape[1]-1)
            self.yslider.setValue(0)
        self.pw.setLabel("bottom", self.names[indexX],
                         self.units[indexX])
        self.pw.setLabel("left", self.names[indexY],
                         self.units[indexY])
        self.update_plot()

    def update_plot(self):
        """
        Updates the plot to show sweep[index] against its range
        """
        self.dMode = self.comboBoxCalc.currentIndex()
        if self.multidim is True:
            self.xslider.setEnabled(True)
            self.yslider.setEnabled(True)
            x = self.xdata[:, self.xslider.value()]
            y = self.ydata[:, self.yslider.value()]
        else:
            self.xslider.setEnabled(False)
            self.yslider.setEnabled(False)
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
        self.pw.getAxis("left").textWidth = 0
        self.plt.setData(y=y, x=x, symbol="o")


def main():
    if len(sys.argv) < 2:
        print("no filename provided, exiting")
        sys.exit(0)
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
