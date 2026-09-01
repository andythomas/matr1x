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
"""Contains classes shared across matr1x scripts."""

import importlib.util
import logging
import socket
import subprocess
import sys
import tempfile
import threading
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, BinaryIO, Literal, TypedDict, final

import tomli_w
from pydantic import BaseModel, ValidationError
from pyqtgraph.Qt.QtGui import QColor
from PySide6.QtCore import (
    QByteArray,
    QDateTime,
    QModelIndex,
    QPersistentModelIndex,
    QPropertyAnimation,
    QSize,
    Qt,
    QThread,
    QTimer,
    QTimeZone,
    Signal,
)
from PySide6.QtGui import QAction, QDropEvent, QFocusEvent, QKeySequence, QMouseEvent, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidgetItem,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from matr1x.core.config import resolved_directory, validation_errors
from matr1x.core.error_handling import Error, InternalInvariantError, Result
from matr1x.core.metadata import VALID_META_KEYS
from matr1x.core.models import (
    Envelope,
    Header,
    MainConfig,
    MeasuredValues,
    SetValues,
    SystemCapability,
    SystemInfo,
    SystemReference,
)
from matr1x.core.util import get_matrix_binary
from matr1x.gui.app import MApplication, SaferQSettings
from matr1x.gui.helpers import get_matrix_icon, get_system_capability, get_system_info
from matr1x.gui.meta_viewer import ConfigEditWidget, blocked_signals
from matr1x.gui.mixins import LoggerMixin
from matr1x.gui.widgets import ReadOnlyTable

logger = logging.getLogger(__name__)

__all__ = [
    "ContentDockWidget",
    "MMainWindow",
    "MToolBar",
    "MeasurementItem",
    "MeasurementTable",
    "MeasurementThread",
    "MeasurementUI",
    "MetaData",
    "MetaDataDialog",
    "Notifier",
    "NotifierMessage",
    "SaferQSettings",
    "SystemListWidget",
]


@dataclass(frozen=True)
class NotifierMessage:
    """A message for the Notifer class."""

    text: str
    level: int = logging.INFO


@final
class Notifier(QGroupBox):
    """
    An animated container titled "Notification" that shows a message with an icon.

    Parameters
    ----------
    logger : logging.Logger
        The logger to use for logging messages.
    """

    def __init__(self, logger: logging.Logger):
        """Initialize the notification widget."""
        super().__init__("Notification")
        self._logger = logger
        self.setMaximumHeight(0)
        self.setVisible(False)
        self._content = QHBoxLayout()
        self._content.setContentsMargins(0, 0, 0, 0)
        self._icon = QLabel()
        self._text = QLabel()
        self._close_button = QPushButton("✕")
        self._close_button.setFixedSize(20, 20)
        self._close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_button.clicked.connect(self.hide_animated)
        self._dismiss_timer = QTimer()
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.hide_animated)
        self._content.addWidget(self._icon)
        self._content.addWidget(self._text, 1)
        self._content.addWidget(self._close_button)
        self.setLayout(self._content)

    def show_message(self, message: NotifierMessage):
        """Show a message text and appropriate icon."""
        if message.level >= logging.ERROR:
            icon_name = "SP_MessageBoxCritical"
        elif message.level >= logging.WARNING:
            icon_name = "SP_MessageBoxWarning"
        else:
            icon_name = "SP_MessageBoxInformation"
        size = MApplication.instance().toolbar_icon_size()
        self._icon.setPixmap(get_matrix_icon(icon_name).pixmap(size, size))
        self._text.setText(message.text)
        self._logger.log(message.level, message.text)
        self._dismiss_timer.stop()
        if message.level < logging.WARNING:
            self._dismiss_timer.start(5000)
        self.show_animated()

    def show_animated(self):
        """Show the notification. Auto-dismiss for warnings and below."""
        self.setVisible(True)
        # Already visible — just update content, no need to re-animate
        if self.maximumHeight() > 0:
            return
        if hasattr(self, "anim") and self.anim.state() == QPropertyAnimation.State.Running:
            self.anim.stop()
        self.anim = QPropertyAnimation(self, b"maximumHeight")
        self.anim.setDuration(250)
        self.anim.setStartValue(0)
        self.anim.setEndValue(int(self.sizeHint().height()))
        self.anim.start()

    def hide_animated(self):
        """Hide the notification."""
        self.anim = QPropertyAnimation(self, b"maximumHeight")
        self.anim.setDuration(250)
        self.anim.setStartValue(self.maximumHeight())
        self.anim.setEndValue(0)
        self.anim.finished.connect(lambda: self.setVisible(False))
        self.anim.start()


