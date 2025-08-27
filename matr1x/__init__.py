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
import sys
import tempfile
from datetime import date
from os.path import abspath, dirname, exists, expanduser, isdir, join, normpath
from pathlib import Path
from typing import Optional, Union

import tomli_w
from pydantic import ValidationError

from matr1x.models import MainConfig, UserlibConfig, format_validation_error

# Import pymeasure threading fix to apply monkey patch automatically
# This must be imported early to ensure all pymeasure instruments are thread-safe
from . import pymeasure_threading_fix
from .metadata import VALID_META_KEYS
from .util import get_package_path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


# default datafile extension
output_extension = ".ma8"


def load_config(optional_config_path: Optional[Union[str, Path]] = None):
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
    optional_config_path : str or pathlib.Path, optional
        Path to an optional TOML configuration file.  If provided, settings
        in this file will override those in the default, user, and local
        configuration files.
    """
    # Load default configuration
    default_config_path = Path(__file__).parent / "default_matr1x.toml"
    with open(default_config_path, "rb") as f:
        config = tomllib.load(f)

    # Override with user configuration if available
    user_config_path = Path(expanduser("~/.matr1x.toml"))
    if user_config_path.exists():
        with open(user_config_path, "rb") as f:
            user_config = tomllib.load(f)
            config = merge_dicts(config, user_config)

    # Override with local configuration if available
    local_config_path = Path("./matr1x.toml")
    if local_config_path.exists():
        with open(local_config_path, "rb") as f:
            local_config = tomllib.load(f)
            config = merge_dicts(config, local_config)

    # Override with optional configuration if available
    if optional_config_path:
        optional_config_path = Path(optional_config_path)
        if optional_config_path.exists():
            with open(optional_config_path, "rb") as f:
                optional_config = tomllib.load(f)
                config = merge_dicts(config, optional_config)
        else:
            print(f"Warning: Optional config file not found: {optional_config_path}")

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
                default_value = normpath(expanduser(default_value))
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
            differences[key] = current_value

    return differences


def write_config(config_dict, optional_config_path: Optional[Union[str, Path]] = None):
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
    optional_config_path : str or pathlib.Path, optional
        Path to an optional TOML configuration file.  If provided, settings
        in this file will be written without comparing to the default
        configuration.
    """
    if optional_config_path:
        optional_config_path = Path(optional_config_path)
        with open(optional_config_path, "wb") as toml_file:
            tomli_w.dump(config_dict, toml_file)
    else:
        # load default settings
        default_config_path = Path(__file__).parent / "default_matr1x.toml"
        with open(default_config_path, "rb") as f:
            default_settings = tomllib.load(f)
        # Dictionary to store new TOML data
        user_config = _find_differences(default_settings, config_dict)

        user_config_path = Path(expanduser("~/.matr1x.toml"))
        if user_config:
            with open(user_config_path, "wb") as toml_file:
                tomli_w.dump(user_config, toml_file)


def reload_config(optional_config_path: Optional[Union[str, Path]] = None):
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
    MainConfig(**config)  # validate matr1x
except (ValidationError, TypeError, ValueError) as e:
    msg += format_validation_error(e)
if msg != "":
    msg = (
        f"Please check your configuration file ({Path.home() / '.matr1x.toml'})! "
        "Some settings will not work as intended. "
        "The following error(s) occured:\n\n"
    ) + msg
print(msg)

datetimefmt = config["matr1x"]["datetime_format"]

# set up logging, mostly for debugging purposes.
# Verbose logs can be produced by changing logging.INFO to logging.DEBUG. This
# is however not recommended in production environments.
logfolder = expanduser(config["matr1x"]["logging_directory"])
kwargs = dict(level=logging.INFO, format=config["matr1x"]["logging_format"], datefmt=datetimefmt)
handlers = []
if not exists(logfolder):
    logfolder = tempfile.gettempdir()  # set logfolder to temp directory
    if sys.stdout is not None:
        # if logging to temp directory also log to stdout
        handlers.append(logging.StreamHandler(stream=sys.stdout))

today = date.today().isocalendar()
if sys.version_info.major == 3 and sys.version_info.minor < 9:
    from collections import namedtuple

    datetuple = namedtuple("Isocalendar", ["year", "week", "weekday"])
    today = datetuple(*today)
handlers.append(
    logging.FileHandler(join(logfolder, f"matr1x_{today.year}{today.week:02d}.log"), mode="a")
)

kwargs["handlers"] = handlers
logging.basicConfig(**kwargs)

usersfolder = expanduser(config["matr1x"]["users_directory"])
if not exists(usersfolder):
    usersfolder = expanduser("~")

_systems_directory = expanduser(config["matr1x"]["systems_directory"])

# replace pkgroot placeholder if present
if "<pkgroot>/" in _systems_directory:
    _systems_directory = join(
        dirname(abspath(__file__)), _systems_directory.replace("<pkgroot>/", "")
    )
# expand eventual home
_systems_directory = expanduser(_systems_directory)
if not isdir(_systems_directory):
    print("matrix.conf: option matr1x/systems_directory is invalid, using fallback")
    # use fallback option
    _systems_directory = join(dirname(abspath(__file__)), "systems")

system_names = [
    "matr1x-systems",
]
system_directories = [
    _systems_directory,
]
for section in config:
    if section != "matr1x":
        if "systems_directory" in config[section]:
            sysdir = config[section]["systems_directory"]
            # replace pkgroot placeholder
            if "<pkgroot>/" in sysdir:
                package_path = get_package_path(section)
                if package_path is not None:
                    sysdir = join(package_path, sysdir.replace("<pkgroot>/", ""))
                else:
                    raise ModuleNotFoundError(f"Optional matr1x module '{section}' not found")
            # expand eventual home
            sysdir = expanduser(sysdir)
            if isdir(sysdir):
                system_names.append(f"{section}-systems")
                system_directories.append(sysdir)
            else:
                print(
                    f"matrix.conf: option {section}/systems_directory has invalid value '{sysdir}'"
                )
