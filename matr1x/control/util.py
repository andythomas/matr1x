# This file is part of a software collection for data acquisition (matr1x).
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
Contains utility functions for generating control GUIs or devices.

This module provides functionality for creating control graphical user
interfaces or devices based on the scpi_tcp_server.
"""

from __future__ import annotations

import copy
import itertools
import logging
import mimetypes
import numbers
import os
import re
import signal
import smtplib
import ssl
import sys
import time
import traceback
from abc import ABC, abstractmethod
from collections import UserDict
from collections.abc import Iterable
from email import encoders
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import IntEnum
from functools import wraps
from operator import attrgetter
from pathlib import Path
from subprocess import PIPE, Popen

import numpy
import psutil
from PyQt6 import QtCore
from PyQt6.QtCore import (
    QObject,
    QSettings,
    QSize,
    Qt,
    QThread,
    QTimer,
    QVariant,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .. import config, datetimefmt, logfolder, system, usersfolder
from ..gui_util import MApplication, OutputDuplication, validator
from ..util import normalize_cmds, set_correct_mac_appname
from .qwidgets import ToggleButton, matr1xProgressBar


def catchEmitError(method):
    """
    Define error handling decorator.

    This decorator works only with ControlWindow which defines a sig_error signal.

    Parameters
    ----------
    method : callable
        The method to be decorated.

    Returns
    -------
    callable
        The decorated method.
    """

    @wraps(method)
    def decorated_method(self, *args, **kwargs):
        try:
            method(self, *args, **kwargs)
        except Exception:
            # report error to the main thread if relevant part can't be disabled
            exc_type, exc_value, exc_traceback = sys.exc_info()
            pointer = method.__name__
            # print timestamp and verbose error message to status display,
            # make a log entry
            timestamp = time.strftime(datetimefmt)
            print(timestamp)
            logger = logging.getLogger(__name__)
            logger.info("handling error in %s: %s", pointer, repr(exc_value))
            traceback.print_tb(exc_traceback)
            # duplicate to stdout
            traceback.print_tb(exc_traceback, file=sys.stdout)
            # if the GuiDict which raised the error allows disabling lets just
            # disable it and swallow the error
            if isinstance(self, (GuiDict, GuiDict._Worker)):
                if isinstance(self, GuiDict._Worker):
                    guidict = self.guidict
                else:
                    guidict = self
                outstr = f"Error occured inside '{guidict.__class__.__name__}'"
                logger.info(outstr)
                print(outstr)
                if guidict.allow_disabling:
                    guidict.enable_switch.setChecked(False)
                    outstr = "Ignoring last Exception since device can be deactivated."
                    logger.info(outstr)
                    print(outstr)
                    return
            if hasattr(self, "sig_error"):
                self.sig_error.emit(exc_type, exc_value, pointer)
            elif hasattr(self, "parent") and self.parent:
                self.parent.sig_error.emit(exc_type, exc_value, pointer)
            # prevent prematurely cleaning up objects,
            # this otherwise causes (sometimes) a segmentation fault
            time.sleep(0.05)

    return decorated_method


class guiObject(IntEnum):
    """
    Enum object for GUI elements identification.

    This enum makes it easier to write readable code and identify GUI
    elements by their name instead of only by a number.
    """

    button = 0
    lineedit = 1
    checkbox = 2
    progressbar = 3
    combobox = 4
    togglebutton = 5
    spinbox = 6
    doublespinbox = 7
    labeltext = 8
    hline = 9

    @classmethod
    def getWidget(cls, label, wType, init=None):
        """
        Return the widget of the correct type.

        Parameters
        ----------
        label : str
            Label of widget (used as a fallback string on the button if no init
            value is given).
        wType : int or guiObject
            Can be one of:
            * str : QLabel: string used as label text.
            * 0 : QPushButton
            * 1 : QLineEdit
            * 2 : QCheckBox
            * 3 : matr1xProgressBar/QProgressBar
            * 4 : QComboBox
            * 5 : QPushButton(checkable=True)
            * 6 : QSpinBox
            * 7 : QDoubleSpinBox
            * 8 : QLabel: used as Value indicator
            * 9 : QFrame: used to generate a horizontal separator line
        init : tuple, str, optional
            Provides the initialization values (button label, valid ranges,
            combobox entries).

        Returns
        -------
        QWidget or None
            Widget of requested type or None.

        Examples
        --------
        Generate a toggle button which changes its label upon being set:
        >>> getWidget("Property", guiObject.togglebutton, init=("Slow", "Fast"))

        Generate a QComboBox with prefilled options:
        >>> getWidget("Property", guiObject.combobox, init=("opt 1", "opt 2"))

        Generate a SpinBox (similar for DoubleSpinBox):
        >>> getWidget("Property", guiObject.spinbox, init=(0, 200))

        Generate a PushBotton with text "Set":
        >>> getWidget("Property", guiObject.button, init="Set")

        Generate a label with text "Example":
        >>> getWidget("Property", "Example")
        """
        widget_creation_methods = {
            str: lambda wType: cls._create_label_widget(wType),
            guiObject.labeltext: lambda init: cls._create_labeltext_widget(init),
            guiObject.button: lambda init: QPushButton(init if init else label),
            guiObject.lineedit: lambda init: QLineEdit(init if init else None),
            guiObject.checkbox: lambda init=None: QCheckBox(),
            guiObject.progressbar: lambda init: cls._create_progressbar_widget(init),
            guiObject.combobox: lambda init: cls._create_combobox_widget(init),
            guiObject.togglebutton: lambda init: ToggleButton(init if init else label),
            guiObject.spinbox: lambda init: cls._create_spinbox_widget(init),
            guiObject.doublespinbox: lambda init: cls._create_doublespinbox_widget(init),
            guiObject.hline: lambda init: cls._create_hline_widget(init),
        }

        if isinstance(wType, str):
            widget_type = str
        else:
            widget_type = wType if not isinstance(wType, int) else guiObject(wType)

        creation_method = widget_creation_methods.get(widget_type)

        if creation_method:
            return creation_method(init)
        return None

    @classmethod
    def _create_label_widget(cls, wType):
        qlab = QLabel(wType)
        qlab.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return qlab

    @classmethod
    def _create_labeltext_widget(cls, init):
        label = QLabel(init if init else None)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    @classmethod
    def _create_progressbar_widget(cls, init):
        pbar = matr1xProgressBar()
        if init:
            pbar.setValue(init)
        return pbar

    @classmethod
    def _create_combobox_widget(cls, init):
        qcombo = QComboBox()
        if init is not None:
            qcombo.insertItems(0, init)
        return qcombo

    @classmethod
    def _create_spinbox_widget(cls, init):
        sb = QSpinBox()
        if init is not None and len(init) == 2:
            sb.setRange(*init)
        return sb

    @classmethod
    def _create_doublespinbox_widget(cls, init):
        sb = QDoubleSpinBox()
        if init is not None and len(init) == 2:
            sb.setRange(*init)
        return sb

    @classmethod
    def _create_hline_widget(cls, init):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if init is not None:
            line.setFixedWidth(init)
        line.setMinimumHeight(2)
        return line


class var(QObject):
    """
    Variable storage for implementing with qt GUI.

    Emits valueChanged signal if the value has changed so it can
    be connected to a display.

    Parameters
    ----------
    dType : type or tuple of (type, type) or None
        Type of variable that is to be stored and its emitted type upon a value
        change.
    outType : type
        Type the emitted value should be cast into (only present for backward
        compatibility. should be set nowadays in the dtype argument).
    columns : list | str | int | guiObject, optional
        GUI elements needed for this variable. Typically here are two
        entries to view the current value in the first element and be able to
        alter it in the second. The values should be enumerations from guiObject.
        Will be converted to a list internally.
    unit : str, optional
        Unit string used in the label and data logging.
    log : bool or None, optional
        Boolean flag to set the default behavior in the logging config. If None,
        no checkbox is shown. If dType is None, this value is ignored.
    init : list, optional
        Initialization values. This should be a list of the same length as
        columns. If it is of non-list type its assumed to apply to all entries of
        columns equally.
    hide : bool, optional
        Flag to hide the variable in the GUI.
    """

    valueChanged = pyqtSignal([str], [float], [int], [bool])
    unitChanged = pyqtSignal([str])

    def __init__(
        self,
        dtype: type | tuple[type, type] | None = (float, str),
        outType: type | None = None,
        columns: list | str | int | guiObject | None = None,
        unit: str = "",
        log: bool | None = False,
        init: list | None = None,
        hide: bool = False,
    ):
        super().__init__()
        if isinstance(dtype, Iterable):
            self.variableType = dtype[0]
            self.outType = dtype[1]
        else:
            self.variableType = dtype
            self.outType = outType if outType is not None else dtype

        self._value = None
        self._unit = unit
        if self.variableType is None:
            self.log = None
        else:
            self.log = log
        self.init = init
        self.hide = hide
        if columns is None:
            self.columns = []
        elif not isinstance(columns, list):
            self.columns = [
                columns,
            ]
        else:
            self.columns = columns
        self.widgets = []

    def setValue(self, newValue):
        """
        Set the value of the variable.

        Parameters
        ----------
        newValue : Any
            The new value to set.
        """
        self.value = newValue

    @property
    def value(self):
        """
        Get the current value of the variable.

        Returns
        -------
        Any
            The current value of the variable.
        """
        return self._value

    @value.setter
    def value(self, newValue):
        """
        Set the value of the variable and emit a signal if it has changed.

        Parameters
        ----------
        newValue : Any
            The new value to set.
        """
        if newValue is None:
            self._value = None
            return
        # cast the value to the internal type (most likely float)
        self._value = self.variableType(newValue)
        # cast the output value to outType and emit matching signal
        self.valueChanged[self.outType].emit(self.outType(self._value))

    @property
    def unit(self):
        """
        Get the unit of the variable.

        Returns
        -------
        str
            The unit of the variable.
        """
        return self._unit

    @unit.setter
    def unit(self, newunit):
        """
        Set the unit of the variable and emit a signal.

        Parameters
        ----------
        newunit : str
            The new unit to set.
        """
        self._unit = newunit
        self.unitChanged[str].emit(self._unit)

    def generate_widgets(self, label=""):
        """
        Generate a list of Qt widgets corresponding to the label and columns.

        These widgets can be used to build a graphical user interface. The
        widgets property is filled with the corresponding items after this
        function was executed. Variable values will be automatically linked to
        these widgets with the connect_signal method.

        Parameters
        ----------
        label : str, optional
            The label for the widgets.

        Examples
        --------
        >>> var(int, columns=[guiObject.lineedit, guiObject.checkbox])
        # will result in a (visible) layout as follows:
        # QLabel(label) - QLineEdit - QCheckBox

        >>> var(int,
        ...     columns=[guiObject.combobox, guiObject.combobox],
        ...     init=("a", "b"))
        # results in:
        # QLabel(label) - QComboBox("a", "b") - QComboBox("a", "b")

        Note
        ----
        In all cases above the label and first GUI element will be
        declared read only since they are assumed to serve to show a value
        read-out from an instrument.

        In addition to the visible items a by default hidden checkbox will be
        added which shows and changes the logging preferences.
        """
        fulllabel = f"{label} ({self.unit})" if "" != self.unit else label
        self.widgets = [
            QLabel(fulllabel),
        ]

        for i, widget in enumerate(self.columns):
            if isinstance(self.init, list):
                widgetinit = self.init[i]
            else:
                widgetinit = self.init
            self.widgets.append(guiObject.getWidget(label, widget, widgetinit))

        # set sensible default values and disable readout column
        if len(self.widgets) > 1:
            if not isinstance(self.widgets[1], QCheckBox):
                self.widgets[1].sizeHint = lambda qsize=self.widgets[1].minimumSizeHint(): qsize
            if isinstance(self.widgets[1], QLineEdit):
                self.widgets[1].setReadOnly(True)
            elif isinstance(self.widgets[1], (QComboBox, QCheckBox)):
                self.widgets[1].setEnabled(False)
        # apply a validator
        if len(self.widgets) > 2:
            if not isinstance(self.widgets[2], QCheckBox):
                self.widgets[1].sizeHint = lambda qsize=self.widgets[1].minimumSizeHint(): qsize
            if isinstance(self.widgets[2], QLineEdit):
                val = validator.get(self.variableType, None)
                if val:
                    self.widgets[2].setValidator(val)

        # add config checkbox
        if len(self.widgets) > 1 and self.log is not None:
            # prepare checkbox for controlling the data logging
            # only add if there is a value attached to the display
            checkbox = QCheckBox()
            # state of logging
            checkbox.setChecked(self.log)
            checkbox.setVisible(False)
            self.widgets.append(checkbox)
        # connect variable value with the widgets
        self.connect_signal()
        if self.hide:
            for w in self.widgets:
                w.hide()

    def updateLabel(self, newunit):
        """
        Update the label of the widget with a new unit.

        Parameters
        ----------
        newunit : str
            The new unit to display in the label.
        """
        label = self.widgets[0].text()
        if re.search(r"\([^)]*\)", label):
            newlabel = re.sub(r"\([^)]*\)", f"({newunit})", label)
        else:
            newlabel = f"{label} ({newunit})"
        self.widgets[0].setText(newlabel)

    def getGUIvalue(self, column=2):
        """
        Return the value obtained from the GUI element in the respective column.

        The return value will be cast to the variableType.

        Parameters
        ----------
        column : int, optional
            Column index in the widget list to read the value from.

        Returns
        -------
        Any
            The value from the GUI element, cast to variableType.

        Raises
        ------
        TypeError
            If the GUI element type is unknown.
        """
        element = self.widgets[column]
        if isinstance(element, (QLineEdit, QLabel)):
            value = element.text()
        elif isinstance(element, (QSpinBox, QDoubleSpinBox, QProgressBar)):
            value = element.value()
        elif isinstance(element, QComboBox):
            if self.variableType in [int, float]:
                value = element.currentIndex()
            else:
                value = element.currentText()
        elif isinstance(element, (QCheckBox, QPushButton)):
            value = element.isChecked()
        else:
            raise TypeError(f"Unknown type of GUI element {type(element)}")
        # cast value and return
        return self.variableType(value)

    def connect_signal(self):
        """Connect the valueChanged signal to the corresponding widget."""
        if len(self.widgets) >= 2 and self.variableType is not None:
            if isinstance(self.widgets[1], (QLineEdit, QLabel)):
                # Handle automatic string conversion for text widgets
                if self.outType is str:
                    self.valueChanged[str].connect(self.widgets[1].setText)
                else:
                    # Create wrapper to convert non-string types to string
                    def string_wrapper(value):
                        self.widgets[1].setText(str(value))

                    self.valueChanged[self.outType].connect(string_wrapper)
            elif isinstance(self.widgets[1], (QSpinBox, QProgressBar)):
                # Handle automatic int conversion for spinboxes and progress bars
                if self.outType is int:
                    self.valueChanged[int].connect(self.widgets[1].setValue)
                else:
                    # Create wrapper to convert non-int types to int
                    def int_wrapper(value):
                        try:
                            self.widgets[1].setValue(int(value))
                        except (ValueError, TypeError):
                            pass

                    self.valueChanged[self.outType].connect(int_wrapper)
            elif isinstance(self.widgets[1], QDoubleSpinBox):
                # Handle automatic float conversion for double spinboxes
                if self.outType is float:
                    self.valueChanged[float].connect(self.widgets[1].setValue)
                else:
                    # Create wrapper to convert non-float types to float
                    def float_wrapper(value):
                        try:
                            self.widgets[1].setValue(float(value))
                        except (ValueError, TypeError):
                            pass

                    self.valueChanged[self.outType].connect(float_wrapper)
            elif isinstance(self.widgets[1], QComboBox):
                # Always connect both int and str signals like the original code
                # This allows combo boxes to be updated by either index or text
                # regardless of outType
                self.valueChanged[int].connect(self.widgets[1].setCurrentIndex)
                self.valueChanged[str].connect(self.widgets[1].setCurrentText)
            elif isinstance(self.widgets[1], QCheckBox):
                # Handle automatic bool conversion for checkboxes
                if self.outType is bool:
                    self.valueChanged[bool].connect(self.widgets[1].setChecked)
                else:
                    # Create wrapper to convert non-bool types to bool
                    def bool_wrapper(value):
                        try:
                            self.widgets[1].setChecked(bool(value))
                        except (ValueError, TypeError):
                            pass

                    self.valueChanged[self.outType].connect(bool_wrapper)
            if isinstance(self.widgets[0], QLabel):
                self.unitChanged[str].connect(self.updateLabel)

        # automatically copy state of checkbox to togglebutton
        if len(self.widgets) >= 3:
            if isinstance(self.widgets[2], ToggleButton) and isinstance(
                self.widgets[1], QCheckBox
            ):
                if self.widgets[2].isCheckable():
                    self.valueChanged[bool].connect(self.widgets[2].setChecked)

    def copy_value(self):
        """Copy the read values into the set field."""
        # check that a set-field exists, otherwise pass
        if len(self.columns) >= 2 and self.variableType is not None:
            try:
                if isinstance(self.widgets[2], (QLineEdit, QLabel)):
                    self.widgets[2].setText(str(self.value))
                elif isinstance(self.widgets[2], QComboBox) and self.variableType is int:
                    self.widgets[2].setCurrentIndex(self.value)
                elif isinstance(self.widgets[2], QComboBox) and self.variableType is str:
                    self.widgets[2].setCurrentText(self.value)
                elif isinstance(self.widgets[2], QCheckBox):
                    self.widgets[2].setChecked(bool(self.value))
                elif isinstance(self.widgets[2], QSpinBox):
                    self.widgets[2].setValue(int(self.value))
                elif isinstance(self.widgets[2], QDoubleSpinBox):
                    self.widgets[2].setValue(float(self.value))
            except TypeError:
                # allow a type mismatch in case a variable is not set
                if self.value is not None:
                    raise

    def __getitem__(self, idx):
        """
        Access GUI dictionary items for backward compatibility.

        This function shall be declared deprecated in future.

        Parameters
        ----------
        idx : int
            Index of the item to retrieve.

        Returns
        -------
        Any
            The requested item.

        Raises
        ------
        NotImplementedError
            If the index is not supported.
        """
        if idx == 0:
            return self
        if idx == 1:
            if self.widgets:
                return self.widgets
            if isinstance(self.columns, list):
                return self.columns + [
                    self.log,
                ]
            return [
                self.columns,
            ] + [
                self.log,
            ]
        if idx == 2:
            return self.unit
        raise NotImplementedError

    def __setitem__(self, idx, value):
        """
        Set an item in the GUI dictionary.

        This function provides backward compatible access to the GUI dictionary items.
        It will be deprecated in the future.

        Parameters
        ----------
        idx : int
            Index of the item to set.
        value : Any
            The value to set.

        Raises
        ------
        NotImplementedError
            If the index is not supported.
        """
        if idx == 1:
            self.widgets = value
        else:
            raise NotImplementedError

    def __len__(self):
        """
        Get the length of the GUI dictionary items.

        This function provides backward compatible access to the GUI dictionary items.
        It will be deprecated in the future.

        Returns
        -------
        int
            The length of the GUI dictionary items.
        """
        if self.unit:
            return 3
        return 2


class GuiDict(UserDict, ABC):
    """
    Custom dictionary representing elements and commands of the control GUI.

    Derived classes have to implement the 'refresh' method which shall read
    updated values from the hardware and write them into the local variable
    storage.

    Additionally a System object with related devices can be stored in this
    class as object variable.

    Important class variables which shall be overwritten are:

    Attributes
    ----------
    cmds : dict
        List of commands for this device.
        e.g.: cmds = {":v1": Command(int, "setV1", "V1"),
                      "*idn": Get(str, "id-string")}
    data : dict
        GUI dictionary elements.
        e.g.
        data = {"Example": var(None, columns=["Readout", "Setpoint"]),
                "V1": var(int, columns=[go.combobox, go.combobox],
                          log=True, init=("i1", "i2")),
                "V2": var(float, columns=[go.lineedit, go.lineedit], unit="mT"),
                "Set": var(None, columns=[go.button, go.button],
                           init=["Set", "Copy"]),
               }
    refresh_period : float
        Period (in seconds) in which the timer attempts to run the refresh method
        once. If the refresh method takes more execution time than this
        period it's called without further delay. It will never be called more
        often than once per this period. (default: 1 sec)
    allow_disabling : bool
        Flag to decide if the GuiDict can be disabled. If this is set to True the
        underlying devices should all provide a `close` method or be a pymeasure
        Instrument. Otherwise likely reenabling will fail.
    """

    cmds = {}
    data = {}
    refresh_period = 1
    allow_disabling = False

    class _Worker(QObject):
        """
        Worker object for the refresh thread.

        This is needed for the QTimer to work inside the QThread.

        Attributes
        ----------
        activity : pyqtSignal
            Signal to indicate an iteration of the refresh timer.
        panic : pyqtSignal
            Signal to indicate a panic state.
        sig_error : pyqtSignal
            Signal to report errors.
        """

        # activity signal to indicate an iteration of the refresh timer
        activity = pyqtSignal(str)
        panic = pyqtSignal(bool, str)
        sig_error = pyqtSignal(type, Exception, str)

        def __init__(self, target, interval, parent=None):
            super().__init__()
            self.target = target  # target function for the refresh loop
            self.interval = interval  # in milliseconds
            self.guidict = parent
            self._timer = QTimer()  # fake definition

        @pyqtSlot()
        @pyqtSlot(bool)
        @catchEmitError
        def run(self, copy=True):
            """
            Start the worker's refresh loop.

            Parameters
            ----------
            copy : bool, optional
                Whether to copy values from readout to set fields upon first run.
            """
            self._timer = QTimer()
            self._timer.setInterval(self.interval)
            counter = itertools.count(1)
            self._timer.timeout.connect(lambda: self._target(next(counter)))
            # start refresh immediately and then again after the timer timeout
            self.target(0)
            # copy values from readout to set fields upon first run
            if copy:
                self.guidict.copy_values()
            self._timer.start()

        @pyqtSlot()
        def stop(self):
            """Stop the worker's refresh loop."""
            self._timer.stop()
            self.activity.emit("lightgray")

        @catchEmitError
        def _target(self, count):
            """
            Encapsulate target function to emit the activity signal.

            Parameters
            ----------
            count : int
                The current iteration count.
            """
            if count % 2:
                self.activity.emit("green")
            else:
                self.activity.emit("lightgreen")
            self.target(count)

    def __init__(self):
        super().__init__(self.data)
        if not hasattr(self, "S"):
            self.S = system.System()
        self._refresh_thread = QThread()
        self._panic = False
        self.refresh_worker = self._Worker(
            target=self.refresh,
            interval=self.refresh_period_ms,
            parent=self,
        )
        self.refresh_worker.moveToThread(self._refresh_thread)
        self._refresh_thread.started.connect(self.refresh_worker.run)
        self._refresh_thread.finished.connect(self.refresh_worker.stop)
        # reference to parent object which it will save in after its assigned
        # this reference is used to raise an error on the parent if needed
        self.parent = None
        self.running = False
        self.showlog = False
        # buffer original commands
        normalize_cmds(self.cmds)
        self._orig_cmds = copy.deepcopy(self.cmds)
        # empty custom menu
        self.menu_actions = []
        # initialize all with None
        self._reset()

    def create_GUI(self):
        """
        Create a QDockWidget to be attached to the main control GUI.

        Also link all buttons to respective methods.

        Returns
        -------
        QDockWidget
            The created dock widget.
        """

        class MyQDockWidget(QDockWidget):
            """Modify QDockWidget to be able to track its closing."""

            dockClosed = pyqtSignal()

            def __init__(self, title, appname):
                super().__init__(title)
                self.application_name = appname
                self.setObjectName(f"{appname}-{title}")
                self.settings = QSettings("matr1x", appname)
                self.disabled = False
                self.extended = False

            @pyqtSlot()
            def saveCurrentState(self):
                """Save current dock geometry and enable state."""
                self.settings.beginGroup(self.windowTitle())
                self.settings.setValue("size", self.size())
                self.settings.setValue("pos", self.pos())
                self.settings.setValue("disabled", self.disabled)
                self.settings.setValue("extended", self.extended)
                self.settings.endGroup()

            def restoreState(self):
                """Load stored dock geometry and disable state."""
                self.settings.beginGroup(self.windowTitle())
                if self.settings.value("size") is not None:
                    self.resize(self.settings.value("size"))
                if self.settings.value("pos") is not None:
                    self.move(self.settings.value("pos"))
                self.disabled = self.settings.value("disabled", False, type=bool)
                self.extended = self.settings.value("extended", False, type=bool)
                self.settings.endGroup()

            def closeEvent(self, event):
                super().closeEvent(event)
                self.dockClosed.emit()

        self.dock = MyQDockWidget(list(self.keys())[0], self.parent.windowTitle())
        self.dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.dock.setAllowedAreas(Qt.DockWidgetArea.TopDockWidgetArea)
        dockcontainer = QWidget()
        column = QVBoxLayout(dockcontainer)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        self.dock.setWidget(dockcontainer)
        self.container = QWidget()
        self.container.setContentsMargins(10, 0, 10, 10)

        # add top controls (hiding/enable) to the content widget
        self.control_layout = QHBoxLayout()
        self.toolbar = QToolBar()
        style = MApplication.style()
        assert style is not None
        icon_size = style.pixelMetric(QStyle.PixelMetric.PM_SmallIconSize)
        self.toolbar.setIconSize(QSize(icon_size, icon_size))
        self.control_layout.addWidget(self.toolbar)
        self.extend_switch = QCheckBox()
        self.enable_switch = QCheckBox()

        has_hiding = any(variable.hide for variable in self.values())
        if has_hiding:
            self.extend_switch.stateChanged.connect(self.toggle_hidden)
            self.extend_switch.setChecked(False)
        if self.allow_disabling:
            self.enable_switch.stateChanged.connect(self.makeEnabled)
        column.addLayout(self.control_layout)
        column.addWidget(self.container)
        column.addStretch()

        # create content
        self.create_content()

        return self.dock

    def create_content(self):
        """
        Create the real content of the GuiDict.

        This function takes the variables from the GuiDict and generates
        the respective GUI widgets. If a user overwrites this function
        it will need to attach its output to self.container!
        """
        grid = QGridLayout(self.container)
        # create items of dictionary inside content
        for row, (key, variable) in enumerate(self.items()):
            variable.generate_widgets(key)
            for col, widget in enumerate(variable.widgets):
                # add widgets to the grid layout at the correct position
                # but skip hidden checkbox
                if col == 0 and row == 0:
                    continue
                grid.addWidget(widget, row, col, 1, 1)

    def toggle_hidden(self, state: bool) -> None:
        """
        Toggle the visibility of hidden widgets.

        Parameters
        ----------
        state : bool
            If True, show hidden widgets; if False, hide them.
        """
        if state:
            self.dock.extended = True
            for variable in self.values():
                if isinstance(variable, var) and variable.hide:
                    for i, w in enumerate(variable.widgets):
                        if (
                            variable.log is not None
                            and i == len(variable.widgets) - 1
                            and not self.showlog
                        ):
                            continue
                        w.show()
        else:
            self.dock.extended = False
            for variable in self.values():
                if isinstance(variable, var) and variable.hide:
                    for w in variable.widgets:
                        w.hide()

    def copy_values(self) -> None:
        """Copy the values from the first to the second column."""
        for variable in self.values():
            variable.copy_value()

    @property
    def refresh_period_ms(self) -> int:
        """
        Get the refresh period in milliseconds.

        Returns
        -------
        int
            The refresh period in milliseconds.
        """
        return int(self.refresh_period * 1000)

    def makeEnabled(self, state: int) -> None:
        """
        Enable or disable the GUI based on the given state.

        Parameters
        ----------
        state : int
            0 to disable, any other value to enable.
        """
        if state == 0:
            self.stop()
        else:
            self.start()
        self.dock.disabled = not self.enable_switch.isChecked()

    def restoreFeatures(self) -> None:
        """Restore features based on the enable switch setting."""
        if self.enable_switch.isChecked():
            self.container.setEnabled(True)
            if self.allow_disabling:
                self.dock.setFeatures(
                    self.dock.features() & ~QDockWidget.DockWidgetFeature.DockWidgetClosable
                )
        else:
            self.container.setEnabled(False)
            if self.allow_disabling:
                self.dock.setFeatures(
                    self.dock.features() | QDockWidget.DockWidgetFeature.DockWidgetClosable
                )

    def stop(self, wait: bool = True) -> None:
        """
        Disable GUI fields and the update loop.

        Parameters
        ----------
        wait : bool, optional
            Flag to make this function block up to twice the refresh period or
            until the refresh thread ended (default is True).

        Returns
        -------
        None
        """
        if self.running:
            self._refresh_thread.quit()
            if wait:
                self._refresh_thread.wait(2 * self.refresh_period_ms)
            self.restoreFeatures()
            self.S.reset()
            self.S.close()
            # reset variables and commands
            self._reset()
            self.running = False

    def _reset(self):
        """
        Reset all values and cmd functions to None.

        This is done to avoid logging or reporting something not
        updated.
        """
        for variable in self.data.values():
            variable.value = None
        for cmd in self.cmds.values():
            cmd.reset_to_None()

    @catchEmitError
    def start(self):
        """Start the refresh loop in a dedicated thread."""
        if not self.running and self.enable_switch.isChecked():
            # initialize the system
            self.S.set()
            # convert command function names to executables
            self.set_cmd_funcs(window_obj=self.parent, system=self.S)
            self.restoreFeatures()
            self._refresh_thread.start()
            self.running = True

    def set_cmd_funcs(self, window_obj=None, system=None):
        """
        Replace setter and getter functions by an instance of Command.

        Depending on the setter and getter functions type either the
        respective class methods, variables or device functions from the
        system are used.
        """
        # replace entries with executable functions
        for name, cmd in self._orig_cmds.items():
            setfunc, setargs = self._create_setfunc(name, cmd, window_obj, system)
            getfunc, getargs = self._create_getfunc(name, cmd, window_obj, system)

            # set new Command properties in existing list
            self.cmds[name].setfunc = setfunc
            self.cmds[name].getfunc = getfunc
            self.cmds[name].setargs = setargs
            self.cmds[name].getargs = getargs
        return self.cmds

    def _create_setfunc(self, name, cmd, window_obj=None, system=None):
        """
        Create the setter function from the command definition.

        The function determines what the user intended by the specified
        cmd and generates an appropriate function.
        """
        setargs = []
        setfunc = None

        if callable(cmd.setfunc):
            setfunc, setargs = self._handle_callable_setfunc(cmd)
        elif cmd.setfunc is None:
            setfunc = None
        elif isinstance(cmd.setfunc, str):
            setfunc, setargs = self._handle_string_setfunc(name, cmd, window_obj)
        elif isinstance(cmd.setfunc, (tuple, list)):
            setfunc, setargs = self._handle_tuple_setfunc(name, cmd, system)
        else:
            raise ValueError(f"could not identify '{cmd.setfunc}' of '{name}'")
        return setfunc, setargs

    def _handle_callable_setfunc(self, cmd):
        """Handle the case where setfunc is a callable."""
        setfunc = cmd.setfunc
        setargs = cmd.setargs
        return setfunc, setargs

    def _handle_string_setfunc(self, name, cmd, window_obj):
        """Handle the case where setfunc is a string."""
        if hasattr(self, cmd.setfunc):  # if GuiDict method or property
            attr = attrgetter(cmd.setfunc)(self)
            if callable(attr):
                setfunc = attr
                setargs = cmd.setargs
            else:

                def setfunc(value, c=self, a=cmd.setfunc):
                    setattr(c, a, value)

                setfunc = setfunc
                setargs = []
        elif cmd.setfunc in self:  # if GuiDict.data entry

            def setfunc(value, c=self.data[cmd.setfunc]):
                setattr(c, "value", value)

            setfunc = setfunc
            setargs = []
        elif hasattr(window_obj, cmd.setfunc):  # if ControlWindow method
            attr = attrgetter(cmd.setfunc)(window_obj)
            if callable(attr):
                setfunc = attr
                setargs = []
            else:

                def setfunc(value, c=window_obj, a=cmd.setfunc):
                    setattr(c, a, value)

                setfunc = setfunc
                setargs = []
        else:
            raise ValueError(f"could not identify '{cmd.setfunc}' of '{name}'")
        return setfunc, setargs

    def _handle_tuple_setfunc(self, name, cmd, system):
        """Handle the case where setfunc is a tuple or list (system device)."""
        if system is None:
            raise ValueError("System must be specified as 'system' keyword argument")
        devname, funcname = cmd.setfunc
        attr = attrgetter(funcname)(system.devs[devname])
        if callable(attr):
            setfunc = attr
            setargs = cmd.setargs
        else:

            def setfunc(value, c=system.devs[devname], a=funcname):
                setattr(c, a, value)

            setfunc = setfunc
            setargs = []
        return setfunc, setargs

    def _create_getfunc(self, name, cmd, window_obj=None, system=None):
        """
        Create the getter function from the command definition.

        The function determines what the user intended by the specified
        cmd and generates an appropriate function.
        """
        getargs = []
        getfunc = None

        if callable(cmd.getfunc):
            getfunc, getargs = self._handle_callable_getfunc(cmd)
        elif cmd.getfunc is None:
            getfunc = None
        elif isinstance(cmd.getfunc, str):
            getfunc, getargs = self._handle_string_getfunc(name, cmd, window_obj, system)
        elif isinstance(cmd.getfunc, (tuple, list)):
            getfunc, getargs = self._handle_tuple_getfunc(name, cmd, system)
        else:
            raise ValueError(f"could not identify '{cmd.getfunc}' of '{name}'")
        return getfunc, getargs

    def _handle_callable_getfunc(self, cmd):
        """Handle the case where getfunc is a callable."""
        getfunc = cmd.getfunc
        getargs = cmd.getargs
        return getfunc, getargs

    def _handle_string_getfunc(self, name, cmd, window_obj, system):
        """Handle the case where getfunc is a string."""
        getargs = []
        if hasattr(self, cmd.getfunc):  # if GuiDict method or property
            attr = attrgetter(cmd.getfunc)(self)
            if callable(attr):
                getfunc = attr
                getargs = cmd.getargs
            else:

                def getfunc(c=self, a=cmd.getfunc):
                    return getattr(c, a)

                getfunc = getfunc
        elif cmd.getfunc in self:  # if GuiDict.data entry

            def getfunc(c=self.data[cmd.getfunc]):
                return getattr(c, "value")

            getfunc = getfunc
        elif hasattr(window_obj, cmd.getfunc):  # if ControlWindow method
            attr = attrgetter(cmd.getfunc)(window_obj)
            if callable(attr):
                getfunc = attr
            else:

                def getfunc(c=window_obj, a=cmd.getfunc):
                    return getattr(c, a)

                getfunc = getfunc
        elif cmd.dtype == str and not cmd.getargs:

            def getfunc(v=cmd.getfunc):
                return cmd.dtype(v)

            getfunc = getfunc
        else:
            raise ValueError(f"could not identify '{cmd.getfunc}' of '{name}'")

        return getfunc, getargs

    def _handle_tuple_getfunc(self, name, cmd, system):
        """Handle the case where getfunc is a tuple or list (system device)."""
        if system is None:
            raise ValueError("System must be specified as 'system' keyword argument")
        devname, funcname = cmd.getfunc
        attr = attrgetter(funcname)(system.devs[devname])
        getargs = []
        if callable(attr):
            getfunc = attr
            getargs = cmd.getargs
        else:

            def getfunc(c=system.devs[devname], a=funcname):
                return getattr(c, a)

        return getfunc, getargs

    def panic(self):
        """
        Enable panic mode and put everyting to a save state.

        Should be overloaded by derived functions if needed.
        """
        self._panic = True
        self.enable_switch.setEnabled(False)

    def unpanic(self):
        """Make device operational again."""
        self.enable_switch.setEnabled(True)
        self._panic = False

    @abstractmethod
    def refresh(self, count):
        """
        Update values from the device and show them in the GUI.

        This method has to be implementated by every derived class.

        It should contain code to refresh the GUI values a single time
        (no endless loop). If some items should be updated infrequently
        it can be done by performing a modulo operation on the 'count'
        argument. Also it should never access the GUI elements directly
        but use the variable value properties which trigger an update to
        the GUI correctly by emitting a signal.
        """
        # an example implementation
        # self["V2"].value = self.S["dev"].get_value_from_hardware_somehow()
        # if count % 10 == 0:
        #     self["V1"].value = self.S["dev"].get_another_value()


