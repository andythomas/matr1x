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
"""Pydantic models for the matr1x configuration."""

from pathlib import Path
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from matr1x.core.visa_helpers import (
    GPIB_VISA_RESOURCE_REQUIREMENTS,
    LOCAL_TCPIP_SOCKET_VISA_RESOURCE_REQUIREMENTS,
    SERIAL_VISA_RESOURCE_REQUIREMENTS,
    TCPIP_SOCKET_VISA_RESOURCE_REQUIREMENTS,
    validate_gpib_visa_resource,
    validate_local_tcpip_socket_visa_resource,
    validate_serial_visa_resource,
    validate_tcpip_socket_visa_resource,
    validate_visa_resource,
)


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


VisaResource = Annotated[
    str,
    AfterValidator(validate_visa_resource),
    GuiField(ui_type="visa_resource", validate_default=True),
]
SerialVisaResource = Annotated[
    str,
    AfterValidator(validate_serial_visa_resource),
    GuiField(
        ui_type="visa_resource",
        validate_default=True,
        json_schema_extra={"visa_resource_requirements": SERIAL_VISA_RESOURCE_REQUIREMENTS},
    ),
]
GPIBVisaResource = Annotated[
    str,
    AfterValidator(validate_gpib_visa_resource),
    GuiField(
        ui_type="visa_resource",
        validate_default=True,
        json_schema_extra={"visa_resource_requirements": GPIB_VISA_RESOURCE_REQUIREMENTS},
    ),
]
TCPIPSocketVisaResource = Annotated[
    str,
    AfterValidator(validate_tcpip_socket_visa_resource),
    GuiField(
        ui_type="visa_resource",
        validate_default=True,
        json_schema_extra={"visa_resource_requirements": TCPIP_SOCKET_VISA_RESOURCE_REQUIREMENTS},
    ),
]
LocalTCPIPSocketVisaResource = Annotated[
    str,
    AfterValidator(validate_local_tcpip_socket_visa_resource),
    GuiField(
        ui_type="visa_resource",
        validate_default=True,
        json_schema_extra={
            "visa_resource_requirements": LOCAL_TCPIP_SOCKET_VISA_RESOURCE_REQUIREMENTS
        },
    ),
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
        msg += f"{base}: {e!s}\n"
    return msg


class SystemConfigModel(BaseModel):
    """Base model for system configuration with validated default values."""

    model_config = ConfigDict(validate_default=True)


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
