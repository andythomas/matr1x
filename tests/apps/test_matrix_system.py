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
Matrix system test module.

This module contains tests for checking the intended behavior of the
matrix and its interaction with the System instance.
"""

import json
import socket
import sys
import threading
from contextlib import suppress
from pathlib import Path
from pprint import pformat

import pytest

import matr1x.core.util
from matr1x.apps import cli as matrix_cli
from matr1x.core.error_handling import Success
from matr1x.core.execthread import matrix_script_process
from matr1x.core.system import get_system_info


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
            except Exception as e:  # noqa: BLE001  # record any failure
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
        Get the list of collected events.

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
def tap_server(monkeypatch):
    """
    Yield a TapCollector for the tapin system to connect to.

    Sets the PLUGIN_TAP_* environment variables and closes the socket
    automatically.
    """
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Bind to localhost on an ephemeral port
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    host, port = srv.getsockname()

    monkeypatch.setenv("PLUGIN_TAP_HOST", host)
    monkeypatch.setenv("PLUGIN_TAP_PORT", str(port))

    collector = TapCollector(srv)
    collector.start()

    try:
        yield collector
    finally:
        with suppress(OSError):
            srv.close()
        collector.join()


def run_matrix(monkeypatch, *args: str) -> int:
    """Run the matrix CLI in-process and return its exit code."""
    monkeypatch.setattr(sys, "argv", ["matrix", *args])
    with pytest.raises(SystemExit) as exc:
        matrix_cli.main()
    return int(exc.value.code or 0)


def _run_tapin_script(user_script: str, input_dir: Path, tmp_path: Path) -> None:
    """Generate and run a matrix script with the tapin system in-process."""
    script = matr1x.core.util.generate_script(user_script)
    script_file = tmp_path / "tapin_test.matrix"
    script_file.write_text("".join(script))
    matrix_script_process(str(script_file), {}, "", None, [str(input_dir / "system_tapin.py")])


def test_tapin_script_events(tap_server, input_dir: Path, tmp_path: Path):
    """
    Test that TapinSystem methods are called and report correct arguments.

    Asserts
    -------
    __init__, set, and reset events are received.
    reset event includes status: finished kwarg.
    """
    collector = tap_server

    user_script = "# empty test script"
    _run_tapin_script(user_script, input_dir, tmp_path)

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


def test_tapin_script_exceptions(tap_server, input_dir: Path, tmp_path: Path):
    """
    Test that TapinSystem methods are called and report correct arguments in case of exceptions.

    Asserts
    -------
    __init__, set, and reset events are received.
    reset event includes status: errored kwarg.
    """
    collector = tap_server

    user_script = """# raise an exception
raise Exception('Test exception')
"""
    _run_tapin_script(user_script, input_dir, tmp_path)

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


def test_tapin_script_keyboardinterrupt(tap_server, input_dir: Path, tmp_path: Path):
    """
    Test that TapinSystem methods are called and report correct arguments in case of Ctrl+C.

    Asserts
    -------
    __init__, set, and reset events are received.
    reset event includes status: aborted kwarg.
    """
    collector = tap_server

    user_script = """# end script with KeyboardInterrupt
end_script(finished=False)
"""
    _run_tapin_script(user_script, input_dir, tmp_path)

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


def test_tapin_matrix(tap_server, input_dir: Path, tmp_path: Path, monkeypatch):
    """
    Test that TapinSystem methods are called by matrix.

    Asserts
    -------
    __init__, set, and reset events are received.
    reset event includes status: finished kwarg.
    """
    collector = tap_server
    input_file = input_dir / "sweep_tapin.sw8"
    # headless urwid screen, see UrwidMeasurement.prepare
    monkeypatch.setenv("CI", "true")
    ret = run_matrix(monkeypatch, "-i", str(input_file), "-o", str(tmp_path / "tapin.ma8"))

    assert ret == 0, f"matrix exited with {ret}"

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


def test_tapin_matrix_exception(tap_server, input_dir: Path, tmp_path: Path, monkeypatch):
    """
    Test that TapinSystem methods are called by matrix and exception handling.

    Asserts
    -------
    __init__, set, and reset events are received.
    reset event includes status: errored kwarg.
    """
    collector = tap_server
    input_file = input_dir / "sweep_tapin_error.sw8"
    # headless urwid screen, see UrwidMeasurement.prepare
    monkeypatch.setenv("CI", "true")
    ret = run_matrix(monkeypatch, "-i", str(input_file), "-o", str(tmp_path / "tapin_error.ma8"))

    assert ret == 1, f"matrix exited with {ret}"

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


def test_system_grab_information(repo_root: Path):
    """
    Test the information retrieval of system information.

    Asserts
    -------
    Success of the air-gapped call.
    """
    dummy_system = str(repo_root / "matr1x/systems/system_dummy.py")
    info = get_system_info([dummy_system])
    assert isinstance(info, Success)
    assert "source" in info.value.dcdata
