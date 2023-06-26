# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2023 matr1x developers. All rights reserved.
# ---
"""
This module contains utility function for generating control guis or devices
based on the scpi_tcp_server
"""
import itertools
import logging
import mimetypes
import numbers
import os
import re
import signal
import sys
import time
import traceback
import warnings
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
from subprocess import PIPE, Popen

import numpy

try:
    from PyQt6 import QtCore
    from PyQt6.QtCore import (QObject, QSettings, Qt, QThread, QTimer, QVariant,
                              pyqtSignal, pyqtSlot)
    from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                                 QDockWidget, QDoubleSpinBox, QFileDialog,
                                 QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                                 QListWidget, QMessageBox, QProgressBar,
                                 QPushButton, QSizePolicy, QSpinBox, QTableView,
                                 QVBoxLayout, QWidget)
except ImportError:
    from PyQt5 import QtCore
    from PyQt5.QtCore import (QObject, QSettings, Qt, QThread, QTimer,
                              QVariant, pyqtSignal, pyqtSlot)
    from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                                 QDockWidget, QDoubleSpinBox, QFileDialog,
                                 QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                                 QListWidget, QMessageBox, QProgressBar,
                                 QPushButton, QSizePolicy, QSpinBox, QTableView,
                                 QVBoxLayout, QWidget)

from .. import datetimefmt, logfolder, system, usersfolder
from ..gui_util import validator
from ..util import normalize_cmds
from .qwidgets import AnimatedToggle, ToggleButton, matr1xProgressBar


def catchEmitError(method):
    """
    Define error handling decorator (works only with ControlWindow which defines
    a sig_error signal)
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
                    outstr = f"Ignoring last Exception since device can be deactivated."
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
    Enum object to make it easier to write readable code and identify GUI
    elements by their name instead of only by a number
    """
    button = 0
    lineedit = 1
    checkbox = 2
    progressbar = 3
    combobox = 4
    togglebutton = 5
    spinbox = 6
    doublespinbox = 7

    @classmethod
    def getWidget(cls, label, wType, init=None):
        """
        Retruns the widget of the correct type

        Parameters
        ----------
        label : str
          label of widget (used as a fallback string on the button if no init
          value is given)
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
        init : tuple, str, optional
          provides the initialization values (button label, valid ranges,
          combobox entries)

        Examples
        --------
        - Generate a toggle button which changes its label upon being set:
          getWidget("Property", guiObject.togglebutton, init=("Slow", "Fast"))
        - Generate a QComboBox with prefilled options:
          getWidget("Property", guiObject.combobox, init=("opt 1", "opt 2"))
        - Generate a SpinBox (similar for DoubleSpinBox):
          getWidget("Property", guiObject.spinbox, init=(0, 200))
        - Generate a PushBotton with text "Set":
          getWidget("Property", guiObject.button, init="Set")
        - Generate a label with text "Example":
          getWidget("Property", "Example")

        Returns
        -----
        widget : QWidget
          widget of requested type or None
        """
        if isinstance(wType, str):
            qlab = QLabel(wType)
            qlab.setSizePolicy(QSizePolicy.Policy.Preferred,
                               QSizePolicy.Policy.Fixed)
            return qlab
        if cls.button == wType:
            return QPushButton(init if init else label)
        if cls.lineedit == wType:
            return QLineEdit(init if init else None)
        if cls.checkbox == wType:
            return QCheckBox()
        if cls.progressbar == wType:
            return matr1xProgressBar()
        if cls.combobox == wType:
            dummy = QComboBox()
            if init is not None:
                dummy.insertItems(0, init)
            return dummy
        if cls.togglebutton == wType:
            return ToggleButton(init if init else label)
        if cls.spinbox == wType:
            sb = QSpinBox()
            if init is not None:
                sb.setRange(*init)
            return sb
        if cls.doublespinbox == wType:
            sb = QDoubleSpinBox()
            if init is not None:
                sb.setRange(*init)
            return sb
        return None


