# This file is part of a software collection for data acquisition (matr1x).
# Copyright (C) 2006-2026 matr1x developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""Define a stateful dummy system for testing and demonstration."""

from pydantic import Field

from matr1x.devices.dummy import dummy
from matr1x.models import LocalTCPIPSocketVisaResource, SystemConfigModel
from matr1x.system import StatefulSystem


class StatefulDummyConfig(SystemConfigModel):
    """Configuration for one selected dummy state."""

    address: LocalTCPIPSocketVisaResource = Field(
        ...,
        description="Local TCP/IP socket used by the dummy device",
    )
    initial_p2: float = Field(3.14, description="Initial p2 value")


class StatefulDummy(StatefulSystem):
    """Dummy system with exclusive and independently usable states."""

    states = ("primary", "primary_fast", "secondary")
    state_exclusion_groups = {
        "primary": "primary_device",
        "primary_fast": "primary_device",
        "secondary": "secondary_device",
    }

    def __init__(self, state: str):
        """Initialize the dummy system in one predefined state."""
        super().__init__(state)
        self.dcdata["source"] = "stateful dummy system for testing matr1x"
        self.load_config(
            StatefulDummyConfig,
            "matr1x.systems.system_stateful_dummy",
        )
        self.add_dev(
            state,
            dummy,
            args=(getattr(self.config, "address", ""),),
            kwargs={"p2": self.config.initial_p2},
        )
        self.add_param(
            f"{state} p2",
            "cnt",
            setter=[state, "p2"],
            getter=[state, "p2"],
        )
