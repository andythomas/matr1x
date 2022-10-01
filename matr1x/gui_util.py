# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
"""
This module contains gui related functions that are required by the sweep
generator and matrix_gui
"""
import numpy as np
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout,
                             QGroupBox, QHBoxLayout, QLabel, QLayout, QLineEdit,
                             QPushButton, QSizePolicy, QSlider, QToolButton,
                             QVBoxLayout)
import pyqtgraph as pg
from .eval import delta


class QRangeWidget(QGroupBox):
    """
    Widget that displays a range slider with a decrement/increment slider
    on either side and a label on the left.

    Parameters
    ---------
    title: base name that is displayed on the left together with current
      value of slider and the number of increments
    parent: parent widget or None
    """
    value_changed = pyqtSignal(int)

    def __init__(self, title, parent=None):
        super().__init__("", parent)
        self.setMinimumHeight(30)
        self.setFixedHeight(30)
        self.base_title = title
        grid = QHBoxLayout()
        self.label = QLabel(title)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.setValue(0)
        self.inc = QToolButton()
        self.inc.setArrowType(Qt.ArrowType.RightArrow)
        self.dec = QToolButton()
        self.dec.setArrowType(Qt.ArrowType.LeftArrow)
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

    def _update_text(self):
        self.label.setText(
            f"{self.base_title} - {self.value()} ({self.maximum()+1})")

    def _value_changed(self, val):
        self._update_text()
        self.value_changed.emit(val)

    def set_base_title(self, title):
        """
        Resets the base title to a new value

        Parameters
        ----------
        title: str
          New base title
        """
        self.base_title = title

    def set_value(self, val):
        """
        Set current value of slider

        Parameters
        ----------
        val: int
          new value of slider, out of range values are ignored
        """
        self.slider.setValue(val)
        self._update_text()

    def value(self):

        return self.slider.value()

    def set_range(self, minimum, maximum):
        """
        Parameters
        ----------
        minimum: int
          Minimum value of slider
        maximum: int
          Maximum value of slider
        """
        self.slider.setRange(minimum, maximum)
        self._update_text()

    def minimum(self):
        """
        Returns minimum value of slider
        """
        return self.slider.minimum()

    def maximum(self):
        """
        Returns maximum value of slider
        """
        return self.slider.maximum()