class var(QObject):
    """
    Variable storage for implementing with qt GUI,
    emits valueChanged signal if the value has changed so it can
    be connected to a display

    Parameters
    -----
    dType : type, or (type, type)
      type of variable that is to be stored and its emitted type upon a value
      change
    outType : type
      type the emitted value should be cast into (only present for backward
      compatibility. should be set nowadays in the dtype argument.
    columns: list
      list of GUI elements needed for this variable. typically here are two
      entries to view the current value in the first element and be able to
      alter it in the second. The values should be enumerations from guiObject.
    unit: str
      unit string used in the label and data logging.
    log: bool
      boolean flag to set the default behavior in the logging config
    init: list
      initialization values. This should be a list of the same length as
      columns. If it is of non-list type its assumed to apply to all entries of
      columns equally.
    """
    valueChanged = pyqtSignal([str], [float], [int], [bool])
    unitChanged = pyqtSignal([str])

    def __init__(self, dtype=(float, str), outType=str, columns=None, unit="",
                 log=False, init=None):
        super().__init__()
        if isinstance(dtype, Iterable):
            self.variableType = dtype[0]
            self.outType = dtype[1]
        else:
            self.variableType = dtype
            self.outType = outType

        self._value = None
        self._unit = unit
        self.log = log
        self.init = init
        if columns is None:
            self.columns = []
        elif not isinstance(columns, list):
            self.columns = [columns, ]
        else:
            self.columns = columns
        self.widgets = []

    def setValue(self, newValue):
        self.value = newValue

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, newValue):
        """
        if the value is set, emit a signal so that a possible change can be
        tracked
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
        return self._unit

    @unit.setter
    def unit(self, newunit):
        self._unit = newunit
        self.unitChanged[str].emit(self._unit)

    def generate_widgets(self, label=""):
        """
        Generates a list of Qt widgets corresponding to the label and columns.

        These widgets can be used to build a graphical user interface. The
        widgets property is filled with the corresponding items after this
        function was executed. Variable values will be automatically linked to
        these widgets with the connect_signal method.

        Example
        -----
        var((int, int), columns=[guiObject.lineedit, guiObject.checkbox])
        will result in a (visible) layout as follows

        QLabel(label) - QLineEdit - QCheckBox

        int to variable type conversion is specified in guiObject.getWidget,
        where the widget is also initialized.
        var((int, int),
            columns=[guiObject.combobox, guiObject.combobox],
            init=("a", "b"))
        results in:

        QLabel(label) - QComboBox("a", "b") - QComboBox("a", "b")

        Note: In all cases above the label and first GUI element will be
        declared read only since the are assumed to serve to show a value
        read-out from an instrument.

        In addition to the visible items a by default hidden checkbox will be
        added which showing and changing the logging preferences.
        """
        fulllabel = f"{label} ({self.unit})" if "" != self.unit else label
        self.widgets = [QLabel(fulllabel), ]

        for i, widget in enumerate(self.columns):
            if isinstance(self.init, list):
                widgetinit = self.init[i]
            else:
                widgetinit = self.init
            self.widgets.append(guiObject.getWidget(label, widget, widgetinit))

        # set sensible default values and disable readout column
        if len(self.widgets) > 1:
            if (not isinstance(self.widgets[1], QCheckBox)):
                self.widgets[1].sizeHint = lambda qsize=self.widgets[1].minimumSizeHint(
                ): qsize
            if isinstance(self.widgets[1], QLineEdit):
                self.widgets[1].setReadOnly(True)
            elif isinstance(self.widgets[1], (QComboBox, QCheckBox)):
                self.widgets[1].setEnabled(False)
        # apply a validator
        if len(self.widgets) > 2:
            if (not isinstance(self.widgets[2], QCheckBox)):
                self.widgets[1].sizeHint = lambda qsize=self.widgets[1].minimumSizeHint(
                ): qsize
            if isinstance(self.widgets[2], QLineEdit):
                val = validator.get(self.variableType, None)
                if val:
                    self.widgets[2].setValidator(val)

        # add config checkbox
        if len(self.widgets) > 1 and not isinstance(self.widgets[1],
                                                    (QLabel, QPushButton)):
            # prepare checkbox for controlling the data logging
            # only add if there is a value attached to the display
            checkbox = QCheckBox()
            # state of logging
            checkbox.setChecked(self.log)
            checkbox.setVisible(False)
            self.widgets.append(checkbox)
        # connect variable value with the widgets
        self.connect_signal()

    def updateLabel(self, newunit):
        label = self.widgets[0].text()
        if re.search(r'\([^)]*\)', label):
            newlabel = re.sub(r'\([^)]*\)', f'({newunit})', label)
        else:
            newlabel = f"{label} ({newunit})"
        self.widgets[0].setText(newlabel)

    def getGUIvalue(self, column=2):
        """
        return the value obtained from the GUI element in the respective
        column. The return value will be cast to the variableType.

        Parameters
        ----------
        column: int, optional
          column index in the widget list to read the value from.
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
        """
        connects the valueChanged signal of self.value to the corresponding
        widget
        """
        if len(self.widgets) >= 2:
            if isinstance(self.widgets[1], QLineEdit):
                self.valueChanged[str].connect(
                    self.widgets[1].setText)
            elif isinstance(self.widgets[1],
                            (QSpinBox, QProgressBar)):
                self.valueChanged[int].connect(
                    self.widgets[1].setValue)
            elif isinstance(self.widgets[1], QDoubleSpinBox):
                self.valueChanged[float].connect(
                    self.widgets[1].setValue)
            elif isinstance(self.widgets[1], QComboBox):
                self.valueChanged[int].connect(
                    self.widgets[1].setCurrentIndex)
                self.valueChanged[str].connect(
                    self.widgets[1].setCurrentText)
            elif isinstance(self.widgets[1], QCheckBox):
                self.valueChanged[bool].connect(
                    self.widgets[1].setChecked)
            if isinstance(self.widgets[0], QLabel):
                self.unitChanged[str].connect(
                    self.updateLabel)

        # automatically copy state of checkbox to togglebutton
        if len(self.widgets) >= 3:
            if (isinstance(self.widgets[2], ToggleButton) and
                    isinstance(self.widgets[1], QCheckBox)):
                if self.widgets[2].isCheckable():
                    self.valueChanged[bool].connect(
                        self.widgets[2].setChecked)

    def copy_value(self):
        """
        copies the read values into the set field
        """
        # check that a set-field exists, otherwise pass
        if len(self.columns) >= 2:
            if isinstance(self.widgets[2], QLineEdit):
                self.widgets[2].setText(str(self.value))
            elif isinstance(self.widgets[2], QComboBox):
                if self.variableType is int:
                    self.widgets[2].setCurrentIndex(self.value)
                if self.variableType is str:
                    self.widgets[2].setCurrentText(self.value)
            elif isinstance(self.widgets[2], QCheckBox):
                self.widgets[2].setChecked(bool(self.value))
            elif isinstance(self.widgets[2], QSpinBox):
                self.widgets[2].setValue(int(self.value))
            elif isinstance(self.widgets[2], QDoubleSpinBox):
                self.widgets[2].setValue(float(self.value))

    def __getitem__(self, idx):
        """
        function for backward compatible access to the GUI dictionary items.
        This function shall be declared deprecated in future.
        """
        if idx == 0:
            return self
        if idx == 1:
            if self.widgets:
                return self.widgets
            if isinstance(self.columns, list):
                return self.columns + [self.log, ]
            return [self.columns, ] + [self.log, ]
        if idx == 2:
            return self.unit
        raise NotImplementedError

    def __setitem__(self, idx, value):
        """
        function for backward compatible access to the GUI dictionary items.
        This function shall be declared deprecated in future.
        """
        if idx == 1:
            self.widgets = value
        else:
            raise NotImplementedError

    def __len__(self):
        """
        function for backward compatible access to the GUI dictionary items.
        This function shall be declared deprecated in future.
        """

        if self.unit:
            return 3
        return 2


