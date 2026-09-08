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
"""Reusable Qt mixins and the AutoSlot decorator."""

from __future__ import annotations

import inspect
import logging
import re
import sys
import types
from collections.abc import Callable
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    ParamSpec,
    Protocol,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)

if sys.version_info >= (3, 12):
    from typing import TypeAliasType
else:
    TypeAliasType = None


import shiboken6
from PySide6.QtCore import (
    QByteArray,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QDragEnterEvent,
    QDropEvent,
)
from PySide6.QtWidgets import (
    QMenu,
    QMessageBox,
)

if TYPE_CHECKING:
    from matr1x.gui.app import SaferQSettings

from .logging import LoggingWindow

logger = logging.getLogger(__name__)


P = ParamSpec("P")
R = TypeVar("R")


class LoggerMixin:
    """Add a logger for fine grained information of the origin."""

    def __init_subclass__(cls, **kwargs):
        """Generate the logger."""
        super().__init_subclass__(**kwargs)
        cls.logger = logging.getLogger(f"{cls.__module__}.{cls.__qualname__}")


class FileDropMixin:
    """Enable drag and drop of a file for QWidgets."""

    file_dropped = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.valid_extensions: list = []

    def setValidExtensions(self, valid_extensions: list[str | re.Pattern]) -> None:
        """
        Set the valid extensions.

        Parameters
        ----------
        valid_extensions: list[str | re.Pattern]
            A list where each element is either a string or a compiled!
            RegEx pattern.
        """
        self.valid_extensions = valid_extensions

    def dragEnterEvent(self, a0: QDragEnterEvent) -> None:
        """Enable drag and drop (1)."""
        if a0.mimeData().hasUrls():
            a0.acceptProposedAction()
        else:
            a0.ignore()

    def dropEvent(self, a0: QDropEvent) -> None:
        """Enable drag and drop (2)."""
        urls = a0.mimeData().urls()
        if len(urls) != 1:
            QMessageBox.warning(None, "Too many Files", "Please only drop a single file.")
            return
        suffix = Path(urls[0].toLocalFile()).suffix
        for extension in self.valid_extensions:
            if (isinstance(extension, re.Pattern) and extension.match(suffix)) or (
                isinstance(extension, str) and suffix == extension
            ):
                self.file_dropped.emit(urls[0].toLocalFile())
                a0.acceptProposedAction()
                return
        QMessageBox.warning(
            None,
            "Invalid File",
            "Unsupported file dropped.",
        )


class hasLogActions(Protocol):
    """The actions needed by the LogWindowMixin."""

    @property
    def show_log(self) -> QAction:
        """The action to show the log window."""

    @property
    def post_install(self) -> QAction:
        """The action to post-install the application."""

    @property
    def remove_desktop_integration(self) -> QAction:
        """The action to remove desktop integration."""