class QtGracefulKiller:
    """Graceful killer, that handles the proper termination of Qt application."""

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signam, frame):
        """Terminates the application."""
        print(f"Kill signal received ({signam})")
        MApplication.quit()

    def __enter__(self):
        """Start a timer for Ctrl+C to work."""
        self.timer = QTimer()
        self.timer.timeout.connect(lambda: None)
        self.timer.start(100)

    def __exit__(self, exc_type, value, traceback):
        """
        Stop the timer when exiting the context manager.

        This method is called when exiting the context manager (i.e., at the end of the
        'with' statement). It stops the timer that was started in the __enter__ method.

        Parameters
        ----------
        exc_type : type
            The type of the exception that caused the context to be exited.
            None if the context was exited without an exception.
        value : Exception
            The instance of the exception that caused the context to be exited.
            None if the context was exited without an exception.
        traceback : traceback
            A traceback object encoding the stack trace.
            None if the context was exited without an exception.
        """
        self.timer.stop()


def linear_trend(timestamps, data, interval=60):
    """
    Calculate the linear trend of the data in the last 'interval' seconds.

    Parameters
    ----------
    timestamps : array-like
      time stamps of data in Unix-time in seconds (e.g. from `time.time()`)
    data : array-like
      past data points (most recent data point has index 0!).
      shape is assumed to be same for the two arguments
    interval : float, optional
      time interval of the data points which should be considered. Older data
      points are ignored.

    Note: best use collections.deque and appendleft to generate the needed data

    Returns
    -------
    slope, stdev
      slope and standard deviation of past `interval` seconds. If there are
      insufficient data points to calculate the statistics each value will be
      `None`.
    """
    ret = (None, None)
    mask = (time.time() - numpy.asarray(timestamps)) < interval
    t, y = numpy.asarray(timestamps)[mask], numpy.asarray(data)[mask]
    if len(t) >= 2:
        if numpy.all([isinstance(el, numbers.Number) for el in y]):
            slope = numpy.mean(numpy.gradient(y, t))
            std = numpy.std(y)
            ret = (slope, std)
    return ret


