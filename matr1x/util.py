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
"""Deprecated re-export shim for `matr1x.core.commands`.

The names re-exported here are deprecated and will be removed in
v8.8.0. Import them from `matr1x.core.commands` instead.
"""

import importlib
from typing import Any

from matr1x.core import deprecation

# deprecated name -> module holding the canonical definition
_CANONICAL = {
    "Command": "matr1x.core.commands",
    "Get": "matr1x.core.commands",
    "Set": "matr1x.core.commands",
}

__all__ = ["Command", "Get", "Set"]  # noqa: F822 (provided via __getattr__)


def __getattr__(name: str) -> Any:
    """Return a deprecated name after notifying about its replacement."""
    module_name = _CANONICAL.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    deprecation.notify_deprecated_access(
        f"{__name__}.{name}",
        f"{module_name}.{name}",
    )
    return getattr(importlib.import_module(module_name), name)


def __dir__() -> list[str]:
    """List the names provided by this shim."""
    return list(__all__)
