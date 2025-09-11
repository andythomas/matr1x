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
"""Validate (some) of the config options for better error messages."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError


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
    options: list[str] | None = None
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
    options: list[str] | None = None
    pip_options: str
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


class Matr1xScriptsMatrix_ScriptConfig(BaseModel):
    """Allow validation of [matr1x.scripts.matrix-script]."""

    model_config = ConfigDict(extra="forbid")

    script_path: Path
    store_script_in_datafile: bool
    duplicate_output_to_logfile: bool
    print_to_comment: bool


class Matr1xScriptsConfig(BaseModel):
    """Allow validation of [matr1x.scripts]."""

    model_config = ConfigDict(extra="forbid")

    matrix_script: Matr1xScriptsMatrix_ScriptConfig = Field(alias="matrix-script")


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
    systems: Any


class MainConfig(BaseModel):
    """Allow validation of the configuration toml."""

    matr1x: Matr1xConfig
