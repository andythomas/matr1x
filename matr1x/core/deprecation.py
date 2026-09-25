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
"""Deprecation notifications for legacy access paths.

Legacy import paths (e.g. `matr1x.models.Message`) are deprecated
aliases of the public API in the layered subpackages. Accessing a
legacy name logs a warning and, if a GUI has registered a notifier
callback, shows a notification that must be dismissed manually.
"""

import logging
from collections.abc import Callable

import matr1x.core.config as core_config

__all__ = ["notify_deprecated_access", "set_deprecation_notifier"]

logger = logging.getLogger(__name__)

# callback displaying a deprecation message in a GUI, if one is running
_notifier: Callable[[str], None] | None = None
# legacy paths already reported in this process
_notified: set[str] = set()


def set_deprecation_notifier(callback: Callable[[str], None] | None) -> None:
    """
    Register a callback that displays deprecation messages.

    Parameters
    ----------
    callback
        Called with the message text, or None to unregister.
    """
    global _notifier
    _notifier = callback


def notify_deprecated_access(old_path: str, new_path: str) -> None:
    """
    Report once per process that old_path moved to new_path.

    Parameters
    ----------
    old_path
        The deprecated access path, e.g. `matr1x.models.Message`.
    new_path
        The canonical replacement, e.g. `matr1x.core.models.Message`.
    """
    if old_path in _notified:
        return
    _notified.add(old_path)
    message = f"{old_path} is deprecated and will be removed in v8.8.0; use {new_path} instead."
    logger.warning(f"{core_config.deprecation_marker} {message}")
    if _notifier is not None:
        _notifier(message)