def sendNotificationEmail(
    address: str, subject: str, msgtext: str, attachments: list[str | Path] = []
) -> None:
    """
    Send messages to a list of email addresses.

    Utility function that uses the sendmail command line function which has to
    be configured to work as intended.

    Parameters
    ----------
    address : str
     email adress(es) in a comma seperated list
    subject : str
     email subject
    msgtext : str
     email message, can contain HTML code including img-tags
     (-> attach the image file)
    attachments: list
     list of file names of things to attach to the email.
    """
    # a check for valid email adresses should be added here!
    if address == "":
        return
    msg = MIMEMultipart()
    msg["To"] = address
    msg["Subject"] = subject
    mimetxt = MIMEText(msgtext, "html")
    msg.attach(mimetxt)
    # add attachments (code adapted from
    # https://docs.python.org/3.4/library/email-examples.html)
    for fname in attachments:
        fpath = Path(fname)
        if not fpath.is_file():
            continue
        # Guess the content type based on the file's extension.  Encoding
        # will be ignored, although we should check for simple things like
        # gzip'd or compressed files.
        ctype, encoding = mimetypes.guess_type(fpath)
        if ctype is None or encoding is not None:
            # No guess could be made, or the file is encoded (compressed),
            # so use a generic bag-of-bits type.
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        if maintype == "text":
            with fpath.open() as fp:
                # Note: we should handle calculating the charset
                att = MIMEText(fp.read(), _subtype=subtype)
        elif maintype == "image":
            with fpath.open("rb") as fp:
                att = MIMEImage(fp.read(), _subtype=subtype)
            att.add_header("Content-ID", f"<{fpath.name}>")
        elif maintype == "audio":
            with fpath.open("rb") as fp:
                att = MIMEAudio(fp.read(), _subtype=subtype)
        else:
            with fpath.open("rb") as fp:
                att = MIMEBase(maintype, subtype)
                att.set_payload(fp.read())
            # Encode the payload using Base64
            encoders.encode_base64(att)
        # Set the filename parameter
        att.add_header("Content-Disposition", "attachment", filename=fpath.name)
        msg.attach(att)

    # read email config
    if "email" in config["matr1x"]:
        conf = config["matr1x"]["email"]
        (smtp_srv, smtp_user, frommail, passwd) = [
            conf.get(field, None)
            for field in ("smtp_server", "smtp_user", "fromemail", "password")
        ]
        port = conf.get("smtp_port", 465)
    else:
        (smtp_srv, smtp_user, frommail, passwd) = (None,) * 4
        port = 465
    context = ssl.create_default_context()

    try:
        if (
            smtp_srv is not None
            and smtp_user is not None
            and frommail is not None
            and passwd is not None
        ):
            with smtplib.SMTP_SSL(smtp_srv, port, context=context) as server:
                server.login(smtp_user, passwd)
                server.send_message(msg, from_addr=frommail, to_addrs=address)
        elif os.name == "posix":
            p = Popen(["sendmail", "-t"], stdin=PIPE)
            p.communicate(msg.as_bytes())
            p.wait()
            logger = logging.getLogger(__name__)
            logger.info("notification email %s sent to %s", msgtext, address)
        else:
            print("no email configuration found; see documentation on how to set it up")
    except Exception as e:
        print(f"ignoring error during sending email: {e}")


