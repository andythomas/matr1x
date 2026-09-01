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
"""Pydantic models for measurement data."""

import logging
import math
from typing import Any, final

from pydantic import BaseModel, Field

from matr1x.core.util import flatten, get_formatted_line


@final
class Header(BaseModel):
    """Model for the header of a measurement output."""

    columns: list
    units: list
    to_stdout: bool | None = None

    def __str__(self) -> str:
        """Return a string representation of the header."""
        lines = [
            get_formatted_line(flatten(self.columns)),
            get_formatted_line(flatten(self.units)),
        ]
        return "\n".join(lines)


@final
class SetValues(BaseModel):
    """Model for the set values."""

    set_values: list
    to_stdout: bool | None = None

    def __init__(self, values: list | None = None, **data: Any):
        if values is not None:
            data["set_values"] = values
        super().__init__(**data)

    def __str__(self) -> str:
        """Return a string representation of the set values."""
        return get_formatted_line(flatten(self.set_values), prefix="Set : ")


@final
class MeasuredValues(BaseModel):
    """Model for the measured values."""

    measured_values: list
    to_stdout: bool | None = None

    def __init__(self, values: list | None = None, **data: Any):
        if values is not None:
            data["measured_values"] = values
        super().__init__(**data)

    def __str__(self) -> str:
        """Return a string representation of the measured values."""
        return get_formatted_line(flatten(self.measured_values), prefix="Meas: ")


@final
class Telemetry(BaseModel):
    """Model for the telemetry data."""

    point: int
    points: int
    elapsed: float
    remaining: float | None
    settime: float | None
    readtime: float | None
    to_stdout: bool | None = None

    def __str__(self) -> str:
        """Return a string representation of the telemetry data."""
        remaining = self.remaining or math.nan
        return (
            f" {self.point}/{self.points} - "
            f"elapsed: {self.elapsed:.1f}m - "
            f"remaining: {remaining:.1f}m - "
            f"set/read: {self.settime:.1f}s/{self.readtime:.1f}s"
        )


class ExecutionLines(BaseModel):
    """Active user-script lines ordered from innermost to outermost."""

    lines: list[int] = Field(min_length=1)


@final
class Datafile(BaseModel):
    """Model for the datafile."""

    datafile: str

    def __init__(self, datafile: str | None = None, **data: Any):
        if datafile is not None:
            data["datafile"] = datafile
        super().__init__(**data)


@final
class InputParameters(BaseModel):
    """Parameters for script input requests."""

    query: str
    input_type: str
    timeout: float | None = None
    default_value: str = ""
    min_value: float | None = None
    max_value: float | None = None
    step: float | None = None
    decimals: int | None = None

    def __str__(self) -> str:
        """Return a string representation of the input parameters."""
        return (
            f"Requesting input type: {self.input_type}, Query: {self.query}, "
            f"Timeout: {self.timeout}, Default: {self.default_value}, Min: {self.min_value},"
            f" Max: {self.max_value}, Step: {self.step}"
        )


@final
class LogEntry(BaseModel):
    """Model for log entries."""

    name: str
    level: int
    getMessage: str
    created: float
    lineno: int

    def log_record(self, logger: logging.Logger) -> None:
        """Create a logging record from the log entry data."""
        record = logger.makeRecord(
            self.name, self.level, __file__, self.lineno, self.getMessage, (), exc_info=None
        )
        logger.handle(record)
