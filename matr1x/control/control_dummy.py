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
"""Provides an example and test implementation of a control GUI."""

import collections
import threading
import time

import numpy
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction

from matr1x import system
from matr1x.control import (
    ControlWindow,
    GuiDict,
    catchEmitError,
    control_main,
    linear_trend,
    var,
)
from matr1x.control import guiObject as go
from matr1x.devices.dummy import dummy
from matr1x.devices.scpi_dev import makeSCPIdevice
from matr1x.gui_util import get_matrix_icon
from matr1x.util import Command, Get

# format is "LayoutKey": Command(type, setfunc, getfunc)
# type can be one of int, float, bool, tuple or list.
# If a pure setter command is needed use Set(type, setfunc)
# If a pure getter command is needed use Get(type getfunc)
# All functions can take optional setargs, getargs arguments containing lists of
# additional arguments for the setfunc and getfunc
common_commands = {
    "*idn": Get(str, "dummy_control"),
}


class exampleDict(GuiDict):
    """
    Initialize dicts for GUI display as well as variable storage.

    Variables are stored in dict[key].value, GUI elements in
    dict[key].widgets The GUI is initialized with the elements specified
    in dict[key].columns, where key is label and entries should be of
    type guiObject. A list means multiple widgets on one row The unit of
    a variable can be set using the "unit" parameter and is then shown
    in the label and included in the logging file. The logging
    preference for the parameter is set by the boolean "log" parameter.
    """

    cmds = {
        ":v1": Command(str, "setV1", "V1"),
        ":v2": Command(float, ("dummy", "p2"), "V2", polling_cmd=":v2rd"),
        ":v3": Command(float, ("dummy", "p5"), "V3"),
        ":v2v3": Command((float, float), "setV2V3", "getV2V3", setargs=(2,)),
        ":v4": Command(bool, ("dummy", "p6"), "V4"),
        ":v2rd": Get(bool, "v2ready"),
    }
    data = {
        "Example": var(None, columns=["Readout", "Setpoint"]),
        "V1": var(
            dtype=str,
            columns=[go.labeltext, go.combobox],
            log=True,
            init=[None, ("i1", "i2")],
        ),
        "V2": var(float, columns=[go.labeltext, go.lineedit], unit="mT"),
        "V3": var(
            dtype=float,
            columns=[go.progressbar, go.doublespinbox],
            log=False,
            unit="%",
            init=[0, (0, 100)],
            hide=True,
        ),
        "V4": var(
            dtype=bool,
            columns=[go.checkbox, go.checkbox],
            log=True,
        ),
        "toggle": var(
            dtype=bool,
            columns=[go.checkbox, go.togglebutton],
            init=[None, ("Slow", "Error")],
            log=None,
        ),
        "Set": var(None, columns=[go.button, go.button], init=["Set", "Copy"]),
    }
    S = system.System(name="dummy")
    S.add_dev(
        "dummy",
        dummy,
        args=("TCPIP::localhost::10006::SOCKET",),
        kwargs={"p1": "i1", "p2": 0, "p5": 5.5, "p6": True},
    )

    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()

    def create_GUI(self):
        """
        Build the actual GUI.

        Returns
        -------
        content : object
            The GUI content.
        """
        content = super().create_GUI()
        # optional custom menu
        print_action = QAction("Print in logger")
        print_action.setIcon(get_matrix_icon("CHAR_P"))
        print_action.triggered.connect(self.print_function)
        # return all actions as a list to the controlwindow
        # Just one action in is case
        self.menu_actions = [print_action]
        # connect set/copy buttons
        self["Set"].widgets[1].clicked.connect(self.write)
        self["Set"].widgets[2].clicked.connect(self.copy_values)
        # connect the toggle buttons to the corresponding functions
        self["toggle"].widgets[2].clicked.connect(self.set_toggle)
        # adjust some widgets details
        self["V3"].widgets[2].setDecimals(1)
        return content

    def print_function(self) -> None:
        """
        Print 'Hello' in the logger.

        Demonstrate the custom menu.
        """
        print("Hello from a guidict.")

    def refresh(self, count):
        """
        Read updated values from hardware (here fake).

        Always set the value (never change GUI directly!!!).

        Parameters
        ----------
        count : int
            The current iteration count.
        """
        with self.lock:
            self["V1"].value = self.S.devs["dummy"].p1
            self["V2"].value = self.S.devs["dummy"].p2
            self["V4"].value = self.S.devs["dummy"].p6
            self["toggle"].value = self.S.devs["dummy"].p7
            # update hidable items also when not shown
            self["V3"].value = self.S.devs["dummy"].p5

        if self["V4"].value is False:
            # emit panic signel
            self.refresh_worker.panic.emit(True, "value V4 is False")

    def write(self):
        """Set values in the hardware."""
        self.setV1(self["V1"].getGUIvalue())
        with self.lock:
            self.S.devs["dummy"].p2 = self["V2"].getGUIvalue()
            self.S.devs["dummy"].p5 = self["V3"].getGUIvalue()
            self.S.devs["dummy"].p6 = self["V4"].getGUIvalue()

    @catchEmitError
    def set_toggle(self, state):
        """
        Set toggle button functionality in hardware.

        Parameters
        ----------
        state : bool
            The state of the toggle button.
        """
        # if it is checked
        if state:
            # here should go code to set the feature in the hardware
            with self.lock:
                self.S.devs["dummy"].p7 = True
        # if it is unchecked
        else:
            # here should go code to unset the feature in the hardware
            with self.lock:
                self.S.devs["dummy"].p7 = False
            raise AttributeError("Test error inside a set function")

    # example functions
    def setV1(self, val):
        """
        Provide example function 1.

        Parameters
        ----------
        val : str
            The value to set.
        """
        with self.lock:
            self.S.devs["dummy"].p1 = val

    def setV2V3(self, val, digits=None):
        """
        Provide example function 2.

        Parameters
        ----------
        val : tuple
            A tuple containing two float values.
        digits : int, optional
            The number of digits to round to.
        """
        with self.lock:
            self.S.devs["dummy"].p2 = round(val[0], digits)
            self.S.devs["dummy"].p5 = round(val[1], digits)

    def getV2V3(self):
        """
        Get V2 and V3 values.

        Returns
        -------
        list
            A list containing the values of V2 and V3.
        """
        return [self["V2"].value, self["V3"].value]

    def v2ready(self):
        """
        Check if V2 is ready.

        Returns
        -------
        bool
            True if V2 is equal to device value, False otherwise.
        """
        with self.lock:
            return self["V2"].value == self.S.devs["dummy"].p2

    def panic(self):
        """
        Raise an error for testing purposes.

        A real controlGUI should bring all parameters to a safe state here.
        e.g. remove field from a magnet.

        Raises
        ------
        ValueError
            This is an error for testing purpose.
        """
        raise ValueError("This is an error for testing purpose.")