class SelectLakeshoreInput(QDialog):
    """
    Open a dialog for selecting a sensor calibration curve for the Lakeshore temperature controller.

    This dialog allows the user to choose from a list of available calibration curves
    for the Lakeshore temperature controller. It displays the curve numbers and names,
    and allows the user to set the selected curve for the controller.

    Attributes
    ----------
    curves : dict
        A dictionary of available calibration curves, where keys are
        curve numbers and values are curve names.
    activeCurve : int
        The currently active curve number.
    curvesList : QListWidget
        A widget displaying the list of available curves.
    """

    def __init__(self, parent, lakeshore_dev=None):
        super().__init__(parent)
        self._dev = lakeshore_dev
        # read input curves
        self.curves = dict()
        for i in range(1, 60):
            self.curves[i] = self._dev.getCurveName(i)
        self.activeCurve = self._dev.getCurveNumber()
        self.initUI()
        self.show()

    def initUI(self):
        """Initialize GUI for popup."""
        self.setWindowTitle("Select Lakeshore input curve")
        grid = QGridLayout()

        self.curvesList = QListWidget()
        self.curvesList.addItems([f"{k}: {v}" for k, v in self.curves.items()])
        self.curvesList.setCurrentRow(self.activeCurve - 1)

        cancelButton = QPushButton("Cancel")
        cancelButton.clicked.connect(self.close)

        setCurveButton = QPushButton("Set")
        setCurveButton.clicked.connect(self.set_curve)

        grid.addWidget(self.curvesList, 0, 0, 10, -1)
        grid.addWidget(cancelButton, 10, 0)
        grid.addWidget(setCurveButton, 10, 1)
        self.setLayout(grid)

    def set_curve(self):
        """
        Set the selected calibration curve for the Lakeshore temperature controller.

        This method reads the selected curve from the QListWidget, sets
        it on the Lakeshore device if possible, and closes the dialog.
        """
        selectedcurve = int(self.curvesList.currentItem().text().split(":")[0])
        if hasattr(self._dev, "setCurveNumber"):
            self._dev.setCurveNumber(selectedcurve)
        self.close()


