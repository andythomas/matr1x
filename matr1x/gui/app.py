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
"""The Qt application object, theme detection and the about box."""

from __future__ import annotations

import logging
import os
import platform
import signal
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType
from typing import (
    TYPE_CHECKING,
)

import PySide6
from PySide6.QtCore import (
    QEvent,
    QLibraryInfo,
    QTimer,
    Signal,
    qVersion,
)
from PySide6.QtGui import (
    QAction,
    QFileOpenEvent,
    QIcon,
    QPalette,
)
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
    QStyle,
    QTextEdit,
    QWidget,
)

from matr1x.error_handling import InternalInvariantError

if TYPE_CHECKING:
    pass

from .helpers import _format_local_timestamp, get_install_info

logger = logging.getLogger(__name__)


class AboutBox(QMessageBox):
    """Provide an about box with install debug info."""

    def __init__(
        self,
        title: str,
        icon: QIcon,
        package: ModuleType,
        date_format: str,
        parent: QWidget | None = None,
    ):
        """
        Initialize an about box dialog with installation information.

        Parameters
        ----------
        title : str
            Title string to show in the window title and header.
        icon : QIcon
            Icon to display in the about box.
        package : module
            Python package/module to get version and git info from.
        date_format : str
            Format string for displaying git commit date.
        parent : QWidget, optional
            Parent widget for this dialog, by default None.
        """
        super().__init__(parent)
        # The rich text (html) messes with the sizes
        style = QApplication.style()
        icon_size = style.pixelMetric(QStyle.PixelMetric.PM_MessageBoxIconSize)
        pixmap = icon.pixmap(icon_size)
        self.setIconPixmap(pixmap)
        self.setWindowTitle(title)
        # Get package and git information
        (version, branch, sha, time) = get_install_info(package)
        if time != "not available":
            date = _format_local_timestamp(time, date_format)
        else:
            date = time
        # Get Python interpreter information
        python_info = self.get_python_interpreter_info()
        # Get system and Qt information
        system_type = platform.system().lower()
        result = subprocess.run(
            "qmake6 --version | grep -oE '6[.][0-9]+[.][0-9]+'",
            shell=True,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            qmake_qt6_version = result.stdout.strip()
        else:
            qmake_qt6_version = "unavailable"
        text = f"""
                <div style="text-align: left;">
                    <p><b>Git information:</b><br>
                    Branch:</b> {branch}<br>
                    Commit:</b> {sha}<br>
                    Date:</b> {date}</p>

                    <p><b>Python Environment</b><br>
                    Python:</b> {python_info["implementation"]} {python_info["full_version"]}<br>
                    Executable:</b> {python_info["executable"]}<br>
                    Environment:</b> {python_info["env_description"]}<br>
                    PySide6 version:</b> {PySide6.__version__}<br>
                    PySide6 build against:</b> {qVersion()}<br>
                    Location:</b> {python_info["env_location"]}</p>

                    <p><b>System Information</b><br>
                    Platform:</b> {system_type}<br>
                    System Qt (qmake):</b> {qmake_qt6_version}</p>

                    <p>(C) 2006-2026 Matr1x Developers. All rights reserved.</p>
                </div>
                """

        self.setText(f"<b>{title} {version}</b>")
        self.setInformativeText(text)
        self.setStandardButtons(QMessageBox.StandardButton.Ok)
        self.action = QAction("About")
        self.action.setMenuRole(QAction.MenuRole.AboutRole)
        self.action.triggered.connect(self.exec)

    def _shorten_path(self, path: str) -> str:
        """
        Shorten a file system path for display by using ~ for home directory.

        Parameters
        ----------
        path : str
            Full file system path to shorten.

        Returns
        -------
        str
            Shortened path with ~ substitution if under home directory.
        """
        try:
            path_obj = Path(path).resolve()
            home = Path.home()
            if path_obj.is_relative_to(home):
                return "~/" + str(path_obj.relative_to(home))
            return str(path_obj)
        except (ValueError, AttributeError, OSError):
            return path

    def get_python_interpreter_info(self) -> dict[str, str]:
        """
        Get Python interpreter information formatted for the about dialog.

        Returns
        -------
        dict[str, str]
            Dictionary containing interpreter version, implementation, and environment info.
        """
        # Full version string (includes build info)
        full_version = sys.version.split()[0]

        # Implementation (CPython, PyPy, etc.)
        implementation = sys.implementation.name.title()

        # Interpreter executable path (shortened)
        executable = self._shorten_path(sys.executable)

        # Virtual environment detection
        venv_info = self.get_virtual_env_info()

        return {
            "full_version": full_version,
            "implementation": implementation,
            "executable": executable,
            "env_description": venv_info["description"],
            "env_location": venv_info["location"],
        }

    def get_virtual_env_info(self) -> dict[str, str]:
        """
        Detect and return virtual environment information.

        Returns
        -------
        dict[str, str]
            Dictionary containing environment description and location.
        """
        # Determine environment type (only modern venv, not old virtualenv)
        if hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix:
            env_type = "venv"
            env_location = sys.prefix
        else:
            env_type = "system"
            env_location = sys.prefix

        # Check for conda
        conda_env = os.environ.get("CONDA_DEFAULT_ENV")
        if conda_env:
            if env_type == "system":
                env_type = "conda"
            env_description = "Conda"
        elif env_type == "system":
            env_description = "System Python"
        else:
            env_description = env_type.title()

        # Shorten location path for display
        location = self._shorten_path(env_location)

        return {"description": env_description, "location": location}


class ThemeDetector(QWidget):
    """
    Hidden widget that detects theme changes.

    This is required because a QWidget receives different signals than
    the QApplication.
    """

    isDarkSignal = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hide()
        self._is_dark = QTextEdit().palette().color(QPalette.ColorRole.Text).value() > 128

    def isDark(self) -> bool:
        """
        Return the desktop theme (Light or Dark).

        Returns
        -------
        bool
            Desktop dark (True) or Light (False).
        """
        return self._is_dark

    def changeEvent(self, event) -> None:
        """Detect theme change event."""
        if event.type() == QEvent.Type.PaletteChange:
            self._is_dark = QTextEdit().palette().color(QPalette.ColorRole.Text).value() > 128
            self.isDarkSignal.emit(self._is_dark)
        super().changeEvent(event)


class MApplication(QApplication):
    """Fix GUI related issues for all applications."""

    isDarkSignal = Signal(bool)
    openfile = Signal(str)

    @property
    def isDark(self) -> bool:
        """
        Return whether the current theme is dark.

        Returns
        -------
        bool
            True if dark theme is active, False otherwise.
        """
        return self._theme_detector.isDark()

    def __init__(self, args: Sequence[str]) -> None:
        """
        Improve theme change handling, linux and mac behavior.

        Use a helper widget for better theme handling. Automatically
        select the xcb client on a Linux machine.  Allow double-click
        file opening on a Mac.

        args : list of str
            Arguments for QApplication
        """
        if sys.platform == "linux":
            if "QT_QPA_PLATFORM" not in os.environ and "xcb" in self._list_platform_plugins():
                os.environ["QT_QPA_PLATFORM"] = "xcb"
        super().__init__(args)
        if not self.applicationName():
            self.setApplicationName("matr1x")
        if not self.organizationName():
            self.setOrganizationName("matr1x")
        if os.name == "nt":
            self.setStyle("fusion")  # Enable modern mode on Windows which allows for dark mode
        self._theme_detector = ThemeDetector()
        self._theme_detector.isDarkSignal.connect(self.isDarkSignal.emit)
        self._pending_files: list[str] = []
        self._handler_connected = False
        self._signal_timer = QTimer()
        self._signal_timer.timeout.connect(lambda: None)
        signal.signal(signal.SIGINT, self._exit_gracefully)
        signal.signal(signal.SIGTERM, self._exit_gracefully)

    def _exit_gracefully(self, signum: int, frame: object) -> None:
        """
        Handle SIGINT/SIGTERM by quitting the application.

        This enables the safety precautions such as "do you want to
        save" and similar things.

        Parameters
        ----------
        signum : int
            The signal number received.
        frame : object
            The current stack frame (unused).
        """
        logger.debug("Kill signal received (%s)", signum)
        MApplication.quit()

    def exec(self) -> int:
        """
        Run the event loop with a keepalive timer for signal handling.

        Starts a periodic no-op timer so Python can process OS signals
        (e.g. SIGINT from Ctrl+C) while Qt owns the event loop.  The
        timer is stopped automatically when exec returns.

        Returns
        -------
        int
            The exit code returned by the Qt event loop.
        """
        self._signal_timer.start(100)
        try:
            return super().exec()
        finally:
            self._signal_timer.stop()

    def _list_platform_plugins(self) -> Sequence[str]:
        """
        List available platforms by inspecting the platforms directory.

        Returns
        -------
        Sequence[str]
            A list consisting of all possible platforms
        """
        plugin_path = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
        platforms_path = plugin_path / "platforms"
        if platforms_path.exists():
            plugins = [f.name for f in platforms_path.iterdir() if f.is_file()]
            platforms = [Path(plugin).stem.replace("libq", "") for plugin in plugins]
            return platforms
        else:
            return []

    def toolbar_icon_size(self) -> int:
        """
        Return the toolbar icon size for all GUIs.

        Returns
        -------
        int
            size of the icon
        """
        small = MApplication.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize)
        standard = MApplication.style().pixelMetric(QStyle.PixelMetric.PM_ToolBarIconSize)
        intermediate = int((small + standard) / 2)
        return intermediate

    def event(self, event: QEvent) -> bool:
        """Handle application events including file open events."""
        if event.type() == QEvent.Type.FileOpen and isinstance(event, QFileOpenEvent):
            filename = event.file()
            if self._handler_connected:
                self.openfile.emit(filename)
            else:
                self._pending_files.append(filename)
        return QApplication.event(self, event)

    def connect_file_handler(self, handler: Callable[[str], None]) -> None:
        """
        Connect file open handler and process any buffered events.

        Parameters
        ----------
        handler: Callable[[str], None]
            A function to connect that takes a filename as a parameter.
        """
        self.openfile.connect(handler)
        self._handler_connected = True
        for filename in self._pending_files:
            self.openfile.emit(filename)
        self._pending_files.clear()

    def setDesktopFileName(self, name: str, /) -> None:
        """
        Set desktop filename with platform-specific optimizations.

        Parameters
        ----------
        name : str
            The desktop filename (e.g., "matrix-script")
        """
        if sys.platform == "darwin":
            from AppKit import NSApplication  # type: ignore
            from Foundation import NSBundle  # type: ignore

            bundle = NSBundle.mainBundle()
            if bundle:
                info_dict = bundle.localizedInfoDictionary() or bundle.infoDictionary()
                info_dict["CFBundleName"] = name
            # Correct the menu
            app = NSApplication.sharedApplication()
            main_menu = app.mainMenu()
            if main_menu:
                # Get left-most menu with app-specific items
                app_menu = main_menu.itemAtIndex_(0).submenu()
                for i in range(app_menu.numberOfItems()):
                    item = app_menu.itemAtIndex_(i)
                    item.setTitle_(item.title().replace("Python", name))

        super().setDesktopFileName(name)

    @classmethod
    def instance(cls) -> MApplication:
        """
        Return the MApplication instance.

        Narrows the return type from QCoreApplication | None to
        MApplication and raises if no instance exists yet.

        Returns
        -------
        MApplication
            The running application instance.

        Raises
        ------
        InternalInvariantError
            If no MApplication instance has been created.
        """
        app = super().instance()
        if not isinstance(app, MApplication):
            raise InternalInvariantError("The application instance is None!")
        return app