class GuiDict(UserDict, ABC):
    """
    Custom dictionary representing elemens and commands related to part of the
    control GUI.

    Derived classes have to implement the 'refresh' method which shall read
    updated values from the hardware and write them into the local variable
    storage.

    Additionally a System object with related devices can be stored in this
    class as object variable.

    Important class variable which shall be overwritten are:

    cmds : dict
      list of commands for this device
      e.g.: cmds = {":v1", Command(int, "setV1", "V1"),
                    "*idn", Get(str, "id-string")}
    data : dict with var entries
      GUI dictionary elements
      e.g.
      data = {"Example": var(None, columns=["Readout", "Setpoint"]),
              "V1": var((int, int), columns=[go.combobox, go.combobox],
                        log=True, init=("i1", "i2")),
              "V2": var(float, columns=[go.lineedit, go.lineedit], unit="mT"),
              "Set": var(None, columns=[go.button, go.button],
                         init=["Set", "Copy"]),
             }
    refresh_period : float
      period (in seconds) in which the timer attempts to run the refresh method
      once. If the refresh method takes more executation time than this
      period its called without further delay. It will never be called more
      often then once per this period. (default: 1 sec)
    allow_disabling : bool
      flag to decide if the GuiDict can be disabled. If this is set to True the
      underlying devices should all provide a `close` method or be a pymeasure
      Instrument. Otherwise likely reenabling will fail.
    """
    cmds = {}
    data = {}
    refresh_period = 1
    allow_disabling = False

    class _Worker(QObject):
        """
        Worker object for the refresh thread. This is needed for the QTimer to
        work inside the QThread.
        """
        # activity signal to indicate an iteration of the refresh timer
        activity = pyqtSignal(str)
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
            self._timer.stop()
            self.activity.emit("lightgray")

        @catchEmitError
        def _target(self, count):
            """
            encapsulate target function to emit the activity signal
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

    def create_GUI(self):
        """
        Create a QDockWidget to be attached to the main control GUI.

        Also link all buttons to repective methods.
        """
        class MyQDockWidget(QDockWidget):
            """
            Modify QDockWidget to be able to track its closing
            """
            dockClosed = pyqtSignal()

            def __init__(self, title, appname):
                super().__init__(title)
                self.application_name = appname
                self.setObjectName(f"{appname}-{title}")
                self.settings = QSettings("matr1x", appname)
                self.disabled = False

            @pyqtSlot()
            def saveCurrentState(self):
                """
                Save current dock geometry and enable state.
                """
                self.settings.beginGroup(self.windowTitle())
                self.settings.setValue("size", self.size())
                self.settings.setValue("pos", self.pos())
                self.settings.setValue("disabled", self.disabled)
                self.settings.endGroup()

            def restoreState(self):
                """
                Load stored dock geometry and disable state.
                """
                self.settings.beginGroup(self.windowTitle())
                if self.settings.value("size") is not None:
                    self.resize(self.settings.value("size"))
                if self.settings.value("pos") is not None:
                    self.move(self.settings.value("pos"))
                self.disabled = self.settings.value(
                    "disabled", False, type=bool)
                self.settings.endGroup()

            def closeEvent(self, event):
                super().closeEvent(event)
                self.dockClosed.emit()

        self.dock = MyQDockWidget(
            list(self.keys())[0], self.parent.windowTitle())
        self.dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable |
            QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        dockcontainer = QWidget()
        column = QVBoxLayout(dockcontainer)
        self.dock.setWidget(dockcontainer)
        self.container = QWidget()

        # add enable widget to the content widget
        enable_layout = QHBoxLayout()
        enable_layout.addWidget(QLabel("Enable"))
        self.enable_switch = AnimatedToggle()
        self.enable_switch.setFixedSize(self.enable_switch.sizeHint())
        if self.allow_disabling:
            enable_layout.addWidget(self.enable_switch)
            self.enable_switch.stateChanged.connect(self.makeEnabled)
            column.addLayout(enable_layout)
        column.addWidget(self.container)
        column.addStretch()

        # create content
        self.create_content()

        return self.dock

    def create_content(self):
        """create the real content of the GuiDict

        This function takes the variables from the GuiDict and generates the
        respective GUI widgets. If a user overwrites this function it will need
        to attach its output to self.container!
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

    def copy_values(self):
        """
        Copies the values of a this GuiDict from the
        first to the second column.
        """
        for variable in self.values():
            variable.copy_value()

    @property
    def refresh_period_ms(self):
        """Return refresh period in milliseconds."""
        return int(self.refresh_period * 1000)

    def makeEnabled(self, state):
        if state == 0:
            self.stop()
        else:
            self.start()
        self.dock.disabled = not self.enable_switch.isChecked()

    def restoreFeatures(self):
        """
        restore features based on enable switch setting.
        """
        if self.enable_switch.isChecked():
            self.container.setEnabled(True)
            if self.allow_disabling:
                self.dock.setFeatures(
                    self.dock.features() &
                    ~QDockWidget.DockWidgetFeature.DockWidgetClosable
                )
        else:
            self.container.setEnabled(False)
            if self.allow_disabling:
                self.dock.setFeatures(
                    self.dock.features() |
                    QDockWidget.DockWidgetFeature.DockWidgetClosable
                )

    def stop(self, wait=True):
        """Disable GUI fields and the update loop

        Parameters
        wait: bool, optional
          flag to make this function block up to twice the refresh period or
          until the refresh thread ended
        """
        if self.running:
            self._refresh_thread.quit()
            if wait:
                self._refresh_thread.wait(2*self.refresh_period_ms)
            self.restoreFeatures()
            self.S.reset()
            self.S.close()
            # set all values to None to avoid showing/logging something not updated
            for variable in self.data.values():
                variable.value = None
            self.running = False

    def start(self):
        """Start the refresh loop in a dedicated thread."""
        if not self.running and self.enable_switch.isChecked():
            # initialize the system
            self.S.set()
            # convert command function names to executables
            self.set_cmd_funcs(window_obj=self.parent, sys=self.S)
            self.restoreFeatures()
            self._refresh_thread.start()
            self.running = True

    def set_cmd_funcs(self, window_obj=None, sys=None):
        """
        Replace setter and getter functions by the respective class methods,
        variables or device functions from the system.
        Also every entry is made to be an instance of Command.
        """
        normalize_cmds(self.cmds)
        # replace entries with executable functions
        for name, cmd in self.cmds.items():
            setargs = []
            getargs = []
            setfunc = None
            getfunc = None
            # obtain set function
            if callable(cmd.setfunc):
                setfunc = cmd.setfunc
                setargs = cmd.setargs
            elif cmd.setfunc is None:
                setfunc = None
            elif isinstance(cmd.setfunc, str):
                if hasattr(self, cmd.setfunc):  # if GuiDict method or property
                    attr = attrgetter(cmd.setfunc)(self)
                    if callable(attr):
                        setfunc = attr
                    else:
                        def setfunc(value, c=self, a=cmd.setfunc):
                            setattr(c, a, value)
                elif cmd.setfunc in self:  # if GuiDict.data entry
                    def setfunc(value, c=self.data[cmd.setfunc]):
                        setattr(c, "value", value)
                elif hasattr(window_obj, cmd.setfunc):  # if ControlWindow method
                    attr = attrgetter(cmd.setfunc)(window_obj)
                    if callable(attr):
                        setfunc = attr
                    else:
                        def setfunc(value, c=window_obj, a=cmd.setfunc):
                            setattr(c, a, value)
            elif isinstance(cmd.setfunc, (tuple, list)):
                # system device name and method
                if sys is None:
                    raise ValueError(
                        "System must be specified as 'sys' keyword argument")
                devname, funcname = cmd.setfunc
                attr = attrgetter(funcname)(sys.devs[devname])
                if callable(attr):
                    setfunc = attr
                else:
                    def setfunc(value, c=sys.devs[devname], a=funcname):
                        setattr(c, a, value)
            else:
                raise ValueError(
                    f"could not identify '{cmd.setfunc}' of '{name}'")

            # obtain get function
            if callable(cmd.getfunc):
                getfunc = cmd.getfunc
                getargs = cmd.getargs
            elif cmd.getfunc is None:
                getfunc = None
            elif isinstance(cmd.getfunc, str):
                if hasattr(self, cmd.getfunc):  # if GuiDict method or property
                    attr = attrgetter(cmd.getfunc)(self)
                    if callable(attr):
                        getfunc = attr
                    else:
                        getfunc = self.__getattribute__
                        getargs = [cmd.getfunc, ]
                elif cmd.getfunc in self:  # if GuiDict.data entry
                    def getfunc(c=self.data[cmd.getfunc]):
                        return getattr(c, "value")
                elif hasattr(window_obj, cmd.getfunc):  # if ControlWindow method
                    attr = attrgetter(cmd.getfunc)(window_obj)
                    if callable(attr):
                        getfunc = attr
                    else:
                        def getfunc(c=window_obj, a=cmd.getfunc):
                            return getattr(c, a)
                elif cmd.dtype == str and not cmd.getargs:
                    def getfunc(v=cmd.getfunc):
                        return cmd.dtype(v)
            elif isinstance(cmd.getfunc, (tuple, list)):
                # system device name and method
                if sys is None:
                    raise ValueError(
                        "System must be specified as 'sys' keyword argument")
                devname, funcname = cmd.getfunc
                attr = attrgetter(funcname)(sys.devs[devname])
                if callable(attr):
                    getfunc = attr
                else:
                    def getfunc(c=sys.devs[devname], a=funcname):
                        return getattr(c, a)
            else:
                raise ValueError(
                    f"could not identify '{cmd.getfunc}' of '{name}'")

            # set new Command properties in existing list
            self.cmds[name].setfunc = setfunc
            self.cmds[name].getfunc = getfunc
            self.cmds[name].setargs = setargs
            self.cmds[name].getargs = getargs
        return self.cmds

    def panic(self):
        """
        Enable panic mode and put everyting to a save state. Should be
        overloaded by derived functions if needed.
        """
        self._panic = True
        self.enable_switch.setEnabled(False)

    def unpanic(self):
        """
        Make device operational again
        """
        self.enable_switch.setEnabled(True)
        self._panic = False

    @abstractmethod
    def refresh(self, count):
        """
        Update values from the device and show them in the GUI.
        This method has to be implementated by every derived class.

        It should contain code to refresh the GUI values a single time (no
        endless loop). If some items should be updated infrequently it can be
        done by performing a modulo operation on the 'count' argument. Also it
        should never access the GUI elements directly but use the variable value
        properties which trigger an update to the GUI correctly by emitting a
        signal.
        """
        # an example implementation
        # self["V2"].value = self.S["dev"].get_value_from_hardware_somehow()
        # if count % 10 == 0:
        #     self["V1"].value = self.S["dev"].get_another_value()