class TableModel(QtCore.QAbstractTableModel):
    """
    A table model for displaying PID parameters.

    This model is designed to work with a 2D numpy array containing
    PID parameters and related data.

    Parameters
    ----------
    data : numpy.ndarray
        A 2D numpy array containing the data to be displayed in the table.
    """

    def __init__(self, data: numpy.ndarray) -> None:
        super().__init__()
        self._data = data

    def data(self, index: QtCore.QModelIndex, role: int) -> str | None:
        """
        Return the data stored under the given role for the item referred to by the index.

        Parameters
        ----------
        index : QtCore.QModelIndex
            The index of the requested data.
        role : int
            The role for which the data is requested.

        Returns
        -------
        Union[str, None]
            The requested data as a string if the role is DisplayRole, None otherwise.
        """
        if role == Qt.ItemDataRole.DisplayRole:
            value = self._data[index.row(), index.column()]
            return str(value)
        return None

    def rowCount(self, index: QtCore.QModelIndex) -> int:
        """
        Return the number of rows in the model.

        Parameters
        ----------
        index : QtCore.QModelIndex
            The parent index (unused in this implementation).

        Returns
        -------
        int
            The number of rows in the data.
        """
        return self._data.shape[0]

    def columnCount(self, index: QtCore.QModelIndex) -> int:
        """
        Return the number of columns in the model.

        Parameters
        ----------
        index : QtCore.QModelIndex
            The parent index (unused in this implementation).

        Returns
        -------
        int
            The number of columns in the data.
        """
        return self._data.shape[1]

    def headerData(self, section: int, orientation: Qt.Orientation, role: int) -> str | QVariant:
        """
        Return the header data.

        Do that for the given role and section in the header with the
        specified orientation.

        Parameters
        ----------
        section : int
            The section number for which the header data is required.
        orientation : Qt.Orientation
            The orientation of the header (horizontal or vertical).
        role : int
            The role for which the data is requested.

        Returns
        -------
        Union[str, QVariant]
            The header data as a string if the conditions are met, QVariant() otherwise.
        """
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            if section == 0:
                return "T (K)"
            elif section == 1:
                return "P"
            elif section == 2:
                return "I"
            elif section == 3:
                return "D"
            elif section == 4:
                return "Heater range"
        return QVariant()


