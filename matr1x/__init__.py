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
``__version__`` and the deprecated metadata constants, which are
removed in v8.8.0.
"""

import importlib
import warnings
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from .core import deprecation


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

# deprecated name -> module holding the canonical definition
_DEPRECATED = {
    "APP_META_KEY": "matr1x.core.metadata",
    "VALID_META_KEYS": "matr1x.core.metadata",
}

__all__ = [
    "APP_META_KEY",
    "VALID_META_KEYS",
    "__version__",
]


def __getattr__(name: str) -> Any:
    """Return a deprecated name after notifying about its replacement."""
    module_name = _DEPRECATED.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    deprecation.notify_deprecated_access(
        f"{__name__}.{name}",
        f"{module_name}.{name}",
    )
    return getattr(importlib.import_module(module_name), name)


def __dir__() -> list[str]:
    """List the names provided by this module."""
    return list(__all__)


try:
    __version__ = version("matr1x-measurements")
except PackageNotFoundError:
    __version__ = "unknown"