class SimplePlotWidget(QGroupBox):
    """
    Plot widget that allows multiple curve or 2d plots to be vertically
    stacked and simultaneously displayed.

    Parameters
    ----------
    cb_error: function
      callback function that takes a single string as paramter, the
      string will describe the present error
      If called with an empty string, it should elear the error.
    cb_index: function
      callback function that takes a PlotObject as parameters.
      The function is called with the currently selected PlotObject if the
      latter changes.
    """
    class PlotObject():
        """
        Object that contains the plot, data corresponding identifiers and
        widgets. Relies on external layouts to insert the widgets/plots.

        Parameters
        ----------
        l_plot: pyqtgraph.GraphicsLayoutWidget
          layout into which the plot is to be inserted
        error: function
          callback function that takes a single string as paramter, the
          string will describe the present error
        l_slider: QVBoxLayout
          layout into which the sliders are added using l_slider.addWidget
        plot2d: bool
          flag that defines whether plot is curve or 2d plot
        index: int
          index of the plot in the pyqtgraph.GraphicsLayoutWidget
        desig: [int, int, int]
          designator that stores an integer that connects the plotted values
          to some external gui elements. Essentially a simple storage.
        pen: bool or None
          If True, lines will be displayed
        """
        # exposed functions that can be used by the custom math eval
        # expression stored in math_texts.
        exposed_functions = {"np": np, "sqrt": np.sqrt, "e": np.e,
                             "pi": np.pi, "power": np.power, "log10": np.log10,
                             "cos": np.cos, "sin": np.sin, "tan": np.tan,
                             "arccos": np.arccos, "arcsin": np.arcsin,
                             "arctan": np.arctan, "log": np.log, "exp": np.exp,
                             }

        # default math operations can be added here if required
        # the key should correspond to the value of math_mode for this to
        # be selected, has to provide a pair of fucntions for the x and y
        # value, respectively
        default_math = {
            "no math": [lambda xf: xf, lambda yf: yf],
            "delta-": [lambda xf: delta(xf)[0],
                       lambda yf: delta(yf)[1]],
            "delta+": [lambda xf: delta(xf)[0],
                       lambda yf: delta(yf)[0]]}

        def __init__(self, l_plot, error, l_slider, plot2d,
                     index, desig, pen=None):
            self.index = index
            self.desig = desig
            self.l_plot = l_plot
            self.l_slider = l_slider
            self.plot2d = plot2d
            self.error = error

            # initialize the pyqtgraph display widgets
            self.vb = CustomViewBox()
            if self.plot2d is True:
                self.plt = pg.ImageView(view=self.vb)
                # self.plt = pg.PColorMeshItem()  # could be used instead
                # self.vb.addItem(self.plt)
                self.pw = self.l_plot.addPlot(row=self.index, col=0,
                                              viewBox=self.vb,
                                              title=f"p{index}")
                # possibly add colorbar to the right of the ImageItem
                # self.bar = pg.ColorBarItem()  # enables a color bar
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

            # initialize storage variables
            self.labels = ["", "", ""]
            self.units = ["", "", ""]
            self.math_mode = "no math"
            self.math_texts = ["y", "x"]
            self.z = np.zeros(0)
            self.x = np.zeros(0)
            self.y = np.zeros(0)
            self.fx = None
            self.fy = None

            # initialize slider widget and horizontal spacer line
            # and add to l_slider
            self.w_hline = QFrame()
            self.w_hline.setFrameShape(QFrame.Shape.HLine)
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
            """
            Function to handle errors

            Parameters
            ----------
            error : str
              describing the error
            """
            self.error(error)

        def _get_math(self, y, x):
            """
            Applies the math operation to the two data arrays, depending on
            value stored in self.math_mode. See default_math for the
            default functions that are implemented.
            Currently can be one of the following:
                any key of self.default_math - applies the
                  functions defined there.
                "custom" - custom math that can be specified via a
                  string stored in self.math_texts that is passed to
                  evaluated by eval(string). Available parameters are defined
                  in self.exposed_functions
                neither of the two above - no math is applied

            Parameters
            ----------
            y: numpy array
              data to be processed
            x: numpy array
              data to be processed

            Returns
            -------
            y: numpy array
              processed data
            x: numpy array
              processed data
            """
            if self.math_mode in self.default_math.keys():
                # some of our default math is supposed to be used
                x = self.default_math[self.math_mode][0](x)
                y = self.default_math[self.math_mode][1](y)
            elif "custom" == self.math_mode:
                # none of the above, so we are in custom mode
                xc = None
                yc = None
                try:
                    # define function based on the string stored in
                    # math_texts[1]
                    def fx(xf, yf):
                        return eval(self.math_texts[1],
                                    ({"x": xf, "y": yf} |
                                     self.exposed_functions))
                    xc = fx(x, y)
                except Exception as e:
                    self._raise_error(
                        "error in math function (x): " + str(e))

                try:
                    # define function based on the string stored in
                    # math_texts[0]
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
                    elif len(yc.shape) > 1 and all(np.array(yc.shape) > 1):
                        self._raise_error(
                            "error in math: y array has too high dimension")
                    elif len(xc.shape) > 1 and all(np.array(xc.shape) > 1):
                        self._raise_error(
                            "error in math: y array has too high dimension")
                    else:
                        y, x = yc, xc
            return y, x

        def _handle_multidim_and_sliders(self):
            """
            Handles slider visibility according to data dimensions
            """
            self.md = False
            for slider, dshape in zip([self.w_zslider, self.w_xslider],
                                      [self.zdata.shape, self.xdata.shape]):
                slider.setVisible(False)
                if len(dshape) > 2:
                    # data is 3D, so show sliders
                    self.md = True
                    slider.setVisible(True)
                    slider.set_range(0, dshape[0]-1)
                elif ((len(dshape) > 1 and dshape[1] > 1) and
                      self.plot2d is False):
                    # array is 2d and second dimension is longer than 1
                    self.md = True
                    slider.setVisible(True)
                    slider.set_range(0, dshape[1]-1)
                else:
                    # reset hidden slider to zero to avoid intereference
                    # with new data
                    slider.set_value(0)

            # hide or show the horizontal spacers
            if self.md is True:
                self.w_hline.setVisible(True)
            else:
                self.w_hline.setVisible(False)
            # sliders are handled, now worry about data
            self._handle_multidim_data()

        def _handle_multidim_data(self):
            """
            Handles data redimensioning and selection according to slider
            position
            """
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
            """
            Handles slider events and updates the displayed data accordingly

            Parameters
            ----------
            val: int
              current value of the slider that is to be applied
            """
            if self.plot2d is True:
                # for 2d plot, select index of current data element
                self._handle_multidim_data()
                self.plt.setCurrentIndex(val)
                self.pw.setTitle(f"p{self.index} - {self.x[val]} "
                                 f"{self.units[0]}")
            else:
                # for curve, handle the data and replot
                self._handle_multidim_data()
                self.plot(symbol="o")

        def remove_plot(self):
            """
            Removes the plot and the widgets that belong to the PlotObject
            from the provided layouts
            """
            self.l_plot.removeItem(self.l_plot.getItem(row=self.index, col=0))
            self.l_slider.removeWidget(self.w_hline)
            self.l_slider.removeWidget(self.w_xslider)
            self.l_slider.removeWidget(self.w_zslider)

        def parse_data(self, z, x, y):
            """
            Parses the data dictionaries into the corresponding
            class variables

            Used keys are "data", "label", "desig" and "unit"
            """
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
            """
            Sets the math mode and texts

            Parameters
            ----------
            index: int
              selects the math operation to be applied, see self.default_math.
            math_texts: [str, str]
              contains two strings that are evaluated by eval(string). Are
              only allowed to contain functions/variables that are defined
              in self.exposed_functions.
            """
            self.math_mode = index
            self.math_texts = math_texts

        def set_data(self, z, x, y=None):
            """
            Updates the data that is stored in the present plot.

            Used keys are "data", "label", "desig" and "unit"

            Parameters
            ----------
            z: dict
              z data dictionary.
            x: dict
              x data dictionary.
            y: dict or None
              y data dictionary.
            """
            self.parse_data(z, x, y)
            self._handle_multidim_and_sliders()

        def plot(self, *args, **kwargs):
            """
            function that handles the actual plotting of the data and takes
            care of updating the labels

            Parameters
            ----------
            *args, **kwargs: args or kwargs
              are passed to the plot function if curve plotting is enabled
            """
            if self.plot2d is True:
                if len(self.zdata.shape) > 2:
                    # 3d plotting
                    self.plt.setImage(self.z, pos=[0, 0], scale=[1, 1],
                                      xvals=self.x,
                                      axes={"t": 0, "x": 1, "y": 2})
                    # set labels to array index, same as on the y-axis
                    self.pw.setLabel("bottom", self.labels[2],
                                     self.units[2])
                else:
                    # 2d data follows different dimensioning scheme
                    x0, x1 = self.x[0], self.x[-1]
                    xscale = (x1-x0)/self.z.shape[0]
                    y0, y1 = self.y[0], self.y[-1]
                    yscale = (y1-y0)/self.z.shape[1]
                    pos = [x0, y0]
                    scale = [xscale, yscale]
                    self.plt.setImage(self.z, pos=pos, scale=scale)
                    # pcolormesh would support x/y/z data
                    # self.plt.setData(self.z)  # for pcolormesh
                    # self.bar.setImageItem(self.plt)  # support colorbar
                    self.pw.setLabel("bottom", self.labels[1],
                                     self.units[1])
                self.pw.getAxis("left").textWidth = 0
                self.pw.setLabel("left", self.labels[2],
                                 self.units[2])
                # remove aspect lock for free zooming and do not invert y axis
                self.vb.setAspectLocked(False)
                self.vb.invertY(False)
            else:
                # for curves apply math, set labels and data
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
        self.plot2d = False

        grid = QGridLayout()

        self.w_pos = QLabel("x: 0.00000e-0\ny: 0.00000e-0")
        self.w_pos.setMinimumWidth(140)

        self.w_delete = QPushButton("delete")
        self.w_delete.clicked.connect(self._remove_plot)
        self.w_delete.setVisible(False)

        self.l_slider = QVBoxLayout()
        self.l_slider.setSpacing(0)

        # initialize w_calc combo box with the default math items defined
        # in the PlotObject, add "custom" for custom math.
        self.w_calc = QComboBox()
        self.w_calc.setToolTip("math operation")
        self.w_calc.addItems(list(self.PlotObject.default_math.keys()) +
                             ["custom"])
        self.w_calc.currentIndexChanged.connect(self._calc_or_data_changed)

        self.w_math = [QLineEdit("y"), QLineEdit("x")]
        self.w_lmath = [QLabel("lambda y : "), QLabel("lambda x : ")]

        for i in range(2):
            self.w_math[i].editingFinished.connect(self._calc_or_data_changed)
            self.w_math[i].setToolTip(
                "You can use power, sqrt, exp, log, log10, cos, sin, tan and "
                "their inverse functions, pi and e.\n"
                "For more complex math, numpy is additionally defined as np.\n"
                "The dimensions on y and x need to be equal after any "
                "operation and have to remain in a single dimension.")

        # hide custom math layouts by default
        for widget in self.w_math + self.w_lmath:
            widget.setVisible(False)

        # put custom math in separate layout to make them scale independetly
        l_math = QHBoxLayout()
        for i in range(2):
            l_math.addWidget(self.w_lmath[i])
            l_math.addWidget(self.w_math[i], stretch=1)

        # Add GraphicsLayout and make most prominent widget
        self.gl = pg.GraphicsLayoutWidget()
        self.gl.setSizePolicy(QSizePolicy.Policy.Expanding,
                              QSizePolicy.Policy.Expanding)

        # have proxy that connects the position of the mouse on the
        # GraphicsLayout to display the x/y position on the current
        # plot
        self.proxy = pg.SignalProxy(self.gl.scene().sigMouseMoved,
                                    rateLimit=30,
                                    slot=self._mouse_moved)

        # add the first empty plot with
        self.plots = [self.PlotObject(self.gl, self.cb_error, self.l_slider,
                                      False, 0, [0, 0, 0]), ]

        self.w_plots = QComboBox()
        self.w_plots.addItem("p0 -  vs")
        self.w_plots.addItem("add plot")
        self.w_plots.currentIndexChanged.connect(self._update_wplots)

        # line_init controls default value of line visibility on startup
        line_init = False
        self.w_line = QCheckBox("lines")
        self.w_line.setChecked(line_init)
        self._update_linesetting(line_init)
        self.w_line.toggled.connect(self._update_linesetting)

        grid.addWidget(self.w_plots, 0, 0, 1, 2)
        grid.addWidget(self.w_delete, 0, 2, 1, 1)
        grid.addWidget(self.w_line, 0, 3)
        grid.addWidget(self.w_calc, 0, 4, 1, 1)
        grid.addWidget(self.w_pos, 0, 5)
        grid.addLayout(l_math, 1, 0, 1, -1)
        grid.addLayout(self.l_slider, 4, 0, 1, -1)
        grid.addWidget(self.gl, 3, 0, 1, -1)

        grid.setColumnStretch(0, 1)
        grid.setRowStretch(3, 1)
        grid.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        grid.setContentsMargins(0, 0, 0, 0)

        self.setLayout(grid)

    def _add_plot(self):
        """
        Adds a plot (via PlotObject) to the current display. Ensures that
        the new plot is always appended to the end.
        """
        index = max([plot.index for plot in self.plots]) + 1
        self.plots.append(self.PlotObject(self.gl, self.cb_error, self.l_slider,
                                          False, index, [0, 0, 0],
                                          pen=self.w_line.isChecked()))
        self.w_plots.setItemText(len(self.plots)-1, f"p{index} -  vs ")
        self.w_plots.addItem("add plot")

    def _remove_plot(self):
        """
        remove plot that is currently selected in self.w_plots
        """
        if len(self.plots) == 1:
            # only single plot present
            return
        index = self.w_plots.currentIndex()
        # pop plot container from list, remove widget and delete object
        # for garbage collection
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

    def _update_wplots(self, index):
        """
        Updates the currently selected plot upon a change of self.w_plots
        """
        cnt = self.w_plots.count()
        if index == cnt-1 and cnt > 1:
            # selecting last index (add plot) leads to plot being added
            self._add_plot()
            cnt += 1
        if cnt > 2 and self.w_delete.isVisible() is False:
            # something can be deleted, make button visible
            self.w_delete.setVisible(True)

        # if currently selected plot is not 2d plot, show math
        self.w_calc.setVisible(not self.plots[index].plot2d)

        # update widgets according to specifications in currently selected plot
        for i in range(2):
            self.w_math[i].setText(self.plots[index].math_texts[i])

        # load math_mode from PlotObject and set index
        index_math = self.w_calc.findText(self.plots[index].math_mode)
        if index_math != -1:
            # for -1, item not found in combo box texts
            self.w_calc.setCurrentIndex(index_math)

        # pass current PlotObject to callback function to be handled externally
        self.cb_index(self.plots[index])

    def _toggle_plot2d(self, flag):
        """
        toggles the plot2d flag and handles visibility of math widgets

        Parameters
        ----------
        flag: bool
          flag that controls whether plot2d is False or True
        """
        self.plot2d = flag
        for widget in self.w_math + self.w_lmath:
            widget.setVisible(not flag)
        self.w_calc.setVisible(not flag)

    def _calc_or_data_changed(self):
        """
        Applies new data, math and labels and updates the plot
        """
        math_mode = self.w_calc.currentText()
        current_plot = self.w_plots.currentIndex()
        if math_mode == "custom" and self.w_math[0].isVisible() is False:
            for widget in self.w_math + self.w_lmath:
                widget.setVisible(True)
        elif math_mode != "custom" and self.w_math[0].isVisible() is True:
            for widget in self.w_math + self.w_lmath:
                widget.setVisible(False)
        # update the labels of the plot combo box
        for i, plot in enumerate(self.plots):
            if plot.plot2d is True:
                name = (f"p{plot.index} - {plot.labels[0]} vs {plot.labels[1]} "
                        f"and {plot.labels[2]}")
            else:
                name = (
                    f"p{plot.index} - {plot.labels[0]} vs {plot.labels[1]}")
            self.w_plots.setItemText(i, name)
        # reset error
        self.cb_error("")

        self.plots[current_plot].set_math_mode(
            math_mode, [math.text() for math in self.w_math])
        self.plots[current_plot].plot(symbol="o")

    def _mouse_moved(self, ev):
        """
        handles mouse interaction - if the mouse in one of the viewboxes,
        then display the x and y value at the mouse position

        Parameters
        ----------
        ev: mouse moved event
          contains the coordinates of the mouse in coordinates of self.gl
        """
        boxes = [plot.vb for plot in self.plots]
        vb_mouse = None
        for vb in boxes:
            # get coordinate transform for top left of viewbox to identify
            # in which of the viewboxes the mouse currently resides
            pos = vb.mapRectFromView(vb.borderRect.rect()).topLeft()
            if vb.boundingRect().contains(ev[0]+pos):
                vb_mouse = vb
                # stop once we have found the correct viewbox
                continue
        if vb_mouse is not None:
            mousePoint = vb_mouse.mapSceneToView(ev[0])
            self.w_pos.setText(
                "x: {:.5e}\ny: {:.5e}".format(mousePoint.x(),
                                              mousePoint.y()))

    def _update_linesetting(self, state):
        """
        Updates the line visibility in all plot objects that are not
        2d plots
        """
        if state is True:
            for plot in self.plots:
                if plot.plot2d is False:
                    plot.plt.setPen((0, 0, 153), width=3)
        if state is False:
            for plot in self.plots:
                if plot.plot2d is False:
                    plot.plt.setPen(None)

    def _plot2d_changed(self, index, new_state):
        """
        handles a change of the plot type by replacing the PlotObject in place

        Parameters
        ----------
        index: int
          index of the plot to be replaced (refers to w_plots)
        new_state: bool
          flag that determines whether the plot is supposed to be 2d or not
        """
        # store index of plot in self.gl
        plotindex = self.plots[index].index
        # remove plot and replace with new one
        plt = self.plots.pop(index)
        plt.remove_plot()
        del plt
        self.plots.insert(index, self.PlotObject(self.gl, self.cb_error,
                                                 self.l_slider, new_state,
                                                 plotindex, [0, 0, 0],
                                                 pen=self.w_line.isChecked()))
        # reset global plot2d flag
        if any([plot.plot2d for plot in self.plots]) is True:
            self._toggle_plot2d(True)
        else:
            self._toggle_plot2d(False)

    def save_plot(self, filename):
        """
        Export the currently displayed plots (everything in self.gl)
        into a png file
        """
        exporter = pg.exporters.ImageExporter(self.gl.scene())
        exporter.export(filename)

    def reset(self):
        """
        Resets the full SimplePlotWidget to its default state
        """
        self.w_plots.blockSignals(True)
        for plot in self.plots:
            plot.remove_plot()
        del self.plots
        self.plots = [self.PlotObject(self.gl, self.cb_error, self.l_slider,
                                      False, 0, [0, 0, 0]), ]
        self.w_plots.setCurrentIndex(0)
        self.w_plots.clear()
        self.w_plots.addItem("p0 -  vs")
        self.w_plots.addItem("add plot")
        self.w_plots.blockSignals(False)
        self.w_calc.setCurrentIndex(0)
        self.w_math[0].setText("y")
        self.w_math[1].setText("x")
        self.w_delete.setVisible(False)
        # self.w_line.setChecked(False)

    def plot(self, z, x, y=None, plot2d=False):
        """
        Function that allows plotting a new set of data.

        TODO: Document possible combinations once fully settled

        Parameters
        ----------
        z: dict
          key "data" contains np.array of dimension 1...3
        x: dict
          key "data" contains np.array of dimension 1 or 2
        y: dict or None
          key "data" contains np.array of dimension 1 or 2
        plot2d: bool
          determines whether plot is 2d or curve
        """
        index = self.w_plots.currentIndex()
        if self.plots[index].plot2d != plot2d:
            self._plot2d_changed(index, plot2d)
        self.plots[index].set_data(z, x, y)
        self._calc_or_data_changed()


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
      mouse wheel zooms in/out with cursor position defining center
    """

    def __init__(self, *args, **kwds):
        pg.ViewBox.__init__(self, *args, **kwds)
        self.setMouseMode(self.RectMode)

    # reimplement right-click to autoscale plot
    def mouseClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.RightButton:
            self.autoRange()
            # set autorange upon change of data
            self.enableAutoRange()
        # elif ev.button() == Qt.MidButton:
        #     self.raiseContextMenu(ev)

    # reimplement drag event
    def mouseDragEvent(self, ev, axis=None):
        if ev.button() in (Qt.MouseButton.RightButton, Qt.MidButton):
            # enable pan mode
            self.setMouseMode(self.PanMode)
            pg.ViewBox.mouseDragEvent(self, ev, axis)
            self.setMouseMode(self.RectMode)
        elif ev.button() == Qt.MouseButton.LeftButton and axis is not None:
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
