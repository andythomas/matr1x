---
name: write-control
description: >
  Write a control file for a matr1x setup.
license: GNU General Public License v3 or later (GPLv3+)
compatibility: Requires Python >=3.10.
---

## 1. Writing a new control GUI

1. Create `control_<name>.py` with `common_commands = {"*idn": Get(str, ...)}`. Usually, just the "identify" command suffices.
2. Define one `GuiDict` subclass per instrument: `cmds`, `data`, `S`, optionally `refresh_period` / `allow_disabling`.
3. Implement `create_GUI` (button wiring), `refresh(count)` (read →`self[...].value`), `write` (setpoint → hardware), and `panic` (safe state) where relevant.
4. Build `clientdevice = makeSCPIdevice(*Cmds, common_commands, system=True)`.
5. Add `main()` calling `control_main(name, ControlWindow, guidicts=(...), extra_cmds=common_commands, package=..., port=...)`.

Please find the details in the next sections.

## 2. The framework layer

Everything below builds on these classes and functions from the `matr1x.control` package:

| Class / function                        | File                         | Role                                                                                                                                                                                                                                           |
| --------------------------------------- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ControlWindow`                         | `controlwindow.py`           | `QMainWindow` base class. Owns the list of `GuiDict`s, the panic button, the logging window, the SCPI server, menus and the enable/disable logic.                                                                                              |
| `GuiDict`                               | `gui_dict.py`                | A `dict[str, var]` subclass. One `GuiDict` = one dockable panel + its device `System` + its refresh thread + its SCPI commands. This is the core building block of every control GUI file.                                                     |
| `var`                                   | `gui_dict.py`                | One row of a panel: a stored `.value`, a list of Qt `.widgets`, a `unit`, a `tooltip`, a `log` flag and `valueChanged`/`unitChanged`/`tooltipChanged` signals.                                                                                 |
| `guiObject`                             | `gui_dict.py`                | `IntEnum` naming the widget types used in `var(..., columns=...)`: `button`, `lineedit`, `checkbox`, `progressbar`, `combobox`, `togglebutton`, `spinbox`, `doublespinbox`, `labeltext`, `hline` (a plain `str` also works as a static label). |
| `MethodBundle`                          | `gui_dict.py`                | Reusable bundle of setup methods (`add_setup_method`) and change handlers (`add_change_handler`) applied to widgets via `var(..., modify=...)`. For more advanced customization.                                                               |
| `catchEmitError`                        | `gui_dict.py`                | Decorator for slot functions: catches exceptions and emits them to the window's error handling instead of crashing.                                                                                                                            |
| `control_main`                          | `util.py`                    | Entry-point helper: creates the Qt app, checks the lock file, instantiates `window_class` with the given `guidicts`/`extra_cmds` and starts the event loop.                                                                                    |
| `linear_trend`, `sendNotificationEmail` | `util.py`                    | Helpers for trend tooltips and email alerts.                                                                                                                                                                                                   |
| `Command`, `Get`, `Set`                 | `matr1x/core/commands.py`    | Containers for the SCPI command map: `Command(type, setfunc, getfunc)`, `Get(type, getfunc)`, `Set(type, setfunc)`.                                                                                                                            |
| `makeSCPIdevice`                        | `matr1x/devices/scpi_dev.py` | Builds a `clientdevice` from the `cmds` dicts so measurement systems can talk to the running GUI over SCPI.                                                                                                                                    |

---

## 3. General file structure

Every control GUI file follows a similar skeleton, one example is given in `matr1x/control/control_dummy.py`:

```python
# 1. Imports
from PySide6.QtWidgets import QDoubleSpinBox

from matr1x.control import (ControlWindow, GuiDict, MethodBundle,
                            catchEmitError, control_main, linear_trend, var)
from matr1x.control import guiObject as go
from matr1x.core.commands import Command, Get
from matr1x.core.system import System
from matr1x.devices.scpi_dev import makeSCPIdevice

# 2. Common SCPI commands shared by all panels of this GUI
# Here, the idn command returns a string to identify the control
common_commands = {"*idn": Get(str, "dummy_control")}

# 3. Optional reusable MethodBundles (widget setup / change handlers)
# This can be used in more advanced cases to customize the standard
# widgets.
one_decimal = MethodBundle()

def set_decimals(widget: QDoubleSpinBox) -> None:
    """Set the number of decimals for a QDoubleSpinBox to 1."""
    widget.setDecimals(1)

one_decimal.add_setup_method(set_decimals)

# 4. One or more GuiDict subclasses  (see section 4)
class exampleDict(GuiDict): ...
class exampleDict2(GuiDict): ...

# 5. clientdevice: exposes the cmds of all panels to measurement systems
clientdevice = makeSCPIdevice(exampleDict.cmds, exampleDict2.cmds,
                              common_commands, system=True)

# 6. main() entry point
def main():
    control_main(
        "dummy",            # name: window title + lock file
        ControlWindow,
        guidicts=(exampleDict, exampleDict2),
        extra_cmds=common_commands,
        port=8897,          # SCPI server port
        package="matr1x",   # used for log files / desktop file
    )
