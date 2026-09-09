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
"""Pydantic data models for configuration, system info, and measurement data."""

from matr1x.core.models.config import (
    ConfigBaseModel,
    FilePath,
    FolderPath,
    GPIBVisaResource,
    GuiField,
    LocalTCPIPSocketVisaResource,
    MainConfig,
    Matr1xConfig,
    Matr1xDevicesConfig,
    Matr1xDevicesVisadeviceConfig,
    Matr1xEmailConfig,
    Matr1xInstallConfig,
    Matr1xScriptsConfig,
    Matr1xScriptsMatrix_ScriptConfig,
    Matr1xScriptsMatrix_ScriptShortcutsConfig,
    SciFloat,
    SerialVisaResource,
    SystemConfigModel,
    TCPIPSocketVisaResource,
    UntypedConfigModel,
    UserlibConfig,
    UserlibInstallConfig,
    VisaResource,
    format_validation_error,
)
from matr1x.core.models.data import (
    Datafile,
    ExecutionLines,
    Header,
    InputParameters,
    LogEntry,
    MeasuredValues,
    SetValues,
    Telemetry,
)
from matr1x.core.models.socket import (
    Envelope,
    ErrorMessage,
    MeasurementData,
    Message,
    Modifier,
)
from matr1x.core.models.system import (
    SystemCapability,
    SystemDevice,
    SystemInfo,
    SystemMethod,
    SystemParameter,
    SystemReference,
    SystemSelectionInfo,
    SystemVariable,
)

__all__ = [
    "ConfigBaseModel",
    "Datafile",
    "Envelope",
    "ErrorMessage",
    "ExecutionLines",
    "FilePath",
    "FolderPath",
    "GPIBVisaResource",
    "GuiField",
    "Header",
    "InputParameters",
    "LocalTCPIPSocketVisaResource",
    "LogEntry",
    "MainConfig",
    "Matr1xConfig",
    "Matr1xDevicesConfig",
    "Matr1xDevicesVisadeviceConfig",
    "Matr1xEmailConfig",
    "Matr1xInstallConfig",
    "Matr1xScriptsConfig",
    "Matr1xScriptsMatrix_ScriptConfig",
    "Matr1xScriptsMatrix_ScriptShortcutsConfig",
    "MeasuredValues",
    "MeasurementData",
    "Message",
    "Modifier",
    "SciFloat",
    "SerialVisaResource",
    "SetValues",
    "SystemCapability",
    "SystemConfigModel",
    "SystemDevice",
    "SystemInfo",
    "SystemMethod",
    "SystemParameter",
    "SystemReference",
    "SystemSelectionInfo",
    "SystemVariable",
    "TCPIPSocketVisaResource",
    "Telemetry",
    "UntypedConfigModel",
    "UserlibConfig",
    "UserlibInstallConfig",
    "VisaResource",
    "format_validation_error",
]
