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
"""Command model for control GUIs.

A command describes how a control GUI reads from and writes to a
variable of a measurement system.
"""

from collections.abc import Callable
from typing import Any

__all__ = ["Command", "Get", "Set", "normalize_cmds"]


class Command:
    """
    Class representing a command provided by a ControlGUI.

    A command contains the data type of the connected variable and
    functions for setting and getting and their respective arguments.
    """

    def __init__(
        self,
        dtype: Callable[..., Any]
        | list[Callable[..., Any]]
        | tuple[Callable[..., Any], ...]
        | None,
        setfunc: Callable[..., None] | str | list[str] | tuple[str, ...] | None,
        getfunc: Callable[..., Any] | str | list[str] | tuple[str, ...] | None,
        setargs: tuple | list | None = None,
        getargs: tuple | list | None = None,
        polling_cmd: str | None = None,
    ):
        """
        Initialize the Command object.

        Parameters
        ----------
        dtype : type
            Data type of the connected variable.
        setfunc : callable or tuple
            Setter function to change the connected variable.
            Can also be a tuple with a device name and device property.
        getfunc : callable or tuple
            Getter function to obtain the value of the variable.
            Can also be a tuple with a device name and device property.
        setargs : tuple, optional
            Additional arguments for the setter function.
        getargs : tuple, optional
            Additional arguments for the getter function.
        polling_cmd : str, optional
            Command to poll to check if the setpoint was reached.
        """
        self.dtype: (
            Callable[..., Any] | list[Callable[..., Any]] | tuple[Callable[..., Any], ...] | None
        ) = dtype
        self.setfunc: Callable[..., None] | str | list[str] | tuple[str, ...] | None = setfunc
        self.getfunc: Callable[..., Any] | str | list[str] | tuple[str, ...] | None = getfunc
        self.setargs: tuple
        self.getargs: tuple
        if setargs is None:
            self.setargs = ()
        else:
            self.setargs = tuple(setargs)
        if getargs is None:
            self.getargs = ()
        else:
            self.getargs = tuple(getargs)
        self.polling_cmd: str | None = polling_cmd

    def __repr__(self) -> str:
        """
        Return a string representation of the Command object.

        Returns
        -------
        str
            A string representation of the Command object.
        """
        return self.__str__()

    def __str__(self) -> str:
        """
        Return a string representation of the Command object.

        Returns
        -------
        str
            A string representation of the Command object, including its class name,
            data type, setter function, getter function, and their respective arguments.
        """
        r = f"{self.__class__.__name__}: {self.dtype}, {self.setfunc}"
        if self.setargs:
            r += f"({self.setargs})"
        r += f", {self.getfunc}"
        if self.getargs:
            r += f"({self.getargs})"
        return r

    def reset_to_None(self) -> None:
        """
        Reset the Command object's setter and getter functions and arguments to None.

        This method sets the setter function, getter function, and their
        respective arguments to None or empty lists.
        """
        self.setfunc = None
        self.getfunc = None
        self.setargs = ()
        self.getargs = ()


class Get(Command):
    """Class representing a Getter-command of a ControlGUI."""

    def __init__(
        self,
        dtype: Callable[..., Any]
        | list[Callable[..., Any]]
        | tuple[Callable[..., Any], ...]
        | None,
        getfunc: Callable[..., Any] | str | list[str] | tuple[str, ...],
        getargs: tuple | None = None,
    ):
        """
        Initialize the Get command.

        Parameters
        ----------
        dtype : type
            Data type of the connected variable.
        getfunc : callable
            Getter function to obtain the value of the variable.
        getargs : tuple or None, optional
            Optional arguments for the getter function.
        """
        super().__init__(dtype, setfunc=None, getfunc=getfunc, getargs=getargs)


class Set(Command):
    """Class representing a Setter-command of a ControlGUI."""

    def __init__(
        self,
        dtype: Callable[..., Any]
        | list[Callable[..., Any]]
        | tuple[Callable[..., Any], ...]
        | None,
        setfunc: Callable[..., None] | str | list[str] | tuple[str, ...],
        setargs: tuple | None = None,
        polling_cmd: str | None = None,
    ):
        """
        Initialize the Set command.

        Parameters
        ----------
        dtype : type
            Data type of the connected variable.
        setfunc : callable
            Setter function to change the connected variable.
        setargs : tuple or None, optional
            Optional additional arguments for the setter function.
        polling_cmd : str or None, optional
            Optional command to poll to check if the setpoint was reached.
        """
        super().__init__(dtype, setfunc, getfunc=None, setargs=setargs, polling_cmd=polling_cmd)


def normalize_cmds(cmds):
    """
    Validate that all commands are Command instances.

    Parameters
    ----------
    cmds : dict
        Dictionary of commands to normalize.

    Returns
    -------
    None
    """
    for cmd, val in cmds.items():
        if not isinstance(val, Command):
            raise TypeError(
                f"Command entry {cmd!r} must be a Command instance, got {type(val).__name__}."
            )
