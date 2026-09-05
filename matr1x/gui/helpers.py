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
"""General GUI helpers: icons, system info, config checks and Qt utilities."""

import datetime
import logging
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from types import ModuleType
from typing import Literal

import pygit2
from pydantic import ValidationError
from PySide6.QtCore import (
    QPoint,
    Qt,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QFontDatabase,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPixmap,
    QPolygon,
)
from PySide6.QtWidgets import (
    QApplication,
    QLayout,
    QMessageBox,
    QStyle,
    QWidget,
)

import matr1x.core.config as core_config
from matr1x.core.error_handling import Error, Result, Success
from matr1x.core.models import (
    SystemCapability,
    SystemInfo,
    SystemReference,
)

logger = logging.getLogger(__name__)


def _format_local_timestamp(value: float, fmt: str, *, trim_trailing_zeros: bool = False) -> str:
    text = datetime.datetime.fromtimestamp(value, datetime.timezone.utc).astimezone().strftime(fmt)
    return text.rstrip("0") if trim_trailing_zeros else text


def get_package_version(module: ModuleType) -> str:
    """Return the version of the given module."""
    if hasattr(module, "__version__"):
        return module.__version__
    try:
        return version(module.__name__)
    except PackageNotFoundError:
        return "unknown"


def get_install_info(
    imported_package: ModuleType,
) -> tuple[str, str, str, Literal["not available"] | int]:
    """
    Receive git infos about the installed version.

    Parameters
    ----------
    imported_package: ModuleType
        Any module (package) that was already imported.

    Returns
    -------
    installed_version: str,
    commit_branch: str,
    commit_short_sha: str,
    commit_time: str or int
        The version and commit info(s) of the package.
    """
    commit_branch = "not available"
    commit_time = "not available"
    commit_short_sha = "not available"
    try:
        repo = pygit2.Repository(imported_package.__file__)
        commit_branch = repo.head.shorthand
        last_commit = repo[repo.head.target]
        commit_short_sha = str(last_commit.id)[:7]
        commit_time = last_commit.author.time
        if commit_branch == "HEAD":
            # Attempt to find the remote branch
            for ref_name in repo.references:
                ref = repo.lookup_reference(ref_name)
                if ref.target == repo.head.target and ref_name.startswith("refs/remotes/"):
                    commit_branch = ref.shorthand
                    break
    except pygit2.GitError:
        pass
    installed_version = get_package_version(imported_package)
    return (installed_version, commit_branch, commit_short_sha, commit_time)


def _load_matr1x_icon(name: str, color: QColor | None) -> QIcon:
    """Load an application icon and optionally replace its white pixels."""
    icon_dir = Path(__file__).parent / "scripts" / "icons"
    pixmap = QPixmap(str(icon_dir / name))
    if color is not None:
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        for x in range(image.width()):
            for y in range(image.height()):
                if QColor(image.pixel(x, y)) == QColor("white"):
                    image.setPixelColor(x, y, color)
                else:
                    image.setPixelColor(x, y, QColor(0, 0, 0, 0))
        pixmap = QPixmap.fromImage(image)
    return QIcon(pixmap.copy(15, 15, 226, 226))


def _draw_character_icon(
    painter: QPainter, pixmap: QPixmap, letter: str, size: int, pencolor: QColor
) -> None:
    """Draw a character in the center of an icon canvas."""
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPointSizeF(size * 0.8)
    painter.setFont(font)
    painter.setPen(pencolor)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, letter)


