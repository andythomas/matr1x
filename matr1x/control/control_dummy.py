# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2024 matr1x developers. All rights reserved.
# ---

import collections
import time
import warnings

import numpy
from matr1x import system
from matr1x.control import ControlWindow, GuiDict, catchEmitError, control_main
from matr1x.control import guiObject as go
from matr1x.control import linear_trend, var
from matr1x.devices.dummy import dummy
from matr1x.devices.scpi_dev import makeSCPIdevice
from matr1x.util import Command, Get

try:
    from PyQt6 import QtCore
except ImportError:
    warnings.warn("PyQt5 support will be removed in 2024. Switch to PyQt6",
                  DeprecationWarning)
    from PyQt5 import QtCore


# format is "LayoutKey": Command(type, setfunc, getfunc)
# type can be one of int, float, bool, tuple or list.
# If a pure setter command is needed use Set(type, setfunc)
# If a pure getter command is needed use Get(type getfunc)
# All functions can take optional setargs, getargs arguments containing lists of
# additional arguments for the setfunc and getfunc
common_commands = {"*idn": Get(str, "dummy_control"), }


class exampleDict(GuiDict):
    # Initialize dicts for GUI display as well as variable storage
    # Variables are stored in dict[key].value, GUI elements in dict[key].widgets
    # The GUI is initialized with the elements specified in dict[key].columns, where
    # key is label and entries should be of type guiObject.
    # A list means multiple widgets on one row
    # The unit of a variable can be set using the "unit" parameter and is then
    # shown in the label and included in the logging file. The logging
    # preference for the parameter is set by the boolean "log" parameter.
    cmds = {
        ":v1": Command(str, "setV1", "V1"),
        ":v2": Command(float, ("dummy", "p2"), "V2"),
        ":v3": Command(float, ("dummy", "p5"), "V3"),
        ":v2v3": Command((float, float), "setV2V3", "getV2V3"),
        ":v4": Command(bool, ("dummy", "p6"), "V4"),
    }
    data = {
        "Example": var(None, columns=["Readout", "Setpoint"]),
        "V1": var(dtype=str, columns=[go.labeltext, go.combobox],
                  log=True, init=[None, ("i1", "i2")]),
        "V2": var(float, columns=[go.labeltext, go.lineedit], unit="mT"),
        "V3": var(dtype=float, outType=int, columns=[go.progressbar,
                                                     go.doublespinbox],
                  log=False, unit="%", init=[None, (0, 100)], hide=True),
        "V4": var(dtype=bool, outType=bool,
                  columns=[go.checkbox, go.checkbox], log=True,),
        "toggle": var(dtype=bool, outType=bool, columns=[go.checkbox,
                                                         go.togglebutton],
                      init=[None, ("Slow", "Error")], log=None),
        "Set": var(None, columns=[go.button, go.button],
                   init=["Set", "Copy"]),
    }
    S = system.System(name="dummy")
    S.add_dev("dummy", dummy, args=("TCPIP::localhost::10007::SOCKET", ),
              kwargs={'p1': 'i1', 'p2': 0, 'p5': 5.5, 'p6': True})

    def create_GUI(self):
        content = super().create_GUI()
        # connect set/copy buttons
        self["Set"].widgets[1].clicked.connect(self.write)
        self["Set"].widgets[2].clicked.connect(self.copy_values)
        # connect the toggle buttons to the corresponding functions
        self["toggle"].widgets[2].clicked.connect(self.set_toggle)
        # adjust some widgets details
        self["V3"].widgets[2].setDecimals(1)
        return content

    def refresh(self, count):
        # read updated values from hardware (here fake)
        # always set the value (never change GUI directly!!!)
        self["V1"].value = self.S.devs["dummy"].p1
        self["V2"].value = self.S.devs["dummy"].p2
        self["V4"].value = self.S.devs["dummy"].p6
        self["toggle"].value = self.S.devs["dummy"].p7

        if self.extend_switch.isChecked():
            # update hidable items only when shown
            self["V3"].value = self.S.devs["dummy"].p5

        if self["V4"].value is False:
            # emit panic signel
            self.refresh_worker.panic.emit(True, "value V4 is False")

    def write(self):
        """
        Set values in the hardware
        """
        self.setV1(self["V1"].getGUIvalue())
        self.S.devs["dummy"].p2 = self["V2"].getGUIvalue()
        self.S.devs["dummy"].p5 = self["V3"].getGUIvalue()
        self.S.devs["dummy"].p6 = self["V4"].getGUIvalue()

    @catchEmitError
    def set_toggle(self, state):
        """
        set toggle button functionality in hardware
        """
        # if it is checked
        if state:
            # here should go code to set the feature in the hardware
            self.S.devs["dummy"].p7 = True
        # if it is unchecked
        else:
            # here should go code to unset the feature in the hardware
            self.S.devs["dummy"].p7 = False
            raise AttributeError("Test error inside a set function")

    # example functions
    def setV1(self, val):
        self.S.devs["dummy"].p1 = val

    def setV2V3(self, val):
        self.S.devs["dummy"].p2 = val[0]
        self.S.devs["dummy"].p5 = val[1]

    def getV2V3(self):
        """
        Return the values buffered in the GUI to make this request fast.
        Alternatively device access here is of course possible.
        """
        return [self["V2"].value, self["V3"].value]

    def panic(self):
        """
        raises an error for testing purposes. A real controlGUI should bring all
        parameters to a safe state here. e.g. remove field from a magnet
        """
        raise ValueError("This is an error for testing purpose.")


