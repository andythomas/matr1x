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
Module for dynamically creating SCPI device interfaces using pymeasure.

This module provides functionality to generate instrument classes for
SCPI (Standard Commands for Programmable Instruments) compatible
devices.
"""

import ast
import pickle
import re
import time
from collections.abc import Callable, Mapping
from typing import Any, Protocol, runtime_checkable

from pymeasure.instruments import Instrument
from pymeasure.instruments.validators import strict_discrete_set

from matr1x.util import Command, Get, normalize_cmds

__all__ = ["makeSCPIdevice"]

_typeplaceholder = {int: "%d", float: "%g", bool: "%d", str: "%s", None: ""}


def _make_identifier(s):
    """
    Create valid Python identifier by omitting invalid characters.

    Parameters
    ----------
    s : str
        Input string to convert to a valid identifier

    Returns
    -------
    str
        A valid Python identifier
    """
    # Remove invalid characters
    s = re.sub("[^0-9a-zA-Z_]", "", s)
    # Remove leading characters until we find a letter or underscore
    s = re.sub("^[^a-zA-Z_]+", "", s)
    return s


def _strict_length(value, values):
    """
    Pymeasure validator to enforce array length.

    Parameters
    ----------
    value : list, tuple
        The collection to validate
    values : int
        Expected length of the collection

    Returns
    -------
    list, tuple
        The original value if validation passed

    Raises
    ------
    ValueError
        If length of value does not match expected length
    """
    if len(value) != values:
        raise ValueError(f"Value {value} does not have an appropriate length of {values}")
    return value


def _list2str(value, dtype):
    """
    Convert a list of values to a comma-separated string.

    Parameters
    ----------
    value : list
        List of values to convert
    dtype : list
        List of data types corresponding to each value

    Returns
    -------
    str
        Comma-separated string of formatted values
    """
    ret = []
    for v, dt in zip(value, dtype):
        if dt is bool:
            ret.append(_typeplaceholder[int] % v)
        else:
            ret.append(_typeplaceholder[dt] % v)
    return ",".join(ret)


def _castlist(values, dtype):
    """
    Convert a list of string values to their appropriate data types.

    Parameters
    ----------
    values : list
        List of string values to convert
    dtype : list
        List of data types to convert each value to

    Returns
    -------
    list
        List of values converted to their specified data types
    """
    ret = []
    for v, t in zip(values, dtype):
        if t is bool:
            if v == "False":
                castval = False
            elif v == "True":
                castval = True
            else:
                castval = None
        else:
            castval = t(v)
        ret.append(castval)
    return ret


def _constructor(self, adapter, name="clientdevice", **kwargs):
    """
    Initialize the SCPI device instance.

    Parameters
    ----------
    adapter : Adapter
        Communication adapter for the instrument
    name : str, optional
        Name of the device. Default is 'clientdevice'
    **kwargs : dict
        Additional keyword arguments passed to the Instrument constructor
    """
    kwargs.update(read_termination="\n", write_termination="\n", includeSCPI=False)
    Instrument.__init__(self, adapter, name, **kwargs)


def _query(self, cmd):
    """
    Query the instrument with a command and return the response.

    Parameters
    ----------
    cmd : str
        Command to send to the instrument

    Returns
    -------
    str
        Response from the instrument
    """
    return self.ask(cmd)


def _check_set_errors(self):
    """
    Check for error responses after setting a value.

    Returns
    -------
    list
        Empty list if no errors

    Raises
    ------
    ValueError
        If the device responds with an error
    """
    reply = self.read()
    if reply != "\x06":
        raise ValueError(
            f"Wrong reply received when there should be an acknowledge. Instead received {reply}"
        )
    return []


def _create_setnwait(attr, pollattr):
    """
    Return a set and wait method which can be used in system files.

    Parameters
    ----------
    attr : str
        Attribute name to set
    pollattr : str
        Attribute name to poll for completion

    Returns
    -------
    function
        A function that sets a value and waits for completion
    """

    def setnwait(self, value):
        """
        Set a value and wait for the operation to complete.

        Parameters
        ----------
        value : any
            Value to set
        """
        setattr(self, attr, value)
        while not getattr(self, pollattr):
            time.sleep(0.1)

    return setnwait


def _create_parameterless(cmd):
    """
    Return a parameterless function that triggers a command.

    Creates a function that sends a command to the instrument
    without parameters (e.g., for trigger commands).

    Parameters
    ----------
    cmd : str
        Command to send

    Returns
    -------
    function
        Function that sends the specified command
    """

    def parameterless(self, cmd=cmd):
        """
        Execute a parameterless command.

        Parameters
        ----------
        cmd : str
            Command to execute
        """
        self.write(cmd)
        self.check_set_errors()

    return parameterless


def _id(self):
    """
    Get the identification of the Instrument.

    Returns
    -------
    str
        Instrument identification string
    """
    return self.idn


def _unused_conf_getfunc():
    """Guard against accidentally calling the synthetic :conf getter."""
    raise RuntimeError("Synthetic SCPI :conf getter placeholder must never be called.")


def _build_property_kwargs(cmd) -> dict:
    """Return the pymeasure Property kwargs for a given command."""
    kwargs = {}
    if isinstance(cmd.dtype, (tuple, list)):
        kwargs["cast"] = lambda x: x
        kwargs["validator"] = _strict_length
        kwargs["values"] = len(cmd.dtype)
        kwargs["set_process"] = lambda v, t=cmd.dtype: _list2str(v, t)
        kwargs["get_process"] = lambda v, t=cmd.dtype: _castlist(v, t)
    elif cmd.dtype == bool:
        kwargs["validator"] = strict_discrete_set
        kwargs["values"] = [True, False, None]
        kwargs["get_process"] = lambda s: _castlist([s], [bool])[0]
        kwargs["set_process"] = int
    else:
        kwargs["cast"] = cmd.dtype
    return kwargs


@runtime_checkable
class SCPIdeviceProtocol(Protocol):
    config_params: dict[str, str]

    def __init__(self, *args: Any, **kwargs: Any) -> None: ...
    def __getattr__(self, name: str) -> Any: ...
    def query(self, cmd: str) -> Any: ...
    def id(self) -> str: ...
    def check_set_errors(self) -> None: ...


def makeSCPIdevice(*cmds: Mapping[str, Command], system: bool = False) -> type[SCPIdeviceProtocol]:
    """
    Dynamically generate a pymeasure device for SCPI commands.

    Creates a new device class that can interface with instruments using
    the SCPI command set. The generated class handles command formatting,
    data type conversion, and polling operations.

    Parameters
    ----------
    cmds : dict
        Multiple dictionaries with commands. Those will be merged internally and
        therefore must only contain unique keys.
    system : bool, optional
        Flag to decide if config_params shall be defined on the device.
        Default is False.

    Returns
    -------
    type
        A dynamically created class derived from pymeasure.Instrument
    """
    cmd_list = {}
    # merge commands in arguments
    for entry in cmds:
        normalize_cmds(entry)
        cmd_list.update(entry)

    attributes = dict()
    methods: dict[str, Callable] = {
        "__init__": _constructor,
        "query": _query,
        "id": _id,
        "check_set_errors": _check_set_errors,
    }

    # make id standard config parameter
    attributes["config_params"] = {"id": "idn"}

    # add system query to config_params
    if system and ":conf" not in cmd_list:
        attributes["config_params"]["SCPIdevconf"] = "conf"
        # The synthetic client-side :conf entry only uses dtype as the response
        # parser. makeSCPIdevice never consults the stored getfunc here. The
        # matching server-side :conf getter is injected by
        # matr1x.control.controlwindow.ControlWindow.__init__.
        cmd_list[":conf"] = Get(
            lambda b: pickle.loads(ast.literal_eval(b)),
            _unused_conf_getfunc,
        )

    for name, cmd in cmd_list.items():
        # create an pymeasure attribute for every command
        att = _make_identifier(name)
        stringplaceholder = ""  # Initialize to prevent unbound variable
        try:
            stringplaceholder = _typeplaceholder[cmd.dtype]
        except (KeyError, TypeError):
            if isinstance(cmd.dtype, (tuple, list)):
                stringplaceholder = "%s"
            elif cmd.setfunc is not None:
                raise

        kwargs = _build_property_kwargs(cmd)

        if cmd.setfunc is None:
            if "validator" in kwargs:
                # for pure get property some kwargs are not allowed
                del kwargs["validator"]
                del kwargs["set_process"]
            attributes[att] = Instrument.measurement(name + "?", f"get {att}", **kwargs)
        elif cmd.getfunc is None:
            if cmd.dtype is None:
                # create parameterless functions (e.g. trigger)
                methods[f"{att}"] = _create_parameterless(name)
            else:
                kwargs["check_set_errors"] = True
                # cast not valid kwarg for Instrument.setting
                if "cast" in kwargs:
                    del kwargs["cast"]
                if "get_process" in kwargs:
                    del kwargs["get_process"]
                attributes[att] = Instrument.setting(
                    name + f" {stringplaceholder}", f"set {att}", **kwargs
                )
        else:  # here both setfunc and getfunc are real
            kwargs["check_set_errors"] = True
            attributes[att] = Instrument.control(
                name + "?", name + f" {stringplaceholder}", f"get/set {att}", **kwargs
            )
        # create set and wait/poll method in case this is asked for
        if cmd.polling_cmd is not None:
            methods[f"set_{att}"] = _create_setnwait(att, _make_identifier(cmd.polling_cmd))

    methods.update(attributes)

    return type("SCPIdevice", (Instrument,), methods)
