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
"""Validate (some) of the config options for better error messages."""

import math
from enum import IntFlag
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationError

from matr1x.util import flatten, get_formatted_line


def format_validation_error(e: ValidationError | TypeError | ValueError, base: str = "") -> str:
    """
    Format the error output of the toml validation.

    Parameters
    ----------
    e: ValidationError or TypeError or ValueError
        The errors with all information.
    base: str
        The prefix of the error location, e.g., 'ifwlib'.

    Returns
    -------
    str
        The properly formatted string with the human readable errors.
    """
    msg = ""
    if isinstance(e, ValidationError):
        for err in e.errors():
            location = base + ".".join(str(i) for i in err["loc"])
            msg += f"{location}: {err['msg']}"
            if "url" in err:
                msg += f". More info at {err['url']}"
            msg += "\n"
    else:
        # Handle TypeError and ValueError which don't have errors() method
        msg += f"{base}: {str(e)}\n"
    return msg


class UserlibInstallConfig(BaseModel):
    """Allow validation of [userlib.install]."""

    model_config = ConfigDict(extra="forbid")

    controlguis: list[str] | None = None
    root_path: Path | None = None


class UserlibConfig(BaseModel):
    """Allow validation of [userlib]."""

    systems_directory: Path | None = None
    install: UserlibInstallConfig | None = None


class Matr1xInstallConfig(BaseModel):
    """Allow validation of [matr1x.install]."""

    model_config = ConfigDict(extra="forbid")

    controlguis: list[str] | None = None
    create_directories: bool
    desktopintegration: bool
    root_path: Path


class Matr1xDevicesVisadeviceConfig(BaseModel):
    """Allow validation of [matr1x.devices.visadevice]."""

    model_config = ConfigDict(extra="forbid")

    cmdpers: int
    pts: bool
    visadebug: bool


class Matr1xDevicesConfig(BaseModel):
    """Allow validation of [matr1x.devices]."""

    visadevice: Matr1xDevicesVisadeviceConfig


class Matr1xScriptsMatrix_ScriptShortcutsConfig(BaseModel):
    """Allow validation of [matr1x.scripts.matrix-script.shortcuts]."""

    model_config = ConfigDict(extra="forbid")

    line_comment_display: str
    line_comment_shortcut: str


class Matr1xScriptsMatrix_ScriptConfig(BaseModel):
    """Allow validation of [matr1x.scripts.matrix-script]."""

    model_config = ConfigDict(extra="forbid")

    script_path: Path
    store_script_in_datafile: bool
    duplicate_output_to_logfile: bool
    print_to_comment: bool
    shortcuts: Matr1xScriptsMatrix_ScriptShortcutsConfig


class Matr1xScriptsConfig(BaseModel):
    """Allow validation of [matr1x.scripts]."""

    model_config = ConfigDict(extra="forbid")

    matrix_script: Matr1xScriptsMatrix_ScriptConfig = Field(alias="matrix-script")


class Matr1xEmailConfig(BaseModel):
    """Allow validation of [matr1x.email]."""

    model_config = ConfigDict(extra="forbid")

    smtp_server: str
    smtp_user: str
    password: str
    fromemail: str
    smtp_port: int = 465


class Matr1xConfig(BaseModel):
    """Allow validation of [matr1x]."""

    model_config = ConfigDict(extra="forbid")

    datetime_format: str
    logging_directory: Path
    logging_format: str
    systems_directory: Path
    users_directory: Path
    install: Matr1xInstallConfig
    devices: Matr1xDevicesConfig
    scripts: Matr1xScriptsConfig
    email: Matr1xEmailConfig | None = None
    systems: Any


class MainConfig(BaseModel):
    """Allow validation of the configuration toml."""

    matr1x: Matr1xConfig


# --- merged system "air-gap" evaluations


class SystemDevice(BaseModel):
    """Model for device entries."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str


class SystemParameter(BaseModel):
    """Model for parameter entries."""

    model_config = ConfigDict(extra="forbid")

    name: str
    unit: str
    description: str
    index: int
    settable: bool


class SystemMethod(BaseModel):
    """Model for method entries."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str


class SystemInfo(BaseModel):
    """Main model for the configuration."""

    model_config = ConfigDict(extra="forbid")

    devices: dict[str, SystemDevice]
    parameters: dict[str, SystemParameter]
    methods: dict[str, SystemMethod]
    config: dict[str, Any]

    @property
    def flat_parameters(self) -> list[SystemParameter]:
        """Returns a flat list of parameters."""
        result: list[SystemParameter] = []
        for parameter in self.parameters.values():
            settable = parameter.settable
            name_parts = [n.strip() for n in parameter.name.split(",")]
            unit_parts = [u.strip() for u in parameter.unit.split(",")]
            for name, unit in zip(name_parts, unit_parts):
                result.append(
                    SystemParameter(
                        name=name,
                        unit=unit,
                        description=parameter.description,
                        index=parameter.index,
                        settable=settable,
                    )
                )
        return result


# --- measurement data for matrix and matrix-script


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


class Modifier(IntFlag):
    """A set of modifiers for message handling."""

    NONE = 0
    DELETE_CURRENT_LINE = 1


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


class ErrorMessage(BaseModel):
    """Model for the error message."""

    error: str

    def __init__(self, error: str | None = None, **data: Any):
        if error is not None:
            data["error"] = error
        super().__init__(**data)


class LineNumber(BaseModel):
    """Model for the line number data."""

    line: int

    def __init__(self, line: int | None = None, **data: Any):
        if line is not None:
            data["line"] = line
        super().__init__(**data)


class Datafile(BaseModel):
    """Model for the datafile."""

    datafile: str

    def __init__(self, datafile: str | None = None, **data: Any):
        if datafile is not None:
            data["datafile"] = datafile
        super().__init__(**data)


class InputParameters(BaseModel):
    """Parameters for script input requests."""

    query: str
    input_type: str
    timeout: float | None = float("inf")
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


MeasurementData = (
    Header
    | SetValues
    | MeasuredValues
    | Telemetry
    | Message
    | ErrorMessage
    | Datafile
    | LineNumber
    | InputParameters
)


class Envelope(RootModel[MeasurementData]):
    """Simplify received data handling."""

    @property
    def payload(self) -> MeasurementData:
        """Return the parsed payload."""
        return self.root
