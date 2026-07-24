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
Runnable dynamic-device test system using local dummy TCP/IP instruments.

Use this system to exercise dynamic config editing and complete measurements
without laboratory hardware. Add one or more labelled devices in the config
editor and give each an unused local TCP port, for example
``TCPIP::localhost::10031::SOCKET`` and
``TCPIP::localhost::10034::SOCKET``. The system starts one dummy SCPI server
for every configured device when the measurement is initialized, so each
address must use a distinct port that is not already occupied.

Each device exposes a ``<label> p2`` measurement parameter. Its initial value
can be configured with ``initial_p2`` and then read or swept like a normal
device parameter.
"""

from pydantic import BaseModel, ConfigDict, Field

from matr1x.devices.dummy import dummy
from matr1x.models import VisaResource
from matr1x.system import System


class DummyDeviceConfig(BaseModel):
    """Configuration for one socket-backed dummy device."""

    model_config = ConfigDict(extra="forbid")

    address: VisaResource = Field(..., description="VISA resource address")
    initial_p2: float = Field(0.0, description="Initial dummy p2 value")


class DynamicDummyConfig(BaseModel):
    """Configuration for dynamically labelled local dummy devices."""

    model_config = ConfigDict(extra="forbid")

    devices: dict[str, DummyDeviceConfig] = Field(
        default_factory=dict,
        description="Dummy devices keyed by device label",
    )


class DynamicDummySystem(System):
    """Measurement system that starts one local dummy server per configured device."""

    def __init__(self) -> None:
        super().__init__()
        self.load_config(DynamicDummyConfig, "matr1x.systems.system_dynamic_dummy")

        self.dcdata["source"] = "Dynamic dummy device system"
        for label, device_config in self.config.devices.items():
            self.add_dev(
                label,
                dummy,
                args=(device_config.address,),
                kwargs={"p2": device_config.initial_p2},
            )
            self.add_param(
                f"{label} p2",
                "cnt",
                setter=[label, "p2"],
                getter=[label, "p2"],
            )


system = DynamicDummySystem()
