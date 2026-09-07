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
from the specific `matr1x.gui` submodules instead.
"""

from matr1x.gui.app import AboutBox, MApplication
from matr1x.gui.helpers import (
    clear_layout,
    create_matr1x_quit_action,
    create_matrix_settings_action,
    detect_shortcut,
    find_parent_of_type,
    get_install_info,
    get_matrix_icon,
    get_system_capability,
    get_system_info,
    open_matrix_toml,
    save_messagebox,
)
from matr1x.gui.logging import LoggingWindow
from matr1x.gui.meta_viewer import (
    ConfigEditWidget,
    MetaViewerWidget,
    blocked_signals,
    validator,
)
from matr1x.gui.mixins import (
    AutoSlot,
    FileDropMixin,
    LoggerMixin,
    LogWindowMixin,
)
from matr1x.gui.plot import CustomViewBox, SimplePlotWidget
from matr1x.gui.shared import check_config
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
    "MApplication",
    "MetaViewerWidget",
    "QRangeWidget",
    "ReadOnlyTable",
    "SimplePlotWidget",
    "blocked_signals",
    "check_config",
    "clear_layout",
    "create_matr1x_quit_action",
    "create_matrix_settings_action",
    "detect_shortcut",
    "find_parent_of_type",
    "get_install_info",
    "get_matrix_icon",
    "get_system_capability",
    "get_system_info",
    "open_matrix_toml",
    "save_messagebox",
    "validator",
]