```

Responsibility split:

- **`GuiDict`** — one instrument or subsystem: its devices (`System`),
  its readout/setpoint widgets, its refresh loop, its SCPI commands.
- **`ControlWindow`** — the frame around the panels: panic handling,
  logging, SCPI server, menus.
- **`clientdevice`** — the measurement-system side of the running GUI.
- **`main()` / `control_main`** — wiring it all together.

---

## 4. `GuiDict` internal structure

A `GuiDict` subclass is fully described by its **class attributes** (the declaration) plus a few **overridden methods** (the behavior).

### 4.1 Class attributes (the declaration)

```python
class exampleDict(GuiDict):
    # SCPI command map: name -> Command/Get/Set bound to methods below
    cmds: ClassVar[dict[str, Command]] = {
        ":v1": Command(str, "setV1", "V1"),
        ":v2": Command(float, ("dummy", "p2"), "V2", polling_cmd=":v2rd"),
        ":v2rd": Get(bool, "v2ready"),
    }

    # The panel layout: one entry per row of the dock widget
    # Three columns in one row, one label and two for widgets
    data: ClassVar[dict[str, var]] = {
        "Example": var(None, columns=["Readout", "Setpoint"]),
        "V1": var(dtype=str, columns=[go.labeltext, go.combobox],
                  log=True, init=[None, ("i1", "i2")]),
        "V2": var(float, columns=[go.labeltext, go.lineedit], unit="mT"),
        "V3": var(dtype=float, columns=[go.progressbar, go.doublespinbox],
                  unit="%", init=[0, (0, 100)], hide=True,
                  modify=[one_decimal]),
        "Set": var(None, columns=[go.button, go.button], init=["Set", "Copy"]),
    }

    # The device system behind this panel
    S = System(name="dummy")
    S.add_dev("dummy", dummy, args=(...), kwargs={...})

    refresh_period = 1.0
    allow_disabling = False
```

Explanations:

- `cmds` values reference methods of the `GuiDict` (by name or as `("devname", "attr")` device attribute paths). `polling_cmd` names a readiness command.

- `data`: The first key is used as the panel (dock widget) title.
- `var(...)` options: `dtype` (data type such as `int` or `float`), `columns` (see next point), `unit` (shown in the label and
  in the log file), `log` (if the row is logged by default, i.e. after start-up), `init` (initial values, spin box ranges, combo box entries, button texts), `hide` (only shown in the "extended" view), `modify` (`MethodBundle`s applied to widgets).
  - `columns` maps positions to widget types; the typical convention is: column 1 = readout, column 2 = setpoint. There is always the label plus two columns available.

- Every `GuiDict` typically adds one device, e.g., `S = System(name="dummy")` plus subsequent `add_dev` and its name must be unique.
- `refresh_period` defines the time in seconds between `refresh()` calls.
- `allow_disabling`: Let the panel get an enable/disable switch. Requires the devices to support close().

### 4.2 Overridden methods (the behavior)

| Method              | Thread        | Purpose                                                                                                                                                                                                                         |
| ------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `__init__`          | GUI           | Call `super().__init__()`, create locks, deques for trends, `MethodBundle` change handlers, etc.                                                                                                                                |
| `create_GUI`        | GUI           | Call `super().create_GUI()`, then connect buttons/toggles to slot methods (e.g. `self["Set"].widgets[1].clicked.connect(self.write)`), add menu actions via `self.menu_actions`, restyle widgets.                               |
| `refresh(count)`    | worker thread | Read hardware via `self.S.devs[...]` and **only set `self[...].value`** (never touch widgets directly). `count` allows "every Nth iteration" tasks (tooltips, trends). May emit `self.refresh_worker.panic.emit(True, reason)`. |
| `write`             | GUI           | Push `self[...].getGUIvalue()` to the hardware (usually behind a lock). This is a naming convention and only wired manually to the "Set" button.                                                                                |
| `copy_values`       | GUI           | Copy readout columns into setpoint columns. Performed once automatically once at start-up. Usually, also wired to a "Copy" button.                                                                                              |
| `panic` / `unpanic` | GUI           | Bring the instrument to a safe state, disable set buttons; call `super().panic()` / `super().unpanic()`.                                                                                                                        |
| command methods     | either        | The functions named in `cmds` (e.g. `setV1`, `V1`, `v2ready`), often decorated with `@catchEmitError`.                                                                                                                          |

### 4.3 `var` (one row in a `GuiDict`)

- `var.value` — the stored value; setting it emits `valueChanged`, which updates the readout widget and any change handlers.
- `var.widgets` — `widgets[0]` is the label, `widgets[1:]` the other two columns.
- `var.getGUIvalue()` — value as entered in the setpoint widget.
- `var.tooltip`, `var.unit` — live-updatable, used for trend displays.

---

## 5. Concrete files

### 5.1 `matr1x/control/control_dummy.py` (reference example)

| Class                   | Role                                                                                                                                                                                                 |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `exampleDict(GuiDict)`  | Full-featured demo: combobox/lineedit/progressbar/checkbox/toggle rows, `MethodBundle`s (`color_bar`, `one_decimal`), custom menu action, `panic`/`unpanic`, `@catchEmitError` slots, `polling_cmd`. |
| `exampleDict2(GuiDict)` | Demo of a fast refresh (`refresh_period = 0.1`), `allow_disabling = True`, trend tooltip via `linear_trend`, hidden info row.                                                                        |
| `main()`                | `control_main("dummy", ControlWindow, guidicts=(exampleDict, exampleDict2), extra_cmds=common_commands, port=8897)`.                                                                                 |