@final
class _SystemReferenceEditor(QWidget):
    """Forward source-area mouse gestures to the owning system list."""

    def __init__(self, system_list: "SystemListWidget", parent: QWidget) -> None:
        super().__init__(parent)
        self._system_list = system_list

    def _forward_mouse_event(self, event: QMouseEvent) -> None:
        viewport = self._system_list.viewport()
        position = viewport.mapFromGlobal(event.globalPosition().toPoint())
        forwarded_event = QMouseEvent(
            event.type(),
            position,
            event.globalPosition(),
            event.button(),
            event.buttons(),
            event.modifiers(),
            event.pointingDevice(),
        )
        QApplication.sendEvent(viewport, forwarded_event)
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Forward selection and drag initialization."""
        self._forward_mouse_event(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Forward an active row drag."""
        self._forward_mouse_event(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Forward completion of selection or dragging."""
        self._forward_mouse_event(event)


@final
class _SystemStateSelector(QComboBox):
    """Select the owning system-list row when interacting with its state."""

    def __init__(
        self,
        system_list: "SystemListWidget",
        item: QListWidgetItem,
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self._system_list = system_list
        self._item = item

    def focusInEvent(self, event: QFocusEvent) -> None:
        """Keep keyboard focus and list selection synchronized."""
        self._system_list.setCurrentItem(self._item)
        super().focusInEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Select the row before opening the state menu."""
        self._system_list.setCurrentItem(self._item)
        super().mousePressEvent(event)


@final
class _SystemReferenceDelegate(QStyledItemDelegate):
    """Provide a persistent state combobox for stateful system rows."""

    def __init__(self, system_list: "SystemListWidget") -> None:
        super().__init__(system_list)
        self.system_list = system_list

    def createEditor(
        self,
        parent: QWidget,
        _option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> QWidget:
        """Create a source label followed by an always-visible state selector."""
        item = self.system_list.item(index.row())
        if not item.data(SystemListWidget.STATEFUL_ROLE):
            return QWidget(parent)

        editor = _SystemReferenceEditor(self.system_list, parent)
        editor.setObjectName("system_reference_editor")
        editor.setAutoFillBackground(True)
        layout = QHBoxLayout(editor)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(4)

        source_label = QLabel(f"{item.data(SystemListWidget.SOURCE_ROLE)}::", editor)
        source_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(source_label)

        state_selector = _SystemStateSelector(self.system_list, item, editor)
        state_selector.setObjectName("system_state")
        state_selector.setEditable(False)
        state_selector.setToolTip(str(item.data(SystemListWidget.SOURCE_ROLE)))
        state_selector.addItems(item.data(SystemListWidget.STATES_ROLE))
        state_selector.setCurrentText(str(item.data(SystemListWidget.STATE_ROLE)))
        state_selector.currentTextChanged.connect(
            lambda state, current=item: self.system_list._select_state(current, state)
        )
        layout.addWidget(state_selector)
        layout.addStretch()
        editor.setFocusProxy(state_selector)
        return editor

    def setEditorData(
        self,
        editor: QWidget,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Synchronize the persistent combobox with row data."""
        state_selector = editor.findChild(QComboBox, "system_state")
        if state_selector is None:
            return
        item = self.system_list.item(index.row())
        blocked = state_selector.blockSignals(True)
        state_selector.setCurrentText(str(item.data(SystemListWidget.STATE_ROLE)))
        state_selector.blockSignals(blocked)


@final
class SystemListWidget(QListWidget):
    """A custom QListWidget that contains the systems."""

    changed = Signal()
    message = Signal(NotifierMessage)

    SOURCE_ROLE = int(Qt.ItemDataRole.UserRole)
    STATE_ROLE = SOURCE_ROLE + 1
    STATEFUL_ROLE = SOURCE_ROLE + 2
    CLASS_ROLE = SOURCE_ROLE + 3
    STATES_ROLE = SOURCE_ROLE + 4
    GROUPS_ROLE = SOURCE_ROLE + 5

    def __init__(self, *, report_config_errors: bool = True) -> None:
        """Initialize the system list and its configuration-error policy."""
        super().__init__()
        self._report_config_errors = report_config_errors
        self._base_directory: Path = resolved_directory
        self.add_action = QAction(get_matrix_icon("CHAR_+"), "Add System", self)
        self.add_action.setToolTip("Add a matrix system file.")
        self.add_action.triggered.connect(self.query_systems)
        self.remove_action = QAction(get_matrix_icon("CHAR_-"), "Remove System", self)
        self.remove_action.setToolTip("Remove the selected or last matrix system file.")
        self.remove_action.triggered.connect(self.delete_systems)
        system_info = get_system_info([])
        if isinstance(system_info, Error):
            raise InternalInvariantError("System list should work for an empty list.")
        self._cached_system_info: SystemInfo = system_info.value
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.setItemDelegate(_SystemReferenceDelegate(self))
        self.itemSelectionChanged.connect(self._sync_selection_highlights)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setMinimumHeight(50)
        self.setMaximumHeight(50)
        self._sync_action_state()

    def setEnabled(self, enabled: bool) -> None:
        """Set enabled state and synchronize the list actions."""
        super().setEnabled(enabled)
        self._sync_action_state()

    def _sync_action_state(self) -> None:
        """Synchronize action state with widget state and list content."""
        enabled = self.isEnabled()
        self.add_action.setEnabled(enabled)
        self.remove_action.setEnabled(enabled and self.count() > 0)

    def add_to_toolbar(self, toolbar: Any) -> None:
        """Add system controls to a toolbar."""
        toolbar.addAction(self.add_action)
        toolbar.addWidget(self)
        toolbar.addAction(self.remove_action)

    def add_actions_to_menu(self, menu: QMenu) -> None:
        """Add system actions to a menu."""
        menu.addAction(self.add_action)
        menu.addAction(self.remove_action)

    @property
    def systems(self) -> list[str]:
        """Return compact static or named system tokens."""
        return [self.item(i).text() for i in range(self.count())]

    @property
    def references(self) -> list[SystemReference]:
        """Return validated structured system references."""
        return [SystemReference.from_value(system) for system in self.systems]

    def clear(self) -> None:
        """Clear the list of systems."""
        super().clear()
        self.systems_changed()

    def dropEvent(self, event: QDropEvent) -> None:
        """Emit a signal if the order changed."""
        before = self.systems
        super().dropEvent(event)
        if before != self.systems:
            self.systems_changed()

    def delete_systems(self) -> None:
        """Remove selected or last system in the list."""
        selected = self.selectedItems()
        if len(selected) > 0:
            self.takeItem(self.row(selected[0]))
            self.systems_changed()
        elif self.count() > 0:
            self.takeItem(self.count() - 1)
            self.systems_changed()
        else:
            self._sync_action_state()

    def add_systems(self, filenames: list[str]) -> None:
        """Add static systems once and stateful systems once per free group."""
        existing_sources = {self.item(i).data(self.SOURCE_ROLE) for i in range(self.count())}
        for filename in filenames:
            candidate_result = self._system_candidate(filename)
            if candidate_result is None:
                continue
            candidate, requested_reference, capability = candidate_result
            if not self._accept_static_candidate(
                candidate, requested_reference, capability, existing_sources
            ):
                continue
            state = self._state_for_candidate(candidate, requested_reference, capability)
            if capability.stateful and state is None:
                continue
            self._add_system_item(candidate, capability, state)
            self.systems_changed()
            existing_sources.add(candidate)
            self._base_directory = Path(requested_reference.source)

    def _system_candidate(
        self, filename: str
    ) -> tuple[str, SystemReference, SystemCapability] | None:
        """Normalize, import, and inspect one requested system source."""
        try:
            reference = SystemReference.from_value(filename)
        except ValidationError as error:
            self.message.emit(NotifierMessage(str(error), level=logging.WARNING))
            return None
        source = reference.source
        try:
            module = importlib.util.find_spec(source)
        except ModuleNotFoundError:
            module = None
        resolved = Path(source).resolve()
        candidate = str(
            module.name
            if module is not None
            else self.get_importable_module_name(resolved) or resolved
        )
        capability_result = self.test_import(candidate)
        if isinstance(capability_result, Error):
            self.message.emit(
                NotifierMessage(
                    f"{candidate} could not import and was omitted: {capability_result.error}",
                    level=logging.WARNING,
                )
            )
            return None
        return candidate, reference, capability_result.value

    def _accept_static_candidate(
        self,
        candidate: str,
        reference: SystemReference,
        capability: SystemCapability,
        existing_sources: set[Any],
    ) -> bool:
        """Reject duplicate or state-qualified static systems."""
        if capability.stateful:
            return True
        if reference.state is not None:
            self.message.emit(
                NotifierMessage(
                    f"{candidate} is static and does not accept a state.",
                    level=logging.WARNING,
                )
            )
            return False
        if candidate in existing_sources:
            self.message.emit(NotifierMessage(f"{candidate} is already present and was omitted."))
            return False
        if any(
            self.item(index).data(self.CLASS_ROLE) == capability.class_name
            for index in range(self.count())
        ):
            self.message.emit(
                NotifierMessage(
                    f"{candidate} was omitted: duplicate system class name "
                    f"'{capability.class_name}'.",
                    level=logging.WARNING,
                )
            )
            return False
        return True

    def _state_for_candidate(
        self,
        candidate: str,
        reference: SystemReference,
        capability: SystemCapability,
    ) -> str | None:
        """Return the allowed selected state, reporting validation failures."""
        if not capability.stateful:
            return None
        state = reference.state or self._first_state_in_free_group(candidate, capability)
        if state is None:
            self.message.emit(
                NotifierMessage(f"{candidate} already uses every available state group.")
            )
        elif state not in capability.states:
            self.message.emit(
                NotifierMessage(
                    f"{candidate} does not define state {state!r}.", level=logging.WARNING
                )
            )
        elif self._group_is_used(candidate, capability.state_exclusion_groups[state]):
            self.message.emit(
                NotifierMessage(
                    f"{candidate} state {state!r} conflicts with an already selected state.",
                    level=logging.WARNING,
                )
            )
        else:
            return state
        return None

    def _add_system_item(
        self, candidate: str, capability: SystemCapability, state: str | None
    ) -> None:
        """Create and insert one fully described system-list item."""
        item = QListWidgetItem()
        item.setData(self.SOURCE_ROLE, candidate)
        item.setData(self.STATE_ROLE, state)
        item.setData(self.STATEFUL_ROLE, capability.stateful)
        item.setData(self.CLASS_ROLE, capability.class_name)
        item.setData(self.STATES_ROLE, capability.states)
        item.setData(self.GROUPS_ROLE, capability.state_exclusion_groups)
        self._update_item_token(item)
        if capability.stateful:
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        super().addItem(item)
        if capability.stateful:
            self.openPersistentEditor(item)
            self._sync_selection_highlights()

    def _group_is_used(
        self,
        source: str,
        group: str,
        *,
        except_item: QListWidgetItem | None = None,
    ) -> bool:
        """Return whether another row for the source occupies an exclusion group."""
        for index in range(self.count()):
            item = self.item(index)
            if item is except_item or item.data(self.SOURCE_ROLE) != source:
                continue
            state = item.data(self.STATE_ROLE)
            groups = item.data(self.GROUPS_ROLE) or {}
            if state is not None and groups.get(state) == group:
                return True
        return False

    def _first_state_in_free_group(
        self,
        source: str,
        capability: SystemCapability,
    ) -> str | None:
        """Return the first state whose exclusion group is not occupied."""
        for state in capability.states:
            group = capability.state_exclusion_groups[state]
            if not self._group_is_used(source, group):
                return state
        return None

    def _update_item_token(self, item: QListWidgetItem) -> None:
        """Synchronize the item's serialized token with its row data."""
        source = str(item.data(self.SOURCE_ROLE))
        state = item.data(self.STATE_ROLE)
        item.setText(
            SystemReference(
                source=source,
                state=state if item.data(self.STATEFUL_ROLE) else None,
            ).to_token()
        )

    def _sync_state_editor(self, item: QListWidgetItem) -> None:
        """Update one persistent combobox after an atomic state assignment."""
        editor = self.indexWidget(self.indexFromItem(item))
        if editor is None:
            return
        state_selector = editor.findChild(QComboBox, "system_state")
        if state_selector is None:
            return
        blocked = state_selector.blockSignals(True)
        state_selector.setCurrentText(str(item.data(self.STATE_ROLE)))
        state_selector.blockSignals(blocked)

    def _sync_selection_highlights(self) -> None:
        """Show list selection behind persistent state editors."""
        list_palette = self.palette()
        for index in range(self.count()):
            item = self.item(index)
            editor = self.indexWidget(self.indexFromItem(item))
            if editor is None:
                continue
            selected = item.isSelected()
            editor_palette = editor.palette()
            background = list_palette.color(
                QPalette.ColorRole.Highlight if selected else QPalette.ColorRole.Base
            )
            foreground = list_palette.color(
                QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
            )
            editor_palette.setColor(QPalette.ColorRole.Base, background)
            editor_palette.setColor(QPalette.ColorRole.Window, background)
            editor_palette.setColor(QPalette.ColorRole.Text, foreground)
            editor_palette.setColor(QPalette.ColorRole.WindowText, foreground)
            editor.setPalette(editor_palette)
            source_label = editor.findChild(QLabel)
            if source_label is not None:
                source_label.setPalette(editor_palette)

    def _select_state(self, item: QListWidgetItem, state: str) -> None:
        """Assign a state and atomically swap with a conflicting row."""
        previous_state = item.data(self.STATE_ROLE)
        if state == previous_state:
            return

        groups = item.data(self.GROUPS_ROLE)
        source = item.data(self.SOURCE_ROLE)
        target_group = groups[state]
        conflicting_item = None
        for index in range(self.count()):
            candidate = self.item(index)
            if candidate is item or candidate.data(self.SOURCE_ROLE) != source:
                continue
            candidate_state = candidate.data(self.STATE_ROLE)
            candidate_groups = candidate.data(self.GROUPS_ROLE)
            if candidate_groups[candidate_state] == target_group:
                conflicting_item = candidate
                break

        item.setData(self.STATE_ROLE, state)
        self._update_item_token(item)
        if conflicting_item is not None:
            conflicting_item.setData(self.STATE_ROLE, previous_state)
            self._update_item_token(conflicting_item)
            self._sync_state_editor(conflicting_item)
        self.systems_changed()

    def systems_changed(self) -> None:
        """Load system info and emit changed signal."""
        system_info = get_system_info(self.systems)
        if isinstance(system_info, Error):
            raise InternalInvariantError("System list should work if systems work individually.")
        if self._report_config_errors and system_info.value.config_validation_errors:
            warning_text = (
                "System configuration validation failed. Default values are shown only so "
                "you can correct the configuration; fix these entries before execution:\n\n"
                + "".join(system_info.value.config_validation_errors)
            )
            # This is actionable in the config editor and should remain in the
            # log without automatically opening the separate log window.
            self.message.emit(NotifierMessage(warning_text, level=logging.WARNING))
        for warning in system_info.value.warnings:
            self.message.emit(NotifierMessage(warning[0], warning[1]))
        self._cached_system_info = system_info.value
        self._sync_action_state()
        self.changed.emit()

    @property
    def system_info(self) -> SystemInfo:
        """Return the (cached) system info."""
        return self._cached_system_info

    def test_import(self, filename: str) -> Result[SystemCapability, str]:
        """Inspect whether a source imports and which states it exposes."""
        return get_system_capability(filename)

    def query_systems(self) -> None:
        """Select and add system files(s)."""
        filenames = QFileDialog.getOpenFileNames(
            self,
            "Select system file(s) to add",
            str(self._base_directory),
            "system files (system*.py)",
        )[0]
        if filenames != []:
            self.add_systems(filenames)

    @staticmethod
    def get_importable_module_name(filename_str: str | Path) -> str | None:
        """
        Return the module name for a package, else None.

        It returns the deepest matching entry.
        """
        path = Path(filename_str).resolve()
        if path.is_file() and path.suffix == ".py":
            module_path = path.with_suffix("")
        elif path.is_dir() and (path / "__init__.py").is_file():
            module_path = path
        else:
            return None
        matches = []
        for base in map(Path, sys.path):
            try:
                rel = module_path.relative_to(base.resolve())
                matches.append((len(base.parts), rel))
            except ValueError:
                pass
        if not matches:
            return None
        _, relative = max(matches, key=lambda x: x[0])
        module_name = ".".join(relative.parts)
        return module_name if importlib.util.find_spec(module_name) else None


@final
class MetaData(TypedDict):
    """Typed dictionary for metadata values."""

    creator: str
    identifier: str
    relation: str
    description: str


@final
@final
class ContentDockWidget(QDockWidget):
    """
    A dock widget with a checkable action to toggle its content.

    The dock provides an action with icon and shortcut for the
    view menu and may be restricted to certain dock areas.

    Parameters
    ----------
    title : str
        The window title and action text.
    object_name : str
        The object name used to persist the dock state.
    icon : str
        The name of the action icon as in get_matrix_icon.
    shortcut : str
        The keyboard shortcut of the action.
    widget : QWidget
        The content widget of the dock.
    areas : Qt.DockWidgetArea, optional
        The dock areas the dock may be moved to. The default is the
        right dock area only.
    """

    def __init__(
        self,
        title: str,
        object_name: str,
        icon: str,
        shortcut: str,
        widget: QWidget,
        areas: Qt.DockWidgetArea = Qt.DockWidgetArea.RightDockWidgetArea,
    ) -> None:
        """Initialize the dock with its content and view action."""
        super().__init__(title)
        self.setObjectName(object_name)
        self.setAllowedAreas(areas)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.setWidget(widget)
        self.action = QAction(get_matrix_icon(icon), title, self)
        self.action.setShortcut(QKeySequence(shortcut))
        self.action.setCheckable(True)
        self.action.setChecked(True)
        self.action.triggered.connect(self.toggle_view)
        self.visibilityChanged.connect(self._sync_view)

    def toggle_view(self, checked: bool) -> None:
        """Toggle the visibility of the dock content."""
        self.setVisible(checked)

    def _sync_view(self) -> None:
        """Match view action state to the restored widget visibility."""
        with blocked_signals(self.action):
            self.action.setChecked(not self.isHidden())


@final
class MeasurementTable(ReadOnlyTable):
    """
    A table showing the current set and readout values of a measurement.

    The table is updated from Header, SetValues and MeasuredValues
    payloads reported by the measurement thread.
    """

    def __init__(self) -> None:
        """Initialize the table with the standard measurement columns."""
        super().__init__()
        self.setColumnCount(4)
        self.setRowCount(1)
        self.setHorizontalHeaderLabels(["Parameter", "Set value", "Readout value", "unit"])
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def _set_value(self, row: int, column: int, value: Any) -> None:
        """Set a centered cell value, using an empty string for None."""
        if value is not None:
            item = QTableWidgetItem(str(value))
        else:
            item = QTableWidgetItem("")
        item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        self.setItem(row, column, item)

    def apply(self, data: Header | SetValues | MeasuredValues) -> None:
        """
        Update the table from a measurement data payload.

        Parameters
        ----------
        data : Header | SetValues | MeasuredValues
            The table data received from the measurement thread.
        """
        if isinstance(data, Header):
            self.apply_header(data)
        elif isinstance(data, SetValues):
            self.apply_set_values(data)
        else:
            self.apply_measured_values(data)

    def apply_header(self, header: Header) -> None:
        """Set the parameter names and units from a header payload."""
        count = len(header.columns)
        self.setRowCount(count)
        for index, item in enumerate(header.columns):
            column = QTableWidgetItem(str(item))
            unit = QTableWidgetItem(str(header.units[index]))
            column.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            unit.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            self.setItem(index, 0, column)
            self.setItem(index, 3, unit)

    def apply_set_values(self, values: SetValues) -> None:
        """Set the set values from a payload."""
        for index, item in enumerate(values.set_values):
            self._set_value(index, 1, item)

    def apply_measured_values(self, values: MeasuredValues) -> None:
        """Set the readout values, converting a trailing timestamp."""
        for index, item in enumerate(values.measured_values):
            self._set_value(index, 2, item)
        last_index = len(values.measured_values) - 1
        last_value = values.measured_values[last_index] if last_index >= 0 else None
        if last_value is None:
            return
        try:
            utc = QDateTime.fromSecsSinceEpoch(int(last_value), QTimeZone.utc())
            local = utc.toLocalTime()
            value = QTableWidgetItem(local.toString("HH:mm:ss"))
            value.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
            value.setToolTip("Converted to local time.")
            self.setItem(last_index, 2, value)
        except Exception:
            logger.debug("Could not convert timestamp to local time.")

    def reset(self) -> None:
        """Reset the table to a single empty row."""
        self.setRowCount(1)
        for i in range(self.columnCount()):
            self.setItem(0, i, QTableWidgetItem(""))


@final
class MetaDataDialog(QDialog):
    """Create a dialog able to handle meta data input for file headers."""

    def __init__(self, popup: bool = False) -> None:
        """Initialize the meta data dialog."""
        super().__init__()
        self.setWindowTitle("Dublin Core Metadata Input")
        self.creator: QLineEdit = QLineEdit()
        self.identifier: QLineEdit = QLineEdit()
        self.relation: QLineEdit = QLineEdit()
        self.description: QTextEdit = QTextEdit()
        form_layout = QFormLayout()
        form_layout.addRow("Creator/User:", self.creator)
        form_layout.addRow("Identifier/Sample:", self.identifier)
        form_layout.addRow("Relation:", self.relation)
        layout = QVBoxLayout()
        layout.addLayout(form_layout)
        layout.addWidget(QLabel("Description:"))
        layout.addWidget(self.description)
        if popup:
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            layout.addWidget(buttons)
        self.setLayout(layout)

    @property
    def metadata(self) -> MetaData:
        """Get the metadata entered in the dialog."""
        return {
            "creator": self.creator.text(),
            "identifier": self.identifier.text(),
            "relation": self.relation.text(),
            "description": self.description.toPlainText(),
        }

    def set_metadata(self, metadata: dict) -> None:
        """Set the metadata fields from a dictionary."""
        self.creator.setText(metadata.get("creator", ""))
        self.identifier.setText(metadata.get("identifier", ""))
        self.relation.setText(metadata.get("relation", ""))
        self.description.setPlainText(metadata.get("description", ""))

    def clear(self) -> None:
        """Clear all input fields."""
        self.creator.clear()
        self.identifier.clear()
        self.relation.clear()
        self.description.clear()


@final
@dataclass
class MeasurementItem:
    """The parameters of an item of the measurement queue."""

    input_file: str
    output_file: str
    metadata: dict
    config: dict
    systems: list[str]
    kind: Literal["script", "sweep"]
    system_info: SystemInfo | None = None

    @property
    def list_entry(self) -> str:
        """Return a human-readable representation of the list entry."""
        output = Path(self.output_file).name if self.output_file else "<use input>"
        return f"Input: {Path(self.input_file).name} - Output: {output}"

    @staticmethod
    def remove_nones(d: dict) -> dict:
        """Remove None values from a dictionary."""
        if isinstance(d, dict):
            return {k: MeasurementItem.remove_nones(v) for k, v in d.items() if v is not None}
        return d

    @property
    def tooltip(self) -> str:
        """Return a tooltip with all data."""
        input_file = f"Input:\n{self.input_file}\n\n"
        output_file = f"Output:\n{self.output_file or '<use input>'}\n\n"
        metadata = f"Metadata:\n{tomli_w.dumps(self.remove_nones(self.metadata))}"
        normalized_config = self.remove_nones(self.config)
        config = f"\nConfig:\n{tomli_w.dumps(normalized_config)}" if normalized_config else ""
        return input_file + output_file + metadata + config


@final
class MToolBar(QToolBar):
    """Standard toolbar with custom properties."""

    def __init__(self, title: str | None = None) -> None:
        super().__init__(title)
        self.setObjectName("main_toolbar")
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setFloatable(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea | Qt.ToolBarArea.BottomToolBarArea)
        self.icon_size = MApplication.instance().toolbar_icon_size()
        self.setIconSize(QSize(self.icon_size, self.icon_size))
        self.action = QAction("Show Toolbar", self)
        self.action.setShortcut(QKeySequence("Ctrl+1"))
        self.action.setCheckable(True)
        self.action.setChecked(True)
        self.action.triggered.connect(self.toggle_toolbar_view)
        self.visibilityChanged.connect(self.action.setChecked)

    @property
    def empty(self) -> QWidget:
        """Return an empty widget with fixed icon size."""
        empty = QWidget()
        empty.setFixedWidth(self.icon_size)
        return empty

    @property
    def spacer(self) -> QWidget:
        """Return a spacer widget that expands horizontally."""
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        return spacer

    def toggle_toolbar_view(self, checked: bool) -> None:
        """Toggle the visibility of the toolbar."""
        self.setVisible(checked)


class MMainWindow(QMainWindow):
    """Main window with shared metadata and config dock layout handling."""

    layout_settings_group = "MainWindowLayoutV3"

    def install_metadata_config_docks(self, metadata: QDockWidget, config: QDockWidget) -> None:
        """Install metadata and device config docks."""
        self.setDockOptions(
            self.dockOptions()
            | QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, metadata)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, config)
        self.splitDockWidget(metadata, config, Qt.Orientation.Vertical)
        config.hide()

    def save_layout_state(self, settings: SaferQSettings) -> None:
        """
        Save the Qt main-window layout state.

        Parameters
        ----------
        settings : SaferQSettings
            The application settings object.
        """
        settings.beginGroup(self.layout_settings_group)
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("window_state", self.saveState())
        settings.endGroup()

    def restore_layout_state(self, settings: SaferQSettings) -> None:
        """
        Restore the Qt main-window layout state.

        Parameters
        ----------
        settings : SaferQSettings
            The application settings object.
        """
        self.resize(self.sizeHint())  # Just in case it is the first start.
        settings.beginGroup(self.layout_settings_group)
        self.restoreGeometry(settings.safer_value("geometry", QByteArray(), type=QByteArray))
        self.restoreState(settings.safer_value("window_state", QByteArray(), type=QByteArray))
        settings.endGroup()


@final
class MeasurementThread(QThread, LoggerMixin):
    """
    Execute and control a measurement subprocess via a TCP socket.

    It can run a script as well as a sweep.
    """

    data_received = Signal(Envelope)

    def __init__(self) -> None:
        """Initialize the measurement thread."""
        super().__init__()
        self.proc: subprocess.Popen[bytes] | None = None
        self.conn: socket.socket | None = None

    def set_parameters(self, parameters: MeasurementItem) -> None:
        """Set measurement parameters."""
        self.parameters = parameters

    def pass_input(self, inp: str) -> None:
        """
        Communicate user input to the subprocess.

        Parameters
        ----------
        inp : str
            The input to be communicated.
        """
        if self.proc is None or self.conn is None:
            return
        if len(inp) < 1 or inp[-1] != "\n":
            inp += "\n"
        self.conn.send(("i" + inp).encode("utf-8"))

    def pause(self) -> None:
        """Communicate pause to the subprocess."""
        if self.proc is None or self.conn is None:
            return
        self.conn.send(b"p")

    def abort(self, char: str = "a") -> None:
        """
        Communicate stop to the subprocess.

        Parameters
        ----------
        char : str
            ``a`` sets state to aborted,
            ``f`` sets state to finished.
        """
        if self.proc is None or self.conn is None:
            return
        self.conn.send(char.encode())

    def finish(self) -> None:
        """Signal the subprocess to finish early."""
        self.abort(char="f")

    def kill(self) -> None:
        """Kill the process."""
        if self.proc is None:
            return
        self.proc.kill()
        self.logger.warning("Measurement thread was manually killed.")

    def process_received_data(self, inp: str) -> None:
        """Process a null-terminated JSON message from the subprocess."""
        try:
            env = Envelope.model_validate_json(inp)
        except ValidationError:
            if inp.strip():
                self.logger.error("Unknown data received: %s", inp)
            return
        self.data_received.emit(env)

    def relay_subprocess_output(self, stream: BinaryIO, is_error: bool) -> None:
        """
        Relay stdout or stderr of the subprocess to the logger.

        Parameters
        ----------
        stream : BinaryIO
            The stream to read from.
        is_error : bool
            True for stderr, False for stdout.
        """
        for line in iter(stream.readline, b""):
            if is_error:
                self.logger.warning(line.decode().strip())
            else:
                self.logger.info(line.decode().strip())

    def _generate_processfile(
        self, port: int, script_tempfile: "IO[bytes] | None", temp_config_file: Path
    ) -> list[str]:
        """
        Generate the subprocess command.

        Parameters
        ----------
        port : int
            The local TCP port the GUI is listening on.
        script_tempfile : IO[bytes] or None
            Open temporary file containing the user script.  Must be provided
            when ``parameters.kind == "script"``; ``None`` for sweep mode.
        temp_config_file : Path
            Path to the temporary TOML config file.

        Returns
        -------
        list[str]
            The command to pass to ``subprocess.Popen``.
        """
        if self.parameters.kind == "script":
            if script_tempfile is None:
                raise InternalInvariantError("script_tempfile must be provided for script mode")
            cmd = (
                f"import matr1x\n"
                f"import matr1x.util as mu\n"
                f"matr1x.reload_config({str(temp_config_file)!r})\n"
                f"mu.matrix_script_process({script_tempfile.name!r}, "
                f"{self.parameters.metadata!r}, "
                f"{self.parameters.output_file!r}, {port!r}, "
                f"{self.parameters.systems!r})"
            )
            return [sys.executable, "-c", cmd]
        result = [
            get_matrix_binary(),
            "-i",
            self.parameters.input_file,
            "-p",
            "--port",
            str(port),
        ]
        if self.parameters.output_file:
            result += ["-o", self.parameters.output_file]
        for key, val in self.parameters.metadata.items():
            if key in VALID_META_KEYS and val and VALID_META_KEYS[key]:
                result += [f"--dc_{key.lower()}", val]
        result += ["--optional-config", str(temp_config_file)]
        return result

    def run(self) -> None:
        """
        Run the subprocess.

        Opens a server socket, spawns the subprocess, accepts the
        incoming connection, then relays null-terminated JSON messages
        to ``process_received_data`` until the process exits.
        """
        tmp_config_file = ConfigEditWidget.write_config_dict(self.parameters.config)
        try:
            with ExitStack() as stack:
                tmp_scriptfile: IO[bytes] | None = None
                if self.parameters.kind == "script":
                    tmp_scriptfile = stack.enter_context(tempfile.NamedTemporaryFile(mode="w+b"))
                    tmp_scriptfile.write(self.parameters.input_file.encode())
                    tmp_scriptfile.flush()

                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
                s.listen(1)
                cmd = self._generate_processfile(port, tmp_scriptfile, tmp_config_file)
                self.proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0,
                )
                self.conn, _ = s.accept()
                s.close()
                threading.Thread(
                    target=self.relay_subprocess_output,
                    args=(self.proc.stdout, False),
                    daemon=True,
                ).start()
                threading.Thread(
                    target=self.relay_subprocess_output, args=(self.proc.stderr, True), daemon=True
                ).start()
                buffer = ""
                while self.proc.poll() is None:
                    try:
                        chunk = self.conn.recv(8192)
                        if not chunk:
                            break
                        buffer += chunk.decode()
                        while "\0" in buffer:
                            msg, buffer = buffer.split("\0", 1)
                            if msg:
                                self.process_received_data(msg)
                    except OSError:
                        self.process_received_data("OS error in thread communication.\n")
                        break
                self.conn.close()
        finally:
            if tmp_config_file.exists():
                tmp_config_file.unlink()


@final
class MeasurementUI(QWidget):
    """
    Provide the required UI elements for the measurement thread.

    The required thread safety does not allow to have the UI elements
    in another thread.
    """

    def __init__(self):
        super().__init__()
        self.start = QAction(get_matrix_icon("CUSTOM_Play"), "Start")
        self.start.setToolTip("Start the measurement.")
        self.start.setEnabled(False)
        self.pause = QAction(get_matrix_icon("CUSTOM_Pause"), "Pause")
        self.pause.setToolTip("Pause the measurement.")
        self.pause.setCheckable(True)
        self.pause.setChecked(False)
        self.pause.setEnabled(False)
        self.abort = QAction(get_matrix_icon("CUSTOM_Stop", color=QColor("#B71C1C")), "Abort")
        self.abort.setToolTip("Stop the measurement and mark as aborted.")
        self.abort.setEnabled(False)
        self.finish = QAction(get_matrix_icon("CUSTOM_Stop", color=QColor("#388E3C")), "Finish")
        self.finish.setToolTip("Stop the measurement and mark as finished.")
        self.finish.setEnabled(False)
        self.kill = QAction(get_matrix_icon("SP_DialogCancelButton"), "Kill")
        self.kill.setToolTip("Kill the measurement thread.")
        self.kill.setEnabled(False)

    def connect_to_thread(self, thread: MeasurementThread) -> None:
        """Connect the UI actions to the measurement thread."""
        self.pause.triggered.connect(thread.pause)
        self.abort.triggered.connect(lambda checked: thread.abort())
        self.finish.triggered.connect(thread.finish)
        self.kill.triggered.connect(thread.kill)

    def add_to_toolbar(self, toolbar: QToolBar) -> None:
        """Add the UI actions to the toolbar."""
        toolbar.addAction(self.start)
        toolbar.addAction(self.pause)
        toolbar.addAction(self.abort)
        toolbar.addAction(self.finish)

    def add_to_menu(self, menu: QMenu) -> None:
        """Add the UI actions to the menu."""
        menu.addAction(self.start)
        menu.addAction(self.pause)
        menu.addAction(self.abort)
        menu.addAction(self.finish)
        menu.addAction(self.kill)


def _format_validation_error(e: ValidationError | TypeError | ValueError, base: str = "") -> str:
    """
    Format the error output of the toml validation in html.

    Parameters
    ----------
    e: ValidationError or TypeError or ValueError
        The errors with all information.
    base: str
        The prefix of the error location, e.g., 'ifwlib'.

    Returns
    -------
    str
        The html with the human readable errors.
    """
    html = ""
    if isinstance(e, ValidationError):
        for err in e.errors():
            location = base + ".".join(str(i) for i in err["loc"])
            msg = err["msg"].replace(">", "&gt;").replace("<", "&lt;")
            html += f"{location}: {msg}"
            if "url" in err:
                url = err["url"]
                html += f' (<a href="{url}">More info</a>)'
            html += "<br><br>"
    else:
        # Handle TypeError and ValueError which don't have errors() method
        msg = str(e).replace(">", "&gt;").replace("<", "&lt;")
        html += f"{base}: {msg}<br><br>"
    return html


def check_config(config: BaseModel, notifier: Notifier) -> None:
    """
    Validate the configuration tomls.

    Parameters
    ----------
    config: BaseModel
        The configuration model to validate.
    notifier: Notifier
        The notification widget to display the validation errors in.
    """
    html = "".join(validation_errors).replace("\n", "<br>")
    try:
        MainConfig.model_validate(config)
    except (ValidationError, TypeError, ValueError) as e:
        html += _format_validation_error(e)
    if html != "":
        html = (
            f"Please check your configuration file ({Path.home() / '.matr1x.toml'})! "
            "Some settings will not work as intended. "
            "The following error(s) occured:<br><br>"
        ) + html
        notifier.show_message(NotifierMessage(html, level=logging.WARNING))