class WriteLakeshoreZonePID(QDialog):
    """
    Dialog to select a PID parameter table for use with the ZONE mode.

    The PID parameter file must be a text file which contains columns for:
    the upper temperature of the zones, P, I, D parameters, and heater range.
    A total of 10 entries are allowed.

    This dialog provides functionality to load a PID table from a file,
    display it in a table view, and write the parameters to the Lakeshore device.
    """

    def __init__(self, parent, lakeshore_dev=None):
        super().__init__(parent)
        self._dev = lakeshore_dev
        self.initUI()
        self.show()

    def initUI(self):
        """Initialize GUI for popup."""
        self.setWindowTitle("Select Lakeshore input curve")
        grid = QGridLayout()

        self.fileEdit = QLineEdit(self)
        self.fileEdit.setReadOnly(True)

        loadButton = QPushButton("Load PID Table")
        loadButton.clicked.connect(self.load_pid_table)

        grid.addWidget(self.fileEdit, 0, 0, 1, 2)
        grid.addWidget(loadButton, 0, 3)

        self.table = QTableView()
        # self.table.setReadOnly(True)
        grid.addWidget(self.table, 1, 0, 10, -1)

        self.writeButton = QPushButton("Write Table to Device")
        self.writeButton.clicked.connect(self.write_zone_to_device)
        self.writeButton.setEnabled(False)
        cancelButton = QPushButton("Cancel")
        cancelButton.clicked.connect(self.close)

        grid.addWidget(cancelButton, 12, 0)
        grid.addWidget(self.writeButton, 12, 1)

        self.setLayout(grid)

    def load_pid_table(self):
        """
        Load a PID table from a file and display it in the table view.

        This method opens a file dialog for the user to select a PID
        table file, loads the data from the file, creates a TableModel
        with the data, and sets it as the model for the table view. If
        the loaded data has the correct shape, it enables the write
        button.
        """
        filename = QFileDialog.getOpenFileName(
            self, "Select PID table file", usersfolder, "calibration file (*.*)"
        )[0]
        self.fileEdit.setText(filename)
        if filename != "":
            self.data = numpy.loadtxt(filename, unpack=True)
            self.model = TableModel(self.data.T)
            self.table.setModel(self.model)
            if len(self.data.shape) == 2 and self.data.shape[0] == 5:
                # if entries found enable write button
                self.writeButton.setEnabled(True)

    def write_zone_to_device(self):
        """
        Write the loaded PID table to the Lakeshore device.

        This method checks if the Lakeshore device has a 'writeZonePID'
        method. If it does, it calls this method with the loaded PID
        data as arguments. After writing the data (or if the method
        doesn't exist), it closes the dialog.
        """
        if hasattr(self._dev, "writeZonePID"):
            self._dev.writeZonePID(*self.data)
        self.close()


