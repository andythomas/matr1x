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
"""Logging helpers for the matr1x package."""

import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

__all__ = ["WeekRotatingFileHandler"]


class WeekRotatingFileHandler(logging.FileHandler):
    """A file handler that rotates log files at ISO week boundaries.

    The log file name is derived from the current ISO year and week
    number, e.g. ``matr1x_202634.log``. The target file is resolved
    for every record, so long-running processes always write to the
    file of the current week.

    Parameters
    ----------
    logfolder:
        Directory the log files are written to.
    prefix:
        File name prefix, the log file name is
        ``{prefix}_{iso_year}{iso_week:02d}.log``.
    """

    # Handler.__init__ always replaces the default None with an RLock.
    lock: threading.RLock

    def __init__(self, logfolder: str | Path, prefix: str = "matr1x") -> None:
        """Create the handler and open the log file of the current week."""
        self.logfolder = Path(logfolder)
        self.prefix = prefix
        iso_year, iso_week, _ = datetime.now().isocalendar()
        self._week: tuple[int, int] = (iso_year, iso_week)
        super().__init__(self._filename_for(self._week), mode="a", encoding="utf-8")

    def _filename_for(self, week: tuple[int, int]) -> Path:
        """Return the log file path for the given ISO year and week."""
        iso_year, iso_week = week
        return self.logfolder / f"{self.prefix}_{iso_year}{iso_week:02d}.log"

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a record, rotating to the current week's file if needed.

        Rotation is performed under the handler lock, so it is safe
        from multiple threads. Errors are reported via `handleError`,
        so logging never interrupts the caller.
        """
        with self.lock:
            iso_year, iso_week, _ = datetime.now(tz=timezone.utc).astimezone().isocalendar()
            week = (iso_year, iso_week)
            if week != self._week:
                try:
                    self._rotate(week)
                except OSError:
                    self.handleError(record)
                    return
            super().emit(record)

    def _rotate(self, week: tuple[int, int]) -> None:
        """Close the current file and open the file of the given week."""
        self.close()
        self.baseFilename = str(self._filename_for(week).resolve())
        self.stream = self._open()
        self._week = week
