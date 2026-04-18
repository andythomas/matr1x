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
Devices for matr1x measurements based on VisaDevice.

Please consider looking into pymeasure before using this device driver
as a template for new devices. We discourage the implementation of new
devices using the matr1x framework. Pull requests with new devices based
on VisaDevice will not be merged in the future.

Devices implemented here are kept for backward compatibility.
Instruments from pymeasure are fully compatible to be used within matr1x
systems.
"""

from collections.abc import Callable
from typing import Any, TypeVar, overload

T = TypeVar("T")

scpiPORTdrivers = 8888


def listToStr(floatList: list[float]) -> str:
    """
    Convert a list of numeric values to a comma separated string.

    Parameters
    ----------
    floatList: list[float]
        The list of floats to convert.

    Returns
    -------
    str
        The comma separated string.
    """
    return ",".join(str(r) for r in floatList)


T = TypeVar("T")


@overload
def strToList(string: str) -> list[float]: ...
@overload
def strToList(string: str, dtype: Callable[[str], T]) -> list[T]: ...


def strToList(
    string: str,
    dtype: Callable[[str], Any] = float,
) -> list[Any]:
    """
    Convert a comma separated string of values into a list.

    The datatype of the values is cast to dtype.

    Parameters
    ----------
    string: str
        The comma separated string.
    dtype: T
        The desired datatype of the values.

    Returns
    -------
    list[T]
        The list of dtypes.
    """
    string = string.strip("[")
    string = string.strip("]")
    return [dtype(r) for r in string.split(",")]
