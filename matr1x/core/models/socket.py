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
"""Pydantic models for the message/socket protocol."""

from enum import IntFlag
from typing import Any, final

from pydantic import BaseModel, RootModel

from matr1x.core.models.data import (
    Datafile,
    ExecutionLines,
    Header,
    InputParameters,
    LogEntry,
    MeasuredValues,
    SetValues,
    Telemetry,
)


class Modifier(IntFlag):
    """A set of modifiers for message routing."""

    NONE = 0
    TO_PROGRESS_LABEL = 1


@final
class Message(BaseModel):
    """Model for messages."""

    message: str
    end: str = "\n"
    to_logfile: bool | None = None
    to_comment: bool | None = None
    modifier: Modifier = Modifier.NONE

    def __init__(self, message: str | None = None, **data: Any):
        if message is not None:
            data["message"] = message
        super().__init__(**data)

    @property
    def should_comment(self):
        """Determine if the message should also be put in the datafile."""
        from matr1x.core.config import config

        conf = config.matr1x
        return self.to_comment is True or (conf.print_to_comment and self.to_comment is not False)

    @property
    def should_log(self):
        """Determine if the message should also be logged."""
        from matr1x.core.config import config

        conf = config.matr1x
        return self.to_logfile is True or (
            conf.duplicate_output_to_logfile and self.to_logfile is not False
        )


@final
class ErrorMessage(BaseModel):
    """Model for the error message."""

    error: str

    def __init__(self, error: str | None = None, **data: Any):
        if error is not None:
            data["error"] = error
        super().__init__(**data)


MeasurementData = (
    Header
    | SetValues
    | MeasuredValues
    | Telemetry
    | Message
    | ErrorMessage
    | Datafile
    | ExecutionLines
    | InputParameters
    | LogEntry
)


class Envelope(RootModel[MeasurementData]):
    """Simplify received data handling."""

    @property
    def payload(self) -> MeasurementData:
        """Return the parsed payload."""
        return self.root
