# This file is part of a software collection for data acquisition (matr1x).
# Copyright (C) 2006-2026 matr1x developers
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
#
# CustomDateAxis class in this file adapted from
# https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/graphicsItems/AxisItem.html#AxisItem.tickValues
# licensed under MIT-license
"""Plotting widgets built on pyqtgraph."""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import (
    Any,
    ClassVar,
    cast,
)

import numpy as np
import pyqtgraph
from pyqtgraph.exporters import ImageExporter
from PySide6.QtCore import (
    Qt,
)
from PySide6.QtGui import (
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from matr1x.core.error_handling import InternalInvariantError
from matr1x.core.eval import delta

from .helpers import _format_local_timestamp
from .widgets import QRangeWidget

logger = logging.getLogger(__name__)


class SimplePlotWidget(QGroupBox):
    """
    Plot widget for multiple vertically stacked curve or 2d plots.

    Parameters
    ----------
    cb_error : callable
        Callback function that takes a single string as parameter.
        The string will describe the present error.
        If called with an empty string, it should clear the error.
    cb_index : callable
        Callback function that takes a PlotObject as parameter.
        The function is called with the currently selected PlotObject if the
        latter changes.
    """

    class PlotObject:
        """
        Object that contains the plot, data corresponding identifiers and widgets.

        Relies on external layouts to insert the widgets/plots.

        Parameters
        ----------
        l_plot : pyqtgraph.GraphicsLayoutWidget
            Layout into which the plot is to be inserted.
        error : callable
            Callback function that takes a single string as parameter.
            The string will describe the present error.
        l_slider : QVBoxLayout
            Layout into which the sliders are added using l_slider.addWidget.
        plot2d : bool
            Flag that defines whether plot is curve or 2d plot.
        index : int
            Index of the plot in the pyqtgraph.GraphicsLayoutWidget.
        desig : list of int
            Designator that stores integers that connect the plotted values
            to some external gui elements. Essentially a simple storage.
        pen : bool or None, optional
            If True, lines will be displayed.
        """

        # exposed functions that can be used by the custom math eval
        # expression stored in math_texts.
        exposed_functions: ClassVar[dict[str, Any]] = {
            "np": np,
            "sqrt": np.sqrt,
            "e": np.e,
            "pi": np.pi,
            "power": np.power,
            "log10": np.log10,
            "cos": np.cos,
            "sin": np.sin,
            "tan": np.tan,
            "arccos": np.arccos,
            "arcsin": np.arcsin,
            "arctan": np.arctan,
            "log": np.log,
            "exp": np.exp,
        }

        # default math operations can be added here if required
        # the key should correspond to the value of math_mode for this to
        # be selected, has to provide a pair of fucntions for the x and y
        # value, respectively
        default_math: ClassVar[dict[str, list[Callable[[Any], Any]]]] = {
            "no math": [lambda xf: xf, lambda yf: yf],
            "delta-": [lambda xf: delta(xf)[0], lambda yf: delta(yf)[1]],
            "delta+": [lambda xf: delta(xf)[0], lambda yf: delta(yf)[0]],
        }

        class CustomDateAxisItem(pyqtgraph.DateAxisItem):
            # This text is included pursuant to the obligations of this upstream licence
            # and must be retained in any derivatives of this class.
            # This specific class may be used under the terms of the MIT-license:
            # Permission is hereby granted, free of charge, to any person obtaining a
            # copy of this software and associated documentation files (the "Software"),
            # to deal in the Software without restriction, including without limitation
            # the rights to use, copy, modify, merge, publish, distribute, sublicense,
            # and/or sell copies of the Software, and to permit persons to whom the
            # Software is furnished to do so, subject to the following conditions:
            #
            # The above copyright notice and this permission notice shall be included in
            # all copies or substantial portions of the Software.
            #
            # THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
            # IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
            # FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
            # THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
            # LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
            # FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
            # DEALINGS IN THE SOFTWARE.
            """
            Custom date axis item for displaying dates with customizable formatting.

            This class extends the pyqtgraph DateAxisItem to provide more flexible
            date formatting options based on the scale of the axis.

            Parameters
            ----------
            *args
                Variable length argument list passed to the parent class.
            **kwargs
            Arbitrary keyword arguments passed to the parent class.
            """

            def tickValues(self, minVal, maxVal, size):
                """
                Return the values and spacing of ticks to draw.

                Parameters
                ----------
                minVal : float
                    Minimum value of the axis range.
                maxVal : float
                    Maximum value of the axis range.
                size : int
                    Size of the axis in pixels.

                Returns
                -------
                list of tuples
                    Each tuple contains (spacing, [ticks]), where:
                    - spacing is the distance between ticks
                    - [ticks] is a list of tick values

                Notes
                -----
                The returned list has the format:
                [
                    (spacing, [major ticks]),
                    (spacing, [minor ticks]),
                    ...
                ]

                This method calls tickSpacing to determine the correct tick locations.
                """
                minVal, maxVal = sorted((minVal, maxVal))

                minVal *= self.scale
                maxVal *= self.scale

                ticks = []
                tickLevels = self.tickSpacing(minVal, maxVal, size)
                allValues = np.array([])
                for i in range(len(tickLevels)):
                    spacing, offset = tickLevels[i]

                    # determine starting tick
                    start = (np.ceil((minVal - offset) / spacing) * spacing) + offset

                    # determine number of ticks
                    num = int((maxVal - start) / spacing) + 1
                    values = (np.arange(num) * spacing + start) / self.scale
                    # remove any ticks that were present in higher levels
                    # we assume here that if the difference between a tick value and
                    # a previously seen tick value
                    # is less than spacing/100, then they are 'equal' and we can
                    # ignore the new tick.
                    close = np.any(
                        np.isclose(
                            allValues,
                            values[:, np.newaxis],
                            rtol=0,
                            atol=spacing / self.scale * 0.01,
                        ),
                        axis=-1,
                    )
                    values = values[~close]
                    allValues = np.concatenate([allValues, values])
                    ticks.append((spacing / self.scale, values.tolist()))

                if self.logMode:
                    # not tested
                    return self.logTickValues(minVal, maxVal, size, ticks)

                return ticks

            def tickStrings(self, values, scale, spacing):
                """
                Return the labels corresponding to the tick values depending on the spacing.

                Parameters
                ----------
                values : array-like
                    The tick values.
                scale : float
                    The scale factor for the values.
                spacing : float
                    The spacing between tick values.

                Returns
                -------
                list of str
                    The tick labels corresponding to the values.
                """
                # Choose the date format based on the scale
                if spacing < 0.5:  # less than 0.5 seconds
                    fmt = "%S.%f"
                elif spacing < 5:  # less than 5 seconds
                    fmt = "%M:%S.%f"
                elif spacing < 100:  # less than a minute
                    fmt = "%H:%M:%S"
                elif spacing < 4000:  # less than an hour
                    fmt = "%H:%M"
                elif spacing < 80000:  # less than a day
                    fmt = "%m-%d %H:%M"
                elif spacing < 6e5:  # less than a week
                    fmt = "%m-%d %Hh"
                elif spacing < 2.5e6:  # less than a month
                    fmt = "%y-%m-%d"
                else:
                    fmt = "%Y-%m-%d"

                # Convert timestamps to formatted date strings
                if spacing >= 5:
                    return [_format_local_timestamp(value, fmt) for value in values]
                return [
                    _format_local_timestamp(value, fmt, trim_trailing_zeros=True)
                    for value in values
                ]

        class CategoricalAxis(pyqtgraph.AxisItem):
            """
            Custom axis item for displaying categorical data.

            This class extends pyqtgraph's AxisItem to properly display categorical
            data by mapping numeric indices to category labels.

            Parameters
            ----------
            orientation : str
                The orientation of the axis ('left', 'right', 'top', or 'bottom').
            mapping : dict, optional
                Dictionary mapping numeric indices to category labels.
            *args
                Variable length argument list passed to parent class.
            **kwargs
                Arbitrary keyword arguments passed to parent class.

            Attributes
            ----------
            mapping : dict
                Dictionary storing the mapping between numeric indices and category labels.
            unique_ticks : set
                Set storing unique tick values.
            """

            def __init__(self, orientation, mapping=None, *args, **kwargs):
                super().__init__(orientation, *args, **kwargs)
                self.mapping = mapping or {}
                self.unique_ticks = set()

            def tickStrings(self, values, scale, spacing):
                """
                Return the strings that should be placed next to ticks.

                For categorical data, shows all tick labels regardless of plot size.

                Parameters
                ----------
                values : list
                    List of values to create tick strings for.
                scale : float
                    Scale factor for values.
                spacing : float
                    Space between ticks.

                Returns
                -------
                list of str
                    List of strings to display at tick marks.
                """
                # For categorical data, show all ticks regardless of plot size
                strings = []
                for v in range(len(self.mapping)):
                    if v in self.mapping:
                        strings.append(str(self.mapping[v]))
                    else:
                        strings.append("")
                return strings

            def tickValues(self, minVal, maxVal, size):
                """
                Return the values and spacing of ticks to draw.

                Parameters
                ----------
                minVal : float
                    Minimum value visible on axis.
                maxVal : float
                    Maximum value visible on axis.
                size : int
                    Width or height of axis in pixels.

                Returns
                -------
                list of tuple
                    List containing (spacing, [tick positions]) pairs.
                """
                # Override to return fixed ticks for categorical data
                ticks = []
                if not self.mapping:
                    return [(1, [])]
                values = list(range(len(self.mapping)))
                ticks.append((1, values))
                return ticks

        def __init__(
            self,
            l_plot: pyqtgraph.GraphicsLayoutWidget,
            error,
            l_slider,
            plot2d: bool,
            index,
            desig,
            pen=None,
        ):
            self.index = index
            self.desig = desig
            self.l_plot: pyqtgraph.GraphicsLayoutWidget = l_plot
            self.l_slider = l_slider
            self.plot2d: bool = plot2d
            self.error = error

            self.pw: pyqtgraph.PlotItem
            self.plt: pyqtgraph.PlotDataItem | pyqtgraph.ImageView
            self.vb: CustomViewBox

            # Store mappings for categorical data
            self.x_mapping = {}
            self.z_mapping = {}
            self.x_is_categorical = False
            self.z_is_categorical = False

            # Cache for unique values
            self.x_unique_values = None
            self.z_unique_values = None

            # initialize the pyqtgraph display widgets
            self.vb = CustomViewBox()
            if self.plot2d is True:
                self.plt = pyqtgraph.ImageView(view=self.vb)
                # please note https://github.com/pyqtgraph/pyqtgraph/issues/3023
                self.pw = self.l_plot.ci.addPlot(
                    row=self.index, col=0, viewBox=self.vb, title=f"p{index}"
                )
            else:
                self.pw = self.l_plot.ci.addPlot(
                    row=self.index, col=0, viewBox=self.vb, title=f"p{index}"
                )
                self.plt = self.pw.plot([])
                if pen is True:
                    self.plt.setPen((0, 0, 153), width=3)
                else:
                    self.plt.setPen(None)

            self.date_axis = {
                "bottom": self.CustomDateAxisItem(orientation="bottom"),
                "top": self.CustomDateAxisItem(orientation="top"),
                "left": self.CustomDateAxisItem(orientation="left"),
                "right": self.CustomDateAxisItem(orientation="right"),
            }

            self.categorical_axis = {
                "bottom": self.CategoricalAxis(orientation="bottom"),
                "left": self.CategoricalAxis(orientation="left"),
            }

            self.ordinary_axis = {
                "bottom": self.pw.getAxis("bottom"),
                "left": self.pw.getAxis("left"),
            }

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

        def _convert_categorical(self, data, is_x=True):
            """Convert categorical data to numeric values with mapping."""
            if data.dtype == np.dtype("O"):
                # For categorical data, convert to numeric indices
                unique_values = np.unique([str(x) for x in data])
                if is_x:
                    self.x_unique_values = unique_values
                    self.x_is_categorical = True
                else:
                    self.z_unique_values = unique_values
                    self.z_is_categorical = True

                # Create mapping
                mapping = {idx: val for idx, val in enumerate(unique_values)}
                numeric_data = np.array(
                    [list(mapping.keys())[list(mapping.values()).index(str(x))] for x in data]
                )

                # Store mapping for axis
                if is_x:
                    self.categorical_axis["bottom"].mapping = mapping
                else:
                    self.categorical_axis["left"].mapping = mapping

                return numeric_data

            if is_x:
                self.x_is_categorical = False
            else:
                self.z_is_categorical = False
            return data

        def _raise_error(self, error):
            """
            Handle errors.

            Parameters
            ----------
            error : str
                Description of the error.
            """
            self.error(error)

        def _get_math(self, y, x):
            """
            Apply the math operation to the two data arrays.

            Applies the math operation depending on the value stored in
            self.math_mode. See default_math for the default functions that
            are implemented.

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
                Data to be processed.
            x: numpy array
                Data to be processed.

            Returns
            -------
            y: numpy array
                Processed data.
            x: numpy array
                Processed data.
            """
            # Don't apply math to categorical data
            if self.x_is_categorical or self.z_is_categorical:
                return y, x

            if self.math_mode in self.default_math:
                # some of our default math is supposed to be used
                x = self.default_math[self.math_mode][0](x)
                y = self.default_math[self.math_mode][1](y)
            elif self.math_mode == "custom":
                # none of the above, so we are in custom mode
                xc = None
                yc = None
                try:
                    # define function based on the string stored in
                    # math_texts[1]
                    def fx(xf, yf):
                        return eval(
                            self.math_texts[1],
                            ({"x": xf, "y": yf} | self.exposed_functions),
                        )

                    xc = fx(x, y)
                except Exception as e:
                    self._raise_error("error in math function (x): " + str(e))

                try:
                    # define function based on the string stored in
                    # math_texts[0]
                    def fy(yf, xf):
                        return eval(
                            self.math_texts[0],
                            ({"y": yf, "x": xf} | self.exposed_functions),
                        )

                    yc = fy(y, x)
                except Exception as e:
                    self._raise_error("error in math function (y): " + str(e))

                if yc is not None and xc is not None:
                    if len(yc) != len(xc):
                        self._raise_error("error in math: arrays have different length")
                    elif (
                        len(yc.shape) > 1
                        and all(np.array(yc.shape) > 1)
                        or len(xc.shape) > 1
                        and all(np.array(xc.shape) > 1)
                    ):
                        self._raise_error("error in math: y array has too high dimension")
                    else:
                        y, x = yc, xc
            return y, x

        def _handle_multidim_and_sliders(self):
            """Handle slider visibility according to data dimensions."""
            self.md = False
            for slider, dshape in zip(
                [self.w_zslider, self.w_xslider], [self.zdata.shape, self.xdata.shape]
            ):
                slider.setVisible(False)
                if len(dshape) > 2:
                    # data is 3D, so show sliders
                    self.md = True
                    slider.setVisible(True)
                    slider.set_range(0, dshape[0] - 1)
                elif (len(dshape) > 1 and dshape[1] > 1) and self.plot2d is False:
                    # array is 2d and second dimension is longer than 1
                    self.md = True
                    slider.setVisible(True)
                    slider.set_range(0, dshape[1] - 1)
                elif (len(dshape) > 1 and dshape[1] == 1) and self.plot2d is False:
                    # array is 2d and second dimension is exactly 1
                    # do not show sliders in this case (only one element)
                    self.md = True
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
            Handle data redimensioning and selection according to slider position.

            This method adjusts the data dimensions and selects
            appropriate data based on the current slider positions for
            multi-dimensional data sets. It updates the x, y, and z data
            attributes of the object accordingly.
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
            Handle slider events and update the displayed data accordingly.

            Parameters
            ----------
            val: int
                Current value of the slider that is to be applied.
            """
            if self.plot2d is True:
                # for 2d plot, select index of current data element
                self._handle_multidim_data()
                if not isinstance(self.plt, pyqtgraph.ImageView):
                    raise InternalInvariantError("Plotting 3D data requires an ImageView widget!")
                self.plt.setCurrentIndex(val)
                self.pw.setTitle(
                    f"p{self.index} at {self.labels[1]} = {self.x[val]} {self.units[1]}"
                )
            else:
                # for curve, handle the data and replot
                self._handle_multidim_data()
                self.plot(symbol="o")

        def remove_plot(self):
            """
            Remove the plot and the widgets that belong to the PlotObject.

            This method removes the plot from the provided layouts,
            including the horizontal line, x-slider, and z-slider
            widgets associated with this PlotObject.
            """
            self.l_plot.removeItem(self.l_plot.ci.getItem(row=self.index, col=0))
            self.l_slider.removeWidget(self.w_hline)
            self.l_slider.removeWidget(self.w_xslider)
            self.l_slider.removeWidget(self.w_zslider)

        def parse_data(self, z, x, y):
            """
            Parse the data dictionaries into the corresponding class variables.

            Parameters
            ----------
            z : dict
                Dictionary containing z data with keys "data", "label", "desig", and "unit".
            x : dict
                Dictionary containing x data with keys "data", "label", "desig", and "unit".
            y : dict or None
                Dictionary containing y data with keys "data", "label", "desig", and "unit",
                or None if not applicable.
            """
            # Handle categorical data conversions
            self.zdata = self._convert_categorical(z["data"], is_x=False)
            self.xdata = self._convert_categorical(x["data"], is_x=True)

            # Update axis types based on data
            self.z_is_categorical = z["data"].dtype == np.dtype("O")
            self.x_is_categorical = x["data"].dtype == np.dtype("O")

            # Update axis items based on data type
            if self.z_is_categorical:
                self.pw.setAxisItems({"left": self.categorical_axis["left"]})
            else:
                # Reset to ordinary axis for numerical data
                self.pw.setAxisItems({"left": self.ordinary_axis["left"]})

            if self.x_is_categorical:
                self.pw.setAxisItems({"bottom": self.categorical_axis["bottom"]})
            else:
                # Reset to ordinary axis for numerical data
                self.pw.setAxisItems({"bottom": self.ordinary_axis["bottom"]})

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
            Set the math mode and texts.

            Parameters
            ----------
            index: int
                Selects the math operation to be applied, see self.default_math.
            math_texts: [str, str]
                Contains two strings that are evaluated by eval(string). Are
                only allowed to contain functions/variables that are defined
                in self.exposed_functions.
            """
            self.math_mode = index
            self.math_texts = math_texts

        def set_data(self, z, x, y=None):
            """
            Update the data that is stored in the present plot.

            Used keys are "data", "label", "desig" and "unit".

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
            Handle the actual plotting of the data and update the labels.

            Parameters
            ----------
            *args
                Variable length argument list passed to the plot
                function if curve plotting is enabled.
            **kwargs
                Arbitrary keyword arguments passed to the plot function
                if curve plotting is enabled.
            """
            if self.plot2d is True:
                if len(self.zdata.shape) > 2:
                    # 3d plotting
                    if not isinstance(self.plt, pyqtgraph.ImageView):
                        raise InternalInvariantError(
                            "Plotting 3D data requires an ImageView widget!"
                        )
                    self.plt.setImage(
                        self.z,
                        pos=[0, 0],
                        scale=[1, 1],
                        xvals=self.x,
                        axes={"t": 0, "x": 1, "y": 2},
                    )
                    # make sure top and right axis are hidden
                    for i, ax in zip(range(2), ["right", "top"]):
                        self.pw.hideAxis(ax)
                    # set labels to array index, same as on the y-axis
                    self.pw.setLabel("bottom", self.labels[2], self.units[2])
                    self.vb.setAspectLocked(False)
                    self.vb.invertY(False)
                else:
                    if not isinstance(self.plt, pyqtgraph.ImageView):
                        raise InternalInvariantError(
                            "Plotting 3D data requires an ImageView widget!"
                        )
                    # 2d data follows different dimensioning scheme
                    x0, x1 = self.x[0], self.x[-1]
                    xscale = (x1 - x0) / self.z.shape[0]
                    y0, y1 = self.y[0], self.y[-1]
                    yscale = (y1 - y0) / self.z.shape[1]  # type: ignore
                    pos = [x0, y0]
                    scale = [xscale, yscale]
                    self.plt.setImage(self.z, pos=pos, scale=scale)
                    for i, ax in zip(range(1, 3), ["top", "right"]):
                        if self.labels[i] == "timeUTC":
                            self.pw.setAxisItems({ax: self.date_axis[ax]})
                        elif self.pw.getAxis(ax).isVisible():
                            self.pw.hideAxis(ax)
                    for i, ax in zip(range(1, 3), ["bottom", "left"]):
                        self.pw.setLabel(ax, self.labels[i], self.units[i])
                self.pw.getAxis("left").textWidth = 0
                # remove aspect lock for free zooming and do not invert y axis
                self.vb.setAspectLocked(False)
                self.vb.invertY(False)
            else:
                # for curves apply math, set labels and data
                z, x = self._get_math(self.z, self.x)
                self.pw.getAxis("left").textWidth = 0

                for i, ax in zip(range(2), ["right", "top"]):
                    if self.labels[i] == "timeUTC":
                        self.pw.setAxisItems({ax: self.date_axis[ax]})
                    elif self.pw.getAxis(ax).isVisible():
                        self.pw.hideAxis(ax)

                # Already set up in parse_data() for categorical axes
                # Set labels for axes
                for i, ax in zip(range(2), ["left", "bottom"]):
                    self.pw.setLabel(ax, self.labels[i], self.units[i])
                if not isinstance(self.plt, pyqtgraph.PlotDataItem):
                    raise InternalInvariantError("Plotting requires an PlotDataItem widget!")
                try:
                    self.plt.setData(*args, x=x, y=z, **kwargs)
                except ValueError as e:
                    # Handle shape mismatch errors
                    self._raise_error(f"Plot error: {e!s}")

            # After plotting, if autorange is enabled on any axis, recompute now.
            auto_range = self.vb.state["autoRange"]
            if auto_range is None or isinstance(auto_range, (int, float)):
                raise InternalInvariantError("Invalid auto_range value!")
            x_auto, y_auto = auto_range
            if x_auto or y_auto:
                # updateAutoRange respects which axes are enabled for auto
                self.vb.updateAutoRange()

    def __init__(self, cb_error, cb_index, parent=None):
        super().__init__("", parent)

        self.cb_error = cb_error
        self.cb_index = cb_index
        self.plot2d = False
        self._is_refreshing = False

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
        self.w_calc.addItems(list(self.PlotObject.default_math.keys()) + ["custom"])
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
                "operation and have to remain in a single dimension."
            )

        # hide custom math layouts by default
        for widget in self.w_math + self.w_lmath:
            widget.setVisible(False)

        # put custom math in separate layout to make them scale independetly
        l_math = QHBoxLayout()
        for i in range(2):
            l_math.addWidget(self.w_lmath[i])
            l_math.addWidget(self.w_math[i], stretch=1)

        # Add GraphicsLayout and make most prominent widget
        self.gl = pyqtgraph.GraphicsLayoutWidget()
        self.gl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # have proxy that connects the position of the mouse on the
        # GraphicsLayout to display the x/y position on the current
        # plot, additionally introduce proxy to select active plot by
        # just clicking into the plot
        scene = cast(pyqtgraph.GraphicsScene, self.gl.scene())
        self.proxy = pyqtgraph.SignalProxy(
            scene.sigMouseMoved, rateLimit=30, slot=self._mouse_moved
        )
        self.proxy2 = pyqtgraph.SignalProxy(
            scene.sigMouseClicked, rateLimit=2, slot=self._mouse_clicked
        )

        # add the first empty plot with
        initial_plot = self.PlotObject(self.gl, self.cb_error, self.l_slider, False, 0, [0, 0, 0])
        self.plots: list[self.PlotObject] = [initial_plot]

        # Connect X-axis linking signal for automatic linking
        if hasattr(initial_plot, "vb") and initial_plot.vb is not None:
            initial_plot.vb.sigRangeChanged.connect(self._on_range_changed)

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
        Add a plot (via PlotObject) to the current display.

        Ensures that the new plot is always appended to the end.
        """
        index = max([plot.index for plot in self.plots]) + 1
        new_plot = self.PlotObject(
            self.gl,
            self.cb_error,
            self.l_slider,
            False,
            index,
            [0, 0, 0],
            pen=self.w_line.isChecked(),
        )
        self.plots.append(new_plot)

        # Connect X-axis linking signal for automatic linking
        if hasattr(new_plot, "vb") and new_plot.vb is not None:
            new_plot.vb.sigRangeChanged.connect(self._on_range_changed)

        self.w_plots.setItemText(len(self.plots) - 1, f"p{index} -  vs ")
        self.w_plots.addItem("add plot")

    def _remove_plot(self):
        """Remove plot that is currently selected in self.w_plots."""
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
            self.w_plots.setCurrentIndex(index - 1)
        self.w_plots.removeItem(index)
        if self.w_plots.count() == 2:
            # nothing else to be deleted, hide button
            self.w_delete.setVisible(False)

    def _update_wplots(self, index):
        """
        Update the currently selected plot upon a change of self.w_plots.

        Parameters
        ----------
        index : int
            Index of the newly selected plot in self.w_plots.
        """
        cnt = self.w_plots.count()
        if index == cnt - 1 and cnt > 1:
            # selecting last index (add plot) leads to plot being added
            self._add_plot()
            cnt += 1
        if cnt > 2 and self.w_delete.isVisible() is False:
            # something can be deleted, make button visible
            self.w_delete.setVisible(True)

        current_plot = self.plots[index]

        # Check if any axes are categorical
        has_categorical = current_plot.x_is_categorical or current_plot.z_is_categorical

        # Keep math box visible but enable/disable based on plot type and data
        self.w_calc.setVisible(not current_plot.plot2d)
        self.w_calc.setEnabled(not current_plot.plot2d and not has_categorical)

        # If categorical, reset to "no math" but keep box visible
        if has_categorical:
            self.w_calc.setCurrentIndex(0)  # "no math" index
            current_plot.math_mode = "no math"

        # update widgets according to specifications in currently selected plot
        for i in range(2):
            self.w_math[i].setText(current_plot.math_texts[i])

        # load math_mode from PlotObject and set index
        index_math = self.w_calc.findText(current_plot.math_mode)
        if index_math != -1:
            # for -1, item not found in combo box texts
            self.w_calc.setCurrentIndex(index_math)

        # pass current PlotObject to callback function to be handled externally
        self.cb_index(current_plot)

    def _toggle_plot2d(self, flag):
        """
        Toggle the plot2d flag and handle visibility of math widgets.

        Parameters
        ----------
        flag: bool
            Flag that controls whether plot2d is False or True.
        """
        self.plot2d = flag
        for widget in self.w_math + self.w_lmath:
            widget.setVisible(not flag)
        self.w_calc.setVisible(not flag)

    def _calc_or_data_changed(self):
        """Apply new data, math and labels and update the plot."""
        math_mode = self.w_calc.currentText()
        current_plot = self.w_plots.currentIndex()

        # Check if current plot has categorical data
        has_categorical = (
            self.plots[current_plot].x_is_categorical or self.plots[current_plot].z_is_categorical
        )

        # Enable/disable math combo box based on categorical data
        self.w_calc.setEnabled(not has_categorical)

        if math_mode == "custom" and self.w_math[0].isVisible() is False:
            for widget in self.w_math + self.w_lmath:
                widget.setVisible(True)
        elif math_mode != "custom" and self.w_math[0].isVisible() is True:
            for widget in self.w_math + self.w_lmath:
                widget.setVisible(False)
        # update the labels of the plot combo box
        for i, plot in enumerate(self.plots):
            if plot.plot2d is True:
                name = f"p{plot.index} - {plot.labels[0]} vs {plot.labels[1]} and {plot.labels[2]}"
            else:
                name = f"p{plot.index} - {plot.labels[0]} vs {plot.labels[1]}"
            self.w_plots.setItemText(i, name)
        # reset error
        self.cb_error("")

        self.plots[current_plot].set_math_mode(math_mode, [math.text() for math in self.w_math])
        self.plots[current_plot].plot(symbol="o")

    def _mouse_moved(self, ev):
        """
        Handle mouse interaction and display x and y values at mouse position.

        If the mouse is in one of the viewboxes, display the x and y value
        at the mouse position.

        Parameters
        ----------
        ev : tuple
            Contains the coordinates of the mouse in coordinates of self.gl.
        """
        boxes = [plot.vb for plot in self.plots]
        vb_mouse = None
        for vb in boxes:
            # get coordinate transform for top left of viewbox to identify
            # in which of the viewboxes the mouse currently resides
            pos = vb.mapRectFromView(vb.borderRect.rect()).topLeft()
            if vb.boundingRect().contains(ev[0] + pos):
                vb_mouse = vb
                # stop once we have found the correct viewbox
                continue
        if vb_mouse is not None:
            mousePoint = vb_mouse.mapSceneToView(ev[0])
            self.w_pos.setText(f"x: {mousePoint.x():.5e}\ny: {mousePoint.y():.5e}")

    def _mouse_clicked(self, ev):
        """
        Handle mouse interaction and set active plot in w_plots ComboBox.

        If the mouse is in one of the viewboxes, change the currently active
        plot on click, currently works for all types of click (left/right/middle)

        Parameters
        ----------
        ev : MouseClickEvent
            Contains the click event of the mouse in coordinates of self.gl.
        """
        boxes = [plot.vb for plot in self.plots]
        vb_mouse = None
        for vb in boxes:
            # get coordinate transform for top left of viewbox to identify
            # in which of the viewboxes the mouse currently resides
            pos = vb.mapRectFromView(vb.borderRect.rect()).topLeft()
            if vb.boundingRect().contains(ev[0].scenePos() + pos):
                vb_mouse = vb
                # stop once we have found the correct viewbox
                continue
        if vb_mouse is not None:
            index = boxes.index(vb_mouse)
            self.w_plots.setCurrentIndex(index)

    def _update_linesetting(self, state):
        """
        Update the line visibility in all plot objects that are not 2d plots.

        Parameters
        ----------
        state : bool
            If True, show lines. If False, hide lines.
        """
        if state is True:
            for plot in self.plots:
                if plot.plot2d is False:
                    if not isinstance(plot.plt, pyqtgraph.PlotDataItem):
                        raise InternalInvariantError("Plotting requires an PlotDataItem widget!")
                    plot.plt.setPen((0, 0, 153), width=3)
        if state is False:
            for plot in self.plots:
                if plot.plot2d is False:
                    if not isinstance(plot.plt, pyqtgraph.PlotDataItem):
                        raise InternalInvariantError("Plotting requires an PlotDataItem widget!")
                    plot.plt.setPen(None)

    def _on_range_changed(self, view_box, ranges: tuple[tuple[float, float], tuple[float, float]]):
        """Handle range change event to synchronize X-axis across plots with same X-column.

        Parameters
        ----------
        view_box : CustomViewBox
            The `CustomViewBox` instance that emitted the `sigRangeChanged` signal.
        ranges : tuple[tuple[float, float], tuple[float, float]]
            A tuple containing two tuples, representing the new X and Y ranges
            of the `view_box`. Each inner tuple is `(min_value, max_value)`.
        """
        # identify source
        source_plot = next((p for p in self.plots if p.vb is view_box), None)
        if source_plot is None or not source_plot.labels:
            return

        source_x_label = source_plot.labels[1]
        state = cast(dict, source_plot.vb.state)  # pyqtgraph is not strongly typed
        x_auto = bool(state["autoRange"][0])
        # pyqtgraph keeps (xAuto, yAuto)

        x_range = ranges[0]

        for plot in self.plots:
            if plot is source_plot or not plot.labels:
                continue
            if plot.labels[1] != source_x_label:
                continue

            plot.vb.sigRangeChanged.disconnect(self._on_range_changed)
            if x_auto:
                plot.vb.enableAutoRange(axis=pyqtgraph.ViewBox.XAxis, enable=True)
                plot.vb.updateAutoRange()
            else:
                plot.vb.enableAutoRange(axis=pyqtgraph.ViewBox.XAxis, enable=False)
                plot.vb.setXRange(*x_range, padding=0)
            plot.vb.sigRangeChanged.connect(self._on_range_changed)

    def _plot2d_changed(self, index, new_state):
        """
        Handle a change of the plot type by replacing the PlotObject in place.

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
        new_plot = self.PlotObject(
            self.gl,
            self.cb_error,
            self.l_slider,
            new_state,
            plotindex,
            [0, 0, 0],
            pen=self.w_line.isChecked(),
        )
        self.plots.insert(index, new_plot)

        # Connect X-axis linking signal for automatic linking
        if hasattr(new_plot, "vb") and new_plot.vb is not None:
            new_plot.vb.sigRangeChanged.connect(self._on_range_changed)
        # reset global plot2d flag
        if any(plot.plot2d for plot in self.plots) is True:
            self._toggle_plot2d(True)
        else:
            self._toggle_plot2d(False)

    def refresh_all_plots(self):
        """
        Refresh every existing plot by briefly activating each tab once.

        Emit currentIndexChanged because that is how plots rebuild.
        """
        if self._is_refreshing:
            return
        self._is_refreshing = True
        try:
            combo = self.w_plots
            current = combo.currentIndex()
            # skip the 'add plot' entry if you keep it as the last tab
            last_real = combo.count() - 1
            if last_real <= 0:
                return
            for i in range(last_real):
                if i == current:
                    continue
                combo.setCurrentIndex(i)
            combo.setCurrentIndex(current)
        finally:
            self._is_refreshing = False

    def save_plot(self, filename):
        """
        Export the currently displayed plots into a PNG file.

        This method exports all plots currently visible in the graphics layout
        (self.gl) to a single PNG image file.

        Parameters
        ----------
        filename : str
            The path and name of the file where the PNG image will be saved.
        """
        exporter = ImageExporter(self.gl.scene())
        exporter.export(filename)

    def get_columns(self) -> tuple[str, str]:
        """Return the plotted columns."""
        index = self.w_plots.currentIndex()
        y = self.plots[index].labels[0]
        x = self.plots[index].labels[1]
        return (y, x)

    def save_data(self, filename) -> None:
        """
        Export the currently displayed plot into a text file.

        Parameters
        ----------
        filename : str
            The path and name of the file where the text file will be saved.
        """
        index = self.w_plots.currentIndex()
        z, x = self.plots[index]._get_math(self.plots[index].z, self.plots[index].x)
        data = np.column_stack((x, z))
        delimiter = "\t"
        newline = "\n"
        with Path(filename).open("w") as f:
            f.write(
                f"{self.plots[index].labels[1]}{delimiter}{self.plots[index].labels[0]}{newline}"
            )
            f.write(
                f"{self.plots[index].units[1]}{delimiter}{self.plots[index].units[0]}{newline}"
            )
        with Path(filename).open("a") as f:
            np.savetxt(f, data, delimiter=delimiter, newline=newline)

    def reset(self):
        """Reset the full SimplePlotWidget to its default state."""
        self.w_plots.blockSignals(True)
        for plot in self.plots:
            plot.remove_plot()
        del self.plots
        initial_plot = self.PlotObject(self.gl, self.cb_error, self.l_slider, False, 0, [0, 0, 0])
        self.plots = [initial_plot]

        # Connect X-axis linking signal for automatic linking
        if hasattr(initial_plot, "vb") and initial_plot.vb is not None:
            initial_plot.vb.sigRangeChanged.connect(self._on_range_changed)

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
        Plot a new set of data.

        TODO: Document possible combinations once fully settled

        Parameters
        ----------
        z : dict
            Dictionary containing the z-axis data. Key "data" contains
            np.array of dimension 1, 2, or 3.
        x : dict
            Dictionary containing the x-axis data. Key "data" contains
            np.array of dimension 1 or 2.
        y : dict or None, optional
            Dictionary containing the y-axis data. Key "data" contains
            np.array of dimension 1 or 2. Default is None.
        plot2d : bool, optional
            Determines whether the plot is 2D or a curve. Default is False.
        """
        index = self.w_plots.currentIndex()
        if self.plots[index].plot2d != plot2d:
            self._plot2d_changed(index, plot2d)
        self.plots[index].set_data(z, x, y)
        self._calc_or_data_changed()


class CustomViewBox(pyqtgraph.ViewBox):
    """
    Reimplements the pyqthgraph ViewBox and improves its usability with the mouse.

    Behavior is as follows:

    - Right click autoscales graph
    - Mouse inside plot:
        - Left drag zooms to rectangle
        - Right drag allows panning plot
        - Mouse wheel zooms in/out with cursor position defining center
    - Mouse on x or y axis:
        - Left button drags corresponding axis
        - Right button allows panning individual axis
        - Mouse wheel zooms in/out with cursor position defining center
    """

    def __init__(self, *args, **kwds):
        """
        Initialize the CustomViewBox.

        Parameters
        ----------
        *args
            Variable length argument list.
        **kwds
            Arbitrary keyword arguments.
        """
        pyqtgraph.ViewBox.__init__(self, *args, **kwds)
        self.setMouseMode(self.RectMode)

    def mouseClickEvent(self, ev: QMouseEvent):
        """
        Handle mouse click events.

        Parameters
        ----------
        ev : QMouseEvent
            The mouse event.
        """
        if ev.button() == Qt.MouseButton.RightButton:
            self.autoRange()
            self.enableAutoRange()

    def mouseDragEvent(self, ev: QMouseEvent, axis=None):
        """
        Handle mouse drag events.

        Parameters
        ----------
        ev : QMouseEvent
            The mouse event.
        axis : str, optional
            The axis being dragged, if any.
        """
        if ev.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            self.setMouseMode(self.PanMode)
            pyqtgraph.ViewBox.mouseDragEvent(self, ev, axis)
            self.setMouseMode(self.RectMode)
        elif ev.button() == Qt.MouseButton.LeftButton and axis is not None:
            # enable pan mode on individual axis
            self.setMouseMode(self.PanMode)
            pyqtgraph.ViewBox.mouseDragEvent(self, ev, axis)
            self.setMouseMode(self.RectMode)
        else:
            pyqtgraph.ViewBox.mouseDragEvent(self, ev, axis)
