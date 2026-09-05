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
"""Re-export shim. The implementation lives in `matr1x.core.pymeasure_threading_fix`.

Importing this module applies the pymeasure thread-safety monkey patch as a
side effect, exactly like importing the implementation module.
"""

from matr1x.core import pymeasure_threading_fix
from matr1x.core.pymeasure_threading_fix import Instrument

__all__ = ["Instrument", "pymeasure_threading_fix"]
