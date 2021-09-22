import logging
import os
import sys
import threading
import time
import traceback

from matr1x import logfolder, scpi_tcpserver
from matr1x.devices.scpi_dev import makeSCPIdevice, set_cmd_funcs
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (QApplication, QGridLayout, QMainWindow,
                             QMessageBox, QPlainTextEdit, QWidget)

from ..gui_util import EmittingStream
from .util import (OutputRedirection, QtGracefulKiller,
                   connectDictValueToDisplay, constructLayout, copyValues, var)

logger = logging.getLogger(os.path.split(__file__)[-1])

# format is "LayoutKey": [type, setFunction, additional args,
#                               GetFunction, additional args,
#                         [optional polling command]]
# LayoutKey: first four characters after ':' must be unique
# type can be one of int, float, bool, tuple or list.
cmd_list = {"*idn": [None, None, [], str,
                     ["dummy_control"]],
            ":v1": [int,
                    "setV1", [],
                    "v1", []],
            ":v2": [float,
                    "v2", [],
                    "v2", []],
            ":v2v3": [[float, bool],
                      "setV2V3", [],
                      "getV2V3", []],
            "v3": [bool,
                   "v3", [],
                   "v3", []],
            }

clientdevice = makeSCPIdevice(cmd_list)


class MainWindow(QMainWindow):
    """
    Define layout, runs everything
    """
    # Initialize dicts for GUI display as well as variable storage
    # Variables are stored in dict[key][0], GUI elements in dict[key][1]
    # The GUI is initialized with the elements specified in dict[key][1], where
    # key is label and
    # 0 : button
    # 1 : lineedit
    # 2 : checkbox
    # 3 : progress
    # 4 : combobox
    # A list means multiple widgets on one row
    # The init dicts contain the matching strings for initialization of the
    # combobox widget
    exampleDict = {"Example": [None, ["Readout", "Setpoint"]],
                   "V1": [var(int, int), [4, 4]],
                   "V2": [var(float), [1, 1]],
                   "V3": [var(bool, bool), [2, 2]],
                   "Set": [None, [0, 0]]}
    exampleDictInit = {"V1": ["i1", "i2"]}
    sig_error = pyqtSignal([Exception, str])

    def __init__(self):
        super().__init__()
        self.setWindowTitle("dummy")
        # initialize paramaters
        self.running = False
        self.terminate = False
        self.terminated = False
        self.devInit = False
        self.sig_error.connect(self.handleError)
        # initialize local variable storage
        self.v1 = 0
        self.v2 = 0
        self.v3 = False
        self.localServer = None
        # initialize GUI
        self.initUI()
        self.show()

        self.output_stream = EmittingStream(text_written=self.output_written)
        # set outputStream as stdout (i.e. all output is written to status
        # preview
        sys.stdout = self.output_stream

        # regenerate function entries in cmd_list
        self.cmd_list = set_cmd_funcs(self, cmd_list)

    # GUI functions
    def initUI(self):
        """
        Initializes GUI for chaosControl operation, i.e. display variable,
        allow chaning setpoints etc.

        Should be overloaded for real GUI
        """
        self.widget = QWidget()
        self.grid = QGridLayout()

        # construct the layout from the dicts specified above
        constructLayout(self.grid, 0, self.exampleDict, self.exampleDictInit)

        self.status = QPlainTextEdit(self)
        self.status.setReadOnly(True)
        self.grid.addWidget(self.status, self.grid.rowCount(), 0, 1, -1)

        # connect the set buttons to the corresponding set functions
        self.exampleDict["Set"][1][1].clicked.connect(self.write)
        self.exampleDict["Set"][1][2].setText("Copy")
        self.exampleDict["Set"][1][2].clicked.connect(lambda:
                                                      copyValues(self.exampleDict))

        # connect dict to readout displays
        connectDictValueToDisplay(self.exampleDict)

        self.widget.setLayout(self.grid)
        self.setCentralWidget(self.widget)

    def output_written(self, text):
        """
        appends the most recent text to the end of the display and makes sure
        that the cursor remains at the end
        """
        if text.strip("\n") != "":
            self.status.appendPlainText(text.strip("\n"))
            self.status.moveCursor(QTextCursor.End)

    # device communication and related functions
    def connectDev(self):
        """
        init device connections
        """
        if self.devInit is False:
            self.devInit = True

    def write(self):
        try:
            v1 = int(self.exampleDict["V1"][1][2].currentIndex())
            self.setV1(v1)
            self.v2 = float(self.exampleDict["V2"][1][2].text())
            self.v3 = bool(self.exampleDict["V3"][1][2].checkState())
        except ValueError:
            print("some value can not be converted to correct type")
            estr = traceback.format_exc()
            print(estr)

    def refreshDict(self):
        """
        This is the main loop!
        Here, the read out is conducted (thread safe) and the newest
        values are stored/updated in the value storage of the respective dicts
        """
        # on first run also initialize the second GUI element using the
        # copy values function
        beginning = True
        # update delay of the refresh function. Can not be significantly
        # lower than 1s usually (limited by device communication)
        # if device communication takes longer, read as fast as possible
        runDelay = 0.1
        # allows to speed up the process most of the time since we only read
        # the necessary values all the time
        # read the not so important values only every tenth time
        runInterval = 10
        runCounter = 0

        a = time.time()
        while self.terminate is False:
            try:
                b = time.time() - a
                if b < runDelay:
                    # wait the remaining interval until 0.5
                    time.sleep(runDelay-b)
                    # always set the value (never change GUI directly!!!)
                    self.exampleDict["V1"][0].setValue(self.v1)
                    self.exampleDict["V2"][0].setValue(self.v2)
                    self.exampleDict["V3"][0].setValue(self.v3)

                a = time.time()
                # refresh dicts of ITC and IPS (takes about 100ms each)
                if beginning is True:
                    # initialize the setpoint columns (only once)
                    # TODO: Maybe do this thirty seconds after a click or something
                    # like that?
                    copyValues(self.exampleDict)
                    time.sleep(0.2)
                    beginning = False
                if 0 == runCounter:
                    # ovcDict
                    pass
                runCounter = (runCounter+1) % runInterval
            except Exception as exc:
                # report error to the main thread
                self.sig_error.emit(exc, "refreshDict")
                # end the refreshDict thread
                self.terminate = True
        # flag for stating that thread has ended
        self.terminated = True
        time.sleep(100)  # avoid deleting of objects prematurely

    # general local server and start stop overhead
    def __enter__(self):
        """
        starts refreshing the values in a separate thread
        check also that the devices are initialized
        """
        # initialize devices
        print("initializing devices")
        try:
            self.connectDev()
        except Exception as exc:
            self.sig_error.emit(exc, "device initialization")

        # initialize thread to refresh dicts
        # check if successful
        if self.devInit is True:
            self.t = threading.Thread(target=self.refreshDict, daemon=True)
            self.t.start()
            self.running = True
            self.startServer()

    def __exit__(self, exc_type, exc_value, traceback):
        """
        stops the refreshDict function and closes devices
        """
        if exc_type is not None:
            print(exc_type, exc_value, traceback)

        self.stopServer()
        if self.running is True:
            self.terminate = True
            self.runnnig = False
            # wait for refreshDict to terminate
            while self.terminated is False:
                time.sleep(0.01)

    def startServer(self):
        """
        starts the local TCP server with the driver functions specified
        in self.cmd_list
        """
        self.localServer = scpi_tcpserver.SCPI_TCP_Server(self.cmd_list)
        self.localServer.start()

    def stopServer(self):
        """
        stops the local TCP server
        """
        if self.localServer is not None:
            self.localServer.stop()
        self.localServer = None

    def handleError(self, exc, pointer):
        # disable all GUI elements but the status display
        for i in reversed(range(self.grid.count())):
            self.grid.itemAt(i).widget().setEnabled(False)
        self.status.setEnabled(True)
        # stop SCPI server to reflect that something is wrong instead of
        # returning the same reading over and over
        self.stopServer()
        # print verbose error message to status display and open popup warning
        traceback.print_tb(exc.__traceback__, file=self.output_stream)
        a = QMessageBox.critical(
            self, f"Error in {pointer}",
            f"""The following error was raised in {pointer}:
            {repr(exc)}
            Please investigate the error and eventually restart the graphical user interface""")

    # driver functions begin here
    # example functions
    def setV1(self, val):
        if 0 == val or 1 == val:
            self.v1 = val

    def setV2V3(self, val):
        self.v2 = val[0]
        self.v3 = val[1]

    def getV2V3(self):
        return [self.v2, self.v3]


def main():
    app = QApplication(sys.argv)

    lockfilename = os.path.join(
        logfolder, os.path.splitext(os.path.split(__file__)[-1])[0])
    if os.path.exists(lockfilename):
        QMessageBox.about(
            QWidget(), "Lockfile exists",
            f"""Lockfile ({lockfilename}) exists. The control GUI will not
            start. Please make sure everything is save! Only then remove the
            lockfile and restart the control GUI""")
        sys.exit()
    # generate lockfile
    with open(lockfilename, "w") as f:
        f.write(f"{os.getpid()}\n")

    logger.info("Starting GUI")
    with QtGracefulKiller():
        with MainWindow():
            sys.stdout = OutputRedirection(sys.stdout, prefix='dummy_control')
            sys.stderr = OutputRedirection(sys.stderr, prefix='dummy_control',
                                           fallbackname="stderr")
            ret = app.exec()
    logger.info("Exiting GUI")
    # clean exit, remove lockfile
    if os.path.exists(lockfilename):
        os.remove(lockfilename)
    sys.stdout = sys.__stdout__
    sys.exit(ret)
