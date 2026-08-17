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
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, BinaryIO, Literal, TypedDict, final, overload

import tomli_w
from pydantic import ValidationError
from pyqtgraph.Qt.QtGui import QColor
from PySide6.QtCore import (
    QByteArray,
    QPoint,
    QPropertyAnimation,
    QSettings,
    QSize,
    Qt,
    QThread,
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
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from matr1x import VALID_META_KEYS, resolved_directory
from matr1x.error_handling import Error, InternalInvariantError, Result, Success
from matr1x.gui_util import (
    ConfigEditWidget,
    LoggerMixin,
    MApplication,
    blocked_signals,
    get_matrix_icon,
    get_system_info,
)
from matr1x.models import Envelope, SystemInfo
from matr1x.util import get_matrix_binary

__all__ = [
    "MMainWindow",
    "MToolBar",
    "MeasurementItem",
    "MeasurementThread",
    "MeasurementUI",
    "MetaData",
    "MetaDataDialog",
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
        if message.level < logging.ERROR:
            self._dismiss_timer.start(3000)
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
        """Add files but avoid duplicates."""
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
            import_check = self.test_import(candidate)
            if isinstance(import_check, Error):
                msg = NotifierMessage(
                    f"{candidate} could not import and was omitted: {import_check.error}",
                    level=logging.WARNING,
                )
                self.message.emit(msg)
                continue
            super().addItem(candidate)
            self.systems_changed()
            existing.add(candidate)
            self._base_directory = Path(filename)

    def systems_changed(self) -> None:
        """Load system info and emit changed signal."""
        system_info = get_system_info(self.systems)
        if isinstance(system_info, Error):
            raise InternalInvariantError("System list should work if systems work individually.")
        if system_info.value.config_validation_errors:
            warning_text = (
                "System configuration validation failed. Default values are shown only so "
                "you can correct the configuration; fix these entries before execution:\n\n"
                + "".join(system_info.value.config_validation_errors)
            )
            self.message.emit(NotifierMessage(warning_text, level=logging.ERROR))
        for warning in system_info.value.warnings:
            self.message.emit(NotifierMessage(warning, level=logging.WARNING))
        self._cached_system_info = system_info.value
        self._sync_action_state()
        self.changed.emit()

    @property
    def system_info(self) -> SystemInfo:
        """Return the (cached) system info."""
        return self._cached_system_info

    def test_import(self, filename: str) -> Result[bool, str]:
        """Test if a filename can be imported."""
        ret = get_system_info([filename])
        if not isinstance(ret, Success):
            return Error(error=ret.error)
        if ret.value.classes[0] in self.system_info.classes:
            return Error(error="Duplicate system class name, please rename.")
        return Success(value=True)

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
        self.action = QAction(get_matrix_icon("SP_FileDialogListView"), "Metadata", self)
        self.action.setShortcut(QKeySequence("Ctrl+2"))
        self.action.setCheckable(True)
        self.action.setChecked(True)
        self.action.triggered.connect(self.toggle_metadata_view)
        self.visibilityChanged.connect(self._sync_metadata_view)

    def toggle_metadata_view(self, checked: bool) -> None:
        """Toggle the visibility of the metadata."""
        self.setVisible(checked)

    def _sync_metadata_view(self) -> None:
        """Match view action state to the restored widget visibility."""
        with blocked_signals(self.action):
            self.action.setChecked(not self.isHidden())


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

    layout_settings_group = "MainWindowLayoutV2"

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
        self.restoreState(settings.safer_value("window_state", QByteArray(), type=QByteArray))
        self._restore_additional_layout_state(settings)
        settings.endGroup()

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
            ``q`` query the user
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
        tmp_scriptfile: IO[bytes] | None = None
        if self.parameters.kind == "script":
            tmp_scriptfile = tempfile.NamedTemporaryFile(mode="w+b")
            tmp_scriptfile.write(self.parameters.input_file.encode())
            tmp_scriptfile.flush()
        try:
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
                target=self.relay_subprocess_output, args=(self.proc.stdout, False), daemon=True
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
            if tmp_scriptfile is not None:
                tmp_scriptfile.close()
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
