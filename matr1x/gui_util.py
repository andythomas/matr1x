# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
"""
This module contains gui related functions that are required by the sweep
generator and matrix_gui
"""
import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QObject, Qt, pyqtSignal, QPoint
from PyQt5.QtWidgets import (QGroupBox, QHBoxLayout, QGridLayout, QPushButton,
                         QLabel, QLineEdit, QVBoxLayout, QComboBox, QFrame,
                         QSlider, QToolButton, QCheckBox, QSizePolicy, QLayout,
                         QFileDialog, 
                        )

from .eval import delta


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
    class PlotObject():
        """
        object that contains the plot and remembers what is plotted
        """
        exposed_functions = {"np": np, "sqrt": np.sqrt, "e": np.e,
                             "pi": np.pi, "power": np.power,
                             "log": np.log, "log10": np.log10,
                             "exp": np.exp}

        def __init__(self, l_plot, error, l_slider, plot2d,
                     index, desig, pen=None):
            self.index = index
            self.desig = desig
            self.l_plot = l_plot
            self.l_slider = l_slider
            self.plot2d = plot2d
            self.error = error
            self.vb = CustomViewBox()
            if self.plot2d is True:
                self.plt = pg.ImageItem(view=self.vb)
                # self.plt = pg.PColorMeshItem()  # not yet supported
                # self.bar = pg.ColorBarItem()
                self.vb.addItem(self.plt)
                self.pw = self.l_plot.addPlot(row=self.index, col=0,
                                              viewBox=self.vb,
                                              title=f"p{index}")
                # self.l_plot.addItem(self.bar, row=self.index, col=1)
            else:
                self.pw = self.l_plot.addPlot(row=self.index, col=0,
                                              viewBox=self.vb,
                                              title=f"p{index}")
                self.plt = self.pw.plot([])
                if pen is True:
                    self.plt.setPen((0, 0, 153), width=3)
                else:
                    self.plt.setPen(None)
            self.labels = ["", "", ""]
            self.units = ["", "", ""]
            self.math_mode = 0
            self.math_texts = ["y", "x"]
            self.z = np.zeros(0)
            self.x = np.zeros(0)
            self.y = np.zeros(0)
            self.fx = None
            self.fy = None

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
                y = delta(y)[1]
            elif 2 == self.math_mode:
                x = delta(x)[0]
                y = delta(y)[0]
            elif 3 == self.math_mode:
                xc = None
                yc = None
                try:
                    def fx(xf, yf):
                        return eval(self.math_texts[1],
                                    ({"x": xf, "y": yf} |
                                     self.exposed_functions))
                    xc = fx(x, y)
                except Exception as e:
                    self._raise_error(
                        "error in math function (x): " + str(e))

                try:
                    def fy(yf, xf):
                        return eval(self.math_texts[0],
                                    ({"y": yf, "x": xf} |
                                     self.exposed_functions))
                    yc = fy(y, x)
                except Exception as e:
                    self._raise_error(
                        "error in math function (y): " + str(e))

                if yc is not None and xc is not None:
                    if len(yc) != len(xc):
                        self._raise_error(
                            "error in math: arrays have different length")
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
                    slider.set_range(0, dshape[0]-1)
                elif ((len(dshape) > 1 and dshape[1] > 1) and
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
            else:
                self.w_hline.setVisible(False)
            self._handle_multidim_data()

        def _handle_multidim_data(self):
            if self.md is True and self.plot2d is False:
                self.x = self.xdata[:, self.w_xslider.value()]
                self.z = self.zdata[:, self.w_zslider.value()]
            elif self.md is False and self.plot2d is False:
                self.x = self.xdata
                self.z = self.zdata
            elif self.plot2d is True:
                self.x = self.xdata
                self.y = self.ydata
                self.z = self.zdata

        def _slider_event(self, val):
            if self.plot2d is True:
                self.plt.setCurrentIndex(val)
                self.pw.setTitle(f"p{self.index} - {self.x[val]} "
                                 f"{self.units[0]}")
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
                data_sets = [z, x, y]
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
                if len(self.zdata.shape) > 2:
                    # 3d plotting
                    self.plt.setImage(self.z, pos=[0,0], scale=[1,1],
                                      xvals=self.x,
                                      axes={"t": 0, "x": 1, "y": 2})
                    # set labels to array index, same as on the y-axis
                    self.pw.setLabel("bottom", self.labels[1],
                                     self.units[1])
                else:
                    x0, x1 = self.x[0], self.x[-1]
                    xscale = (x1-x0)/self.z.shape[0]
                    y0, y1 = self.y[0], self.y[-1]
                    yscale = (y1-y0)/self.z.shape[1]
                    pos = [x0, y0]
                    scale = [xscale, yscale]
                    self.plt.setImage(self.z, pos=pos, scale=scale)
                    # self.plt.setData(self.z)  # for pcolormesh
                    self.pw.setLabel("bottom", self.labels[1],
                                     self.units[1])
                    # self.bar.setImageItem(self.plt)  # support colorbar
                self.pw.getAxis("left").textWidth = 0
                self.pw.setLabel("left", self.labels[2],
                                 self.units[2])
                self.vb.setAspectLocked(False)
                self.vb.invertY(False)
            else:
                z, x = self._get_math(self.z, self.x)
                self.pw.getAxis("left").textWidth = 0
                self.pw.setLabel("bottom", self.labels[1],
                                 self.units[1])
                self.pw.setLabel("left", self.labels[0],
                                 self.units[0])
                self.plt.setData(x=x, y=z, *args, **kwargs)

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

        l_math = QHBoxLayout()
        for i in range(2):
            l_math.addWidget(self.w_lmath[i])
            l_math.addWidget(self.w_math[i])

        self.gl = pg.GraphicsLayoutWidget()
        self.plots = [self.PlotObject(self.gl, self.cb_error, self.l_slider,
                                      False, 0, [0, 0, 0]), ]

        self.w_plots = QComboBox()
        self.w_plots.addItem("")
        self.w_plots.addItem("add plot")
        self.update_wplots(0)
        self.w_plots.currentIndexChanged.connect(self.update_wplots)

        lineinit = False
        self.w_line = QCheckBox("show lines")
        self.w_line.setChecked(lineinit)
        self.update_linesetting(lineinit)
        self.w_line.toggled.connect(self.update_linesetting)

        self.proxy = pg.SignalProxy(self.gl.scene().sigMouseMoved,
                                    rateLimit=30,
                                    slot=self.mouse_moved)

        self.gl.setSizePolicy(QSizePolicy.Expanding,
                              QSizePolicy.Expanding)

        grid.addWidget(self.w_calc, 1, 0, 1, 2)
        grid.addWidget(w_save, 1, 3, 1, 1)
        grid.addLayout(l_math, 2, 0, 1, -1)
        grid.addWidget(self.w_line, 1, 2)
        grid.addWidget(self.w_delete, 0, 2, 1, 1)
        grid.addWidget(self.posLabel, 0, 3, 1, 1)
        grid.addLayout(self.l_slider, 4, 0, 1, -1)
        grid.addWidget(self.gl, 3, 0, 1, -1)
        grid.addWidget(self.w_plots, 0, 0, 1, 2)

        grid.setColumnStretch(0, 1)
        grid.setRowStretch(3, 1)
        grid.setSizeConstraint(QLayout.SetNoConstraint)
        grid.setContentsMargins(0, 0, 0, 0)

        self.setLayout(grid)

    def add_plot(self):
        taken_indices = [plot.index for plot in self.plots]
        index = max(taken_indices) + 1
        self.plots.append(self.PlotObject(self.gl, self.cb_error, self.l_slider,
                                          False, index, [0, 0, 0],
                                          pen=self.w_line.isChecked()))
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
            # last index leads to plot being added
            self.add_plot()
            cnt += 1
        if cnt > 2 and self.w_delete.isVisible() is False:
            # something can be deleted, make button visible
            self.w_delete.setVisible(True)

        self.w_calc.setVisible(not self.plots[index].plot2d)

        # update widgets according to specifications in currently selected plot
        for i in range(2):
            self.w_math[i].setText(self.plots[index].math_texts[i])
        self.w_calc.setCurrentIndex(self.plots[index].math_mode)

        # pass current inde to callback function
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
            if plot.plot2d is True:
                name = (f"p{plot.index} - {plot.labels[0]} vs {plot.labels[1]} "
                        f"and {plot.labels[2]}")
            else:
                name = (f"p{plot.index} - {plot.labels[0]} vs {plot.labels[1]}")
            self.w_plots.setItemText(i, name)
        # reset error
        self.cb_error("")

        self.plots[current_plot].set_math_mode(
            index, [math.text() for math in self.w_math])
        self.plots[current_plot].plot(symbol="o")

    def mouse_moved(self, ev):
        boxes = [plot.vb for plot in self.plots]
        vb_mouse = None
        for vb in boxes:
            # get coordinate transform for top left of viewbox
            pos = vb.mapRectFromView(vb.borderRect.rect()).topLeft()
            if vb.boundingRect().contains(ev[0]+pos):
                vb_mouse = vb
                # stop once we have found the correct view
                continue
        if vb_mouse is not None:
            mousePoint = vb_mouse.mapSceneToView(ev[0])
            self.posLabel.setText(
                "x: {:.5e}\ny: {:.5e}".format(mousePoint.x(),
                                              mousePoint.y()))

    def save_plot(self):
        exporter = pg.exporters.ImageExporter(self.gl.scene())
        filename = QFileDialog.getSaveFileName(
            self, 'Select output png file', matr1x.usersfolder,
            "png files (*.png)")[0]
        if ".png" != filename[-4:].lower():
            filename += ".png"
        exporter.export(filename)

    def update_linesetting(self, state):
        if state is True:
            for plot in self.plots:
                if plot.plot2d is False:
                    plot.plt.setPen((0, 0, 153), width=3)
        if state is False:
            for plot in self.plots:
                if plot.plot2d is False:
                    plot.plt.setPen(None)

    def plot2d_changed(self, index, new_state):
        plotindex = self.plots[index].index
        self.plots[index].remove_plot()
        plt = self.plots.pop(index)
        del plt
        self.plots.insert(index, self.PlotObject(self.gl, self.cb_error,
                                                 self.l_slider, new_state,
                                                 plotindex, [0, 0, 0],
                                                 pen=self.w_line.isChecked()))
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
        cplot.set_data(z, x, y)
        self.calc_or_data_changed()


class CustomViewBox(pg.ViewBox):
    """
    Reimplements the pyqthgraph ViewBox and improves its usability with the
    mouse.
    Behavior is as follows:

      right click autoscales graph
      ---
      mouse inside plot:
      left drag zooms to rectangle
      right drag allows panning plot
      mouse wheel zooms in/out with cursor position defining center
      ---
      mouse on x or y axis:
      left button drags corresponding axis
      right button allows panning individual axis
      mouse wheel zooms in/out with cursor position deifning center
    """

    def __init__(self, *args, **kwds):
        pg.ViewBox.__init__(self, *args, **kwds)
        self.setMouseMode(self.RectMode)

    # reimplement right-click to autoscale plot
    def mouseClickEvent(self, ev):
        if ev.button() == Qt.RightButton:
            self.autoRange()
            # set autorange upon change of data
            self.enableAutoRange()
        # elif ev.button() == Qt.MidButton:
        #     self.raiseContextMenu(ev)

    # reimplement drag event
    def mouseDragEvent(self, ev, axis=None):
        if ev.button() in (Qt.RightButton, Qt.MidButton):
            # enable pan mode
            self.setMouseMode(self.PanMode)
            pg.ViewBox.mouseDragEvent(self, ev, axis)
            self.setMouseMode(self.RectMode)
        elif ev.button() == Qt.LeftButton and axis is not None:
            # enable pan mode on individual axis
            self.setMouseMode(self.PanMode)
            pg.ViewBox.mouseDragEvent(self, ev, axis)
            self.setMouseMode(self.RectMode)
        else:
            pg.ViewBox.mouseDragEvent(self, ev, axis)


class EmittingStream(QObject):
    """
    Stream to communicate between the threads
    """
    name = "GUIStream"
    text_written = pyqtSignal(str)

    def write(self, text):
        self.text_written.emit(str(text))

    def flush(self):
        pass
