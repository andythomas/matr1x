# This file is part of a software collection for data acquisition (matr1x).
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
Matrix system test module.

This module contains tests for checking the intended behavior of the
matrix and its interaction with the System instance.
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
from contextlib import suppress
from pathlib import Path
from pprint import pformat

import pytest

import matr1x.core.util
from matr1x import output_extension
from matr1x.core.error_handling import Success
from matr1x.gui.helpers import get_system_info

path = Path(__file__).resolve().parent


class TapCollector:
    """
    Collect JSON events from a socket connection.

    Use .events to read the collected list after .join().
    """

    def __init__(self, srv_sock: socket.socket) -> None:
        """
        Initialize the TapCollector.

        Parameters
        ----------
        srv_sock : socket.socket
            The server socket to accept connections from.
        """
        self._srv: socket.socket = srv_sock
        self._thread: threading.Thread | None = None
        self._conn: socket.socket | None = None
        self._events: list[dict] = []
        self._error: Exception | None = None

    def start(self, timeout: float = 10) -> None:
        """
        Start collecting events in a separate thread.

        The server socket will start listening for an incoming connection
        and then read JSON events line by line until the connection closes
        or an error occurs.

        Parameters
        ----------
        timeout : float, optional
            Timeout in seconds for accepting the initial connection.
            Defaults to 10 second.
        """
        self._srv.settimeout(timeout)

        def _run() -> None:
            try:
                conn: socket.socket
                conn, _ = self._srv.accept()
                self._conn = conn
                f = conn.makefile("r", encoding="utf-8", newline="\n")
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    self._events.append(json.loads(line))
            except Exception as e:
                self._error = e
            finally:
                with suppress(OSError):
                    if self._conn:
                        self._conn.close()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def join(self, timeout: float = 5) -> None:
        """
        Wait for the collector thread to finish.

        Parameters
        ----------
        timeout : float, optional
            The maximum time in seconds to wait for the thread to complete.
            Defaults to 5 seconds.
        """
        if self._thread is None:
            return
        self._thread.join(timeout=timeout)

    @property
    def events(self) -> list[dict]:
        """
        Get the list of collected JSON events.

        Returns
        -------
        list[dict]
            A list where each element is a dictionary parsed from a JSON event.
        """
        return list(self._events)

    @property
    def error(self) -> Exception | None:
        """
        Get any error that occurred during event collection.

        Returns
        -------
        Exception or None
            The exception object if an error occurred, otherwise None.
        """
        return self._error


