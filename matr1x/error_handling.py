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
"""
Help to handle errors in the matr1x modules.

This addresses several concerns:
(1) Qt6 sometimes "eats" exceptions, i.e. it throws them in the
commandline, but does not quit the app. Since the main scripts are all
GUI apps and not necessarily started via a terminal, the error becomes
silent.
(2) One should always distinguish between a successful call of a
function and an erroneous one.
(3) Qt functions can often return "None" in addition to the expected
return value.
"""

import asyncio
import logging
import sys
import threading
import traceback
from asyncio import AbstractEventLoop
from dataclasses import dataclass
from threading import ExceptHookArgs
from types import TracebackType
from typing import Any, Generic, TypeAlias, TypeVar, final

from PySide6.QtWidgets import QApplication, QMessageBox

logger = logging.getLogger(__name__)


# (1) General exception handler


def _show_error_messagebox(
    exc_type: type[BaseException],
    exc_value: BaseException | None,
    exc_tb: TracebackType | None,
    /,
) -> None:
    """Show a QMessageBox for any uncaught exception."""
    app = QApplication.instance()

    formatted = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.error("Unhandled exception:\n%s", formatted)

    if app is None:
        print("Unhandled exception:", formatted, file=sys.stderr)
        return

    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setWindowTitle("An unexpected error occurred")
    msg.setText(f"{exc_type.__name__}: {exc_value}")
    msg.setDetailedText(formatted)
    msg.exec()


def _threading_excepthook(args: ExceptHookArgs) -> None:
    """Exception hook for background threads."""
    _show_error_messagebox(args.exc_type, args.exc_value, args.exc_traceback)


def _asyncio_exception_handler(loop: AbstractEventLoop, context: dict[str, Any]) -> None:
    """Handle exceptions in asyncio tasks."""
    msg = context.get("exception", context["message"])
    exc = context.get("exception")
    if exc:
        exc_type = type(exc)
        exc_value = exc
        exc_tb = exc.__traceback__
    else:
        exc_type = RuntimeError
        exc_value = RuntimeError(msg)
        exc_tb = None
    _show_error_messagebox(exc_type, exc_value, exc_tb)


def install_error_handler():
    """Handle all uncaught exceptions."""
    sys.excepthook = _show_error_messagebox
    if hasattr(threading, "excepthook"):
        threading.excepthook = _threading_excepthook
    try:
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(_asyncio_exception_handler)
    except RuntimeError:
        # No event loop yet
        pass
    logger.info("Error handler installed.")


# (2) Dinstinguish successful function call


T = TypeVar("T")
E = TypeVar("E")


@final
@dataclass(frozen=True)
class Success(Generic[T]):
    """Received value from a successful operation."""

    value: T


@final
@dataclass(frozen=True)
class Error(Generic[E]):
    """Received error from a failed operation."""

    error: E


Result: TypeAlias = Success[T] | Error[E]


# (3) Catch "None" returns in function calls


class InternalInvariantError(RuntimeError):
    """
    A core assumption of the code was violated.

    The application reached a state that should be impossible.
    """


def expect_not_none(value: T | None, message: str) -> T:
    """
    Expect a value to not be None.

    Parameters
    ----------
    value: Any
        The value to be tested.
    message: str
        The message of the raise in case the value is None.

    Raises
    ------
    InternalInvariantError
        If the value is None, which should be impossible.

    Returns
    -------
    Any, but not None.
    """
    if value is None:
        raise InternalInvariantError(message)
    return value
