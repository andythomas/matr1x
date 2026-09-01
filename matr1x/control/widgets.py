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
"""Contains reusable Qt widgets for control GUIs."""

import logging

from PySide6.QtCore import (
    QPoint,
    QSize,
    Signal,
)
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDockWidget,
    QPushButton,
)

from matr1x.gui.shared import SaferQSettings
from matr1x.gui_util import AutoSlot

__all__ = [
    "MyQDockWidget",
    "ToggleButton",
]

logger = logging.getLogger(__name__)


class ToggleButton(QPushButton):
    """
    Custom QPushButton to emulate a proper toggle button.

    Including the change of the button's label upon pushing.

    Parameters
    ----------
    *args : str | list[str] | tuple[str, str]]
        Positional arguments. The first argument should be either a
        string (single label) or a list/tuple of two strings (labels
        for unchecked/checked states).
    **kwargs : dict
        Keyword arguments to be passed to the QPushButton constructor.
    """

    def __init__(self, *args: str | list[str] | tuple[str, str], **kwargs):
        if isinstance(args[0], (list, tuple)):
            label = args[0][0]
        else:
            label = args[0]
        super().__init__(label, **kwargs)
        self._labels = args[0]
        self.setCheckable(True)

    def setChecked(self, state: bool) -> None:
        """
        Change label of toggle button.

        Parameters
        ----------
        state : bool
            The new checked state of the button.
        """
        super().setChecked(state)
        # if it is checked
        if isinstance(self._labels, (list, tuple)):
            if state:
                self.setText(self._labels[1])
            # if it is unchecked
            else:
                self.setText(self._labels[0])


class MyQDockWidget(QDockWidget):
    """Modify QDockWidget to be able to track its closing."""

    dockClosed: Signal = Signal()

    def __init__(self, title: str, appname: str) -> None:
        super().__init__(title)
        self.application_name: str = appname
        self.setObjectName(f"{appname}-{title}")
        self.settings: SaferQSettings = SaferQSettings("matr1x", appname)
        self.disabled: bool = False
        self.extended: bool = False

    @AutoSlot
    def saveCurrentState(self) -> None:
        """Save current dock geometry and enable state."""
        self.settings.beginGroup(self.windowTitle())
        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("disabled", self.disabled)
        self.settings.setValue("extended", self.extended)
        self.settings.endGroup()

    def restoreState(self) -> None:
        """Load stored dock geometry and disable state."""
        self.settings.beginGroup(self.windowTitle())
        self.resize(self.settings.safer_value("size", self.size(), type=QSize))
        self.move(self.settings.safer_value("pos", self.pos(), type=QPoint))
        self.disabled = self.settings.safer_value("disabled", False, type=bool)
        self.extended = self.settings.safer_value("extended", False, type=bool)
        self.settings.endGroup()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Emit dockClosed signal when the dock is closed."""
        super().closeEvent(event)
        self.dockClosed.emit()
