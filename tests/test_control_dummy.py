# This file is part of a software collection for data aquisition (matr1x).
# Copyright (C) 2006-2026 matr1x developers
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
"""
Module for testing the matr1x data acquisition system.

This module contains test fixtures and test functions to verify the
functionality of the matr1x data acquisition system, particularly
focusing on the control GUI and script execution capabilities.
"""

import os
import platform
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from importlib.metadata import entry_points
from pathlib import Path
from typing import cast

import numpy as np
import pytest
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QMessageBox

import matr1x.core.eval
import matr1x.core.util
from matr1x import output_extension
from matr1x.control import ControlWindow, GuiDict, MethodBundle, var
from matr1x.control import guiObject as go
from matr1x.control.control_dummy import exampleDict
from matr1x.core.scpi_tcpserver import SCPI_TCP_Server
from matr1x.core.system import System

path = Path(__file__).resolve().parent

user_script = """
import numpy as np
fields = np.linspace(0, 200, 11)
init_datafile("epische_messdatei", comment="testcomment")
for field in fields:
    set_value(1, (field, field/fields.max()*100))
    system.devs["gui"].v2 = field  # test direct access and poll command
    measure_system()
    wait(until="+0.1s")  # wait one refresh cycle of control-dummy
"""


@pytest.fixture(autouse=True)
def clean_data_files():
    """
    Clean up data files created during tests.

    This fixture runs automatically before and after each test. It keeps track
    of existing data files before the test and removes any new files created
    during the test execution.

    Yields
    ------
    None
        Control is yielded to the test function.
    """
    existingfiles = list(path.glob(f"*{output_extension}"))
    # run test
    yield
    files = list(path.glob(f"*{output_extension}"))
    newfiles = set(files) - set(existingfiles)
    for f in newfiles:
        f.unlink()


