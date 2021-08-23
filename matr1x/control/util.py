"""
This module contains utility function for generating control guis or devices
based on the scpi_tcp_server
"""
import itertools
import logging
import mimetypes
import os
import signal
from email import encoders
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from subprocess import PIPE, Popen

import numpy
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QLabel,
                             QLineEdit, QProgressBar, QPushButton)

from .. import logfolder


class var(QObject):
    """
    Variable storage for implementing with qt GUI,
    emits valueChanged signal if the value has changed so it can
    be connected to a display

    Parameters
    -----
    variableType : type
      type of variable that is to be stored
    outType : type
      type the emitted value should be cast into
    """
    # overloaded pyQt signal, has to be set here because it is implemented in a
    # subclass somehow
    valueChanged = pyqtSignal([str], [float], [int], [bool])

    def __init__(self, variableType, outType=str):
        super().__init__()
        self.variableType = variableType
        self.outType = outType

        self.value = None

    def setValue(self, newValue):
        """
        if the value is set, emit a signal so that a possible change can be
        tracked
        """
        # cast the value to the internal type (most likely float)
        self.value = self.variableType(newValue)
        # cast the output value to outType and emit matching signal
        self.valueChanged[self.outType].emit(self.outType(self.value))


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


def connectDictValueToDisplay(connDict):
    """
    connects the storage variable to the GUI display using the
    corresponding widgets slot and the value changed signal from
    our variable storage

    Parameters
    ----
    connDict : dictionary
      can be used to connect widgets of a sertain type to a signal emitted by a
      value change of the variable storage (variable of type var).

    connDict is contains the widget in conndict[key][1][1] and the value stored
    as var in connDict[key][0], it typically is the same layout that is used
    to create the layout using the constructLayout function.
    """
    for key in connDict:
        if type(connDict[key][1][1]) == QLineEdit:
            connDict[key][0].valueChanged[str].connect(
                connDict[key][1][1].setText)
        elif type(connDict[key][1][1]) == QProgressBar:
            connDict[key][0].valueChanged[float].connect(
                connDict[key][1][1].setValue)
        elif type(connDict[key][1][1]) == QComboBox:
            connDict[key][0].valueChanged[int].connect(
                connDict[key][1][1].setCurrentIndex)
        elif type(connDict[key][1][1]) == QCheckBox:
            connDict[key][0].valueChanged[bool].connect(
                connDict[key][1][1].setChecked)


