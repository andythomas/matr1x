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
"""Qt error dialog for uncaught exceptions.

Qt sometimes "eats" exceptions: it prints them to the command line but does
not quit the app, so the error becomes silent in a GUI that is not started
from a terminal. :func:`install_qt_error_dialog` registers a ``QMessageBox``
handler with :mod:`matr1x.core.error_handling` so that uncaught exceptions
are shown to the user. Each GUI app calls it before
:py:meth:`QApplication.exec`.

Keeping the Qt dependency here (instead of in the Qt-free
:mod:`matr1x.core.error_handling`) is what lets the core stay GUI-agnostic.
"""

import traceback
from types import TracebackType

from PySide6.QtWidgets import QMessageBox

from matr1x.core.error_handling import set_uncaught_exception_dialog


def _qt_error_messagebox(
    exc_type: type[BaseException],
    exc_value: BaseException | None,
    exc_tb: TracebackType | None,
) -> None:
    """Show a QMessageBox for an uncaught exception."""
    formatted = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setWindowTitle("An unexpected error occurred")
    msg.setText(f"{exc_type.__name__}: {exc_value}")
    msg.setDetailedText(formatted)
    msg.exec()


def install_qt_error_dialog() -> None:
    """Register the Qt error dialog as the uncaught-exception handler."""
    set_uncaught_exception_dialog(_qt_error_messagebox)
