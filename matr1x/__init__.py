# This file is part of a software collection for data aquisition (matr1x).
# Copyright (C) 2024 matr1x developers
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

import logging
import sys
import tempfile
from datetime import date
from os.path import abspath, dirname, exists, expanduser, isdir, join, normpath

import tomli_w

from .util import get_package_path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


# default datafile extension
output_extension = ".ma8"


def load_config():
    """
    Load configuration file from default config, user config and local config.
    """
    # Load default configuration
    with open(join(dirname(__file__), "default_matr1x.toml"), "rb") as f:
        config = tomllib.load(f)

    # Override with user configuration if available
    user_config_path = expanduser(join("~", ".matr1x.toml"))
    if exists(user_config_path):
        with open(user_config_path, "rb") as f:
            user_config = tomllib.load(f)
            config = merge_dicts(config, user_config)

    # Override with local configuration if available
    local_config_path = "./matrix.toml"
    if exists(local_config_path):
        with open(local_config_path, "r") as f:
            local_config = tomllib.load(f)
            config = merge_dicts(config, local_config)

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
    return the dictionary with config settings of a specific subsection.

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


def write_config(config_dict):
    """
    Write non-default config options to the user config
    """

    def find_differences(default_dict, current_dict):
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
                sub_diff = find_differences(default_value, current_value)
                if sub_diff:  # Only add non-empty differences
                    differences[key] = sub_diff
            elif default_value != current_value:  # Value differs
                differences[key] = current_value

        # Add keys that are in current_dict but not in default_dict
        for key in current_dict:
            if key not in default_dict:
                differences[key] = current_dict[key]

        return differences

    # load default settings
    with open(join(dirname(__file__), "default_matr1x.toml"), "rb") as f:
        default_settings = tomllib.load(f)
    # Dictionary to store new TOML data
    user_config = find_differences(default_settings, config_dict)

    if user_config:
        with open(expanduser("~/.matr1x.toml"), "wb") as toml_file:
            tomli_w.dump(user_config, toml_file)


# load config and combine values from multiple sources
config = load_config()

datetimefmt = config["matr1x"]["datetime_format"]

# define allowed dublin core meta keys
VALID_META_KEYS = {  # valid key and item defines whether it is editable
    "creator": True,
    "date": False,
    "identifier": True,
    "relation": True,
    "description": True,
    "source": True,
    "type": True,
    "publisher": True,
    "format": False,
    "language": False,
}

# set up logging, mostly for debugging purposes.
# Verbose logs can be produced by changing logging.INFO to logging.DEBUG. This
# is however not recommended in production environments.
logfolder = expanduser(config["matr1x"]["logging_directory"])
kwargs = dict(
    level=logging.INFO, format=config["matr1x"]["logging_format"], datefmt=datetimefmt
)
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
    logging.FileHandler(
        join(logfolder, f"matr1x_{today.year}{today.week:02d}.log"), mode="a"
    )
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

system_names = ['matr1x-systems', ]
system_directories = [_systems_directory, ]
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
                    raise ModuleNotFoundError(
                        f"Optional matr1x module '{section}' not found"
                    )
            # expand eventual home
            sysdir = expanduser(sysdir)
            if isdir(sysdir):
                system_names.append(f"{section}-systems")
                system_directories.append(sysdir)
            else:
                print(
                    f"matrix.conf: option {section}/systems_directory has "
                    f"invalid value '{sysdir}'"
                )
