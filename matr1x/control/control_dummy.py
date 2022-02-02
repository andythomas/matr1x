# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
import logging
import os
import sys
import time
import traceback

import numpy
from matr1x import logfolder
from matr1x.control import ControlWindow, catchEmitError
from matr1x.control.util import (OutputRedirection, QtGracefulKiller,
                                 connectDictValueToDisplay, constructLayout,
                                 copyValues, var)
from matr1x.devices.scpi_dev import makeSCPIdevice, set_cmd_funcs
from PyQt5.QtWidgets import QApplication, QMessageBox, QWidget

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
            ":v3": [float,
                    "v3", [],
                    "v3", []],
            ":v2": [float,
                    "v2", [],
                    "v2", []],
            ":v2v3": [[float, float],
                      "setV2V3", [],
                      "getV2V3", []],
            ":v4": [int,
                    "v4", [],
                    "v4", []],
            ":v5": [float,
                    "v5", [],
                    "v5", []],
            }

clientdevice = makeSCPIdevice(cmd_list)


class MainWindow(ControlWindow):
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
    # boolean (last value in list!): default value for logging parameter
    # A list means multiple widgets on one row
    # The init dicts contain the matching strings for initialization of the
    # combobox widget
    exampleDict = {"Example": [None, ["Readout", "Setpoint"]],
                   "V1": [var(int, int), [4, 4, True]],
                   "V2": [var(float), [1, 1], "mT"],
                   "V3": [var(float, int), [3, 1, True], "%"],
                   "V4": [var(bool, bool), [2, 2]],
                   "Set": [None, [0, 0]]}
    exampleDictInit = {"V1": ["i1", "i2"]}
    exampleDict2 = {"Example2": [None, ["Readout"]],
                    "V5": [var(float), [1], "mbar"]}

    def __init__(self):
        # initialize local variable storage
        self.v1 = 0
        self.v2 = 0
        self.v3 = 0
        self.v4 = False
        self.v5 = 0

        super().__init__("dummy", guidicts=[self.exampleDict,
                                            self.exampleDict2, ])

        # regenerate function entries in cmd_list
        self.cmd_list = set_cmd_funcs(self, cmd_list)

    # GUI functions
    def initUI(self):
        """
        Initializes GUI for chaosControl operation, i.e. display variable,
        allow chaning setpoints etc.

        Should be overloaded for real GUI
        """
        super().initUI()

        # construct the layout from the dicts specified above
        ccol = constructLayout(self.grid, 0, self.exampleDict,
                               self.exampleDictInit)
        constructLayout(self.grid, ccol, self.exampleDict2)

        # connect the set buttons to the corresponding set functions
        self.exampleDict["Set"][1][1].clicked.connect(self.write)
        self.exampleDict["Set"][1][2].setText("Copy")
        self.exampleDict["Set"][1][2].clicked.connect(lambda:
                                                      copyValues(self.exampleDict))

        # connect dict to readout displays
        connectDictValueToDisplay(self.exampleDict)
        connectDictValueToDisplay(self.exampleDict2)

    # device communication and related functions
    @catchEmitError
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
            self.v3 = float(self.exampleDict["V3"][1][2].text())
            self.v4 = bool(self.exampleDict["V4"][1][2].checkState())
        except ValueError:
            print("some value can not be converted to correct type")
            estr = traceback.format_exc()
            print(estr)

    @catchEmitError
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
        runDelay = 0.3
        # allows to speed up the process most of the time since we only read
        # the necessary values all the time
        # read the not so important values only every tenth time
        runInterval = 10
        runCounter = 0

        a = time.time()
        while self.terminate is False:
            b = time.time() - a
            if b < runDelay:
                # wait the remaining interval until 0.5
                time.sleep(runDelay-b)
                # always set the value (never change GUI directly!!!)
                self.exampleDict["V1"][0].setValue(self.v1)
                self.exampleDict["V2"][0].setValue(self.v2)
                self.exampleDict["V3"][0].setValue(self.v3)
                self.exampleDict["V4"][0].value = self.v4

                self.exampleDict2["V5"][0].setValue(self.v5)

            a = time.time()
            # refresh dicts of ITC and IPS (takes about 100ms each)
            if beginning is True:
                # initialize the setpoint columns (only once)
                # TODO: Maybe do this thirty seconds after a click or something
                # like that?
                time.sleep(0.1)  # sleep seems to be needed here on some setups
                copyValues(self.exampleDict)
                beginning = False
            if 0 == runCounter:
                # add tasks which run only upon every tenths iteration
                self.v5 = round(30*numpy.random.random(), 3)
            # make activity blink
            if runCounter % 2:
                self.activity.emit("green")
            else:
                self.activity.emit("lightgreen")
            runCounter = (runCounter+1) % runInterval
        # flag for stating that thread has ended
        self.terminated = True

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
        logfolder, os.path.splitext(os.path.split(__file__)[-1])[0] + ".lock")
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
