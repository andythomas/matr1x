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
"""Module defines a class to recording calls to System methods for test purposes."""

# system_tapin.py
import atexit
import json
import os
import socket
from collections.abc import Callable, Generator
from contextlib import contextmanager
from threading import Lock
from typing import Any, TextIO

from matr1x.core.system import System
from matr1x.devices.dummy import dummy

# -----------------------------------------------------------------------------
# Persistent tap connection state (singleton per process)
# -----------------------------------------------------------------------------

_TAP_SOCK: socket.socket | None = None
_TAP_FILE: TextIO | None = None  # text-mode file from makefile("w", ...)
_TAP_LOCK = Lock()


def _open_once() -> TextIO | None:
    """Open the tap connection exactly once; return the writeable file-like object."""
    global _TAP_SOCK, _TAP_FILE

    if _TAP_FILE is not None:
        return _TAP_FILE

    host = os.getenv("PLUGIN_TAP_HOST")
    port_str = os.getenv("PLUGIN_TAP_PORT")
    if not host or not port_str:
        return None

    s = socket.create_connection((host, int(port_str)))
    f = s.makefile("w", encoding="utf-8", newline="\n")
    _TAP_SOCK, _TAP_FILE = s, f
    atexit.register(_close_tap)
    return _TAP_FILE


def _close_tap() -> None:
    """Flush and close the persistent tap connection if open."""
    global _TAP_SOCK, _TAP_FILE
    try:
        if _TAP_FILE is not None:
            try:
                _TAP_FILE.flush()
            finally:
                _TAP_FILE.close()
    finally:
        if _TAP_SOCK is not None:
            try:
                _TAP_SOCK.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            _TAP_SOCK.close()
    _TAP_SOCK = None
    _TAP_FILE = None


@contextmanager
def tap() -> Generator[Callable[..., None], None, None]:
    """
    Yield an `emit` function writing JSON lines to a persistent socket.

    Falls back to a no-op emitter if PLUGIN_TAP_* environment variables are unset.
    """
    with _TAP_LOCK:
        f = _open_once()

    if f is None:

        def noop(*_a: Any, **_k: Any) -> None:
            """No-op emitter when no listener is configured."""
            return

        yield noop
        return

    def emit(
        event: str,
        *,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Emit a single event record and flush immediately."""

        def _safe(obj: Any) -> Any:
            try:
                json.dumps(obj)
                return obj
            except TypeError:
                return repr(obj)

        record: dict[str, Any] = {
            "event": event,
            "args": [_safe(a) for a in (args or ())],
            "kwargs": {k: _safe(v) for k, v in (kwargs or {}).items()},
        }
        if extra:
            record.update({k: _safe(v) for k, v in extra.items()})

        json.dump(record, f, ensure_ascii=False)
        f.write("\n")
        f.flush()

    yield emit


class TapinSystem(System):
    """Measurement system reporting arguments as events for tests."""

    def __init__(self) -> None:
        """Initialize the measurement system and emit an '__init__' event."""
        super().__init__()
        with tap() as emit:
            emit("__init__")
        # Instantiate and wire devices/parameters as before.
        self.add_dev(
            "dev",
            dummy,
            args=("TCPIP::localhost::10008::SOCKET",),
        )
        self.add_param(
            "dev",
            "unit",
            setter="set_p1",
            getter=["dev", "p1"],
            trigger=["dev", "trg"],
        )

    def set(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialize and configure the measurement.

        Called by matrix upon initialization. Devices are opened/initialized
        and may be configured.
        """
        super().set(*args, **kwargs)
        with tap() as emit:
            emit("set", args=list(args), kwargs=dict(kwargs))

    def reset(self, *args: Any, **kwargs: Any) -> None:
        """Reset device connections."""
        with tap() as emit:
            emit("reset", args=list(args), kwargs=dict(kwargs))
        super().reset(*args, **kwargs)

    def set_p1(self, value):
        """Set the value of parameter p1.

        If the value is negative, raise a ValueError.
        """
        self.devs["dev"].p1 = value
        if value < 0:
            raise ValueError("Value must be non-negative")
