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
"""Re-export shim for `matr1x.core.system`.

The system classes now live in `matr1x.core.system` (``base`` and
``merged``). This module re-exports the public names so that
``from matr1x.system import ...`` keeps working.
"""

from matr1x.core.system import (
    ALLOWED_SIGNATURE_TYPES,
    BUILTIN_TYPES,
    ConfigParameter,
    ConfigScheme,
    ConfigValue,
    DcDict,
    MergedSystem,
    Parameter,
    StatefulSystem,
    System,
    T,
)

__all__ = [
    "ALLOWED_SIGNATURE_TYPES",
    "BUILTIN_TYPES",
    "ConfigParameter",
    "ConfigScheme",
    "ConfigValue",
    "DcDict",
    "MergedSystem",
    "Parameter",
    "StatefulSystem",
    "System",
    "T",
]
