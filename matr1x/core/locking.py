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
"""Per-instance locking helper for device drivers."""

import functools
import threading
from collections.abc import Callable
from typing import Any, TypeVar, cast

__all__ = ["synchronized"]

_F = TypeVar("_F", bound=Callable)

# Guards the creation of the per-instance locks so that concurrent first
# calls on the same instance share a single lock.
_meta_lock = threading.Lock()


def synchronized(method: _F) -> _F:
    """
    Synchronize method calls with a per-instance reentrant lock.

    The lock is created on first use and stored on the instance under
    the attribute name ``_synchronized_lock``.
    """

    @functools.wraps(method)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        lock = self.__dict__.get("_synchronized_lock")
        if lock is None:
            with _meta_lock:
                lock = self.__dict__.get("_synchronized_lock")
                if lock is None:
                    lock = self._synchronized_lock = threading.RLock()
        with lock:
            return method(self, *args, **kwargs)

    return cast(_F, wrapper)
