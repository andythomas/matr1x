# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
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
import time
from collections.abc import Iterable
from email import encoders
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import IntEnum
from subprocess import PIPE, Popen

import numpy

try:
    from PyQt6 import QtCore
    from PyQt6.QtCore import QObject, Qt, QTimer, QVariant, pyqtSignal
    from PyQt6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                                 QDoubleSpinBox, QFileDialog, QGridLayout,
                                 QLabel, QLineEdit, QListWidget, QProgressBar,
                                 QPushButton, QSizePolicy, QSpinBox, QTableView)
except ImportError:
    from PyQt5 import QtCore
    from PyQt5.QtCore import QObject, Qt, QTimer, QVariant, pyqtSignal
    from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                                 QDoubleSpinBox, QFileDialog, QGridLayout,
                                 QLabel, QLineEdit, QListWidget, QProgressBar,
                                 QPushButton, QSizePolicy, QSpinBox, QTableView)

from .. import datetimefmt, logfolder, usersfolder


class matr1xProgressBar(QProgressBar):
    """
    overload Progressbar to make it better suite the needs to show values in
    the range between -5 and 105. Values outside that range are indicated by a
    red color
    """

    def __init__(self):
        super().__init__()
        self.setRange(-5, 105)
        self.setFormat("%v")

    def setValue(self, value):
        if value > self.maximum() or value < self.minimum():
            # change color
            self.reset()
            self.setStyleSheet("QProgressBar"
                               "{"
                               "background-color : red;"
                               "}")
        else:
            self.setStyleSheet("QProgressBar"
                               "{"
                               "}")

        super().setValue(value)


class ToggleButton(QPushButton):
    """
    custom QPushButton to emulate a proper toggle button (including the change
    of the button's label upon pushing)
    """

    def __init__(self, *args, **kwargs):
        if isinstance(args[0], (list, tuple)):
            label = args[0][0]
        else:
            label = args[0]
        super().__init__(label, **kwargs)
        self._labels = args[0]
        self.setCheckable(True)

    def setChecked(self, state):
        """
        change label of toggle button
        """
        super().setChecked(state)
        # if it is checked
        if isinstance(self._labels, (list, tuple)):
            if state:
                self.setText(self._labels[1])
            # if it is unchecked
            else:
                self.setText(self._labels[0])


