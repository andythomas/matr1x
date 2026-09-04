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
Configuration and utility module for the matr1x data acquisition software.

This module is a thin re-export shim. The actual configuration logic lives in
`matr1x.core.config`; this module re-exports the public names so that the
historical ``import matr1x`` and ``matr1x.<name>`` access patterns keep working.

The live configuration globals (``config``, ``datetimefmt``) are rebound by
`reload_config`, so they are exposed lazily via `__getattr__` to
always reflect the current values. Model re-exports (``MainConfig`` and
friends) are likewise resolved lazily so that this module does not import
`matr1x.models` at module level.
"""

import warnings
from importlib.metadata import PackageNotFoundError, version

from .core import config as _core_config

# Import pymeasure threading fix to apply monkey patch automatically
# This must be imported early to ensure all pymeasure instruments are thread-safe
from .core import pymeasure_threading_fix
from .core.config import (
    MIGRATIONS,
    deprecation_marker,
    load_config,
    logfolder,
    merge_dicts,
    output_extension,
    reload_config,
    resolved_directory,
    system_directories,
    system_names,
    usersfolder,
    validation_errors,
    write_config,
)
from .core.metadata import APP_META_KEY, VALID_META_KEYS
from .core.util import (
    create_temp_dir_with_symlinks,
    get_package_path,
    resolve_config_path,
    resolve_pkgroot_path,
)


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
    # Config data
    "MIGRATIONS",
    # Re-exports
    "VALID_META_KEYS",
    "MainConfig",
    "UserlibConfig",
    # Version / constants
    "__version__",
    "config",
    "create_temp_dir_with_symlinks",
    "datetimefmt",
    "deprecation_marker",
    "format_validation_error",
    "get_package_path",
    # Config management
    "load_config",
    "logfolder",
    "merge_dicts",
    "output_extension",
    "reload_config",
    "resolve_config_path",
    "resolve_pkgroot_path",
    "resolved_directory",
    "system_directories",
    "system_names",
    # System dirs / globals
    "usersfolder",
    "validation_errors",
    "write_config",
]

try:
    __version__ = version("matr1x-measurements")
except PackageNotFoundError:
    __version__ = "unknown"


def __getattr__(name: str):
    """Lazily expose live config globals and model re-exports (PEP 562).

    ``config`` and ``datetimefmt`` are rebound by `reload_config`, so they
    are proxied to `matr1x.core.config` on every access to stay current.
    The model re-exports are resolved lazily to avoid importing
    `matr1x.models` at module level.
    """
    if name in ("config", "datetimefmt"):
        return getattr(_core_config, name)
    if name in ("MainConfig", "UserlibConfig", "format_validation_error"):
        from matr1x import models

        return getattr(models, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
