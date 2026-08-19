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

import ipaddress
import threading
from typing import Any, TypedDict

from pyvisa import rname

_resource_managers: dict[int, tuple[Any, Any]] = {}


class VisaResourceRequirements(TypedDict, total=False):
    """Constraints for a VISA resource field."""

    interface_types: list[str]
    resource_classes: list[str]
    loopback_host: bool
    valid_port: bool


SERIAL_VISA_RESOURCE_REQUIREMENTS: VisaResourceRequirements = {
    "interface_types": ["ASRL"],
    "resource_classes": ["INSTR"],
}
GPIB_VISA_RESOURCE_REQUIREMENTS: VisaResourceRequirements = {
    "interface_types": ["GPIB"],
    "resource_classes": ["INSTR"],
}
TCPIP_SOCKET_VISA_RESOURCE_REQUIREMENTS: VisaResourceRequirements = {
    "interface_types": ["TCPIP"],
    "resource_classes": ["SOCKET"],
    "valid_port": True,
}
LOCAL_TCPIP_SOCKET_VISA_RESOURCE_REQUIREMENTS: VisaResourceRequirements = {
    **TCPIP_SOCKET_VISA_RESOURCE_REQUIREMENTS,
    "loopback_host": True,
}


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


def validate_visa_resource(
    value: str,
    requirements: VisaResourceRequirements | None = None,
) -> str:
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
    if requirements:
        _validate_visa_resource_requirements(value, requirements)
    return value


def _validate_visa_resource_requirements(
    value: str,
    requirements: VisaResourceRequirements,
) -> None:
    """Validate that a parsed VISA resource meets field constraints."""
    try:
        resource = rname.parse_resource_name(value)
    except rname.InvalidResourceName as exc:
        raise ValueError(f"Invalid VISA resource address {value!r}: {exc}") from exc

    _validate_resource_type(value, resource, requirements)
    if requirements.get("loopback_host"):
        _validate_loopback_host(value, resource)
    if requirements.get("valid_port"):
        _validate_tcp_port(value, resource)


def _validate_resource_type(
    value: str,
    resource: rname.ResourceName,
    requirements: VisaResourceRequirements,
) -> None:
    """Validate the VISA interface and resource class."""
    interface_types = requirements.get("interface_types", [])
    resource_classes = requirements.get("resource_classes", [])
    if _resource_type_matches(resource, interface_types, resource_classes):
        return

    expected = " or ".join(
        f"{interface} {resource_class}"
        for interface in interface_types or ["VISA"]
        for resource_class in resource_classes or ["resource"]
    )
    raise ValueError(f"VISA resource address {value!r} must use resource type {expected}")


def _resource_type_matches(
    resource: rname.ResourceName,
    interface_types: list[str],
    resource_classes: list[str],
) -> bool:
    """Return whether a resource meets its interface and class constraints."""
    if interface_types and resource.interface_type not in interface_types:
        return False
    if resource_classes and resource.resource_class not in resource_classes:
        return False
    return True


def _validate_loopback_host(value: str, resource: rname.ResourceName) -> None:
    """Validate that a TCP/IP socket uses a supported loopback address."""
    if isinstance(resource, rname.TCPIPSocket) and _is_loopback_host(resource.host_address):
        return
    raise ValueError(
        f"VISA resource address {value!r} must use 'localhost' or an IPv4 loopback address"
    )


def _validate_tcp_port(value: str, resource: rname.ResourceName) -> None:
    """Validate that a TCP/IP socket specifies a usable TCP port."""
    try:
        port = int(getattr(resource, "port", ""))
    except ValueError as exc:
        raise ValueError(
            f"VISA resource address {value!r} must specify a TCP port from 1 to 65535"
        ) from exc
    if not 1 <= port <= 65535:
        raise ValueError(
            f"VISA resource address {value!r} must specify a TCP port from 1 to 65535"
        )


def _is_loopback_host(host: str) -> bool:
    """Return whether a TCP/IP host is localhost or an IPv4 loopback address."""
    if host == "localhost":
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.version == 4 and address.is_loopback


def validate_serial_visa_resource(value: str) -> str:
    """Validate a serial VISA instrument resource."""
    return validate_visa_resource(value, SERIAL_VISA_RESOURCE_REQUIREMENTS)


def validate_gpib_visa_resource(value: str) -> str:
    """Validate a GPIB VISA instrument resource."""
    return validate_visa_resource(value, GPIB_VISA_RESOURCE_REQUIREMENTS)


def validate_tcpip_socket_visa_resource(value: str) -> str:
    """Validate a TCP/IP VISA socket resource."""
    return validate_visa_resource(value, TCPIP_SOCKET_VISA_RESOURCE_REQUIREMENTS)


def validate_local_tcpip_socket_visa_resource(value: str) -> str:
    """Validate a local TCP/IP VISA socket resource."""
    return validate_visa_resource(value, LOCAL_TCPIP_SOCKET_VISA_RESOURCE_REQUIREMENTS)