def control_main(
    name,
    window_class,
    guidicts=None,
    extra_cmds=None,
    lockfile=True,
    package="matr1x",
    **kwargs,
):
    """
    Run main function of control GUI.

    This function exists to avoid duplication in all control GUIs.

    Parameters
    ----------
    name : str
        Identifier string used as Window title and for the lock file.
    window_class : ControlWindow or QMainWindow
        Class derived from QMainWindow to be used to construct the GUI.
    guidicts : GuiDict, list or tuple of GuiDicts, optional
        GuiDict object(s) with the definition of the GUI.
    extra_cmds : dict, optional
        Dictionary with commands for the measurement interface. While most
        commands will be connected with the GuiDicts, those which do not fit there
        can be supplied here.
    lockfile : bool, optional
        Boolean flag to specify if a lockfile shall be created/checked to avoid
        multiple instances of the control GUI. Default is True.
    package : str, optional
        Package name to identify the desktop file. Default is "matr1x".
    **kwargs : dict
        Keyword arguments which are forwarded to the window_class constructor.
    """
    if sys.platform == "win32":
        try:
            from ctypes import windll

            myappid = f"python.{package}.{name}.version"
            windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except ImportError:
            pass

    app = MApplication(sys.argv)
    if os.name == "nt":
        # enable modern mode on windows which allows for darkmode
        app.setStyle("fusion")
    elif sys.platform == "darwin":
        set_correct_mac_appname(f"{name}")
    app.setDesktopFileName(f"python.{package}.{Path(sys.argv[0]).name}")

    if lockfile:
        lockfilename = Path(logfolder) / f"{package}_gui_{name}.lock"
        if lockfilename.exists():
            # check if process still running
            with lockfilename.open(encoding="utf-8") as lockf:
                otherpid = int(lockf.read())
            try:
                psutil.Process(otherpid)
                QMessageBox.critical(
                    QWidget(),
                    "Other instance running",
                    f"""Another instance of '{name}' was found running.
The control GUI can not start.
Kill the other process ({otherpid}) before restarting.""",
                )
                sys.exit()
            except psutil.NoSuchProcess:
                # this is the normal behavior in this case -> move on.
                pass
        # generate lockfile and write in the process ID
        with lockfilename.open("w", encoding="utf-8") as lockf:
            lockf.write(f"{os.getpid()}\n")

    kwargs["package"] = package
    logger = logging.getLogger(__name__)
    logger.info("Starting GUI")
    with QtGracefulKiller():
        with window_class(name, guidicts=guidicts, extra_cmds=extra_cmds, **kwargs):
            sys.stdout = OutputDuplication(sys.stdout, prefix=f"{package}.{name}")
            sys.stderr = OutputDuplication(
                sys.stderr, prefix=f"{package}.{name}", fallbackname="stderr"
            )
            ret = app.exec()
    logger.info("Exiting GUI")
    if lockfile:
        # clean exit, remove lockfile
        if lockfilename.exists():
            lockfilename.unlink()
    sys.stdout.close()
    sys.stderr.close()
    sys.stderr = sys.__stderr__
    sys.stdout = sys.__stdout__
    sys.exit(ret)