def wait_for_tcp_port(
    host: str, port: int, timeout: float = 30, poll_interval: float = 0.1
) -> bool:
    """
    Wait for a TCP port to become available for connection.

    Parameters
    ----------
    host : str
        The hostname or IP address to check.
    port : int
        The port number to check.
    timeout : float, optional
        Maximum time to wait in seconds (default: 30).
    poll_interval : float, optional
        Time to wait between checks in seconds (default: 0.1).

    Returns
    -------
    bool
        True if port becomes available within timeout, False otherwise.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex((host, port))
                if result == 0:
                    return True
        except (TimeoutError, socket.gaierror):
            pass
        time.sleep(poll_interval)
    return False


@pytest.fixture
def start_control_dummy():
    """
    Start and manage the control-dummy GUI application.

    This session-scoped fixture starts the control-dummy GUI application in a
    subprocess before running tests and ensures proper cleanup afterward.

    Yields
    ------
    None
        Control is yielded to the test function while the GUI runs.

    Notes
    -----
    The GUI process is terminated gracefully after the tests complete.
    A warning is issued if the DISPLAY environment variable is not set.
    """
    # Start the control-dummy GUI app in a subprocess
    env = os.environ.copy()
    if platform.system() == "Linux" and "DISPLAY" not in env:
        print("Warning: DISPLAY is not set. GUI may not run.")

    # Find the 'control-dummy' GUI script entry point
    eps = entry_points()
    try:
        ep = next(ep for ep in eps.select(group="gui_scripts") if ep.name == "control-dummy")
    except StopIteration:
        raise RuntimeError("Entry point 'control-dummy' not found in gui_scripts")

    # Split the entry point target: "module.submodule:func"
    module_path, func_name = ep.value.split(":")

    # Build the Python one-liner to run it
    command = f"import {module_path}; {module_path}.{func_name}()"

    # Start the GUI script as a subprocess
    print("Starting control-dummy GUI in pytest fixture ...")
    gui_proc = subprocess.Popen(
        [sys.executable, "-u", "-c", command],  # -u = unbuffered stdout/stderr
        stdout=None,
        stderr=None,
        env=env,
    )

    # Wait for the control GUI to start and be ready to accept connections

    if not wait_for_tcp_port("localhost", 8897, timeout=30):
        gui_proc.kill()
        raise RuntimeError("Control-dummy GUI failed to start within 30 seconds")

    yield  # Run the test now

    # Cleanup: gracefully terminate the GUI
    try:
        gui_proc.send_signal(signal.SIGTERM)
        gui_proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        gui_proc.kill()
    except ProcessLookupError:
        pass


def test_environment_variable_is_set():
    """Check if the QT_QPA_PLATFORM environment variable is set to 'offscreen'."""
    assert os.getenv("QT_QPA_PLATFORM") == "offscreen"
    assert os.getenv("QT_QUICK_BACKEND") == "software"


def test_control_window_panic_stops_and_restores_server(qapp, qtbot, monkeypatch):
    """Panic mode should suspend and later restore the SCPI server."""

    class SpyControlWindow(ControlWindow):
        def __init__(self) -> None:
            super().__init__("panic-test", [exampleDict()])
            self.start_server_calls = 0
            self.stop_server_calls = 0

        def startServer(self) -> None:
            self.start_server_calls += 1
            self._local_server = cast(SCPI_TCP_Server, object())

        def stopServer(self) -> None:
            self.stop_server_calls += 1
            self._local_server = None

    window = SpyControlWindow()
    qtbot.addWidget(window)

    def _fail_on_modal_error(*args, **kwargs):
        raise AssertionError("panic test unexpectedly triggered the modal error dialog")

    monkeypatch.setattr(QMessageBox, "critical", _fail_on_modal_error)
    window.running = True
    window._local_server = cast(SCPI_TCP_Server, object())

    window.panic(True, "test panic")

    assert window.stop_server_calls >= 1
    assert window._server_disabled_by_panic is True
    assert window._local_server is None

    window.panic(True, "still panicking")

    assert window._server_disabled_by_panic is True
    assert window._local_server is None

    window.panic(False, "test unpanic")

    assert window.start_server_calls >= 1
    assert window._server_disabled_by_panic is False
    assert window._local_server is not None


def test_control_window_uses_unique_guidict_system_names(qapp, qtbot):
    """Implicit GuiDict systems use their unique names after merging."""

    class FirstPanel(GuiDict):
        data = {"First": var(None, columns="Readout")}

    class SecondPanel(GuiDict):
        data = {"Second": var(None, columns="Readout")}

    window = ControlWindow("named-systems", [FirstPanel, SecondPanel])
    qtbot.addWidget(window)

    assert [guidict.S.name for guidict in window.guidicts] == [
        "FirstPanel",
        "SecondPanel",
    ]
    assert window.S.FirstPanel is window.guidicts[0].S
    assert window.S.SecondPanel is window.guidicts[1].S


def test_control_window_rejects_duplicate_system_names(qapp):
    """System instance names are the unique binding contract in a control GUI."""

    class FirstPanel(GuiDict):
        S = System(name="shared")
        data = {"First": var(None, columns="Readout")}

    class SecondPanel(GuiDict):
        S = System(name="shared")
        data = {"Second": var(None, columns="Readout")}

    with pytest.raises(ValueError):
        ControlWindow("duplicate-systems", [FirstPanel, SecondPanel])


def test_methodbundle_guidict_method_runs_on_gui_thread(qapp, qtbot):
    """MethodBundle change handlers should execute through the GUI thread."""

    class MethodBundleDict(GuiDict):
        change_bundle = MethodBundle()
        data = {
            "MethodBundle": var(None, columns="Readout"),
            "Value": var(int, columns=go.labeltext, modify=[change_bundle, None]),
        }

        def __init__(self) -> None:
            super().__init__()
            self.change_bundle.add_change_handler(self.record_callback)
            self.callback_thread: QThread | None = None
            self.callback_value: int | None = None

        def record_callback(self, *, value: int) -> None:
            self.callback_thread = QThread.currentThread()
            self.callback_value = value

    guidict = MethodBundleDict()
    dock = guidict.create_GUI()
    qtbot.addWidget(dock)

    def update_value() -> None:
        guidict["Value"].value = 42

    worker = threading.Thread(target=update_value)
    worker.start()
    worker.join()

    qtbot.waitUntil(lambda: guidict.callback_thread is not None, timeout=1000)

    assert guidict.callback_thread == qapp.thread()
    assert guidict.callback_value == 42


def test_matrix_script_control_dummy(start_control_dummy):
    """
    Test the matrix script execution with the control dummy GUI.

    This test function verifies that the matrix script can be properly executed
    using the control dummy GUI. It generates a test script, runs it, and
    validates the output data files and their contents.

    Returns
    -------
    None

    Raises
    ------
    AssertionError
        If any of the test validations fail.
    """
    # prepares and runs a test script in the same fashion as done by
    # matrix_script, code is partially duplicated but should not require
    # changes except for bugfixes

    script = matr1x.core.util.generate_script(user_script)
    with tempfile.NamedTemporaryFile(mode="w+b") as tf:
        for line in script:
            tf.write(line.encode())
        tf.flush()
        script = (
            "import matr1x.util as mu\n"
            f"mu.matrix_script_process({tf.name!r}, {{}}, '', None, ['system_dummygui'])"
        )
        ret = subprocess.run([sys.executable, "-c", script], cwd=path, check=False)
        assert ret.returncode == 0
        files = list(path.glob(f"epische_messdatei{output_extension}"))
        assert len(files) >= 1
        h, d = matr1x.core.eval.loadmatrix(files[-1], structured=False)
        assert len(h["columns"]) == 6
        assert isinstance(d, np.ndarray), f"Expected np.ndarray, got {type(d)}"
        assert d.shape == (11, 6)
