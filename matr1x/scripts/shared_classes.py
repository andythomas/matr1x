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

import contextlib
import importlib.util
import logging
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict, final, overload

from PySide6.QtCore import (
    QByteArray,
    QObject,
    QPoint,
    QPropertyAnimation,
    QSettings,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from matr1x import resolved_directory
from matr1x.error_handling import Error, InternalInvariantError, Success
from matr1x.gui_util import (
    ConfigEditWidget,
    MApplication,
    get_matrix_icon,
    get_system_info,
)
from matr1x.models import SystemInfo

__all__ = [
    "MetaData",
    "MetaDataDialog",
    "MetadataConfigDockMainWindow",
    "MetadataDockWidget",
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
class Notifier(QWidget):
    """
    An animated layout that shows a message with an icon.

    Parameters
    ----------
    logger : logging.Logger
        The logger to use for logging messages.
    """

    def __init__(self, logger: logging.Logger):
        """Initialize the notification widget."""
        super().__init__()
        self._logger = logger
        self.setMaximumHeight(0)
        self.setVisible(False)
        self._content = QHBoxLayout()
        self._content.setContentsMargins(0, 0, 0, 0)
        self._icon = QLabel()
        self._text = QLabel()
        self._content.addWidget(self._icon)
        self._content.addWidget(self._text)
        self._content.addStretch()
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
        self.show_animated()

    def show_animated(self):
        """Show the notification and hide after 3s."""
        self.setVisible(True)
        self.anim = QPropertyAnimation(self, b"maximumHeight")
        self.anim.setDuration(250)
        self.anim.setStartValue(0)
        self.anim.setEndValue(int(self.sizeHint().height()))
        self.anim.start()
        QTimer.singleShot(3000, self.hide_animated)

    def hide_animated(self):
        """Hide the notification."""
        self.anim = QPropertyAnimation(self, b"maximumHeight")
        self.anim.setDuration(250)
        self.anim.setStartValue(self.maximumHeight())
        self.anim.setEndValue(0)
        self.anim.finished.connect(lambda: self.setVisible(False))
        self.anim.start()


@final
class SystemListWidget(QListWidget):
    """A custom QListWidget that contains the systems."""

    changed = Signal()
    message = Signal(NotifierMessage)

    def __init__(self) -> None:
        """Initialize the class with sorting enabled."""
        super().__init__()
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
        """Return the list of systems."""
        return [self.item(i).text() for i in range(self.count())]

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
        """Add files but avoid duplicates."""
        added = False
        existing = {self.item(i).text() for i in range(self.count())}
        for filename in filenames:
            try:
                module = importlib.util.find_spec(filename)
            except ModuleNotFoundError:
                module = None
            if module is None:
                filename = Path(filename).resolve()
                module_name = self.get_importable_module_name(filename)
            else:
                module_name = module.name
            candidate = str(module_name if module_name is not None else filename)
            if candidate in existing:
                msg = NotifierMessage(f"{candidate} is already present and was omitted.")
                self.message.emit(msg)
                continue
            if not self.test_import(candidate):
                msg = NotifierMessage(
                    f"{candidate} could not import and was omitted.", level=logging.ERROR
                )
                self.message.emit(msg)
                continue
            super().addItem(candidate)
            added = True
            existing.add(candidate)
            self._base_directory = Path(filename)
        if added:
            self.systems_changed()
        else:
            self._sync_action_state()

    def clear(self) -> None:
        """Clear the list and synchronize action state."""
        super().clear()
        self._sync_action_state()

    def systems_changed(self) -> None:
        """Load system info and emit changed signal."""
        system_info = get_system_info(self.systems)
        if isinstance(system_info, Error):
            raise InternalInvariantError("System list should work if systems work individually.")
        if system_info.value.warnings:
            for warning in system_info.value.warnings:
                self.message.emit(NotifierMessage(warning, level=logging.WARNING))
        self._cached_system_info = system_info.value
        self._sync_action_state()
        self.changed.emit()

    @property
    def system_info(self) -> SystemInfo:
        """Return the (cached) system info."""
        return self._cached_system_info

    @staticmethod
    def test_import(filename: str) -> bool:
        """Test if a filename can be imported."""
        ret = get_system_info([filename])
        return True if isinstance(ret, Success) else False

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
class MetadataDockWidget(QDockWidget):
    """Dock widget for metadata editing."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the metadata dock widget."""
        super().__init__("Metadata", parent=parent)
        self.setObjectName("dockable_metadata")
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.meta_view = MetaDataDialog()
        self.setWidget(self.meta_view)


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
class SaferQSettings(QSettings):
    """Require default value and type hint for settings restore."""

    @overload
    def safer_value(self, key: str, defaultValue: QPoint, type: type[QPoint]) -> QPoint: ...
    @overload
    def safer_value(self, key: str, defaultValue: QSize, type: type[QSize]) -> QSize: ...
    @overload
    def safer_value(
        self, key: str, defaultValue: QByteArray, type: type[QByteArray]
    ) -> QByteArray: ...
    @overload
    def safer_value(self, key: str, defaultValue: bool, type: type[bool]) -> bool: ...
    @overload
    def safer_value(self, key: str, defaultValue: int, type: type[int]) -> int: ...
    @overload
    def safer_value(self, key: str, defaultValue: list, type: type[list]) -> list: ...
    @overload
    def safer_value(self, key: str, defaultValue: float, type: type[float]) -> float: ...
    @overload
    def safer_value(self, key: str, defaultValue: str, *, type: type[str]) -> str: ...

    def safer_value(self, key: str, defaultValue: Any, type: object):  # noqa: A002
        """Call the original QSettings value method."""
        return super().value(key, defaultValue, type)


@contextlib.contextmanager
def _blocked_signals(*objects: QObject) -> Iterator[None]:
    """Temporarily block signals for Qt objects."""
    blocked_objects = [(obj, obj.blockSignals(True)) for obj in objects]
    try:
        yield
    finally:
        for obj, previous_state in blocked_objects:
            obj.blockSignals(previous_state)


class MetadataConfigDockMainWindow(QMainWindow):
    """Main window with shared metadata and config dock layout handling."""

    ui: Any
    layout_settings_group = "MainWindowLayoutV2"

    @staticmethod
    def create_config_editor() -> ConfigEditWidget:
        """Create the common device config editor dock."""
        return ConfigEditWidget()

    @staticmethod
    def create_device_config_action() -> QAction:
        """Create the common device config action."""
        action = QAction(get_matrix_icon("CHAR_≡"), "Device config")
        action.setToolTip("Show the devices preferences/ configuration.")
        action.setShortcut(QKeySequence("Ctrl+3"))
        action.setCheckable(True)
        return action

    @staticmethod
    def create_metadata_action() -> QAction:
        """Create the common metadata visibility action."""
        action = QAction(get_matrix_icon("SP_FileDialogListView"), "Metadata")
        action.setShortcut(QKeySequence("Ctrl+2"))
        action.setCheckable(True)
        action.setChecked(True)
        return action

    def install_metadata_config_docks(self) -> None:
        """Install metadata and device config docks."""
        metadata_dock = self.ui.widgets.dockable_metadata
        config_dock = self.ui.widgets.config_editor
        self.setDockOptions(
            self.dockOptions()
            | QMainWindow.DockOption.AllowNestedDocks
            | QMainWindow.DockOption.AllowTabbedDocks
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, metadata_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, config_dock)
        self.splitDockWidget(metadata_dock, config_dock, Qt.Orientation.Vertical)
        config_dock.hide()

    def connect_layout_actions(self) -> None:
        """Connect the shared layout actions and visibility changes."""
        self.ui.actions.config.toggled.connect(self.toggle_preferences)
        self.ui.actions.toggle_metadata.triggered.connect(self.toggle_metadata_view)
        self.ui.actions.toggle_toolbar.triggered.connect(self.toggle_toolbar_view)
        self.ui.widgets.config_editor.visibilityChanged.connect(self._sync_layout_actions)
        self.ui.widgets.dockable_metadata.visibilityChanged.connect(self._sync_layout_actions)
        self.ui.toolbar.visibilityChanged.connect(self._sync_layout_actions)

    def layout_action_mappings(self) -> list[tuple[QAction, QWidget]]:
        """
        Return action and widget pairs synchronized with layout visibility.

        Returns
        -------
        list of tuple of QAction and QWidget
            Actions paired with the widgets whose visibility they control.
        """
        return [
            (self.ui.actions.config, self.ui.widgets.config_editor),
            (self.ui.actions.toggle_metadata, self.ui.widgets.dockable_metadata),
            (self.ui.actions.toggle_toolbar, self.ui.toolbar),
        ]

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
        self._save_additional_layout_state(settings)
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
        actions = [action for action, _widget in self.layout_action_mappings()]
        with _blocked_signals(*actions):
            self.restoreState(settings.safer_value("window_state", QByteArray(), type=QByteArray))
        self._restore_additional_layout_state(settings)
        settings.endGroup()
        self._sync_layout_actions()

    def toggle_toolbar_view(self, checked: bool) -> None:
        """
        Toggle the visibility of the toolbar.

        Parameters
        ----------
        checked: bool
            Show (True) or hide (False) the toolbar.
        """
        if checked:
            self.ui.toolbar.show()
        else:
            self.ui.toolbar.hide()

    def toggle_metadata_view(self, checked: bool) -> None:
        """
        Toggle the visibility of the metadata.

        Parameters
        ----------
        checked: bool
            Show (True) or hide (False) the metadata.
        """
        metadata = self.ui.widgets.dockable_metadata
        if checked:
            metadata.show()
        else:
            metadata.hide()

    def toggle_preferences(self, checked: bool) -> None:
        """
        Toggle the preferences pane.

        Parameters
        ----------
        checked: bool
            Show (True) or hide (False) the preferences.
        """
        config_editor = self.ui.widgets.config_editor
        if checked:
            config_editor.show()
            config_editor.raise_()
            config_editor.activateWindow()
        else:
            config_editor.hide()

    def _sync_layout_actions(self) -> None:
        """Match view action state to the restored widget visibility."""
        for action, widget in self.layout_action_mappings():
            with _blocked_signals(action):
                action.setChecked(not widget.isHidden())

    def _save_additional_layout_state(self, settings: SaferQSettings) -> None:
        """
        Save application-specific layout state.

        Parameters
        ----------
        settings : SaferQSettings
            The application settings object opened in the layout group.
        """

    def _restore_additional_layout_state(self, settings: SaferQSettings) -> None:
        """
        Restore application-specific layout state.

        Parameters
        ----------
        settings : SaferQSettings
            The application settings object opened in the layout group.
        """
