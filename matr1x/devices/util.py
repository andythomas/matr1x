# This file is part of a software collection for data aquisition (matr1x).
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

def listToStr(floatList):
    """
    converts a list of numeric values to a comma separated string
    """
    return ",".join(str(r) for r in floatList)


def strToList(string, dtype=float):
    """
    converts a comma separated string of values into a list with of
    values corresponding cast to dtype
    """
    string = string.strip("[")
    string = string.strip("]")
    return [dtype(r) for r in string.split(",")]
