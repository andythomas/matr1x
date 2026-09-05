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
"""Pydantic models describing system properties."""

from collections.abc import Callable
from functools import cached_property
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SystemReference(BaseModel):
    """Identify one static system or one selected state of a stateful system."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    state: str | None = None

    @model_validator(mode="after")
    def validate_reference(self):
        """Validate the source and optional state."""
        if not self.source.strip():
            raise ValueError("System source must not be empty")
        if "::" in self.source:
            raise ValueError("'::' is reserved and cannot occur in a system source")
        if self.state is not None and not self.state.isidentifier():
            raise ValueError("System state must be a valid Python identifier")
        return self

    @classmethod
    def from_value(cls, value: "SystemReference | str | Path") -> "SystemReference":
        """Normalize a reference object, source path, or compact ``source::name`` token."""
        if isinstance(value, cls):
            return value
        token = str(value).strip()
        if "::" not in token:
            return cls(source=token)
        source, state = token.rsplit("::", 1)
        return cls(source=source, state=state)

    def to_token(self) -> str:
        """Return the compact representation used in legacy-compatible headers."""
        if self.state is None:
            return self.source
        return f"{self.source}::{self.state}"


class SystemCapability(BaseModel):
    """Describe a system class without constructing an instance."""

    model_config = ConfigDict(extra="forbid")

    source: str
    stateful: bool = False
    states: tuple[str, ...] = ()
    state_exclusion_groups: dict[str, str] = Field(default_factory=dict)
    class_name: str


class SystemSelectionInfo(SystemCapability):
    """Describe one selected and constructed system."""

    state: str | None = None
    accessor_name: str
    config_section: str | None = None


class SystemDevice(BaseModel):
    """Model for device entries."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str


class SystemParameter(BaseModel):
    """Model for parameter entries."""

    model_config = ConfigDict(extra="forbid")

    name: str
    unit: str
    index: int
    settable: bool


class SystemVariable(BaseModel):
    """Model for variables."""

    model_config = ConfigDict(extra="forbid")

    name: str
    prefix: str
    signature: str | None = None


class SystemMethod(SystemVariable):
    """Model for method entries."""

    model_config = ConfigDict(extra="forbid")

    docstring: str | None = None
    callable: Callable[[], Any] | None = None

    @property
    def doc_summary(self):
        """Returns the first line of the docstring as a summary."""
        return "" if not self.docstring else self.docstring.split("\n")[0].strip()


class SystemInfo(BaseModel):
    """Main model for the configuration."""

    model_config = ConfigDict(extra="forbid")

    classes: list[str]
    devices: dict[str, SystemDevice]
    parameters: dict[str, SystemParameter]
    methods: dict[str, SystemMethod]
    variables: dict[str, SystemVariable]
    config: dict[str, Any]
    selections: list[SystemSelectionInfo] = Field(default_factory=list)
    warnings: list[tuple[str, int]] = Field(default_factory=list)
    config_validation_errors: list[str] = Field(default_factory=list)

    @property
    def flat_parameters(self) -> list[SystemParameter]:
        """Returns a flat list of parameters."""
        result: list[SystemParameter] = []
        for parameter in self.parameters.values():
            settable = parameter.settable
            name_parts = [n.strip() for n in parameter.name.split(",")]
            unit_parts = [u.strip() for u in parameter.unit.split(",")]
            for name, unit in zip(name_parts, unit_parts):
                result.append(
                    SystemParameter(name=name, unit=unit, index=parameter.index, settable=settable)
                )
        return result

    @property
    def configurable_sections(self) -> list[str]:
        """Return config sections for selections without a system file on disk.

        For each selection whose ``source`` does not exist as a file, the
        ``config_section`` is returned if set, otherwise the ``source``.
        """
        return [
            selection.config_section or selection.source
            for selection in self.selections
            if not Path(selection.source).exists()
        ]

    @cached_property
    def stub(self) -> str:
        """Generate the type-checking lines."""
        text = "from typing import TYPE_CHECKING\n"
        text += "from typing import Any as _Any\n"
        text += "if TYPE_CHECKING:\n"
        for cls in self.classes:
            text += f"    class {cls}:\n"
            text += "        def __init__(self):\n"
            text += self._add_variables(cls)
            text += "            pass\n"
            text += self._add_methods(cls)
            text += "        pass\n"
        text += "    class MergedSystem:\n"
        text += "        def __init__(self):\n"
        for cls in self.classes:
            text += f"            self.{cls} = {cls}()\n"
        text += "            pass\n"
        text += "    system = MergedSystem()\n"
        return text

    @cached_property
    def stub_length(self) -> int:
        """Return the length of the type-checking stub."""
        return len(self.stub.splitlines())

    def _add_variables(self, name: str) -> str:
        """Generate the variable declarations."""
        stub = ""
        for var in self.variables.values():
            if var.prefix == name:
                if var.signature and var.signature != "(NoneType)":
                    stub += f"            self.{var.name}: {var.signature}\n"
                else:
                    stub += f"            self.{var.name}: _Any\n"
        return stub

    def _add_methods(self, name: str) -> str:
        """Generate the methods declarations."""
        stub = ""
        for method in self.methods.values():
            if method.prefix == name:
                stub += f"        def {method.name}"
                if method.signature:
                    stub += f"{method.signature}:"
                else:
                    stub += ":"
                if method.docstring:
                    stub += '\n            """'
                    for line in method.docstring.splitlines():
                        stub += f"\n            {line}"
                    stub += '\n            """'
                stub += "\n            ...\n"
        return stub
