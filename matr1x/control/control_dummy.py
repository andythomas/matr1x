# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
import logging
import os
import sys
import time
import traceback
import warnings

import numpy
from matr1x import logfolder
from matr1x.control import ControlWindow, catchEmitError
from matr1x.control.util import OutputRedirection, QtGracefulKiller, copyValues
from matr1x.control.util import guiObject as go
from matr1x.control.util import var
from matr1x.devices.scpi_dev import makeSCPIdevice, set_cmd_funcs

try:
    from PyQt6.QtWidgets import QApplication, QMessageBox, QWidget
except ImportError:
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

if os.name == 'nt':
    try:
        from ctypes import windll  # Only exists on Windows.
        myappid = 'python.matr1x.control-dummy.version'
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass


class MainWindow(ControlWindow):
    """
    Define layout, runs everything
    """
    # Initialize dicts for GUI display as well as variable storage
    # Variables are stored in dict[key].value, GUI elements in dict[key].widgets
    # The GUI is initialized with the elements specified in dict[key].columns, where
    # key is label and
    # 0 : button
    # 1 : lineedit
    # 2 : checkbox
    # 3 : progress
    # 4 : combobox
    # A list means multiple widgets on one row
    # The unit of a variable can be set using the "unit" parameter and is then
    # shown in the label and included in the logging file. The logging
    # preference for the parameter is set by the boolean "log" parameter.
    exampleDict = {"Example": var(None, columns=["Readout", "Setpoint"]),
                   "V1": var((int, int), columns=[go.combobox, go.combobox],
                             log=True, init=["i1", "i2"]),
                   "V2": var(float, columns=[go.lineedit, go.lineedit], unit="mT"),
                   "V3": var(dtype=(float, int), columns=[go.progressbar, go.lineedit],
                             log=True, unit="%"),
                   "V4": var(dtype=(bool, bool), columns=[go.checkbox, go.checkbox]),
                   "toggle": var(dtype=(bool, bool), columns=[go.checkbox, go.togglebutton], init=["Slow", "Fast"]),
                   "Set": var(None, columns=[go.button, go.button],
                              init=["Set", "Copy"]),
                   }
    exampleDict2 = {"Example2": var(None, columns="Readout"),
                    "V5": var(float, columns=1, unit="mbar"),
                    }

    def __init__(self):
        # initialize local variable storage
        self.v1 = 1
        self.v2 = 0
        self.v3 = 5.5
        self.v4 = False
        self.v5 = 0
        self.toggle = False

        super().__init__("dummy", guidicts=[self.exampleDict,
                                            self.exampleDict2, ])

    # GUI functions
    def initUI(self):
        """
        Initializes GUI for chaosControl operation, i.e. display variable,
        allow chaning setpoints etc.

        Should be overloaded for real GUI
        """
        super().initUI()

        # connect the set buttons to the corresponding set functions
        self.exampleDict["Set"].widgets[1].clicked.connect(self.write)
        self.exampleDict["Set"].widgets[2].clicked.connect(
            lambda: copyValues(self.exampleDict))
        # connect the toggle buttons to the corresponding functions
        self.exampleDict["toggle"].widgets[2].clicked.connect(
            self.setToggleFunction)

    # device communication and related functions
    @catchEmitError
    def connectDev(self):
        """
        init device connections
        """
        if self.devInit is False:
            # regenerate function entries in cmd_list
            self.cmd_list = set_cmd_funcs(self, cmd_list)
            self.devInit = True

    def write(self):
        try:
            self.setV1(self.exampleDict["V1"].getGUIvalue())
            self.v2 = self.exampleDict["V2"].getGUIvalue()
            self.v3 = self.exampleDict["V3"].getGUIvalue()
            self.v4 = self.exampleDict["V4"].getGUIvalue()
        except ValueError:
            print("some value can not be converted to correct type")
            estr = traceback.format_exc()
            print(estr)

    def setToggleFunction(self):
        """
        set toggle button functionality in hardware
        """
        # if it is checked
        if self.exampleDict["toggle"].widgets[2].isChecked():
            # here should go code to set the feature in the hardware
            self.toggle = True
        # if it is unchecked
        else:
            # here should go code to unset the feature in the hardware
            self.toggle = False

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
        run_delay = 0.3
        # allows to speed up the process most of the time since we only read
        # the necessary values all the time
        # read the not so important values only every tenth time
        run_interval = 10
        run_counter = 0

        while not self.terminate:
            start_time = time.time()
            # always set the value (never change GUI directly!!!)
            self.exampleDict["V1"].value = self.v1
            self.exampleDict["V2"].value = self.v2
            self.exampleDict["V3"].value = self.v3
            self.exampleDict["V4"].value = self.v4
            self.exampleDict["toggle"].value = self.toggle

            self.exampleDict2["V5"].value = self.v5

            # refresh dicts of ITC and IPS (takes about 100ms each)
            if beginning is True:
                # initialize the setpoint columns (only once)
                # TODO: Maybe do this thirty seconds after a click or something
                # like that?
                time.sleep(0.1)  # sleep seems to be needed here on some setups
                copyValues(self.exampleDict)
                beginning = False
            if 0 == run_counter:
                # add tasks which run only upon every tenths iteration
                self.v5 = round(30*numpy.random.random(), 3)
            # make activity blink
            if run_counter % 2:
                self.activity.emit("green")
            else:
                self.activity.emit("lightgreen")
            run_counter = (run_counter+1) % run_interval

            step_time = time.time() - start_time
            if step_time < run_delay:
                # wait the remaining interval until 0.5
                time.sleep(run_delay-step_time)

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
    if "_" in os.path.basename(sys.argv[0]):
        warnings.warn(
            "The executable name 'control_dummy' is deprecated. Use 'control-dummy' instead.",
            FutureWarning)
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
