---
name: matr1x-write-control
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

Read section 4.4 (concurrency and thread safety) before wiring the
`cmds` getters/setters and `refresh` — the refresh worker and the SCPI
server run in parallel and must not race each other.

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

from matr1x.control import (
    ControlWindow,
    GuiDict,
    MethodBundle,
    catchEmitError,
    control_main,
    linear_trend,
    var,
)
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
clientdevice = makeSCPIdevice(exampleDict.cmds, exampleDict2.cmds, common_commands, system=True)


# 6. main() entry point
def main():
    control_main(
        "dummy",  # name: window title + lock file
        ControlWindow,
        guidicts=(exampleDict, exampleDict2),
        extra_cmds=common_commands,
        port=8897,  # SCPI server port
        package="matr1x",  # used for log files / desktop file
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
        "V1": var(
            dtype=str, columns=[go.labeltext, go.combobox], log=True, init=[None, ("i1", "i2")]
        ),
        "V2": var(float, columns=[go.labeltext, go.lineedit], unit="mT"),
        "V3": var(
            dtype=float,
            columns=[go.progressbar, go.doublespinbox],
            unit="%",
            init=[0, (0, 100)],
            hide=True,
            modify=[one_decimal],
        ),
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
  `add_dev(name, descriptor, args=..., kwargs=...)` takes a device class as
  `descriptor`, so import it at the top of the file (in the example below
  `dummy` comes from `from matr1x.devices.dummy import dummy`). The `args`
  hold the connection/adapter address the device needs (the `dummy` device
  requires the resource string, e.g. `args=("TCPIP::localhost::10006::SOCKET",)`,
  while its named properties go into `kwargs`).
- `refresh_period` defines the time in seconds between `refresh()` calls.
- `allow_disabling`: Let the panel get an enable/disable switch. Requires the devices to support close().

### 4.2 Overridden methods (the behavior)

| Method              | Thread        | Purpose                                                                                                                                                                                                                         |
| ------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `__init__`          | GUI           | Call `super().__init__()`, create locks, deques for trends, `MethodBundle` change handlers, etc.                                                                                                                                |
| `create_GUI`        | GUI           | Call `super().create_GUI()`, then connect buttons/toggles to slot methods (e.g. `self["Set"].widgets[1].clicked.connect(self.write)`), add menu actions via `self.menu_actions`, restyle widgets.                               |
| `refresh(count)`    | worker thread | Read hardware via `self.S.devs[...]` and **only set `self[...].value`** (never touch widgets directly). `count` allows "every Nth iteration" tasks (tooltips, trends). May emit `self.refresh_worker.panic.emit(True, reason)`. |
| `write`             | GUI           | Push `self[...].getGUIvalue()` to the hardware (usually behind a lock). This is a naming convention and only wired manually to the "Set" button. See 4.4 for locking.                                                                                |
| `copy_values`       | GUI           | Copy readout columns into setpoint columns. Performed once automatically once at start-up. Usually, also wired to a "Copy" button.                                                                                              |
| `panic` / `unpanic` | GUI           | Bring the instrument to a safe state, disable set buttons; call `super().panic()` / `super().unpanic()`.                                                                                                                        |
| command methods     | either        | The functions named in `cmds` (e.g. `setV1`, `V1`, `v2ready`), often decorated with `@catchEmitError`. Prefer buffered getters, see 4.4.                                                                                                                          |

### 4.3 `var` (one row in a `GuiDict`)

- `var.value` — the stored value; setting it emits `valueChanged`, which updates the readout widget and any change handlers.
- `var.widgets` — `widgets[0]` is the label, `widgets[1:]` the other two columns.
- `var.getGUIvalue()` — value as entered in the setpoint widget.
- `var.tooltip`, `var.unit` — live-updatable, used for trend displays.

### 4.4 Concurrency and thread safety

A control GUI is implicitly multi-threaded: the **refresh worker
thread**
(runs `refresh`) and the **SCPI server threads** (run the `get`/`set`
functions bound to `cmds`) concurrently talk to the same instrument(s).
This is the most common source of hard-to-reproduce bugs, so follow
the rules below.

#### Which thread runs what

| Entry point            | Thread            | Hardware access?              |
| ---------------------- | ----------------- | ----------------------------- |
| `refresh(count)`       | refresh worker   | yes (reads)                   |
| SCPI `get` command     | SCPI server      | only if the getter reads HW   |
| SCPI `set` command     | SCPI server      | yes (writes)                  |
| GUI buttons / `write`  | GUI (Qt) thread  | yes, when the slot writes     |
| `panic` / `unpanic`    | GUI (Qt) thread  | yes, when the slot writes     |

So a given device may be accessed from up to three threads at once. You
must make sure the underlying communication is safe before relying
on it.

#### 1. Prefer buffered `get` commands

The primary idea of the control GUI is that `refresh()` keeps a buffered
snapshot of the instrument state in `self[...].value`, and getter
commands should **return that buffered value** instead of re-reading the
hardware. This avoids extra bus traffic and, more importantly, means a
`get` does not race the `refresh` thread.

```python
cmds = {
    # returns the value last cached by refresh() - no hardware access
    ":temperature": Get(float, "Temperature"),
}
```

The `Get` shorthand with a `GuiDict.data` key name as `getfunc` resolves
straight to `self["Temperature"].value`, so no I/O happens on the server
thread. Only break this pattern with a specific reason, e.g. a command
that must report a value `refresh` does not sample.

#### 2. Serialize every hardware-accessing getter/setter with the locks

For commands that genuinely touch the hardware, your device access is
only safe if the underlying communication is synchronized:

- **PyMeasure instruments**: matr1x applies the thread-safety patch
  (`matr1x.core.pymeasure_threading_fix`) to `pymeasure.instruments.
  Instrument` on import. Its per-instance reentrant lock makes
  individual
  `write`/`read`/`ask` calls and property accessors atomic across
  threads. Prefer that patch over writing your own locks around
  PyMeasure calls, and use `with dev.atomic_operation():` to group
  several low-level calls that must stay together (e.g. a `write`
  followed by `check_set_errors`).
- **`VisaDevice` family** (`matr1x.devices.visadevice`): `query`,
  `read`, `write` are already wrapped in `@synchronized` (see
  `sharedlock`).
- **Anything else** (custom devices, or compound read-modify-write
  sequences that must not interleave with another thread): protect them
  with a `threading.Lock` (or `RLock`) shared by every accessor, and
  reuse the same lock in `refresh` as well. If you take a lock, use it
  in *every* access path, including `refresh` and the `panic`/
  `unpanic` handlers; a lock that only guards the setter does not
  protect against the refresh thread.

#### 3. Keep the refresh worker out of the GUI event loop

`refresh()` runs on its own worker thread, so it must **never touch
widgets directly**. It may only set `self[...].value` (which marshals
the update to the GUI thread via the Qt signal). See the `refresh` row
in table 4.2. Do not block the refresh thread on GUI operations or vice
versa; use `QTimer.singleShot` for deferred UI-side work.

#### 4. Read setpoint values thread-safely

`self[...].getGUIvalue()` is thread-safe when called from the SCPI set
function/`write`: it reads the widget directly on the GUI thread and
falls back to a cached value otherwise (see `getGUIvalue`). Do not read
Qt widgets from the SCPI server thread yourself; always go through
`getGUIvalue`.

#### Checklist

- [ ] Every device is accessed through a lock (or the built-in
      PyMeasure/VisaDevice synchronization) from **all** entry points.
- [ ] `get` commands return buffered `self[...].value` unless there is a
      specific reason to read hardware.
- [ ] A multi-call atomic sequence uses `atomic_operation()` (PyMeasure)
      or one shared lock.
- [ ] `refresh` sets only `self[...].value`, never widgets.
- [ ] Device attributes that are read by `refresh` and written by a
      `set` use the same lock on both sides.

---

## 5. Concrete files

### 5.1 `matr1x/control/control_dummy.py` (reference example)

| Class                   | Role                                                                                                                                                                                                 |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `exampleDict(GuiDict)`  | Full-featured demo: combobox/lineedit/progressbar/checkbox/toggle rows, `MethodBundle`s (`color_bar`, `one_decimal`), custom menu action, `panic`/`unpanic`, `@catchEmitError` slots, `polling_cmd`. |
| `exampleDict2(GuiDict)` | Demo of a fast refresh (`refresh_period = 0.1`), `allow_disabling = True`, trend tooltip via `linear_trend`, hidden info row.                                                                        |
| `main()`                | `control_main("dummy", ControlWindow, guidicts=(exampleDict, exampleDict2), extra_cmds=common_commands, port=8897)`.                                                                                 |

## 6. Debugging

All commands below assume the current directory is the matr1x installation
(pkg-root). If you work in a user workspace instead, use the Python command
recorded in the workspace's `AGENTS.md` (i.e. `uv run --project <pkgroot>
python ...`) in place of `uv run python`.

Determine the log folder via

`uv run python -c "from matr1x.core.config import logfolder;print(logfolder)"`

### 6.1 Offscreen smoke test

`main()` creates its own `QApplication` (`MApplication`) and owns the event
loop, so the reliable smoke test is to run it in a subprocess, let it run for
a while, then terminate it. Use the Python recipe below so it works
identically on Linux, macOS and Windows (no shell-specific `&`, `timeout`
or `kill`):

```sh
uv run python -c "
import os, subprocess, sys, time
env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
proc = subprocess.Popen(
    [sys.executable, '-c',
     'from matr1x.control import control_dummy; control_dummy.main()'],
    env=env)
time.sleep(20)
proc.terminate()
proc.wait(timeout=10)
"
```

`sys.executable` is the venv interpreter, so the subprocess runs in the same
environment as the outer `uv run`. Then check:

- The newest log in the log folder: "Control window '<name>' starting" should
  be followed by a clean shutdown ("closed by user" / "Exiting GUI") with no
  "failed to start" traceback. The log folder is the best source for startup
  bugs.
- The subprocess stdout/stderr for Qt warnings (add a `stdout=`/`stderr=`
  file handle to the `Popen` call if you want to capture them).

Gotchas:

- Do **not** construct `ControlWindow` yourself for testing: its first
  positional argument `name` is required
  (`ControlWindow(name, guidicts=..., extra_cmds=...)`) and you would miss the
  wiring `control_main` performs (lock file, error handler, SCPI server).
- Do **not** pre-create a `QApplication` or patch `QApplication.exec` to
  auto-quit; `main()` manages the application itself.
- The lock file is PID-based, so terminating the process is fine; the next
  start detects the stale lock and continues.
- Use `uv run python` (not `python3`), which resolves on all platforms.

### 6.2 SCPI query test (read-only)

While the control is running (e.g. during the 6.1 smoke test, offscreen or
visible), verify that the SCPI server answers by querying it over TCP.
**Only send get commands (the ones ending in `?`)** — the test must be
strictly read-only and must never send a set command, so it cannot change
the state of the control or of any instrument behind it. A good set of
queries is `*IDN?` plus the `Get` commands of the control's `cmds` dicts.

```sh
uv run python -c "
import socket

def query(cmd, port):
    with socket.create_connection(('127.0.0.1', port), timeout=10) as s:
        s.sendall((cmd + '\n').encode())
        chunks = []
        while True:
            data = s.recv(4096)
            if not data:
                break
            chunks.append(data)
            if b'\n' in b''.join(chunks):
                break
    return b''.join(chunks).decode().strip()

port = 8897  # the port passed to control_main in main()
print(query('*IDN?', port))
print(query(':v1?', port))  # replace with the control's Get commands
"
```

Notes:

- Get commands are answered with the value followed by a newline, which the
  loop above waits for. Set commands only send a single ACK byte (`\x06`)
  and no newline — another reason to keep the test read-only.
- The server lowercases every received line, so a query is case-insensitive,
  but any value you would send gets lowercased as well (e.g. string set
  values must be matched case-insensitively by the control).
- One connection per command is fine for a manual test; the server handles
  them sequentially.

### 6.3 Interactive run (mandatory final step)

Once the offscreen startup is clean, start the control visibly via its
`main()` function:

`uv run python -c "from matr1x.control import control_<name>; control_<name>.main()"`

and let the user interact with it: click buttons, toggle panels, trigger
panic. This catches runtime errors that never appear at startup. The control
is only finished after the user has exercised it without errors.