class LogWindowMixin:
    """Shared log-window action handling for GUI scripts."""

    log_window: LoggingWindow

    @staticmethod
    def create_show_log_action() -> QAction:
        """Create the common log-window action."""
        show_log = QAction("Show Log Window")
        show_log.setCheckable(True)
        return show_log

    @staticmethod
    def create_about_action() -> QAction:
        """Create the common about action."""
        about = QAction("About")
        about.setMenuRole(QAction.MenuRole.AboutRole)
        return about

    @staticmethod
    def create_post_install_action() -> QAction:
        """Create the common desktop integration installation action."""
        return QAction("Install Desktop Integration")

    @staticmethod
    def create_remove_desktop_integration_action() -> QAction:
        """Create the common desktop integration removal action."""
        return QAction("Remove Desktop Integration")

    @classmethod
    def add_common_help_actions(cls, menu: QMenu, actions: hasLogActions) -> None:
        """
        Add common help menu actions.

        Parameters
        ----------
        menu : QMenu
            The help menu to populate.
        actions : hasLogActions
            Object exposing about, show_log, post_install and
            remove_desktop_integration actions.
        """
        menu.addAction(actions.show_log)
        menu.addSeparator()
        menu.addAction(actions.post_install)
        menu.addAction(actions.remove_desktop_integration)
        menu.addSeparator()

    def save_log_window_state(self, settings: SaferQSettings, *, enabled: bool = True) -> None:
        """
        Save the log window geometry.

        Parameters
        ----------
        settings : SaferQSettings
            The application settings object.
        enabled : bool
            Whether this window owns the log window state.
        """
        if not enabled:
            return
        if not shiboken6.isValid(self.log_window):
            return
        settings.setValue("log_window/geometry", self.log_window.saveGeometry())

    def restore_log_window_state(self, settings: SaferQSettings, *, enabled: bool = True) -> None:
        """
        Restore the log window geometry.

        Parameters
        ----------
        settings : SaferQSettings
            The application settings object.
        enabled : bool
            Whether this window owns the log window state.
        """
        if not enabled:
            return
        if not shiboken6.isValid(self.log_window):
            return
        self.log_window.restoreGeometry(
            settings.safer_value("log_window/geometry", QByteArray(), type=QByteArray)
        )

    def cleanup_log_window(self, *, enabled: bool = True) -> None:
        """
        Remove the log handler and delete the log window.

        Parameters
        ----------
        enabled : bool
            Whether this window owns the log window.
        """
        if not enabled:
            return
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.log_window.log_handler)
        self.log_window.deleteLater()

    def toggle_log_window(self) -> None:
        """Toggle the visibility of the logging window."""
        if self.log_window.isVisible():
            self.log_window.hide()
        else:
            self.log_window.show()
            self.log_window.raise_()
            self.log_window.activateWindow()

    def _on_log_window_visibility_changed(self, visible: bool, actions: hasLogActions) -> None:
        """Keep the 'Show Log Window' action state in sync."""
        action = actions.show_log
        action.setChecked(visible)
        action.setText("Hide Log Window" if visible else "Show Log Window")


def AutoSlot(function: Callable[P, R]) -> Callable[P, R]:
    """
    Provide a Qt slot for a typed python function or method.

    To have only one source of truth, the type hints generate the
    appropriate slot automatically and automatically generates Qt Slot
    overloads.
    """
    function = inspect.unwrap(function)
    hints = get_type_hints(function)
    signature = inspect.signature(function)
    params = _collect_parameters(signature, hints)
    overloads = _build_overloads(params)
    result_type = _normalize_result_type(hints.get("return"))
    for args in reversed(overloads):
        if result_type is not None:
            function = Slot(*args, result=result_type)(function)
        else:
            function = Slot(*args)(function)
    return function


def _collect_parameters(
    signature: inspect.Signature, hints: dict[str, Any]
) -> list[dict[str, Any]]:
    """Extract parameter metadata (types + default info)."""
    params: list[dict[str, Any]] = []
    for name, param in signature.parameters.items():
        if name == "self":
            continue
        if name not in hints:
            raise TypeError(f"Missing type hint for parameter '{name}'")
        params.append(
            {
                "types": _expand_type(hints[name]),
                "has_default": param.default is not inspect._empty,
            }
        )
    return params


def _expand_type(t: Any) -> list[type]:
    """Expand a Python type hint into Qt-compatible types."""
    # Special handling for Python 3.12+ TypeAliasType (e.g., numpy.typing.ArrayLike)
    if TypeAliasType is not None and isinstance(t, TypeAliasType):
        return _expand_type(t.__value__)
    origin = get_origin(t)
    if origin is type:
        return [type]
    if origin in (Union, types.UnionType):
        result = []
        for arg in get_args(t):
            result.extend(_expand_type(arg))
        return result
    if origin is not None:
        return [origin]
    return [t]


def _build_overloads(params: list[dict]) -> list[list[type]]:
    """Create all Qt slot overload combinations."""
    overloads = [[]]
    for param in params:
        new_overloads = [base + [t] for base in overloads for t in param["types"]]
        if param["has_default"]:
            overloads = overloads + new_overloads
        else:
            overloads = new_overloads
    seen = []
    for o in overloads:
        if o not in seen:
            seen.append(o)
    return seen


def _normalize_result_type(t: Any) -> Any:
    """Convert Python return annotation to Qt-compatible type."""
    if t is type(None):
        return None
    if t is None:
        return None
    # Special handling for Python 3.12+ TypeAliasType
    if TypeAliasType is not None and isinstance(t, TypeAliasType):
        return _normalize_result_type(t.__value__)
    origin = get_origin(t)
    if origin is type:
        return type
    if origin is not None:
        return origin
    return t