class QtGracefulKiller():
    """
    Graceful killer, that handles the proper termination of Qt application
    """

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signam, frame):
        """
        terminates the application
        """
        print(f"Kill signal received ({signam})")
        QApplication.quit()

    def __enter__(self):
        """
        start a timer for Ctrl+C to work
        """
        self.timer = QTimer()
        self.timer.timeout.connect(lambda: None)
        self.timer.start(100)

    def __exit__(self, type, value, traceback):
        self.timer.stop()


def linear_trend(timestamps, data, interval=60):
    """
    Calculate the slope and standard deviation of the data in the last
    'interval' seconds.

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


def sendNotificationEmail(address, subject, msgtext, attachments=[]):
    """
    utility function to send messages to a list of email addresses. The function
    uses the sendmail command line function which has to be configured to work
    as intended!

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
    if address != '':
        msg = MIMEMultipart()
        msg["To"] = address
        msg["Subject"] = subject
        mimetxt = MIMEText(msgtext, 'html')
        msg.attach(mimetxt)
        # add attachments (code adapted from
        # https://docs.python.org/3.4/library/email-examples.html)
        for fname in attachments:
            if not os.path.isfile(fname):
                continue
            # Guess the content type based on the file's extension.  Encoding
            # will be ignored, although we should check for simple things like
            # gzip'd or compressed files.
            ctype, encoding = mimetypes.guess_type(fname)
            if ctype is None or encoding is not None:
                # No guess could be made, or the file is encoded (compressed),
                # so use a generic bag-of-bits type.
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)
            if maintype == 'text':
                with open(fname) as fp:
                    # Note: we should handle calculating the charset
                    att = MIMEText(fp.read(), _subtype=subtype)
            elif maintype == 'image':
                with open(fname, 'rb') as fp:
                    att = MIMEImage(fp.read(), _subtype=subtype)
                att.add_header('Content-ID', '<{}>'.format(fname))
            elif maintype == 'audio':
                with open(fname, 'rb') as fp:
                    att = MIMEAudio(fp.read(), _subtype=subtype)
            else:
                with open(fname, 'rb') as fp:
                    att = MIMEBase(maintype, subtype)
                    att.set_payload(fp.read())
                # Encode the payload using Base64
                encoders.encode_base64(msg)
            # Set the filename parameter
            att.add_header('Content-Disposition', 'attachment', filename=fname)
            msg.attach(att)

        try:
            p = Popen(["/usr/sbin/sendmail", "-t"], stdin=PIPE)
            p.communicate(msg.as_bytes())
            p.wait()
            logger = logging.getLogger(__name__)
            logger.info(
                "notification email {} sent to {}".format(msgtext, address))
        except Exception as e:
            print("ignoring error during sending email: {}".format(e))


