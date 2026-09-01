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
#
"""
Contains GUI related functions and class definitions.

These are used by sweep-generator, matrix-gui, matrix-preview, matrix-
script and control-guis.

This module is a re-export shim kept for backwards compatibility. Import
from the specific :mod:`matr1x.gui` submodules instead.
"""

from matr1x.gui.app import AboutBox, MApplication, ThemeDetector
from matr1x.gui.helpers import (
    _draw_character_icon,
    _draw_custom_icon,
    _format_local_timestamp,
    _load_matr1x_icon,
    _resolve_icon_colors,
    clear_layout,
    create_matr1x_quit_action,
    create_matrix_settings_action,
    detect_shortcut,
    find_parent_of_type,
    get_install_info,
    get_matrix_icon,
    get_package_version,
    get_system_capability,
    get_system_info,
    open_matrix_toml,
    save_messagebox,
)
from matr1x.gui.logging import LoggingWindow, _LogSignalHelper, _QTableLogger
from matr1x.gui.meta_viewer import (
    _DEFAULT_PARENT_INDEX,
    MAX_INT64,
    MIN_INT64,
    ConfigEditWidget,
    MetaViewerWidget,
    _lo,
    blocked_signals,
    validator,
)
from matr1x.gui.mixins import (
    AutoSlot,
    FileDropMixin,
    LoggerMixin,
    LogWindowMixin,
    P,
    R,
    _build_overloads,
    _collect_parameters,
    _expand_type,
    _normalize_result_type,
    hasLogActions,
)
from matr1x.gui.plot import CustomViewBox, SimplePlotWidget
from matr1x.gui.shared import _format_validation_error, check_config
from matr1x.gui.widgets import FileLineEdit, QRangeWidget, ReadOnlyTable

__all__ = [
    "AboutBox",
    "AutoSlot",
    "ConfigEditWidget",
    "CustomViewBox",
    "FileDropMixin",
    "FileLineEdit",
    "LogWindowMixin",
    "LoggerMixin",
    "LoggingWindow",
    "MAX_INT64",
    "MApplication",
    "MIN_INT64",
    "MetaViewerWidget",
    "P",
    "QRangeWidget",
    "R",
    "ReadOnlyTable",
    "SimplePlotWidget",
    "ThemeDetector",
    "_DEFAULT_PARENT_INDEX",
    "_LogSignalHelper",
    "_QTableLogger",
    "_build_overloads",
    "_collect_parameters",
    "_draw_character_icon",
    "_draw_custom_icon",
    "_expand_type",
    "_format_local_timestamp",
    "_format_validation_error",
    "_lo",
    "_load_matr1x_icon",
    "_normalize_result_type",
    "_resolve_icon_colors",
    "blocked_signals",
    "check_config",
    "clear_layout",
    "create_matr1x_quit_action",
    "create_matrix_settings_action",
    "detect_shortcut",
    "find_parent_of_type",
    "get_install_info",
    "get_matrix_icon",
    "get_package_version",
    "get_system_capability",
    "get_system_info",
    "hasLogActions",
    "open_matrix_toml",
    "save_messagebox",
    "validator",
]
