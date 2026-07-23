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
Define data models for configuration, system information, and measurement data.

This module provides Pydantic models used for:
1. Validating and providing default values for the matr1x configuration.
2. Describing system-wide properties (devices, parameters, methods).
3. Handling structured measurement, telemetry, and message data.
"""

import math
from collections.abc import Callable
from enum import IntFlag
from functools import cached_property
from pathlib import Path
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    ValidationError,
    model_validator,
)

import matr1x
from matr1x.util import flatten, get_formatted_line


def GuiField(
    default: Any = ..., *, decimals: int | None = None, ui_type: str | None = None, **kwargs
):
    """
    Wrap pydantic.Field to simplify GUI hints.

    Parameters
    ----------
    default : Any
        The default value for the field.
    decimals : int, optional
        The number of decimals to display for float values.
    ui_type : str, optional
        The GUI hint for the field (e.g., 'scifloat', 'file', 'folder', 'visa_resource').
    **kwargs
        Additional arguments passed to pydantic.Field.
    """
    json_schema_extra = kwargs.pop("json_schema_extra", {})
    if decimals is not None:
        json_schema_extra["decimals"] = decimals
    if ui_type is not None:
        json_schema_extra["ui_type"] = ui_type

    return Field(default, json_schema_extra=json_schema_extra, **kwargs)


# Semantic type aliases for GUI hints
SciFloat = Annotated[float, GuiField(ui_type="scifloat")]
FilePath = Annotated[str, GuiField(ui_type="file")]
FolderPath = Annotated[str, GuiField(ui_type="folder")]


def validate_visa_resource(value: str) -> str:
    """
    Validate a VISA resource string without opening the instrument.

    ``VisaResource`` can be used in Pydantic config models for systems that
    need a VISA address. The config editor will render the field as an
    editable combo box with PyVISA resource suggestions while still allowing
    free text input.

    Example
    -------
    ```python
    from pydantic import BaseModel, Field

    from matr1x.models import VisaResource


    class DeviceConfig(BaseModel):
        address: VisaResource = Field(..., description="VISA resource address")
    ```
    """
    if not value.strip():
        raise ValueError("VISA resource address must not be empty")

    import pyvisa

    try:
        resource_info = pyvisa.ResourceManager().resource_info(value)
    except Exception as exc:
        raise ValueError(f"Invalid VISA resource address {value!r}: {exc}") from exc
    if resource_info.resource_name is None:
        raise ValueError(f"Invalid VISA resource address {value!r}")
    return value


VisaResource = Annotated[
    str,
    AfterValidator(validate_visa_resource),
    GuiField(ui_type="visa_resource"),
]


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


class ConfigBaseModel(BaseModel):
    """Base class for configuration models providing recursive attribute access for extra fields."""

    def __getattr__(self, name: str) -> Any:
        """Allow attribute-style access to extra fields."""
        if (
            self.model_config.get("extra") == "allow"
            and self.model_extra is not None
            and name in self.model_extra
        ):
            val = self.model_extra[name]
            if isinstance(val, dict):
                return UntypedConfigModel(**val)
            return val
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


class UntypedConfigModel(ConfigBaseModel):
    """A model that allows any extra fields and provides attribute access."""

    model_config = ConfigDict(extra="allow")


class UserlibInstallConfig(BaseModel):
    """Allow validation of [userlib.install]."""

    model_config = ConfigDict(extra="forbid")

    controlguis: list[str] = []
    root_path: Path | None = None


class UserlibConfig(ConfigBaseModel):
    """Allow validation of [userlib]."""

    model_config = ConfigDict(extra="allow")

    systems_directory: Path | None = None
    install: UserlibInstallConfig | None = None


class Matr1xInstallConfig(BaseModel):
    """Allow validation of [matr1x.install]."""

    model_config = ConfigDict(extra="forbid")

    controlguis: list[str] = []
    create_directories: bool = True
    desktopintegration: bool = True
    root_path: Path = Path("core_library/")


class Matr1xDevicesVisadeviceConfig(BaseModel):
    """Allow validation of [matr1x.devices.visadevice]."""

    model_config = ConfigDict(extra="forbid")

    cmdpers: int = 30
    pts: bool = False
    visadebug: bool = False


class Matr1xDevicesConfig(BaseModel):
    """Allow validation of [matr1x.devices]."""

    visadevice: Matr1xDevicesVisadeviceConfig = Field(
        default_factory=Matr1xDevicesVisadeviceConfig
    )


class Matr1xScriptsMatrix_ScriptShortcutsConfig(BaseModel):
    """Allow validation of [matr1x.scripts.matrix-script.shortcuts]."""

    model_config = ConfigDict(extra="forbid")

    line_comment_display: str = "Ctrl+/"
    line_comment_shortcut: str = "Ctrl+/"


class Matr1xScriptsMatrix_ScriptConfig(BaseModel):
    """Allow validation of [matr1x.scripts.matrix-script]."""

    model_config = ConfigDict(extra="forbid")

    script_path: Path | None = None
    store_script_in_datafile: bool = False
    shortcuts: Matr1xScriptsMatrix_ScriptShortcutsConfig = Field(
        default_factory=Matr1xScriptsMatrix_ScriptShortcutsConfig
    )


class Matr1xScriptsConfig(BaseModel):
    """Allow validation of [matr1x.scripts]."""

    model_config = ConfigDict(extra="forbid")

    matrix_script: Matr1xScriptsMatrix_ScriptConfig = Field(
        alias="matrix-script", default_factory=Matr1xScriptsMatrix_ScriptConfig
    )


class Matr1xEmailConfig(BaseModel):
    """Allow validation of [matr1x.email]."""

    model_config = ConfigDict(extra="forbid")

    smtp_server: str | None = None
    smtp_user: str | None = None
    password: str | None = None
    fromemail: str | None = None
    smtp_port: int = 465

    @model_validator(mode="after")
    def validate_complete(self):
        """Make sure all email fields are set if any are configured."""
        fields = [self.smtp_server, self.smtp_user, self.password, self.fromemail]
        if any(v is not None for v in fields) and not all(v is not None for v in fields):
            raise ValueError("Set all settings: smtp_server, smtp_user, password, and fromemail")
        return self


class Matr1xConfig(BaseModel):
    """Allow validation of [matr1x]."""

    model_config = ConfigDict(extra="forbid")

    datetime_format: str = "%Y-%m-%dT%H:%M:%S"
    logging_directory: Path = Path("~/logs")
    logging_format: str = "%(asctime)s,%(msecs)03d,%(levelname)s,%(name)s: %(message)s"
    systems_directory: Path = Path("<pkgroot>/systems")
    users_directory: Path = Path("~/users")
    install: Matr1xInstallConfig = Matr1xInstallConfig()
    devices: Matr1xDevicesConfig = Matr1xDevicesConfig()
    scripts: Matr1xScriptsConfig = Matr1xScriptsConfig()
    email: Matr1xEmailConfig = Matr1xEmailConfig()
    systems: UntypedConfigModel = UntypedConfigModel()
    duplicate_output_to_logfile: bool = False
    print_to_comment: bool = False


class MainConfig(ConfigBaseModel):
    """Allow validation of the configuration toml."""

    model_config = ConfigDict(extra="allow")

    matr1x: Matr1xConfig = Field(default_factory=Matr1xConfig)

    @model_validator(mode="after")
    def validate_extra_sections(self):
        """Validate extra top-level sections as UserlibConfig."""
        if self.model_extra:
            for key, value in self.model_extra.items():
                if isinstance(value, dict):
                    # Validate and replace the raw dict with a validated model
                    self.model_extra[key] = UserlibConfig(**value)
        return self


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
    index: int
    settable: bool


class SystemVariable(BaseModel):
    """Model for variables."""

    model_config = ConfigDict(extra="forbid")

    name: str
    prefix: str
    signature: str | None = None


class SystemMethod(SystemVariable):
    """Model for method entries."""

    model_config = ConfigDict(extra="forbid")

    docstring: str | None = None
    callable: Callable[[], Any] | None = None

    @property
    def doc_summary(self):
        """Returns the first line of the docstring as a summary."""
        return "" if not self.docstring else self.docstring.split("\n")[0].strip()


class SystemInfo(BaseModel):
    """Main model for the configuration."""

    model_config = ConfigDict(extra="forbid")

    classes: list[str]
    devices: dict[str, SystemDevice]
    parameters: dict[str, SystemParameter]
    methods: dict[str, SystemMethod]
    variables: dict[str, SystemVariable]
    config: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)
    config_validation_errors: list[str] = Field(default_factory=list)

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
                    SystemParameter(name=name, unit=unit, index=parameter.index, settable=settable)
                )
        return result

    @cached_property
    def stub(self) -> str:
        """Generate the type-checking lines."""
        text = "from typing import TYPE_CHECKING\n"
        text += "from typing import Any as _Any\n"
        text += "if TYPE_CHECKING:\n"
        for cls in self.classes:
            text += f"    class {cls}:\n"
            text += "        def __init__(self):\n"
            text += self._add_variables(cls)
            text += "            pass\n"
            text += self._add_methods(cls)
            text += "        pass\n"
        text += "    class MergedSystem:\n"
        text += "        def __init__(self):\n"
        for cls in self.classes:
            text += f"            self.{cls} = {cls}()\n"
        text += "            pass\n"
        text += "    system = MergedSystem()\n"
        return text

    @cached_property
    def stub_length(self) -> int:
        """Return the length of the type-checking stub."""
        return len(self.stub.splitlines())

    def _add_variables(self, name: str) -> str:
        """Generate the variable declarations."""
        stub = ""
        for var in self.variables.values():
            if var.prefix == name:
                if var.signature and var.signature != "(NoneType)":
                    stub += f"            self.{var.name}: {var.signature}\n"
                else:
                    stub += f"            self.{var.name}: _Any\n"
        return stub

    def _add_methods(self, name: str) -> str:
        """Generate the methods declarations."""
        stub = ""
        for method in self.methods.values():
            if method.prefix == name:
                stub += f"        def {method.name}"
                if method.signature:
                    stub += f"{method.signature}:"
                else:
                    stub += ":"
                if method.docstring:
                    stub += '\n            """'
                    for line in method.docstring.splitlines():
                        stub += f"\n            {line}"
                    stub += '\n            """'
                stub += "\n            ...\n"
        return stub


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

    @property
    def should_comment(self):
        """Determine if the message should also be put in the datafile."""
        conf = matr1x.config.matr1x
        return self.to_comment is True or (conf.print_to_comment and self.to_comment is not False)

    @property
    def should_log(self):
        """Determine if the message should also be logged."""
        conf = matr1x.config.matr1x
        return self.to_logfile is True or (
            conf.duplicate_output_to_logfile and self.to_logfile is not False
        )


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
