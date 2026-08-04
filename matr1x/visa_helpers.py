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
"""Helpers for VISA resource discovery and address validation."""

import threading
from typing import Any

_resource_managers: dict[int, tuple[Any, Any]] = {}


def get_visa_resource_manager() -> Any:
    """Return a cached PyVISA resource manager for the current thread."""
    import pyvisa

    thread_id = threading.get_ident()
    resource_manager_factory = pyvisa.ResourceManager
    cached_resource_manager = _resource_managers.get(thread_id)
    if (
        cached_resource_manager is None
        or cached_resource_manager[0] is not resource_manager_factory
    ):
        cached_resource_manager = (resource_manager_factory, resource_manager_factory())
        _resource_managers[thread_id] = cached_resource_manager
    return cached_resource_manager[1]


def validate_visa_resource(value: str) -> str:
    """
    Validate a VISA resource string without opening the instrument.

    ``VisaResource`` can be used in Pydantic config models for systems that
    need a VISA address. The config editor renders the field as an editable
    combo box with discovered resource suggestions while still allowing free
    text input.

    Example
    -------
    ```python
    from pydantic import Field

    from matr1x.models import SystemConfigModel, VisaResource


    class DeviceConfig(SystemConfigModel):
        address: VisaResource = Field(..., description="VISA resource address")
    ```
    """
    if not value.strip():
        raise ValueError("VISA resource address must not be empty")

    try:
        resource_info = get_visa_resource_manager().resource_info(value)
    except Exception as exc:
        raise ValueError(f"Invalid VISA resource address {value!r}: {exc}") from exc
    if resource_info.resource_name is None:
        raise ValueError(f"Invalid VISA resource address {value!r}")
    return value