class exampleDict2(GuiDict):
    cmds = {
        ":v5": Command(float, "v5", "V5"),
    }
    data = {
        "Example2": var(None, columns="Readout"),
        "V5": var(float, columns=go.labeltext, unit="mbar"),
        " ": var(None, columns=go.hline, hide=True),
        "Info": var(str, columns="For testing purposes errors are raised \n"
                    "when V4 is set to False, the toggle \n"
                    "switch is pressed twice, or via the \n"
                    "Panic Button.",
                    hide=True),
    }
    # set a custom interval for the refresh function which updates the values
    # from the hardware
    refresh_period = 0.3
    # allow deactivating the GuiDict which also closes all device connections
    allow_disabling = True
    v5 = 0  # fake hardware value storage. Should be avoided in real GUIs

    class MyQObject(QtCore.QObject):
        """
        In order to be able to define pyqtSignals we need an object derived from
        QObject here. In this example it is used to be able to set a tooltip
        string in a thread safe manner.
        """
        tooltip = QtCore.pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        # FIFO queues to calculate linear trend of varying value
        N = 40  # length of all FIFO queues
        self.dataseries = collections.deque(maxlen=N)
        self.timestamps = collections.deque(maxlen=N)
        # enable setting the tooltip
        self.qobject = self.MyQObject()
        self.qobject.tooltip.connect(self.set_tooltip)

    def refresh(self, count):
        self["V5"].value = self.v5
        self.timestamps.appendleft(time.time())
        self.dataseries.appendleft(self.v5)
        if count % 5 == 0:
            # tasks performed every 5 iterations
            # generate and update tooltip
            slope, std = linear_trend(self.timestamps, self.dataseries)
            if slope is not None and std is not None:
                self.qobject.tooltip.emit(
                    "V5",
                    "last minute \n"
                    f"slope: {slope/60:.3f}mbar/min\n"
                    f"std: {std:.3f} mbar")
            self.v5 = round(30*numpy.random.random(), 3)

    def set_tooltip(self, label, tooltip):
        """Set tooltip thread safe on any widget in the first column."""
        if label in self:
            self[label].widgets[1].setToolTip(tooltip)


# define clientdevice to be used by measurement systems interfacing with this
# controlGUI. If no interfacing of a measurement system is intended this can be
# removed.
clientdevice = makeSCPIdevice(exampleDict.cmds, exampleDict2.cmds,
                              common_commands, sys=True)


def main():
    control_main("dummy",
                 ControlWindow,
                 guidicts=(exampleDict(), exampleDict2()),
                 extra_cmds=common_commands)
