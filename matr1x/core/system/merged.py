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
"""MergedSystem: combine multiple systems into a single system."""

from __future__ import annotations

import builtins
import time
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any, ClassVar

from pydantic import ValidationError

import matr1x.core.config as core_config
from matr1x.core.error_handling import Error, Result, Success
from matr1x.core.models import (
    SystemReference,
    SystemSelectionInfo,
    UntypedConfigModel,
)
from matr1x.core.system.base import Parameter, StatefulSystem, System


class MergedSystem(System):
    """
    Defines a measurement setup/system of multiple individual systems.

    Gracefully combines the systems into one system instance, so that
    "mobile" parts of a system can be used together with multiple
    "stationary" systems. An example of this is e.g. a cryostat and
    different sets of measurement devices (one for DC and one for AC
    measurements).

    If duplicate parameters are found, they are removed. Parameters
    remain unsorted apart from the timeUTC parameter (used to delay the
    trigger after setting all values).

    Refer to parent System for further attributes.

    Parameters
    ----------
    systems : list[System]
        List of system instances that should be combined into the
        merged system.

    Attributes
    ----------
    subsys : list[System]
        Contains the individual System instances that go into the
        merged system.
    """

    _exclude_custom_information: ClassVar[bool] = True

    def __init__(self, systems: list[System]):
        self.subsys: list[System] = systems
        # initialize superclass
        # here self.subsys is already used when initializing the
        # filename, so this needs to come here
        super().__init__()
        self._filename: Path | None = None
        self.__name__ = ",".join(
            SystemReference(
                source=subsys.source or subsys.__name__,
                state=subsys.state,
            ).to_token()
            for subsys in self.subsys
        )
        self._parameter_owners: list[tuple[System, int] | None] = []
        parameter_entries = self._merge_subsystems()
        self._add_merged_parameters(parameter_entries)

        self._merge_dcdata()
        self._check_hdf5()

        # add timeUTC if not in system yet
        if "timeUTC" not in self.columns:
            self.add_param("timeUTC", "s", default=None, setter=time.sleep, getter=time.time)
            self._parameter_owners.append(None)

    def _merge_subsystems(self) -> list[tuple[Parameter, System, int]]:
        """Validate and merge all subsystem-owned values."""
        parameter_entries: list[tuple[Parameter, System, int]] = []
        seen_devices: dict[str, System] = {}
        seen_accessors: set[str] = set()
        selected_groups: dict[tuple[str, str, str], str] = {}
        for subsystem in self.subsys:
            self._validate_subsystem(subsystem, seen_accessors, selected_groups)
            self._merge_subsystem_devices(subsystem, seen_devices)
            self._merge_subsystem_config(subsystem)
            parameter_entries.extend(
                (parameter, subsystem, index)
                for index, parameter in enumerate(subsystem.parameters)
            )
            subsystem.merged_system = self
        self._validate_stateful_columns(parameter_entries)
        return parameter_entries

    @staticmethod
    def _validate_subsystem(
        subsystem: System,
        seen_accessors: builtins.set[str],
        selected_groups: dict[tuple[str, str, str], str],
    ) -> None:
        """Ensure the subsystem has a unique accessor and compatible state."""
        if subsystem.accessor_name in seen_accessors:
            raise ValueError(f"Duplicate subsystem accessor name '{subsystem.accessor_name}'")
        seen_accessors.add(subsystem.accessor_name)
        if not isinstance(subsystem, StatefulSystem):
            return
        assert subsystem.state is not None
        _, groups = subsystem.state_declaration()
        source = subsystem.source or subsystem.__class__.__module__
        source_path = Path(source).expanduser()
        identity = (
            str(source_path.resolve()) if source_path.is_file() else subsystem.__class__.__module__
        )
        group = groups[subsystem.state]
        group_key = (identity, subsystem.__class__.__qualname__, group)
        if group_key in selected_groups:
            other_state = selected_groups[group_key]
            raise ValueError(
                f"States '{other_state}' and '{subsystem.state}' from '{source}' "
                f"share exclusion group '{group}'"
            )
        selected_groups[group_key] = subsystem.state

    def _merge_subsystem_devices(self, subsystem: System, seen_devices: dict[str, System]) -> None:
        """Add uniquely named devices and their configuration queries."""
        for device_name, device in subsystem.devs.items():
            if device_name in seen_devices:
                other = seen_devices[device_name]
                raise ValueError(
                    f"Duplicate device name '{device_name}' in "
                    f"'{other.accessor_name}' and '{subsystem.accessor_name}'"
                )
            seen_devices[device_name] = subsystem
            self.devs[device_name] = device
        for device_name, config_params in subsystem.system_config_params.items():
            if device_name in self.system_config_params:
                raise ValueError(f"Duplicate device configuration name '{device_name}'")
            self.system_config_params[device_name] = config_params

    def _merge_subsystem_config(self, subsystem: System) -> None:
        """Merge public and sensitive configuration from one subsystem."""
        config = subsystem.config
        config_dict = (
            config.model_dump(by_alias=True, exclude=set(subsystem._sensitive_keys))
            if hasattr(config, "model_dump")
            else config
        )
        self.config = {**self.config, **config_dict}
        self.sensitive_config = UntypedConfigModel(
            **{**self.sensitive_config.model_dump(), **subsystem.sensitive_config.model_dump()}
        )

    def _validate_stateful_columns(self, entries: list[tuple[Parameter, System, int]]) -> None:
        """Reject ambiguous output columns when a stateful system is present."""
        if not any(subsystem.stateful for subsystem in self.subsys):
            return
        seen_columns: dict[str, System] = {}
        for parameter, subsystem, _ in entries:
            names = (
                parameter.name if isinstance(parameter.name, (list, tuple)) else [parameter.name]
            )
            for column_name in names:
                if column_name in seen_columns:
                    other = seen_columns[column_name]
                    raise ValueError(
                        f"Duplicate final column name '{column_name}' in "
                        f"'{other.accessor_name}' and '{subsystem.accessor_name}'"
                    )
                seen_columns[column_name] = subsystem

    def _add_merged_parameters(self, entries: list[tuple[Parameter, System, int]]) -> None:
        """Append parameters in their legacy order while tracking owners."""
        entries.sort(key=lambda entry: "timeUTC" in self._parameter_names(entry[0]))
        for parameter, subsystem, local_index in entries:
            if not subsystem.stateful and parameter in self.parameters:
                print(f"removing duplicated column {parameter.name} from merged system")  # noqa: T201
                continue
            self.parameters.append(parameter)
            self._parameter_owners.append((subsystem, local_index))

    @staticmethod
    def _parameter_names(parameter: Parameter) -> list[str]:
        """Return all column names represented by one parameter."""
        return parameter.name if isinstance(parameter.name, (list, tuple)) else [parameter.name]

    @classmethod
    def from_references(
        cls,
        references: Iterable[str | Path | SystemReference],
    ) -> Result[MergedSystem, str]:
        """Load, bind, and merge static or stateful system references."""
        normalized: list[SystemReference] = []
        try:
            for value in references:
                reference = SystemReference.from_value(value)
                normalized.append(reference)
        except (ValidationError, ValueError) as error:
            return Error(str(error))

        systems: list[System] = []
        for reference in normalized:
            system = System.from_file(reference)
            if isinstance(system, Error):
                return Error(system.error)
            systems.append(system.value)
        try:
            return Success(cls(systems))
        except ValueError as error:
            return Error(str(error))

    @classmethod
    def from_files(cls, system_filenames: Iterable[str | Path]) -> Result[MergedSystem, str]:
        """
        Merge multiple systems and return a MergedSystem instance.

        Note that the order of the systems matters when setting/reading
        parameters during a measurement. Typically the core system (e.g.
        Magnet-cryostat) comes first and measurement systems afterwards.

        Parameters
        ----------
        system_filenames : list[str | Path]
            List of system paths that should be merged.

        Returns
        -------
        MergedSystem or str.
            MergedSystem instance that contains the description of all
            subsystems or an error message.
        """
        return cls.from_references(system_filenames)

    def __getattr__(self, attr: str) -> Any:
        """
        Return methods/variables from subsystems.

        This method is called when an attribute is not found in the
        MergedSystem instance. First, it searches for a subsystem of
        that name, then, it searches for the attribute in all
        subsystems.

        Parameters
        ----------
        attr : str
            The name of the attribute being accessed.

        Returns
        -------
        Any
            The attribute if found.

        Raises
        ------
        AttributeError
            If the attribute is not found in any subsystem.
        """
        for subsys in self.subsys:
            if attr == subsys.accessor_name:
                return subsys
            if hasattr(subsys, attr):
                return getattr(subsys, attr)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{attr}'")

    def _parameter_index(self, value: int | str) -> int:
        """Resolve a merged parameter name or index."""
        if isinstance(value, str) and value in self.columns:
            return self.columns.index(value)
        if isinstance(value, int) and value < len(self.columns):
            return value
        raise ValueError(f"Invalid index or name: {value}")

    def set_value(
        self, i: int | str, values: float | list[float] | None
    ) -> float | list[float] | None:
        """Set a value through the subsystem that owns the merged parameter."""
        index = self._parameter_index(i)
        owner = self._parameter_owners[index]
        if owner is None:
            return super().set_value(index, values)
        subsystem, local_index = owner
        return subsystem.set_value(local_index, values)

    def trigger_value(self, i: str | int) -> None:
        """Trigger a value through the subsystem that owns the merged parameter."""
        index = self._parameter_index(i)
        owner = self._parameter_owners[index]
        if owner is None:
            super().trigger_value(index)
            return
        subsystem, local_index = owner
        subsystem.trigger_value(local_index)

    def read_value(self, i: str | int) -> Any:
        """Read a value through the subsystem that owns the merged parameter."""
        index = self._parameter_index(i)
        owner = self._parameter_owners[index]
        if owner is None:
            return super().read_value(index)
        subsystem, local_index = owner
        return subsystem.read_value(local_index)

    @property
    def filename(self) -> Path | None:
        """Filename property getter."""
        return self._filename

    @filename.setter
    def filename(self, value: Path | str | None):
        """
        Set the filename property.

        This method is needed to keep the filename on the subsystems in
        sync.

        Parameters
        ----------
        value : Path | str | None
            The new filename value to be set.
        """
        value = Path(value) if value is not None else None
        for subsys in self.subsys:
            subsys.filename = value
        self._filename = value

    @property
    def _datafile_initialized(self) -> bool:
        """Datafile initialized flag property getter."""
        return all(subsys._datafile_initialized for subsys in self.subsys)

    @_datafile_initialized.setter
    def _datafile_initialized(self, value: bool):
        """
        Set the datafile initialized property.

        This method is needed to keep the flag on the subsystems in sync.

        Parameters
        ----------
        value : bool
            The new value to be set.
        """
        for subsys in self.subsys:
            subsys._datafile_initialized = value

    def _merge_dcdata(self) -> None:
        class OrderedSetList:
            def __init__(self):
                self.items = []
                self.seen = set()

            def add(self, value):
                if value not in self.seen:
                    self.items.append(value)
                    self.seen.add(value)

            def __iter__(self):
                return iter(self.items)

        tmpdcdata = defaultdict(OrderedSetList)
        for subsys in self.subsys:
            for key, value in subsys.dcdata.items():
                if key == "date":
                    # skip date
                    continue
                if value:
                    tmpdcdata[key].add(value)
        # merge dcdata
        for key, vlist in tmpdcdata.items():
            self.dcdata[key] = ";".join(vlist)
        # set correct timestamp, overwrites value
        self.dcdata["date"] = time.strftime(f"{core_config.datetimefmt}", time.localtime())

    def _check_hdf5(self) -> None:
        """Check whether one of the systems requires HDF5."""
        for subsys in self.subsys:
            self.hdf5 = self.hdf5 or subsys.hdf5

    def grab_information(self) -> dict:
        """
        Obtain meta information from the merged system.

        Returns
        -------
        system_descriptor : dict
            System information, methods and parameters from all
            subsystems.
        """
        info = {
            "classes": [],
            "selections": [],
            "devices": {},
            "parameters": {},
            "methods": {},
            "variables": {},
            "config": {},
            "warnings": [],
        }
        base_info = super().grab_information()
        self._merge_base_information(info, base_info)
        for subsystem in self.subsys:
            self._add_subsystem_information(info, subsystem)

        return info

    @staticmethod
    def _merge_base_information(info: dict[str, Any], base_info: dict[str, Any]) -> None:
        """Copy merged devices, parameters, and methods from base metadata."""
        for category in ("devices", "parameters", "methods"):
            info[category].update(base_info.get(category, {}))

    def _add_subsystem_information(self, info: dict[str, Any], subsystem: System) -> None:
        """Add selection, attributes, configuration, and warnings for one subsystem."""
        info["classes"].append(subsystem.accessor_name)
        info["selections"].append(self._selection_information(subsystem).model_dump())
        subsystem._add_attributes_to_dict(info, prefix=subsystem.accessor_name)
        subsystem._add_config_to_information(info)
        if subsystem.warnings:
            info["warnings"].extend(subsystem.warnings)

    @staticmethod
    def _selection_information(subsystem: System) -> SystemSelectionInfo:
        """Build the structured selection record for one subsystem."""
        states: tuple[str, ...] = ()
        groups: dict[str, str] = {}
        if isinstance(subsystem, StatefulSystem):
            states, groups = subsystem.state_declaration()
        return SystemSelectionInfo(
            source=subsystem.source or subsystem.__name__,
            state=subsystem.state,
            stateful=subsystem.stateful,
            states=states,
            state_exclusion_groups=groups,
            class_name=subsystem.__class__.__name__,
            accessor_name=subsystem.accessor_name,
            config_section=subsystem.config_section,
        )

    def set(self, *args, **kwargs):
        """
        Set function that properly initializes the subsystems and updates the list of devices.

        Parameters
        ----------
        *args : tuple
            Arguments that can be used here, currently not used.
        **kwargs : dict
            Keyword arguments that can be used here, currently not used.
        """
        # use individual system for opening devices
        for subsys in self.subsys:
            subsys.set(*args, **kwargs)
        self.refresh_devs()
        # remerge potentially changed dcdata
        self.opened = True

    def query(self) -> dict[str, dict[str, Any]]:
        """Query devices and keep stateful system configuration selection-scoped."""
        if not any(subsystem.stateful for subsystem in self.subsys):
            return super().query()

        result: dict[str, Any] = {}
        system_config: dict[str, Any] = {}
        for subsystem in self.subsys:
            subsystem_result = subsystem.query()
            config = subsystem_result.pop("system_config", None)
            result.update(subsystem_result)
            if config is not None:
                key = subsystem.config_section or subsystem.accessor_name
                system_config[key] = config
        if system_config:
            result["system_config"] = system_config
        return result

    def refresh_devs(self) -> None:
        """
        Refresh the merged device dictionary from all subsystems.

        This is needed after subsystems have been opened individually,
        because System.set replaces device definitions with initialized
        device instances.
        """
        self.devs = {}
        for subsys in self.subsys:
            for device_name, device in subsys.devs.items():
                if device_name in self.devs:
                    raise ValueError(f"Duplicate device name '{device_name}' after initialization")
                self.devs[device_name] = device

    def reset(self, *args, **kwargs):
        """
        Reset function that properly deinitializes the subsystems and updates the list of devices.

        Parameters
        ----------
        *args : tuple
            Arguments that can be used here, currently not used.
        **kwargs : dict
            Keyword arguments that can be used here, currently not used.
        """
        # close all individual systems again
        if "status" in kwargs:
            self._write_status(f"{kwargs['status']}")
        self.opened = False
        for subsys in self.subsys:
            subsys.reset(*args, **kwargs)