def constructLayout(grid, cCol, layoutDict, layoutDictInit=None):
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
    layoutDictInit : dict
      If a combo box is specified in the layoutDict, the corresponding values
      that is should be populated with should be specified here

    Returns
    -----
    ncCount : int
      index of new rightmost column in the grid layout

    Example
    -----
    layoutDict["this row"][1] = [1, 2] will result in a layout as
    follows

    QLabel("this row") - QLineEdit - QCheckBox

    int to variable type conversion is specified in getWidgetType, where
    the widget is also initialized
    layoutDict["row2"][1] = [4, 4] and layoutDictInit["row2"] = ["a", "b"]

    QLabel("this row") - QComboBox("a", "b") - QComboBox("a", "b")
    """
    # number of columns that are added
    count = 0
    # current row
    row = 0
    for key in layoutDict:
        spec = layoutDict[key][1]
        if isinstance(spec, (tuple, list)):
            # iterable (i.e. multiple widgets in this row)
            if len(layoutDict[key][1]) > count:
                # make sure count corresponds to the longest column number
                count = len(layoutDict[key][1]) + 1
            dummy = []
            for widget in spec:
                if 4 == widget and layoutDictInit is not None:
                    # get initialized widget of correct type
                    try:
                        dummy.append(
                            getWidgetType(key, widget,
                                          layoutDictInit[key]))
                    except KeyError:
                        # key not found in initDict?!
                        print("key not found in initDict!?")
                else:
                    dummy.append(getWidgetType(key, widget))
        else:
            # not iterable, single widget in row
            if 2 > count:
                # if count is just one, set to two to have correct indicator
                # for column count
                count = 2
            if 4 == layoutDict[key][1] and layoutDictInit is not None:
                # we have a QComboBox and the corresponding initDict,
                # make sure key is present in the init dictionary
                try:
                    # get initialized widget of correct type
                    dummy = [getWidgetType(key, layoutDict[key][1],
                                           layoutDictInit[key])]
                except KeyError:
                    # key not found in initDict?!
                    print("key not found in initDict!?")
            else:
                # not a comboBox, so just
                # get initialized widget of correct type
                dummy = [getWidgetType(key, layoutDict[key][1])]

        if dummy[0].minimumWidth() < 100:
            dummy[0].setMinimumWidth(100)
        if type(dummy[0]) is QLineEdit:
            dummy[0].setReadOnly(True)
        elif type(dummy[0]) is QComboBox:
            dummy[0].setEnabled(False)
        elif type(dummy[0]) is QCheckBox:
            dummy[0].setEnabled(False)
        # replace spec with widgets in place
        layoutDict[key][1] = [QLabel(key)] + dummy
        # populate grid
        col = 0
        for widget in layoutDict[key][1]:
            # add widgets to the grid layout at the correct position
            if 1 == len(layoutDict[key][1]):
                grid.addWidget(widget, row, cCol+col, 1, 2)
                col += 2
            else:
                grid.addWidget(widget, row, cCol+col, 1, 1)
                col += 1
        row += 1
    return cCol + count


def getWidgetType(label, wType, init=None):
    """
    Retruns the widget of the correct type

    Parameters
    ----
    label : str
      label of widget/name of button
    wType : int
      Can be one of:

      * str : QLabel
      * 0 : QPushButton
      * 1 : QLineEdit
      * 2 : QCheckBox
      * 3 : QProgressBar
      * 4 : QComboBox
    init : list
      provides the values the QComboBox is initialized with

    Returns
    -----
    widget : QWidget
      widget of requested type or None
    """
    if isinstance(wType, str):
        return QLabel(wType)
    elif 0 == wType:
        return QPushButton(label)
    elif 1 == wType:
        return QLineEdit()
    elif 2 == wType:
        return QCheckBox()
    elif 3 == wType:
        dummy = QProgressBar()
        dummy.setRange(0, 100)
        return dummy
    elif 4 == wType:
        dummy = QComboBox()
        if init is not None:
            dummy.insertItems(0, init)
        return dummy
    else:
        return None


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
    for key in copyDict:
        if ((type(copyDict[key][1][1]) == QLineEdit and
             len(copyDict[key][1]) > 2)):
            copyDict[key][1][2].setText(
                copyDict[key][1][1].text())
        elif (type(copyDict[key][1][1]) == QProgressBar and
              len(copyDict[key][1]) > 2):
            copyDict[key][1][2].setText(str(
                copyDict[key][1][1].value()))
        elif (type(copyDict[key][1][1]) == QComboBox and
              len(copyDict[key][1]) > 2):
            try:
                copyDict[key][1][2].setCurrentIndex(
                    copyDict[key][1][1].currentIndex())
            except Exception:
                pass
        elif (type(copyDict[key][1][1]) == QCheckBox and
              len(copyDict[key][1]) > 2):
            copyDict[key][1][2].setChecked(
                copyDict[key][1][1].checkState())


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
        if(imax >= 2):
            slope = numpy.mean(numpy.gradient(
                list(itertools.islice(temp, 0, imax)),
                list(itertools.islice(-t, 0, imax))  # '-' represents past!
            ))
            ret = (slope, ret[1], ret[2])
    if len(where90) > 0:
        imax = where90[-1]
        if(imax >= 2):
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
    def __init__(self, stream, prefix='control'):
        """
        object for output duplication into a file. Useful to avoid loss of
        output upon crash of GUI programs.
        """
        self.terminal = stream
        name = stream.name.strip('<>')
        self.log = open(os.path.join(logfolder, f"{prefix}-{name}.log"), "a")
        print(f"opening log: {self.log}")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()