class OutputRedirection:
    def __init__(self, stream, prefix='control', fallbackname=""):
        """
        object for output duplication into a file. Useful to avoid loss of
        output upon crash of GUI programs.
        """
        self.terminal = stream
        if stream is not None:
            name = stream.name.strip('<>')
        else:
            name = fallbackname
        self.log = open(os.path.join(logfolder, f"{prefix}-{name}.log"), "a")
        print(f"opening log: {self.log.name}")

    def write(self, message):
        if self.terminal is not None:
            self.terminal.write(message)
        if message != '\n':
            self.log.write(f"{time.strftime(datetimefmt)}: ")
        self.log.write(message)
        self.flush()

    def flush(self):
        if self.terminal is not None:
            self.terminal.flush()
        self.log.flush()

    def close(self):
        self.log.close()

    def __exit__(self):
        self.close()


class SelectLakeshoreInput(QDialog):
    """
    open dialog which allows the user to select a sensor calibration curve
    for the Lakeshore temperature controller
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
        """
        Initialize GUI for popup
        """
        self.setWindowTitle("Select Lakeshore input curve")
        grid = QGridLayout()

        self.curvesList = QListWidget()
        self.curvesList.addItems([f"{k}: {v}" for k, v in self.curves.items()])
        self.curvesList.setCurrentRow(self.activeCurve-1)

        cancelButton = QPushButton("Cancel")
        cancelButton.clicked.connect(self.close)

        setCurveButton = QPushButton("Set")
        setCurveButton.clicked.connect(self.set_curve)

        grid.addWidget(self.curvesList, 0, 0, 10, -1)
        grid.addWidget(cancelButton, 10, 0)
        grid.addWidget(setCurveButton, 10, 1)
        self.setLayout(grid)

    def set_curve(self):
        selectedcurve = int(self.curvesList.currentItem().text().split(":")[0])
        if hasattr(self._dev, "setCurveNumber"):
            self._dev.setCurveNumber(selectedcurve)
        self.close()


class TableModel(QtCore.QAbstractTableModel):

    def __init__(self, data):
        super(TableModel, self).__init__()
        self._data = data

    def data(self, index, role):
        if role == Qt.ItemDataRole.DisplayRole:
            # Note: self._data[index.row()][index.column()] will also work
            value = self._data[index.row(), index.column()]
            return str(value)

    def rowCount(self, index):
        return self._data.shape[0]

    def columnCount(self, index):
        return self._data.shape[1]

    def headerData(self, section, orientation, role):
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
    open dialog which allows the user to select PID parameter table for use
    with the ZONE mode.

    The PID parameter file must be a text file which contains columns for:
    The upper temperature of the zones, P, I, D parameters, and heater range.
    A total of 10 entries are allowed.
    """

    def __init__(self, parent, lakeshore_dev=None):
        super().__init__(parent)
        self._dev = lakeshore_dev
        self.initUI()
        self.show()

    def initUI(self):
        """
        Initialize GUI for popup
        """
        self.setWindowTitle("Select Lakeshore input curve")
        grid = QGridLayout()

        self.fileEdit = QLineEdit(self)
        self.fileEdit.setReadOnly(True)

        loadButton = QPushButton('Load PID Table')
        loadButton.clicked.connect(self.load_pid_table)

        grid.addWidget(self.fileEdit, 0, 0, 1, 2)
        grid.addWidget(loadButton, 0, 3)

        self.table = QTableView()
        # self.table.setReadOnly(True)
        grid.addWidget(self.table, 1, 0, 10, -1)

        self.writeButton = QPushButton('Write Table to Device')
        self.writeButton.clicked.connect(self.write_zone_to_device)
        self.writeButton.setEnabled(False)
        cancelButton = QPushButton("Cancel")
        cancelButton.clicked.connect(self.close)

        grid.addWidget(cancelButton, 12, 0)
        grid.addWidget(self.writeButton, 12, 1)

        self.setLayout(grid)

    def load_pid_table(self):
        # get filename from dialog
        filename = QFileDialog.getOpenFileName(
            self, 'Select PID table file', usersfolder,
            "calibration file (*.*)")[0]
        self.fileEdit.setText(filename)
        if filename != "":
            self.data = numpy.loadtxt(filename, unpack=True)
            self.model = TableModel(self.data.T)
            self.table.setModel(self.model)
            if len(self.data.shape) == 2 and self.data.shape[0] == 5:
                # if entries found enable write button
                self.writeButton.setEnabled(True)

    def write_zone_to_device(self):
        if hasattr(self._dev, "writeZonePID"):
            self._dev.writeZonePID(*self.data)
        self.close()