@pytest.fixture
def tap_server():
    """
    Yield (env_overrides, collector) for the child to connect to.

    Closes the socket automatically.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Bind to localhost on an ephemeral port
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    host, port = srv.getsockname()

    collector = TapCollector(srv)
    collector.start()

    env = {
        "PLUGIN_TAP_HOST": host,
        "PLUGIN_TAP_PORT": str(port),
    }
    try:
        yield env, collector
    finally:
        with suppress(OSError):
            srv.close()
        collector.join()


@pytest.fixture(autouse=True)
def clean_data_files():
    """
    Clean up data files created during tests.

    This fixture runs automatically before and after each test to clean up any
    data files that were created. It tracks existing files before the test and
    removes any new files created during test execution.

    Yields
    ------
    None
    """
    existingfiles = set(path.glob(f"*{output_extension}"))
    # run test
    yield
    files = set(path.glob(f"*{output_extension}"))
    newfiles = files - existingfiles
    for f in newfiles:
        f.unlink()


def _launch_tapin_script(
    user_script: str,
    env_overrides: dict[str, str],
) -> subprocess.CompletedProcess:
    """
    Launch a child Python process that directly imports `system_tapin`.

    Parameters
    ----------
    user_script : Path
        User script for matrix-script execution.
    env_overrides : dict[str, str]
        Environment variables to override.

    Returns
    -------
    subprocess.CompletedProcess
        A CompletedProcess object of the child process
    """
    env = os.environ.copy()
    env.update(env_overrides)
    # Get the absolute path to system_tapin.py
    system_tapin_abs_path = path / "system_tapin.py"
    # Generate the script
    script = matr1x.core.util.generate_script(user_script)
    with tempfile.NamedTemporaryFile(mode="w+b") as tf:
        for line in script:
            tf.write(line.encode())
        tf.flush()
        execscript = (
            "import matr1x.util as mu\n"
            "mu.matrix_script_process(\n"
            f"{tf.name!r}, {{}}, '', None, [{str(system_tapin_abs_path)!r}]\n"
            ")"
        )
        ret = subprocess.run([sys.executable, "-c", execscript], cwd=path, env=env, check=False)
    return ret


def _launch_tapin_matrix(
    inputfile: Path | str,
    env_overrides: dict[str, str],
):
    """Launch a matrix measurement with a tapin system.

    Parameters
    ----------
    inputfile : Path or str
        Path to the input file.

    Returns
    -------
    subprocess.CompletedProcess
        A CompletedProcess object of the child process
    """
    env = os.environ.copy()
    env.update(env_overrides)
    cmd = [matr1x.core.util.get_matrix_binary(), "-i", str(inputfile)]
    print(subprocess.list2cmdline(cmd))
    return subprocess.run(cmd, env=env, check=False)


def test_tapin_script_events(tap_server):
    """
    Test that TapinSystem methods are called and report correct arguments.

    Asserts
    -------
    __init__, set, and reset events are received.
    reset event includes status: finished kwarg.
    """
    env_overrides, collector = tap_server

    user_script = "# empty test script"
    ret = _launch_tapin_script(user_script, env_overrides)

    assert ret.returncode == 0, f"Script exited with {ret.returncode}"

    # Allow the collector thread to finish reading any buffered lines
    collector.join()
    if collector.error:
        raise AssertionError(f"Tapin collector error: {collector.error}")

    events = collector.events

    # Assertions
    actual_events = [e for e in events if e and e.get("event")]
    expected = ["__init__", "set", "reset"]
    names = [e["event"] for e in actual_events]
    assert names == expected, (
        "Event sequence mismatch.\n"
        f"Expected: {expected}\n"
        f"Actual:   {names}\n"
        f"Full records:\n{pformat(actual_events)}"
    )

    # Check for reset kwarg
    reset_events = [e for e in actual_events if e["event"] == "reset"]
    assert "status" in reset_events[0]["kwargs"]
    assert reset_events[0]["kwargs"]["status"] == "finished"


def test_tapin_script_exceptions(tap_server):
    """
    Test that TapinSystem methods are called and report correct arguments in case of exceptions.

    Asserts
    -------
    __init__, set, and reset events are received.
    reset event includes status: errored kwarg.
    """
    env_overrides, collector = tap_server

    user_script = """# raise an exception
raise Exception('Test exception')
"""
    ret = _launch_tapin_script(user_script, env_overrides)

    assert ret.returncode == 0, f"Script exited with {ret.returncode}"

    # Allow the collector thread to finish reading any buffered lines
    collector.join()
    if collector.error:
        raise AssertionError(f"Tapin collector error: {collector.error}")

    events = collector.events

    # Assertions
    actual_events = [e for e in events if e and e.get("event")]
    expected = ["__init__", "set", "reset"]
    names = [e["event"] for e in actual_events]
    assert names == expected, (
        "Event sequence mismatch.\n"
        f"Expected: {expected}\n"
        f"Actual:   {names}\n"
        f"Full records:\n{pformat(actual_events)}"
    )

    # Check for reset kwarg
    reset_events = [e for e in actual_events if e["event"] == "reset"]
    assert "status" in reset_events[0]["kwargs"]
    assert reset_events[0]["kwargs"]["status"] == "errored"


def test_tapin_script_keyboardinterrupt(tap_server):
    """
    Test that TapinSystem methods are called and report correct arguments in case of Ctrl+C.

    Asserts
    -------
    __init__, set, and reset events are received.
    reset event includes status: aborted kwarg.
    """
    env_overrides, collector = tap_server

    user_script = """# end script with KeyboardInterrupt
