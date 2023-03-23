# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2023 matr1x developers. All rights reserved.
# ---

import numpy
from matr1x import system
from matr1x.control import ControlWindow, GuiDict, catchEmitError, control_main
from matr1x.control import guiObject as go
from matr1x.control import var
from matr1x.devices.dummy import dummy
from matr1x.devices.scpi_dev import makeSCPIdevice
from matr1x.util import Command, Get

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
    cmds = {
        ":v1": Command(int, "setV1", "V1"),
        ":v2": Command(float, "V2", "V2"),
        ":v3": Command(float, "V3", "V3"),
        ":v2v3": Command((float, float), "setV2V3", "getV2V3"),
        ":v4": Command(int, "V4", "V4"),
    }
    data = {
        "Example": var(None, columns=["Readout", "Setpoint"]),
        "V1": var((int, int), columns=[go.combobox, go.combobox],
                  log=True, init=("i1", "i2")),
        "V2": var(float, columns=[go.lineedit, go.lineedit], unit="mT"),
        "V3": var(dtype=float, outType=int, columns=[go.progressbar,
                                                     go.doublespinbox],
                  log=True, unit="%", init=[None, (0, 100)]),
        "V4": var(dtype=bool, outType=bool, columns=[go.checkbox, go.checkbox]),
        "toggle": var(dtype=bool, outType=bool, columns=[go.checkbox,
                                                         go.togglebutton],
                      init=[None, ("Slow", "Error")]),
        "Set": var(None, columns=[go.button, go.button],
                   init=["Set", "Copy"]),
    }

    S = system.System(name="dummy")
    S.add_dev("dummy", dummy, args=("TCPIP::localhost::10007::SOCKET", ),
              kwargs={'p1': 1, 'p2': 0, 'p5': 5.5, 'p6': True})

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
        self["V3"].value = self.S.devs["dummy"].p5
        self["V4"].value = self.S.devs["dummy"].p6
        self["toggle"].value = self.S.devs["dummy"].p7

        if count == 0:
            self.copy_values()

        if self["V4"].value is False:
            raise ValueError("Test error raised inside refresh")

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
        if self["toggle"].widgets[2].isChecked():
            # here should go code to set the feature in the hardware
            self.S.devs["dummy"].p7 = True
        # if it is unchecked
        else:
            # here should go code to unset the feature in the hardware
            self.S.devs["dummy"].p7 = False
            raise AttributeError("Test error inside a set function")

    # example functions
    def setV1(self, val):
        if val in (0, 1):
            self.S.devs["dummy"].p1 = val

    def setV2V3(self, val):
        self.S.devs["dummy"].p2 = val[0]
        self.S.devs["dummy"].p5 = val[1]

    def getV2V3(self):
        """
        Return the values buffered in the GUI to make this request fast.
        Alternatively device access here is of course possible.
        """
        return [self["V2"].getGUIvalue(), self["V3"].getGUIvalue()]

    def panic(self):
        """
        raises an error for testing purposes. A real controlGUI should bring all
        parameters to a safe state here. e.g. remove field from a magnet
        """
        raise ValueError("This is an error for testing purpose.")


class exampleDict2(GuiDict):
    cmds = {
        ":v5": Command(float, "V5", "V5"),
    }
    data = {
        "Example2": var(None, columns="Readout"),
        "V5": var(float, columns=1, unit="mbar"),
        "Info": var(None, columns="For testing purposes errors are raised \n"
                                  "when V4 is set to False, the toggle \n"
                                  "switch is pressed twice, or via the \n"
                                  "Panic Button."),
    }
    refresh_period = 0.3
    v5 = 0  # fake hardware value storage. Should be avoided in real GUIs

    def refresh(self, count):
        self["V5"].value = self.v5
        if count % 5 == 0:
            self.v5 = round(30*numpy.random.random(), 3)


# define clientdevice to be used by measurement systems interfacing with this
# controlGUI. If no interfacing of a measurement system is intended this can be
# removed.
clientdevice = makeSCPIdevice(exampleDict.cmds, exampleDict2.cmds,
                              common_commands, sys=True)


def main():
    control_main("dummy",
                 ControlWindow,
                 guidicts=(exampleDict(), exampleDict2()),
                 extra_cmds=common_commands,
                 lockfile=True)