class guiObject(IntEnum):
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
        elif cls.button == wType:
            return QPushButton(init if init else label)
        elif cls.lineedit == wType:
            return QLineEdit(init if init else None)
        elif cls.checkbox == wType:
            return QCheckBox()
        elif cls.progressbar == wType:
            return matr1xProgressBar()
        elif cls.combobox == wType:
            dummy = QComboBox()
            if init is not None:
                dummy.insertItems(0, init)
            return dummy
        elif cls.togglebutton == wType:
            return ToggleButton(init if init else label)
        elif cls.spinbox == wType:
            sb = QSpinBox()
            if init is not None:
                sb.setRange(*init)
            return sb
        elif cls.doublespinbox == wType:
            sb = QDoubleSpinBox()
            if init is not None:
                sb.setRange(*init)
            return sb
        else:
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
        else:
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
            elif isinstance(self.widgets[1], (QSpinBox, QDoubleSpinBox, QProgressBar)):
                self.valueChanged[int].connect(
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
            elif isinstance(self.widgets[2], (QSpinBox, QDoubleSpinBox)):
                self.widgets[2].setValue(int(self.value))

    def __getitem__(self, idx):
        """
        function for backward compatible access to the GUI dictionary items.
        This function shall be declared deprecated in future.
        """
        if idx == 0:
            return self
        elif idx == 1:
            if self.widgets:
                return self.widgets
            else:
                if isinstance(self.columns, list):
                    return self.columns + [self.log, ]
                else:
                    return [self.columns, ] + [self.log, ]
        elif idx == 2:
            return self.unit
        else:
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
        else:
            return 2


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


def constructLayout(grid, cCol, layoutDict):
    """
    Generates a multi column multi row layout as specified in
    layoutDict[key][1] starting at column cCol in gridLayout grid.
    Here, key will be used as label in the first column
    and the elements of the list (or single int) are used as one row
    Layout will always require three columns in the grid, where cCol specifies
    the leftmost.

    Replaces the widget specification in layoutDict by the initialized widgets
    in-place.

    Parameters
    -----
    grid : gridLayout
      basic grid that the layout is supposed to be added to
    cCol : int
      column index, where the layout is supposed to be added
    layoutDict : dict
      layout dict of correct format that describes the layout that is supposed
      to be generated

    Returns
    -----
    ncCount : int
      index of new rightmost column in the grid layout

    Example
    -----
    layoutDict["this row"] = var((int, int), columns=[guiObject.lineedit, guiObject.checkbox])
    will result in a layout as follows

    QLabel("this row") - QLineEdit - QCheckBox

    int to variable type conversion is specified in guiObject.getWidget, where
    the widget is also initialized.
    var((int, int), columns=[guiObject.combobox, guiObject.combobox], init=("a", "b"))
    results in:

    QLabel("this row") - QComboBox("a", "b") - QComboBox("a", "b")

    Note: In all cases above the label and first GUI element will be declared
    read only since the are assumed to serve to show a value read-out from an
    instrument.
    """
    # number of columns that are added
    count = 0
    # current row
    row = 0
    for key in layoutDict:

        spec = layoutDict[key].columns
        init = layoutDict[key].init
        if isinstance(spec, (tuple, list)):
            # iterable (i.e. multiple widgets in this row)
            if len(spec) >= count:
                # make sure count corresponds to the longest column number
                count = len(spec) + 1
            dummy = []
            for i, widget in enumerate(spec):
                if isinstance(init, list):
                    widgetinit = init[i]
                else:
                    widgetinit = init
                dummy.append(guiObject.getWidget(
                    key, widget, widgetinit))
        else:
            # not iterable, single widget in row
            if 2 > count:
                # if count is just one, set to two to have correct indicator
                # for column count
                count = 2
            dummy = [guiObject.getWidget(key, spec, init)]

        # set sensible default values and disable readout column
        if isinstance(dummy, (tuple, list)) and len(dummy) > 0:
            if dummy[0].minimumWidth() < 100:
                dummy[0].setMinimumWidth(100)
            if type(dummy[0]) is QLineEdit:
                dummy[0].setReadOnly(True)
            elif type(dummy[0]) is QComboBox:
                dummy[0].setEnabled(False)
            elif type(dummy[0]) is QCheckBox:
                dummy[0].setEnabled(False)

        # generate label for row
        unit = layoutDict[key].unit
        label = f"{key} ({unit})" if "" != unit else key

        # replace spec with widgets in place
        layoutDict[key].widgets = [QLabel(label)] + dummy
        # populate grid
        col = 0
        for i, widget in enumerate(layoutDict[key].widgets):
            # add widgets to the grid layout at the correct position
            # but skip hidden checkbox
            grid.addWidget(widget, row, cCol+col, 1, 1)
            col += 1
        if isinstance(dummy, (tuple, list)) and len(dummy) > 0 and not isinstance(dummy[0], (QLabel, QPushButton)):
            # prepare checkbox for controlling the data logging
            # only add if there is a value attached to the display
            checkbox = QCheckBox()
            # state of logging
            checkbox.setChecked(layoutDict[key].log)
            checkbox.setVisible(False)
            layoutDict[key].widgets.append(checkbox)
            # if layouts with more than three widgets should be possible
            # the following line should be redesigned
            grid.addWidget(checkbox, row, cCol+3, 1, 1)
        row += 1
    # connects the storage variable to the GUI display
    for var in layoutDict.values():
        var.connect_signal()

    # +1 for checkbox at the end of QLabel
    return cCol + count + 1


def copyValues(copyDict):
    """
    takes a data dict containing var variables and gui construction info and
    copies the read values into the set field
    The definition of the array can be found in constructLayout
    Replaces the values in-place

    Parameters
    ------
    copyDict : dict
      copies values from first column with values to second column with values
    """
    for var in copyDict.values():
        var.copy_value()


def temp_statistics(deltat, temp):
    """
    calculate temperature statistics (slope and standard deviation)

    Parameters
    ----------
    deltat : array-like
      time intervals between data points in seconds
    temp : array-like
      past temperature data points (most recent data point has index 0!).
      shape is assumed to be same for the two arguments

    Note: best use collections.deque and appendleft to generate the needed data

    Returns
    -------
    s30, s90, std90
      slope of past 30 and 90 seconds as well as standard deviation of last
      90 seconds. If there are insufficient data points to calculate the
      statistics each value will be None
    """
    t = numpy.cumsum(deltat) / 60  # convert time to min
    ret = (None, None, None)
    where30 = numpy.where(t < 3/6)[0]
    where90 = numpy.where(t < 1.5)[0]
    if len(where30) > 0:
        imax = where30[-1]
        if imax >= 2:
            if numpy.all([isinstance(el, numbers.Number) for el in
                          itertools.islice(temp, 0, imax)]):
                slope = numpy.mean(numpy.gradient(
                    list(itertools.islice(temp, 0, imax)),
                    list(itertools.islice(-t, 0, imax))  # '-' represents past!
                ))
                ret = (slope, ret[1], ret[2])
    if len(where90) > 0:
        imax = where90[-1]
        if imax >= 2:
            if numpy.all([isinstance(el, numbers.Number) for el in
                          itertools.islice(temp, 0, imax)]):
                slope = numpy.mean(numpy.gradient(
                    list(itertools.islice(temp, 0, imax)),
                    list(itertools.islice(-t, 0, imax))
                ))
                std = numpy.std(list(itertools.islice(temp, 0, imax)))
                ret = (ret[0], slope, std)
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


class OutputRedirection(object):
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
