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
                             QFrame, QGridLayout, QGroupBox, QHBoxLayout,
                             QLabel, QLayout, QLineEdit, QMainWindow,
                             QMessageBox, QPushButton, QSizePolicy, QSlider,
                             QToolButton, QVBoxLayout, QWidget)


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

    def set_base_title(self, title):
        self.base_title = title

    def set_value(self, val):
        self.slider.setValue(val)
        self._updateText()

    def value(self):
        return self.slider.value()

    def set_range(self, minimum, maximum):
        self.slider.setRange(minimum, maximum)
        self._updateText()

    def maximum(self):
        return self.slider.maximum()


class SimplePlotWidget(QGroupBox):
    """
    plot widget that contains the simple part of the plotting functions
    """

    def __init__(self, cb_error, cb_index, parent=None):
        super().__init__("", parent)
        self.cb_error = cb_error
        self.cb_index = cb_index
        # 2d flag
        self.plot2d = False

        grid = QGridLayout()

        w_save = QPushButton("save plot")
        w_save.clicked.connect(self.save_plot)

        self.posLabel = QLabel("x: 0.0e-0\ny: 0.0e-0")
        self.posLabel.setMinimumWidth(100)

        self.w_delete = QPushButton("delete plot")
        self.w_delete.clicked.connect(self.remove_plot)
        self.w_delete.setVisible(False)

        self.l_slider = QVBoxLayout()
        #self.l_slider.setMargins(0, 0, 0, 0)
        self.l_slider.setSpacing(0)

        self.w_calc = QComboBox()
        self.w_calc.addItems(["None", "delta-", "delta+", "custom"])
        self.w_calc.currentIndexChanged.connect(self.calc_or_data_changed)

        self.w_math = [QLineEdit("y"), QLineEdit("x")]
        self.w_lmath = [QLabel("lambda y : "),
                        QLabel("lambda x : ")]

        for i in range(2):
            self.w_math[i].returnPressed.connect(self.calc_or_data_changed)
            self.w_math[i].setToolTip(
                "You can use power,sqrt,exp,log,log10 and "
                "numpy is defined as np.\nThe dimensions on "
                "y and x need to be equal after any operation")

        for widget in self.w_math + self.w_lmath:
            widget.setVisible(False)

        self.gl = pg.GraphicsLayoutWidget()
        self.plots = [PlotObject(self.gl, self.cb_error, self.l_slider,
                                 False, 0, [0, 0, 0]), ]

        self.w_plots = QComboBox()
        self.w_plots.addItem("")
        self.w_plots.addItem("add plot")
        self.update_wplots(0)
        self.w_plots.currentIndexChanged.connect(self.update_wplots)

        lineinit = False
        self.plotlineBox = QCheckBox("show plot line")
        self.plotlineBox.setChecked(lineinit)
        self.update_linesetting(lineinit)
        self.plotlineBox.toggled.connect(self.update_linesetting)

        self.proxy = pg.SignalProxy(self.gl.scene().sigMouseMoved,
                                    rateLimit=30,
                                    slot=self.mouse_moved)

        self.gl.setSizePolicy(QSizePolicy.Expanding,
                              QSizePolicy.Expanding)

        grid.addWidget(self.w_calc, 4, 0)
        for i in range(2):
            grid.addWidget(self.w_lmath[i], 4, 2*i+1)
            grid.addWidget(self.w_math[i], 4, 2*i+2)
        grid.addWidget(self.plotlineBox, 3, 5)
        grid.addWidget(self.w_delete, 0, 4, 1, 1)
        grid.addWidget(self.posLabel, 0, 5, 1, 1)
        grid.addLayout(self.l_slider, 2, 0, 2, 5)
        grid.addWidget(self.gl, 1, 0, 1, 6)
        grid.addWidget(self.w_plots, 0, 0, 1, 4)
        grid.addWidget(w_save, 2, 5, 1, 1)

        grid.setColumnStretch(0, 1)
        grid.setRowStretch(1, 1)
        grid.setSizeConstraint(QLayout.SetNoConstraint)
        grid.setContentsMargins(0, 0, 0, 0)

        self.setLayout(grid)

    def add_plot(self):
        taken_indices = [plot.index for plot in self.plots]
        index = max(taken_indices) + 1
        self.plots.append(PlotObject(self.gl, self.cb_error,
                                     self.l_slider,
                                     False,
                                     index, [0, 0, 0]))
        self.w_plots.addItem("add plot")

    def remove_plot(self):
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
            self.add_plot()
            cnt += 1
        if cnt > 2 and self.w_delete.isVisible() is False:
            # something can be deleted, make button visible
            self.w_delete.setVisible(True)

        self.w_calc.setVisible(not self.plots[index].plot2d)

        # update widgets according to specifications in currently selected plot
        self.w_calc.setCurrentIndex(self.plots[index].math_mode)
        for i in range(2):
            self.w_math[i].setText(self.plots[index].math_texts[i])
        self.cb_index(self.plots[index])

    def toggle_plot2d(self, flag):
        self.plot2d = flag
        for widget in self.w_math + self.w_lmath:
            widget.setVisible(not flag)
        self.w_calc.setVisible(not flag)

    def calc_or_data_changed(self):
        index = self.w_calc.currentIndex()
        current_plot = self.w_plots.currentIndex()
        if index == 3 and self.w_math[0].isVisible() is False:
            for widget in self.w_math + self.w_lmath:
                widget.setVisible(True)
        elif index != 3 and self.w_math[0].isVisible() is True:
            for widget in self.w_math + self.w_lmath:
                widget.setVisible(False)
        # update the labels of the plot combo box
        for i, plot in enumerate(self.plots):
            name = f"p{plot.index} - {plot.labels[0]} vs {plot.labels[1]}"
            self.w_plots.setItemText(i, name)
        # reset error
        self.cb_error("")

        self.plots[current_plot].set_math_mode(
            index, [math.text() for math in self.w_math])
        self.plots[current_plot].plot(symbol="o")

    def mouse_moved(self, ev):
        vb = self.plots[0].vb
        mousePoint = vb.mapSceneToView(ev[0])
        self.posLabel.setText("x: {:.5e}\ny: {:.5e}".format(mousePoint.x(),
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

    def update_linesetting(self, state):
        if state is True:
            for plot in self.plots:
                plot.plt.setPen((0, 0, 153), width=3)
        if state is False:
            for plot in self.plots:
                plot.plt.setPen(None)

    def plot2d_changed(self, index, new_state):
        plotindex = self.plots[index].index
        self.plots[index].remove_plot()
        plt = self.plots.pop(index)
        del plt
        self.plots.insert(index, PlotObject(self.gl, self.cb_error,
                                            self.l_slider, new_state, plotindex, [0, 0, 0]))
        # reset flag
        if any([plot.plot2d for plot in self.plots]) is True:
            self.toggle_plot2d(True)
        else:
            self.toggle_plot2d(False)

    def plot(self, z, x, y=None, plot2d=False):
        index = self.w_plots.currentIndex()
        if self.plots[index].plot2d != plot2d:
            self.plot2d_changed(index, plot2d)
        cplot = self.plots[index]
        if y is not None:
            cplot.set_data(z, x, y)
        else:
            cplot.set_data(z, x)
        self.calc_or_data_changed()


class PlotObject():
    """
    object that contains the plot and remembers what is plotted
    """
    exposed_functions = {"np": np, "sqrt": np.sqrt, "e": np.e, "pi": np.pi,
                         "power": np.power, "log": np.log, "log10": np.log10,
                         "exp": np.exp}

    def __init__(self, l_plot, error, l_slider, plot2d,
                 index, desig):
        self.index = index
        self.desig = desig
        self.l_plot = l_plot
        self.l_slider = l_slider
        self.plot2d = plot2d
        self.error = error
        self.vb = gu.CustomViewBox()
        if self.plot2d is True:
            self.plt = pg.ImageView(view=self.vb)  # , title=f"p{index}")
            self.pw = self.l_plot.addPlot(row=self.index, col=0,
                                          viewBox=self.vb)
        else:
            self.pw = self.l_plot.addPlot(row=self.index, col=0,
                                          viewBox=self.vb, title=f"p{index}")
            self.plt = self.pw.plot([])
            self.plt.setPen(None)
        self.labels = ["", "", ""]
        self.units = ["", "", ""]
        self.math_mode = 0
        self.math_texts = ["y", "x"]
        self.z = np.zeros(0)
        self.x = np.zeros(0)
        self.y = np.zeros(0)
        self.fx = None

        self.w_hline = QFrame()
        self.w_hline.setFrameShape(QFrame.HLine)
        self.w_hline.setFixedHeight(2)
        self.w_hline.setVisible(False)
        if plot2d is True:
            self.w_zslider = QRangeWidget(f"p{index} - z")
        else:
            self.w_zslider = QRangeWidget(f"p{index} - y")
        self.w_zslider.set_range(0, 19)
        self.w_zslider.value_changed.connect(self._slider_event)
        self.w_zslider.setVisible(False)
        self.w_xslider = QRangeWidget(f"p{index} - x")
        self.w_xslider.set_range(0, 0)
        self.w_xslider.value_changed.connect(self._slider_event)
        self.w_xslider.setVisible(False)
        self.l_slider.addWidget(self.w_hline)
        self.l_slider.addWidget(self.w_zslider)
        self.l_slider.addWidget(self.w_xslider)

    def _raise_error(self, error):
        self.error(error)

    def _get_math(self, y, x):
        if 0 == self.math_mode:
            pass
            # no calculus to be done
        elif 1 == self.math_mode:
            x = delta(x)[0]
            y = delta(y)[0]
        elif 2 == self.math_mode:
            x = delta(x)[0]
            y = delta(y)[0]
        elif 3 == self.math_mode:
            xc = None
            yc = None
            try:
                def fx(xf):
                    return eval(self.math_texts[0],
                                {"x": xf} | self.exposed_functions)
                xc = fx(x)
            except Exception as e:
                self._raise_error(
                    "error in math function (x): " + str(e))

            try:
                def fy(yf):
                    return eval(self.math_texts[1],
                                {"y": yf} | self.exposed_functions)
                yc = fy(y)
            except Exception as e:
                self._raise_error(
                    "error in math function (y): " + str(e))

            if yc is not None and xc is not None:
                if len(yc) != len(xc):
                    self._raise_error(
                        "error in math results: arrays have different length")
                else:
                    y, x = yc, xc
        return y, x

    def _handle_multidim_and_sliders(self):
        self.md = False
        for slider, dshape in zip([self.w_zslider, self.w_xslider],
                                  [self.zdata.shape, self.xdata.shape]):
            slider.setVisible(False)
            if len(dshape) > 2:
                self.md = True
                slider.setVisible(True)
                slider.set_range(0, dshape[2]-1)
            elif (len(dshape) > 1 and all(np.array(dshape) > 1) and
                  self.plot2d is False):
                self.md = True
                slider.setVisible(True)
                slider.set_range(0, dshape[1]-1)
            else:
                # reset hidden slider to zero to avoid intereference
                # with new data
                slider.set_value(0)

        if self.md is True:
            self.w_hline.setVisible(True)
            self._handle_multidim_data()
        else:
            self.w_hline.setVisible(False)
            self.x = self.xdata
            self.z = self.zdata

    def _handle_multidim_data(self):
        if self.md is True and self.plot2d is False:
            self.x = self.xdata[:, self.w_xslider.value()]
            self.z = self.zdata[:, self.w_zslider.value()]
        elif self.md is True and self.plot2d is True:
            self.x = self.xdata
            self.z = self.zdata

    def _slider_event(self, val):
        if self.plot2d is True:
            self.plt.setCurrentIndex(val)
        else:
            self._handle_multidim_data()
            self.plot(symbol="o")

    def remove_plot(self):
        self.l_plot.removeItem(self.l_plot.getItem(row=self.index, col=0))
        self.l_slider.removeWidget(self.w_hline)
        self.l_slider.removeWidget(self.w_xslider)
        self.l_slider.removeWidget(self.w_zslider)

    def parse_data(self, z, x, y=None):
        self.zdata = z["data"]
        self.xdata = x["data"]
        if y is not None:
            self.ydata = y["data"]
            data_sets = [x, y, z]
            self.labels = [dat["label"] for dat in data_sets]
            self.desig = [dat["desig"] for dat in data_sets]
            self.units = [dat["unit"] for dat in data_sets]
        else:
            data_sets = [z, x]
            self.labels[:2] = [dat["label"] for dat in data_sets]
            self.desig[:2] = [dat["desig"] for dat in data_sets]
            self.units[:2] = [dat["unit"] for dat in data_sets]

    def set_math_mode(self, index, math_texts):
        self.math_mode = index
        self.math_texts = math_texts

    def set_data(self, z, x, y=None):
        self.parse_data(z, x, y)
        self._handle_multidim_and_sliders()

    def plot(self, *args, **kwargs):
        if self.plot2d is True:
            x0, x1 = self.x.min(), self.x.max()
            xscale = (x1-x0)/self.z.shape[0]
            if len(self.y) > 0:
                y0, y1 = self.y.min(), self.y.max()
                yscale = (y1-y0)/self.z.shape[1]
                pos = [x0, y0]
                scale = [xscale, yscale]
            else:
                pos = [x0, 0]
                scale = [xscale, 1]
            if len(self.z.shape) > 2:
                self.plt.setImage(self.z, pos=pos, scale=scale,
                                  axes={"t": 2, "x": 0, "y": 1})
            else:
                self.plt.setImage(self.z, pos=pos, scale=scale)
            self.pw.getAxis("left").textWidth = 0
            self.pw.setLabel("bottom", self.labels[0],
                             self.units[0])
            self.pw.setLabel("left", self.labels[1],
                             self.units[1])
            self.vb.setAspectLocked(False)
            self.vb.invertY(False)
        else:
            z, x = self._get_math(self.z, self.x)
            self.pw.getAxis("left").textWidth = 0
            self.pw.setLabel("bottom", self.labels[0],
                             self.units[0])
            self.pw.setLabel("left", self.labels[1],
                             self.units[1])
            self.plt.setData(x=x, y=z, *args, **kwargs)


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

        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')

        # w_close = QPushButton("close preview")
        # w_close.clicked.connect(self.close)

        w_update = QPushButton("update plot")
        w_update.clicked.connect(lambda: self.conditional_fetch_data(True))

        self.autoupdateBox = QCheckBox("auto update data")
        auinit = False
        self.autoupdateBox.setChecked(auinit)
        self.autoupdateBox.toggled.connect(self.updatethread)
        self.updatethread(auinit)

        w_file = QLabel(self.filename)
        self.w_status = QLabel("")
        self.w_status.setStyleSheet("QLabel { color : red; }")

        self.setWindowTitle(os.path.basename(self.filename))

        self.w_l = [QLabel("y"), QLabel("x"), QLabel("y")]
        self.w_l[2].setVisible(False)

        self.w_index = [QComboBox(), QComboBox(), QComboBox()]
        self.w_index[1].setEnabled(False)
        self.w_index[2].setVisible(False)

        column_items = [f"{name}, {len(shape)}D data" for name, shape
                        in zip(self.names, self.shapes)]

        for i in range(3):
            self.w_index[i].addItems([""] + column_items)
            self.w_index[i].currentIndexChanged.connect(self.index_changed)

        self.w_plot2d = QCheckBox("2d plotting")
        self.w_plot2d.toggled.connect(self.plotting_toggled)

        self.spw = SimplePlotWidget(self.raise_error, self.index_callback)
        self.iv = None

        self.w_plot2d_comp = QCheckBox("2d complex")
        self.w_plot2d_comp.toggled.connect(self.plotting_complex)
        self.w_plot2d_comp.setVisible(False)

        self.w_transpose = QCheckBox("transpose array")
        self.w_transpose.setVisible(False)
        self.w_transpose.toggled.connect(self.transpose_toggled)

        grid.addWidget(w_file, 5, 0, 1, -1)
        grid.addWidget(self.w_status, 6, 0, 1, -1)
        grid.addWidget(self.w_plot2d, 1, 3, 1, 1)
        # grid.addWidget(w_close, 0, 0)
        grid.addWidget(w_update, 0, 2)
        grid.addWidget(self.autoupdateBox, 0, 3)
        for i in range(3):
            grid.addWidget(self.w_l[i], i, 0)
            grid.addWidget(self.w_index[i], i, 1)
        grid.addWidget(self.w_plot2d_comp, 2, 3, 1, 1)
        grid.addWidget(self.w_transpose, 1, 2, 1, 1)
        grid.addWidget(self.spw, 3, 0, 1, 4)

        # set rescaling behavior
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(3, 1)
        grid.setSizeConstraint(QLayout.SetNoConstraint)

        self.widget = QWidget()
        self.widget.setLayout(grid)
        self.setCentralWidget(self.widget)
        self.show()

    def index_changed(self, newIndex):
        """
        If index is changed, show the interface for new index
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
        self.reload_data()

    def plotting_complex(self, check_state):
        if check_state is True:
            self.spw.setVisible(False)
            if self.iv is None:
                # set up image view on first initialization
                self.iv = pg.ImageView()
                self.widget.layout().addWidget(self.iv, 3, 0, 1, 4)
            else:
                self.iv.setVisible(True)
        elif check_state is False and self.iv is not None:
            self.iv.setVisible(False)
            self.spw.setVisible(True)
        # reload data and set widget labels
        self.plotting_toggled(check_state or self.w_plot2d.isChecked())

    def raise_error(self, error):
        """
        raise the error flag
        """
        self.w_status.setText(error)
        self.error = True

    def index_callback(self, plot_object):
        self.w_plot2d.blockSignals(True)
        self.w_plot2d.setChecked(plot_object.plot2d)
        self.w_plot2d.blockSignals(False)
        for i in range(3):
            self.w_index[i].setCurrentIndex(plot_object.desig[i])

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

    def plotting_toggled(self, check_state):
        self.w_l[0].setText("z" if check_state is True else "y")
        self.w_l[2].setVisible(check_state)
        self.w_index[2].setVisible(check_state)
        self.w_plot2d_comp.setVisible(check_state)
        self.reload_data()

    def reload_data(self):
        if (self.w_plot2d.isChecked() is True or
                self.w_plot2d_comp.isChecked() is True):
            ret = self.reload_data_2d()
        else:
            ret = self.reload_data_curve()
        self.handle_error(ret)

    def handle_error(self, ret):
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
        elif self.error is True:
            self.error = False
            self.w_status.setText("")

    def reload_data_2d(self):
        indexZ, indexX, indexY = [
            self.w_index[i].currentIndex() - 1 for i in range(3)]
        x = {}
        y = {}
        z = {}
        if indexZ == -1:
            # empty index selected
            return -3
        for index, dat in zip([indexZ, indexX, indexY], [z, x, y]):
            if index == -1:
                dat["data"] = False
                continue
            else:
                dim = len(self.shapes[index])
                name = self.names[index]
                dat["label"] = name
                dat["desig"] = index+1
                dat["unit"] = self.units[index]
                dat["data"] = self.data[name]
                dat["dim"] = dim
            if dim > 3 or dim < 2:
                # <1D or >3D data cannot be 2d plotted.
                return -5

        # data in a 2d plot can always be transposed
        self.w_transpose.setVisible(True)

        # data is loaded, now try to combine the data so that it becomes
        # plottable in a 2d plot
        if self.w_transpose.isChecked() is True:
            if z["dim"] == 3:
                z["data"] = z["data"].transpose(1, 0, 2)
            else:
                z["data"] = z["data"].T
        z["shape"] = z["data"].shape
        if x["data"] is False and y["data"] is False:
            # no x and y data available
            x = dict(label="array index", unit="", dim=1,
                     data=np.arange(z["shape"][0]), desig=0,
                     shape=(z["shape"][0],))
            y = dict(label="array index", unit="", dim=1,
                     data=np.arange(z["shape"][1]), desig=0,
                     shape=(z["shape"][1],))
        elif x["data"] is False:
            x = dict(label="array index", unit="", dim=1,
                     data=np.arange(z["shape"][0]), desig=0,
                     shape=(z["shape"][0],))
        elif y["data"] is False:
            y = dict(label="array index", unit="", dim=1,
                     data=np.arange(z["shape"][1]), desig=0,
                     shape=(z["shape"][1],))
        else:
            pass

        if self.w_plot2d_comp.isChecked() is True:
            if z["dim"] > 2:
                self.iv.setImage(z["data"],
                                 axes={"t": 2, "x": 0, "y": 1})
                self.iv.getView().invertY(False)
            else:
                self.iv.setImage(z["data"], axes={"x": 0, "y": 1})
                self.iv.getView().invertY(False)

        else:
            if y["data"] is False:
                self.spw.plot(z, x,
                              plot2d=self.w_plot2d.isChecked())
            else:
                self.spw.plot(z, x, y,
                              plot2d=self.w_plot2d.isChecked())
        return 0

    def reload_data_curve(self):
        """
        Updates the data to match the index of the edits, stays in 1D curves
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
            # only have x data
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
            yname = self.names[indexY]
            y["label"] = yname
            y["desig"] = indexY+1
            y["unit"] = self.units[indexY]
            y["data"] = self.data[yname]
            y["shape"] = y["data"].shape
            y["dim"] = len(y["shape"])
            xname = self.names[indexX]
            x["label"] = xname
            x["desig"] = indexX+1
            x["unit"] = self.units[indexX]
            x["data"] = self.data[xname]
            x["shape"] = x["data"].shape
            x["dim"] = len(x["shape"])

        # data is loaded, now try to combine the data so that it becomes
        # plottable in a curve/scatter plot
        if not x["shape"] == y["shape"]:
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
                # This will flatten 3D arrays into something that can be
                # previewed as curve, although it does not make too
                # much sense.
                x["data"] = x["data"].reshape(x["shape"][0], -1)
                y["data"] = y["data"].reshape(x["shape"][0], -1)
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