class exampleDict2(GuiDict):
    """
    Initialize dicts for GUI display as well as variable storage.

    Provide a second example to demonstrate, e.g. the dockable widgets
    and a fake pressure gauge.
    """

    cmds = {
        ":v5": Command(float, "v5", "V5"),
    }
    data = {
        "Example2": var(None, columns="Readout"),
        "V5": var(float, columns=go.labeltext, unit="mbar"),
        " ": var(None, columns=go.hline, hide=True),
        "Info": var(
            str,
            columns="For testing purposes errors are raised \n"
            "when V4 is set to False, the toggle \n"
            "switch is pressed twice, or via the \n"
            "Panic Button.",
            hide=True,
        ),
    }
    # set a custom interval for the refresh function which updates the values
    # from the hardware
    refresh_period = 0.1
    # allow deactivating the GuiDict which also closes all device connections
    allow_disabling = True
    v5 = 0  # fake hardware value storage. Should be avoided in real GUIs

    class MyQObject(QObject):
        """
        Define Signals via QObjects.

        We need an object derived from QObject here. In this example it
        is used to set a tooltip string in a thread safe manner.
        """

        tooltip = Signal(str, str)

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
        """
        Refresh the (fake) read-out values.

        Parameters
        ----------
        count : int
            The current iteration count.
        """
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
                    f"last minute \nslope: {slope / 60:.3f}mbar/min\nstd: {std:.3f} mbar",
                )
        self.v5 = round(30 * numpy.random.random(), 3)

    def set_tooltip(self, label, tooltip):
        """
        Set tooltip thread safe on any widget in the first column.

        Parameters
        ----------
        label : str
            The label of the widget.
        tooltip : str
            The tooltip text to set.
        """
        if label in self:
            self[label].widgets[1].setToolTip(tooltip)


# define clientdevice to be used by measurement systems interfacing with this
# controlGUI. If no interfacing of a measurement system is intended this can be
# removed.
clientdevice = makeSCPIdevice(exampleDict.cmds, exampleDict2.cmds, common_commands, system=True)


def main():
    """Run the actual control window."""
    control_main(
        "dummy",
        ControlWindow,
        guidicts=(exampleDict(), exampleDict2()),
        extra_cmds=common_commands,
        # use specific port to allow running next to other controlGUIs
        port=8897,
    )
