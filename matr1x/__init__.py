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
Configuration and utility module for the matr1x data acquisition software.

This module provides functionality to load and manage configuration settings,
handle logging, and define global constants for the matr1x software. It includes
functions for merging configuration dictionaries, writing user-specific configs,
and setting up logging based on the loaded configuration.

Key features:
- Configuration loading from default, user, and local sources
- Recursive dictionary merging for configuration overrides
- Logging setup with configurable output locations
- Re-export of metadata constants from the system module
- Management of system directories for various matr1x modules

The module also sets up important global variables and constants used throughout
the matr1x software, such as output file extensions, datetime formats, and
system directories.
"""

import logging
import os
import sys
import warnings
from dataclasses import dataclass
from datetime import date
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import tomli_w
from pydantic import BaseModel, ValidationError

# Import pymeasure threading fix to apply monkey patch automatically
# This must be imported early to ensure all pymeasure instruments are thread-safe
from . import pymeasure_threading_fix
from .models import MainConfig, UserlibConfig, format_validation_error
from .system import APP_META_KEY, VALID_META_KEYS
from .util import (
    create_temp_dir_with_symlinks,
    get_package_path,
    resolve_config_path,
    resolve_pkgroot_path,
)


def _clean_formatwarning(
    message: Warning | str,
    category: type[Warning],
    filename: str,
    lineno: int,
    line: str | None = None,
) -> str:
    """Format a warning into a single line without pulling source code context."""
    return f"{filename}:{lineno}: {category.__name__}: {message}\n"


warnings.formatwarning = _clean_formatwarning  # ty: ignore[invalid-assignment]

deprecation_marker = "[MATR1X_DEPRECATED]"

__all__ = [
    # Config management
    "load_config",
    "merge_dicts",
    "write_config",
    "reload_config",
    # Config data
    "MIGRATIONS",
    "validation_errors",
    "config",
    "datetimefmt",
    # System dirs / globals
    "usersfolder",
    "logfolder",
    "system_names",
    "system_directories",
    "resolved_directory",
    # Version / constants
    "__version__",
    "output_extension",
    # Re-exports
    "VALID_META_KEYS",
    "APP_META_KEY",
    "MainConfig",
    "UserlibConfig",
    "format_validation_error",
    "create_temp_dir_with_symlinks",
    "get_package_path",
    "resolve_config_path",
    "resolve_pkgroot_path",
    "deprecation_marker",
]

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # ty: ignore [unresolved-import]

try:
    __version__ = version("matr1x-measurements")
except PackageNotFoundError:
    __version__ = "unknown"

# enforce PySide use in pyqtgraph
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")
# default datafile extension
output_extension = ".ma8"

# Global list to store validation errors from configuration loading
validation_errors: list[str] = []


@dataclass(frozen=True)
class _Migration:
    """Conversion info for old config entries."""

    old_path: tuple[str, ...]
    new_path: tuple[str, ...]
    warning: str


MIGRATIONS = [
    _Migration(
        old_path=("matr1x", "scripts", "matrix-script", "duplicate_output_to_logfile"),
        new_path=("matr1x", "duplicate_output_to_logfile"),
        warning="Please move all 'duplicate_output_to_logfile' entries "
        "to [matr1x.duplicate_output_to_logfile]\n",
    ),
    _Migration(
        old_path=("matr1x", "scripts", "matrix-script", "print_to_comment"),
        new_path=("matr1x", "print_to_comment"),
        warning="Please move all 'print_to_comment' entries to [matr1x.print_to_comment]\n",
    ),
]


def _get_path(data, *path) -> Any:
    """Get a nested value from a dictionary using a sequence of keys."""
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _set_path(data, *path, value) -> None:
    """Set a nested value in a dictionary using a sequence of keys."""
    for key in path[:-1]:
        data = data.setdefault(key, {})
    data[path[-1]] = value


def _delete_path(data: dict[str, Any], *path: str) -> None:
    """Delete a nested key from a dictionary."""
    current = data
    for key in path[:-1]:
        current = current[key]
    del current[path[-1]]


def _migrate_config(config_data):
    """Migrate old config keys to new ones."""
    for migration in MIGRATIONS:
        old_value = _get_path(config_data, *migration.old_path)
        new_value = _get_path(config_data, *migration.new_path)
        if old_value is not None and new_value is None:
            _set_path(config_data, *migration.new_path, value=old_value)
            _delete_path(config_data, *migration.old_path)
            validation_errors.append(migration.warning)
    return config_data


def load_config(optional_config_path: Path | None = None) -> dict[str, Any]:
    """
    Load configuration from user config, local config, and an optional config.

    The configuration files are loaded in the following order, with later files
    overriding settings from earlier ones:
    1. User configuration (~/.matr1x.toml)
    2. Local configuration (./matr1x.toml)
    3. Optional configuration (if provided e.g. in GUI)

    Parameters
    ----------
    optional_config_path : pathlib.Path, optional
        Path to an optional TOML configuration file.  If provided, settings
        in this file will override those in the user and local configuration
        files.
    """
    config_data = {}

    # Load user configuration if available
    user_config_path = Path("~/.matr1x.toml").expanduser()
    if user_config_path.exists():
        with user_config_path.open("rb") as f:
            user_config = tomllib.load(f)
            config_data = merge_dicts(config_data, user_config)

    # Override with local configuration if available
    local_config_path = Path("./matr1x.toml")
    if local_config_path.exists():
        with local_config_path.open("rb") as f:
            local_config = tomllib.load(f)
            config_data = merge_dicts(config_data, local_config)

    # Override with optional configuration if available
    if optional_config_path:
        if optional_config_path.exists():
            with optional_config_path.open("rb") as f:
                optional_config = tomllib.load(f)
                config_data = merge_dicts(config_data, optional_config)
        else:
            print(f"Warning: Optional config file not found: {optional_config_path}")  # noqa: T201
    config_data = _migrate_config(config_data)
    return config_data


def merge_dicts(dict1: dict[str, Any], dict2: dict[str, Any]) -> dict[str, Any]:
    """Recursively merges dict2 into dict1."""
    for k, v in dict2.items():
        if isinstance(v, dict) and k in dict1:
            dict1[k] = merge_dicts(dict1[k], v)
        else:
            dict1[k] = v
    return dict1


def _validate_loaded_config(loaded_config: dict[str, Any]) -> tuple[MainConfig, str]:
    """Validate loaded config and return validated model."""
    msg = ""
    try:
        # Validate and update config with defaults from the model.
        validated = MainConfig.model_validate(loaded_config)
    except (ValidationError, TypeError, ValueError) as e:
        msg = format_validation_error(e)
        validated = MainConfig()
        if msg:
            validation_errors.append(msg)

    return validated, msg


def _warn_config_errors(msg: str) -> None:
    """Print configuration validation warnings."""
    if msg == "":
        return
    msg = (
        f"Please check your configuration files (e.g. {Path.home() / '.matr1x.toml'})! "
        "Some settings might not work as intended. "
        "The following error(s) occured:\n\n"
    ) + msg
    print(msg)  # noqa: T201


def _find_differences(
    default_dict: dict[str, Any], current_dict: dict[str, Any]
) -> dict[str, Any]:
    """
    Recursively compares two dictionaries and finds differences.

    This function compares a dictionary representing default settings with
    a dictionary representing current settings. It returns a new
    dictionary containing only the keys and values that differ from the
    default settings.

    Parameters
    ----------
    default_dict : dict
        The dictionary representing the default settings.
    current_dict : dict
        The settings to compare against the defaults.

    Returns
    -------
    differences : dict
        A dictionary containing only the settings that differ from the
        default settings. If no differences are found, an empty dictionary
        is returned.
    """
    differences = {}
    for key, default_value in default_dict.items():
        if key not in current_dict:
            continue  # Key is missing in the current settings
        current_value = current_dict[key]

        # If both are dictionaries, compare recursively
        if isinstance(default_value, dict) and isinstance(current_value, dict):
            sub_diff = _find_differences(default_value, current_value)
            if sub_diff:  # Only add non-empty differences
                differences[key] = sub_diff
        elif default_value != current_value:  # Value differs
            differences[key] = current_value

    # Add keys that are in current_dict but not in default_dict
    for key in current_dict:
        if key not in default_dict:
            differences[key] = current_dict[key]

    return differences


def write_config(
    config_dict: dict[str, Any] | BaseModel, optional_config_path: Path | None = None
):
    """
    Write non-default config options to the user config or optional config.

    Writes the differences between the current configuration and the default
    configuration to the user configuration file (~/.matr1x.toml) or the
    specified optional configuration file. If an optional configuration file
    is specified, the differences are written to that file instead of the
    user configuration file, and no comparison with the default settings
    is performed.

    Parameters
    ----------
    config_dict : dict or BaseModel
        Configuration settings to write.
    optional_config_path : pathlib.Path, optional
        Path to an optional TOML configuration file.  If provided, settings
        in this file will be written without comparing to the default
        configuration.
    """
    # Ensure we are working with a dictionary for tomli_w
    # Using mode='json' converts Paths to strings and Enums to their values
    if isinstance(config_dict, BaseModel):
        dump_dict = config_dict.model_dump(mode="json", by_alias=True, exclude_none=True)
    else:
        dump_dict = config_dict

    if optional_config_path:
        with optional_config_path.open("wb") as toml_file:
            tomli_w.dump(dump_dict, toml_file)
    else:
        # load default settings from Pydantic model
        default_settings = MainConfig().model_dump(mode="json", by_alias=True, exclude_none=True)
        # Dictionary to store new TOML data
        user_config = _find_differences(default_settings, dump_dict)

        user_config_path = Path("~/.matr1x.toml").expanduser()
        if user_config:
            with user_config_path.open("wb") as toml_file:
                tomli_w.dump(user_config, toml_file)


def reload_config(optional_config_path: str | Path | None = None):
    """
    Reload the configuration dictionary.

    Reloads the configuration dictionary by calling the `load_config` function
    with the specified optional configuration path.

    Parameters
    ----------
    optional_config_path : str or pathlib.Path, optional
        Path to an optional TOML configuration file.  If provided, settings
        in this file will override those in the user and local configuration
        files.
    """
    global config, datetimefmt, validation_errors
    if isinstance(optional_config_path, str):
        optional_config_path = Path(optional_config_path)
    validation_errors = []
    loaded_config = load_config(optional_config_path)
    config, msg = _validate_loaded_config(loaded_config)
    _warn_config_errors(msg)
    datetimefmt = config.matr1x.datetime_format


# load config and combine values from multiple sources
# validate the entries
config: MainConfig
config, msg = _validate_loaded_config(load_config())
_warn_config_errors(msg)

datetimefmt = config.matr1x.datetime_format

usersfolder: Path = config.matr1x.users_directory.expanduser()
if not usersfolder.exists():
    usersfolder = Path.home()

# set up logging to configure, e.g., the log-windows
logfolder = config.matr1x.logging_directory.expanduser()
if logfolder.exists():
    today = date.today().isocalendar()
    handlers = [
        logging.FileHandler(logfolder / f"matr1x_{today.year}{today.week:02d}.log", mode="a")
    ]
    logging.basicConfig(
        level=logging.INFO,
        format=config.matr1x.logging_format,
        datefmt=datetimefmt,
        handlers=handlers,
    )
else:
    logging.basicConfig(format=config.matr1x.logging_format, datefmt=datetimefmt)
    # fallback to usersfolder if logfolder does not exist
    logfolder = usersfolder

_systems_directory = resolve_pkgroot_path(
    config.matr1x.systems_directory, Path(__file__).resolve().parent
)
if not _systems_directory.is_dir():
    print("matrix.conf: option matr1x/systems_directory is invalid, using fallback")  # noqa: T201
    # use fallback option
    _systems_directory = Path(__file__).resolve().parent / "systems"

system_names: list[str] = [
    "matr1x-systems",
]
system_directories: list[Path] = [
    _systems_directory,
]

# Iterate over both defined fields and extra sections
all_sections = set(type(config).model_fields.keys())
if config.model_extra:
    all_sections.update(config.model_extra.keys())

for section in all_sections:
    if section != "matr1x":
        section_config = getattr(config, section)
        if hasattr(section_config, "systems_directory") and section_config.systems_directory:
            sysdir = resolve_pkgroot_path(
                section_config.systems_directory, get_package_path(section)
            )
            if sysdir.is_dir():
                system_names.append(section)
                system_directories.append(sysdir)

# Create a temporary directory with symlinks to all system directories
# This allows us to have a single "base" directory for all systems
_temp_dir = create_temp_dir_with_symlinks(system_names, system_directories)
resolved_directory = Path(_temp_dir.name)