end_script(finished=False)
"""
    ret = _launch_tapin_script(user_script, env_overrides)

    assert ret.returncode == 0, f"Script exited with {ret.returncode}"

    # Allow the collector thread to finish reading any buffered lines
    collector.join()
    if collector.error:
        raise AssertionError(f"Tapin collector error: {collector.error}")

    events = collector.events

    # Assertions
    actual_events = [e for e in events if e and e.get("event")]
    expected = ["__init__", "set", "reset"]
    names = [e["event"] for e in actual_events]
    assert names == expected, (
        "Event sequence mismatch.\n"
        f"Expected: {expected}\n"
        f"Actual:   {names}\n"
        f"Full records:\n{pformat(actual_events)}"
    )

    # Check for reset kwarg
    reset_events = [e for e in actual_events if e["event"] == "reset"]
    assert "status" in reset_events[0]["kwargs"]
    assert reset_events[0]["kwargs"]["status"] == "aborted"


def test_tapin_matrix(tap_server):
    """
    Test that TapinSystem methods are called by matrix.

    Asserts
    -------
    __init__, set, and reset events are received.
    reset event includes status: finished kwarg.
    """
    env_overrides, collector = tap_server
    input_file = path / "sweep_tapin.sw8"
    ret = _launch_tapin_matrix(input_file, env_overrides)

    assert ret.returncode == 0, f"matrix exited with {ret.returncode}"

    # Allow the collector thread to finish reading any buffered lines
    collector.join()
    if collector.error:
        raise AssertionError(f"Tapin collector error: {collector.error}")

    events = collector.events

    # Assertions
    actual_events = [e for e in events if e and e.get("event")]
    expected = ["__init__", "set", "reset"]
    names = [e["event"] for e in actual_events]
    assert names == expected, (
        "Event sequence mismatch.\n"
        f"Expected: {expected}\n"
        f"Actual:   {names}\n"
        f"Full records:\n{pformat(actual_events)}"
    )

    # Check for reset kwarg
    reset_events = [e for e in actual_events if e["event"] == "reset"]
    assert "status" in reset_events[0]["kwargs"]
    assert reset_events[0]["kwargs"]["status"] == "finished"


def test_tapin_matrix_exception(tap_server):
    """
    Test that TapinSystem methods are called by matrix and exception handling.

    Asserts
    -------
    __init__, set, and reset events are received.
    reset event includes status: errored kwarg.
    """
    env_overrides, collector = tap_server
    input_file = path / "sweep_tapin_error.sw8"
    ret = _launch_tapin_matrix(input_file, env_overrides)

    assert ret.returncode == 1, f"matrix exited with {ret.returncode}"

    # Allow the collector thread to finish reading any buffered lines
    collector.join()
    if collector.error:
        raise AssertionError(f"Tapin collector error: {collector.error}")

    events = collector.events

    # Assertions
    actual_events = [e for e in events if e and e.get("event")]
    expected = ["__init__", "set", "reset"]
    names = [e["event"] for e in actual_events]
    assert names == expected, (
        "Event sequence mismatch.\n"
        f"Expected: {expected}\n"
        f"Actual:   {names}\n"
        f"Full records:\n{pformat(actual_events)}"
    )

    # Check for reset kwarg
    reset_events = [e for e in actual_events if e["event"] == "reset"]
    assert "status" in reset_events[0]["kwargs"]
    assert reset_events[0]["kwargs"]["status"] == "errored"


def test_system_grab_information():
    """
    Test the information retrieval of system information.

    Asserts
    -------
    Success of the air-gapped call.
    """
    dummy_system = str((path / "../matr1x/systems/system_dummy.py").resolve())
    info = get_system_info([dummy_system])
    assert isinstance(info, Success)