def control_main(name, window_class, guidicts=None, extra_cmds=None,
                 lockfile=True, package='matr1x', **kwargs):
    """
    Utility main function to avoid duplication in all control GUIs

    Parameters
    ----------
    name : str
      identifier string used as Window title and for the lock file
    window_class : ControlWindow, QMainWindow
      class derived from QMainWindow to be used to construct the GUI
    guidicts : list, tuple
      several GuiDict (or normal dict) objects with the description of the GUI
    extra_cmds : dict
      dictionary with commands for the measurement interface. While most
      commands will be connected with the GuiDicts those which do not fit there
      can be supplied here.
    lockfile : bool, optional
      boolean flag to specify if an lockfile shall be created/checked to avoid
      multiple instances of the control GUI
    package : str, optional
      package name to identify the desktop file
    kwargs : dict, optional
      keyword arguments which are forwarded to the window_class constructor
    """

    if os.name == 'nt':
        try:
            from ctypes import windll  # Only exists on Windows.
            myappid = f'python.{package}.{name}.version'
            windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except ImportError:
            pass

    if "_dummy" in os.path.basename(sys.argv[0]):
        warnings.warn(
            "The executable name 'control_dummy' is deprecated. Use 'control-dummy' instead.",
            FutureWarning)
    app = QApplication(sys.argv)
    app.setDesktopFileName(
        f"python.{package}.{os.path.basename(sys.argv[0])}.desktop")

    if lockfile:
        lockfilename = os.path.join(
            logfolder, f"{package}_gui_{name}.lock")
        if os.path.exists(lockfilename):
            QMessageBox.about(
                QWidget(), "Lockfile exists",
                f"""Lockfile ({lockfilename}) exists. The control GUI will not
                start. Please make sure everything is save! Only then remove
                the lockfile and restart the control GUI""")
            sys.exit()
        # generate lockfile
        with open(lockfilename, "w", encoding="utf-8") as lockf:
            lockf.write(f"{os.getpid()}\n")

    logger = logging.getLogger(__name__)
    logger.info("Starting GUI")
    with QtGracefulKiller():
        with window_class(name,
                          guidicts=guidicts,
                          extra_cmds=extra_cmds,
                          **kwargs):
            sys.stdout = OutputRedirection(sys.stdout, prefix=f"matr1x.{name}")
            sys.stderr = OutputRedirection(sys.stderr, prefix=f"matr1x.{name}",
                                           fallbackname="stderr")
            ret = app.exec()
    logger.info("Exiting GUI")
    if lockfile:
        # clean exit, remove lockfile
        if os.path.exists(lockfilename):
            os.remove(lockfilename)
    sys.stdout.close()
    sys.stderr.close()
    sys.stderr = sys.__stderr__
    sys.stdout = sys.__stdout__
    sys.exit(ret)
