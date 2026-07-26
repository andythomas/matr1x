# This file is part of a software collection for data acquisition (matr1x).
# Copyright (C) 2006-2026 matr1x developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""Define a reusable dummy system for testing and demonstration."""

from pydantic import Field

from matr1x.devices.dummy import dummy
from matr1x.models import SystemConfigModel, VisaResource
from matr1x.system import ReusableSystem


class ReusableDummyConfig(SystemConfigModel):
    """Configuration for one reusable dummy instance."""

    address: VisaResource = Field(..., description="VISA resource address")
    initial_p2: float = Field(3.14, description="Initial p2 value")


class ReusableDummy(ReusableSystem):
    """Dummy system which may be selected multiple times."""

    name_prefix = "dummy"

    def __init__(self, name: str):
        """Initialize one named dummy system instance."""
        super().__init__(name)
        self.dcdata["source"] = "reusable dummy system for testing matr1x"
        self.load_config(
            ReusableDummyConfig,
            "matr1x.systems.system_reusable_dummy",
        )
        self.add_dev(
            name,
            dummy,
            args=(getattr(self.config, "address", ""),),
            kwargs={"p2": self.config.initial_p2},
        )
        self.add_param(
            f"{name} p2",
            "cnt",
            setter=[name, "p2"],
            getter=[name, "p2"],
        )