def _draw_custom_icon(painter: QPainter, name: str, size: int, pencolor: QColor) -> None:
    """Draw one of the supported custom glyphs on an icon canvas."""
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(pencolor)
    painter.setPen(pencolor)
    if name == "Play":
        triangle = QPolygon(
            [
                QPoint(int(size // 15 + size * 0.3), int(size * 0.2)),
                QPoint(int(size // 15 + size * 0.3), int(size * 0.8)),
                QPoint(int(size // 15 + size * 0.7), int(size * 0.5)),
            ]
        )
        painter.drawPolygon(triangle)
    elif name == "Updown":
        up_arrow = QPolygon(
            [
                QPoint(int(size * 0.25), int(size * 0.2)),
                QPoint(int(size * 0.05), int(size * 0.8)),
                QPoint(int(size * 0.45), int(size * 0.8)),
            ]
        )
        down_arrow = QPolygon(
            [
                QPoint(int(size * 0.55), int(size * 0.2)),
                QPoint(int(size * 0.75), int(size * 0.8)),
                QPoint(int(size * 0.95), int(size * 0.2)),
            ]
        )
        painter.drawPolygon(up_arrow)
        painter.drawPolygon(down_arrow)
    elif name == "Power":
        width = size // 8
        height = size // 2
        painter.drawRect(size // 2 - width // 2, size // 4, width, height)
    elif name == "Stop":
        painter.drawRect(int(size * 0.3), int(size * 0.3), int(size * 0.4), int(size * 0.4))
    elif name == "Pause":
        bar_width = size * 0.15
        bar_height = size * 0.4
        spacing = size * 0.1
        x_offset = (size - 2 * bar_width - spacing) / 2
        y_offset = (size - bar_height) / 2
        painter.drawRect(int(x_offset), int(y_offset), int(bar_width), int(bar_height))
        painter.drawRect(
            int(x_offset + bar_width + spacing),
            int(y_offset),
            int(bar_width),
            int(bar_height),
        )
    else:
        raise ValueError(f"Unknown icon type CUSTOM_{name}.")


def _resolve_icon_colors(color: QColor | None, pencolor: QColor | None) -> tuple[QColor, QColor]:
    """Return icon colors, filling in the standard defaults when needed."""
    if color is None:
        color = QColor("RoyalBlue")
    if pencolor is None:
        pencolor = QColor("white")
    return color, pencolor


def get_matrix_icon(
    name: str, color: QColor | None = None, pencolor: QColor | None = None
) -> QIcon:
    """
    Look up 'name' and get corresponding QIcon back.

    Icons from a theme such as QIcon.fromTheme("media-playback-start") are not available on all
    platforms. Consequently, we fallback to the Qt icons, which are also repecting platform and
    theme, at least to some extent. Additionally, icons can be generated or the Matrix
    applications icons can be used.

    Parameters
    ----------
    name : str
        The name of the icon. If it starts 'SP_' it signifies to use the Qt build-in icon,
        'CHAR_' will generate a circle with the letter in it, 'CUSTOM_' provides several
        painted icons and 'matr1x-' will use the matrix application icons.
    color : QColor or str
        The color of the icon if applicable.
    pencolor: QColor
        The color of the painted items.

    Returns
    -------
    QIcon
    """
    if name.startswith("SP_"):
        return QApplication.style().standardIcon(getattr(QStyle.StandardPixmap, name))
    if name.startswith("matr1x-"):
        return _load_matr1x_icon(name, color)

    color, pencolor = _resolve_icon_colors(color, pencolor)
    size = 256
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(5, 5, size - 10, size - 10)
    if name.startswith("CHAR_"):
        _draw_character_icon(painter, pixmap, name[5], size, pencolor)
    elif name.startswith("CUSTOM_"):
        _draw_custom_icon(painter, name[7:], size, pencolor)
    else:
        raise ValueError(f"Unknown icon type {name}.")
    painter.end()
    return QIcon(pixmap)


def detect_shortcut(event, shortcut):
    """
    Compare a combination of keys in a string to a keypress event.

    Parameters
    ----------
    event : QEvent
        The event that was detected
    shortcut : str or QKeySequence
        The keyboard shortcut as used in QKeySequence(string) or directly

    Returns
    -------
    bool
        Indicates if there is a match
    """
    key = event.key()
    modifiers = event.modifiers()
    # A QKeySequence could be a sequence of several keys. Only the first
    # combination makes sense as a shortcut
    if isinstance(shortcut, str):
        # There seems to be bug bug, but this code is unreachable.
        # Will look at it later (at).
        keys = QKeySequence(shortcut)[0]  # type: ignore
    elif isinstance(shortcut, QKeySequence):
        keys = shortcut[0]
    else:
        raise TypeError("Shortcut has to be of type(str) or type(QKeySequence).")
    return bool(key == keys.key() and modifiers == keys.keyboardModifiers())


def save_messagebox(instance, save_cb: Callable[[], bool]) -> bool:
    """
    Show a messagebox to query file save.

    Ask the user to write unsaved changes to a file
    and return choice.

    Returns
    -------
    return : bool
        The file was saved (True) or not (False).
    """
    msg = QMessageBox(parent=instance)
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setText("Unsaved modifications!")
    msg.setInformativeText("Do you want to save your changes?")
    msg.setStandardButtons(
        QMessageBox.StandardButton.Save
        | QMessageBox.StandardButton.Discard
        | QMessageBox.StandardButton.Cancel
    )
    discard = msg.button(QMessageBox.StandardButton.Discard)
    discard.setText("Don't Save")
    msg.setDefaultButton(QMessageBox.StandardButton.Save)
    ret = msg.exec()
    if ret == QMessageBox.StandardButton.Cancel:
        return False
    return not (ret == QMessageBox.StandardButton.Save and not save_cb())


def get_system_info(
    systems: Sequence[str | Path | SystemReference],
) -> Result[SystemInfo, str]:
    """Get system information using a subprocess."""
    try:
        tokens = [SystemReference.from_value(system).to_token() for system in systems]
    except ValidationError as error:
        return Error(str(error))
    script = (
        "import json\n"
        "import sys\n"
        "from matr1x import validation_errors\n"
        "from matr1x.core.error_handling import Error\n"
        "from matr1x.core.system import MergedSystem\n"
        "validation_error_count = len(validation_errors)\n"
        f"result = MergedSystem.from_references({tokens!r})\n"
        "if isinstance(result, Error):\n"
        "    print(result.error, file=sys.stderr)\n"
        "    raise SystemExit(1)\n"
        "info = result.value.grab_information()\n"
        "info['config_validation_errors'] = validation_errors[validation_error_count:]\n"
        "print(json.dumps(info))\n"
    )
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
            ],
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return Error(f"Could not run system info subprocess: {e}")

    if result.returncode != 0:
        stderr_output = result.stderr.decode()
        return Error(stderr_output)
    output_str = result.stdout.decode()
    error_output = result.stderr.decode().strip()
    if error_output != "":
        marker = core_config.deprecation_marker
        if marker in error_output:
            logger.error(error_output)
        else:
            logger.warning(error_output)
    # Find the last line that looks like JSON to avoid warnings/garbage
    json_str = ""
    for line in reversed(output_str.splitlines()):
        if line.strip().startswith("{") and line.strip().endswith("}"):
            json_str = line.strip()
            break

    if not json_str:
        return Error(f"Warning: No JSON found in subprocess output:\n{output_str}")

    try:
        validated_data = SystemInfo.model_validate_json(json_str)
        return Success(validated_data)
    except ValidationError as e:
        return Error(f"Warning: Could not parse JSON from subprocess output:\n{e}")


def get_system_capability(source: str) -> Result[SystemCapability, str]:
    """Inspect one system definition without constructing it."""
    script = (
        "import sys\n"
        "from matr1x.core.error_handling import Error\n"
        "from matr1x.core.system import System\n"
        f"result = System.inspect_file({source!r})\n"
        "if isinstance(result, Error):\n"
        "    print(result.error, file=sys.stderr)\n"
        "    raise SystemExit(1)\n"
        "print(result.value.model_dump_json())\n"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            timeout=30,
        )
    except Exception as error:
        return Error(f"Could not inspect system in subprocess: {error}")
    if result.returncode != 0:
        return Error(result.stderr.decode())
    try:
        output = result.stdout.decode().splitlines()[-1]
        return Success(SystemCapability.model_validate_json(output))
    except (IndexError, ValidationError) as error:
        return Error(f"Could not parse system capability: {error}")


def create_matrix_settings_action() -> QAction:
    """Create the common matr1x.toml action."""
    action = QAction("Open matr1x.toml")
    action.setMenuRole(QAction.MenuRole.PreferencesRole)
    action.setShortcut(QKeySequence.StandardKey.Preferences)
    return action


def create_matr1x_quit_action() -> QAction:
    """Create the common matr1x quit action."""
    action = QAction("Quit")
    if os.name == "nt":
        action.setShortcut(QKeySequence.StandardKey.Close)
    else:
        action.setShortcut(QKeySequence.StandardKey.Quit)
    return action


def open_matrix_toml() -> None:
    """Open a file browser with the matrix toml selected."""
    toml_home = Path.home() / ".matr1x.toml"
    if not toml_home.exists():
        QMessageBox.warning(
            None,
            "Toml file does not exist!",
            f"Please create a '.matr1x.toml' file at {Path.home()}.",
        )
        return
    if os.name == "nt":
        subprocess.run(["explorer", f"/select,{toml_home.resolve(strict=False)}"], check=False)
    elif sys.platform == "darwin":
        subprocess.run(["open", "-R", toml_home], check=False)
    else:
        subprocess.run(["xdg-open", toml_home], check=False)


def find_parent_of_type(widget: QWidget, cls: type[QWidget]) -> QWidget | None:
    """
    Return first ancestor of `widget` that is an instance of `cls`.

    Parameters
    ----------
    widget: QWidget
        The widget to start the search from.
    cls: type[QWidget]
        The class to search for.

    Returns
    -------
    QWidget or None
        The first ancestor of 'widget' that is an instance of 'cls'.
    """
    w = widget
    while w is not None:
        if isinstance(w, cls):
            return w
        w = w.parentWidget()
    return None


def clear_layout(layout: QLayout) -> None:
    """Clear all child widgets from layout."""
    while layout.count():
        item = layout.takeAt(0)
        if item is not None:
            if widget := item.widget():
                widget.deleteLater()
            elif child_layout := item.layout():
                clear_layout(child_layout)
