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
"""Deprecated re-export shim for `matr1x.core.models`.

The names re-exported here are deprecated and will be removed in
v8.8.0. Import them from `matr1x.core.models` instead.
"""

import importlib
from typing import TYPE_CHECKING, Any

from matr1x.core import deprecation

if TYPE_CHECKING:
    from matr1x.core.models import (
        FilePath,
        FolderPath,
        GPIBVisaResource,
        GuiField,
        LocalTCPIPSocketVisaResource,
        Message,
        Modifier,
        SciFloat,
        SerialVisaResource,
        SystemConfigModel,
        TCPIPSocketVisaResource,
        VisaResource,
    )

# deprecated name -> module holding the canonical definition
_CANONICAL = {
    "FilePath": "matr1x.core.models",
    "FolderPath": "matr1x.core.models",
    "GPIBVisaResource": "matr1x.core.models",
    "GuiField": "matr1x.core.models",
    "LocalTCPIPSocketVisaResource": "matr1x.core.models",
    "Message": "matr1x.core.models",
    "Modifier": "matr1x.core.models",
    "SciFloat": "matr1x.core.models",
    "SerialVisaResource": "matr1x.core.models",
    "SystemConfigModel": "matr1x.core.models",
    "TCPIPSocketVisaResource": "matr1x.core.models",
    "VisaResource": "matr1x.core.models",
}

# names are provided lazily via __getattr__ (PEP 562)
__all__ = [
    "FilePath",
    "FolderPath",
    "GPIBVisaResource",
    "GuiField",
    "LocalTCPIPSocketVisaResource",
    "Message",
    "Modifier",
    "SciFloat",
    "SerialVisaResource",
    "SystemConfigModel",
    "TCPIPSocketVisaResource",
    "VisaResource",
]


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
