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
Root package of the matr1x data acquisition software.

The public API lives in the layered subpackages (``matr1x.core``,
``matr1x.gui``, ``matr1x.control``, ``matr1x.devices``); see the
reference section of the documentation. This module only exposes
``__version__`` and re-exports the metadata constants.
"""

import warnings
from importlib.metadata import PackageNotFoundError, version

from .core.metadata import APP_META_KEY, VALID_META_KEYS


def _clean_formatwarning(
    message: Warning | str,
    category: type[Warning],
    filename: str,
    lineno: int,
    line: str | None = None,
) -> str:
    """Format a warning into a single line without pulling source code context."""
    return f"{filename}:{lineno}: {category.__name__}: {message}\n"


warnings.formatwarning = _clean_formatwarning  # ty: ignore[invalid-assignment]

__all__ = [
    "APP_META_KEY",
    "VALID_META_KEYS",
    "__version__",
]

try:
    __version__ = version("matr1x-measurements")
except PackageNotFoundError:
    __version__ = "unknown"
