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
"""Re-export shim. The implementation lives in `matr1x.core.eval`."""

from matr1x.core.eval import (
    HeaderDict,
    OptionalFields,
    RequiredHeader,
    delta,
    delta3p,
    loadmatrix,
)

__all__ = ["HeaderDict", "OptionalFields", "RequiredHeader", "delta", "delta3p", "loadmatrix"]
