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
- Re-export of metadata constants from the metadata module
- Management of system directories for various matr1x modules

The module also sets up important global variables and constants used throughout
the matr1x software, such as output file extensions, datetime formats, and
system directories.
"""

import logging
import os
import sys
from datetime import date
from pathlib import Path

import tomli_w
from pydantic import ValidationError

# Import pymeasure threading fix to apply monkey patch automatically
# This must be imported early to ensure all pymeasure instruments are thread-safe
from . import pymeasure_threading_fix
from .metadata import VALID_META_KEYS
from .models import MainConfig, UserlibConfig, format_validation_error
from .util import create_temp_dir_with_symlinks, get_package_path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # ty: ignore [unresolved-import]

# enforce PySide use in pyqtgraph
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PySide6")
# default datafile extension
output_extension = ".ma8"


def load_config(optional_config_path: Path | None = None):
    """
    Load configuration file from default config, user config, local config, and an optional config.

    The configuration files are loaded in the following order, with later files
    overriding settings from earlier ones:
    1. Default configuration
    2. User configuration (~/.matr1x.toml)
    3. Local configuration (./matr1x.toml)
    4. Optional configuration (if provided e.g. in GUI)

    Parameters
    ----------
    optional_config_path : pathlib.Path, optional
        Path to an optional TOML configuration file.  If provided, settings
        in this file will override those in the default, user, and local
        configuration files.
    """
    # Load default configuration
    default_config_path = Path(__file__).parent / "default_matr1x.toml"
    with default_config_path.open("rb") as f:
        config = tomllib.load(f)

    # Override with user configuration if available
    user_config_path = Path("~/.matr1x.toml").expanduser()
    if user_config_path.exists():
        with user_config_path.open("rb") as f:
            user_config = tomllib.load(f)
            config = merge_dicts(config, user_config)

    # Override with local configuration if available
    local_config_path = Path("./matr1x.toml")
    if local_config_path.exists():
        with local_config_path.open("rb") as f:
            local_config = tomllib.load(f)
            config = merge_dicts(config, local_config)

    # Override with optional configuration if available
    if optional_config_path:
        if optional_config_path.exists():
            with optional_config_path.open("rb") as f:
                optional_config = tomllib.load(f)
                config = merge_dicts(config, optional_config)
        else:
            print(f"Warning: Optional config file not found: {optional_config_path}")  # noqa: T201

    return config


def merge_dicts(dict1, dict2):
    """Recursively merges dict2 into dict1."""
    for k, v in dict2.items():
        if isinstance(v, dict) and k in dict1:
            dict1[k] = merge_dicts(dict1[k], v)
        else:
            dict1[k] = v
    return dict1


def get_config_dict(section: str):
    """
    Return the dictionary with config settings of a specific subsection.

    If no such entry exists in the config an empty dict will be returned.

    Parameters
    ----------
    section : str
        section name in TOML synthax
    """
    ret = config
    for sec in section.split("."):
        if sec in ret:
            ret = ret[sec]
        else:
            ret = {}
    return ret


def _find_differences(default_dict, current_dict):
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
        The dictionary representing the current settings.

    Returns
    -------
    differences : dict
        A dictionary containing only the settings that differ from the
        default settings. If no differences are found, an empty dictionary
        is returned.
    """
    differences = {}
    for key, default_value in default_dict.items():
        if isinstance(default_value, str):
            if "~" in default_value:
                default_value = str(Path(default_value).expanduser().resolve())
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


def write_config(config_dict, optional_config_path: Path | None = None):
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
    config_dict : dict
        Dictionary containing the current configuration settings.
    optional_config_path : pathlib.Path, optional
        Path to an optional TOML configuration file.  If provided, settings
        in this file will be written without comparing to the default
        configuration.
    """
    if optional_config_path:
        with optional_config_path.open("wb") as toml_file:
            tomli_w.dump(config_dict, toml_file)
    else:
        # load default settings
        default_config_path = Path(__file__).parent / "default_matr1x.toml"
        with default_config_path.open("rb") as f:
            default_settings = tomllib.load(f)
        # Dictionary to store new TOML data
        user_config = _find_differences(default_settings, config_dict)

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
        in this file will override those in the default, user, and local
        configuration files.
    """
    global config
    if isinstance(optional_config_path, str):
        optional_config_path = Path(optional_config_path)
    config = load_config(optional_config_path)


# load config and combine values from multiple sources
# validate the entries
config = load_config()
data = dict(config)
msg = ""
for key in list(data.keys()):  # validate everything but matr1x
    if key != "matr1x":
        try:
            UserlibConfig(**data.pop(key))
        except (ValidationError, TypeError, ValueError) as e:
            msg = format_validation_error(e, key + ".")
try:
    MainConfig.model_validate(config)
except (ValidationError, TypeError, ValueError) as e:
    msg += format_validation_error(e)
if msg != "":
    msg = (
        f"Please check your configuration file ({Path.home() / '.matr1x.toml'})! "
        "Some settings will not work as intended. "
        "The following error(s) occured:\n\n"
    ) + msg
    print(msg)  # noqa: T201

datetimefmt = config["matr1x"]["datetime_format"]

usersfolder: Path = Path(config["matr1x"]["users_directory"]).expanduser()
if not usersfolder.exists():
    usersfolder = Path.home()

# set up logging to configure, e.g., the log-windows
logfolder = Path(config["matr1x"]["logging_directory"]).expanduser()
if logfolder.exists():
    today = date.today().isocalendar()
    handlers = [
        logging.FileHandler(logfolder / f"matr1x_{today.year}{today.week:02d}.log", mode="a")
    ]
    logging.basicConfig(
        level=logging.INFO,
        format=config["matr1x"]["logging_format"],
        datefmt=datetimefmt,
        handlers=handlers,
    )
else:
    logging.basicConfig(format=config["matr1x"]["logging_format"], datefmt=datetimefmt)
    # fallback to usersfolder if logfolder does not exist
    logfolder = usersfolder

_systems_directory_str = config["matr1x"]["systems_directory"]

# replace pkgroot placeholder if present
if "<pkgroot>/" in _systems_directory_str:
    _systems_directory = Path(__file__).resolve().parent / _systems_directory_str.replace(
        "<pkgroot>/", ""
    )
else:
    _systems_directory = Path(_systems_directory_str)
# expand eventual home
_systems_directory = _systems_directory.expanduser()
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
for section in config:
    if section != "matr1x":
        if "systems_directory" in config[section]:
            sysdir_str = config[section]["systems_directory"]
            # replace pkgroot placeholder
            if "<pkgroot>/" in sysdir_str:
                package_path = get_package_path(section)
                if package_path is not None:
                    sysdir = Path(package_path) / sysdir_str.replace("<pkgroot>/", "")
                else:
                    raise ModuleNotFoundError(f"Optional matr1x module '{section}' not found")
            else:
                sysdir = Path(sysdir_str)
            # expand eventual home
            sysdir = sysdir.expanduser()
            if sysdir.is_dir():
                system_names.append(f"{section}-systems")
                system_directories.append(sysdir)
            else:
                print(  # noqa: T201
                    f"matrix.conf: option {section}/systems_directory has invalid value '{sysdir}'"
                )
if len(system_names) > 1:
    temp = create_temp_dir_with_symlinks(system_names, system_directories)
    resolved_directory = Path(temp.name) / system_names[-1]
else:
    resolved_directory = system_directories[-1]
