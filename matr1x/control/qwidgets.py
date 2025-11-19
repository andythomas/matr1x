# This file is part of a software collection for data acquisition (matr1x).
# Copyright (C) 2006-2025 matr1x developers
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
"""Module containing custom GUI widgets for the matr1x data acquisition software."""

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import QProgressBar, QPushButton

from matr1x.gui_util import get_matrix_icon


class matr1xProgressBar(QProgressBar):
    """
    Overload QProgressBar to allow values between -5 and 105.

    Values outside that range are indicated by a red color.
    """

    def __init__(self):
        super().__init__()
        self.setRange(-5, 105)
        self.setFormat("%v")

    def setValue(self, value: int) -> None:
        """
        Set the current value of the progress bar.

        Parameters
        ----------
        value : int
            The value to set for the progress bar.
        """
        if value > self.maximum() or value < self.minimum():
            # change color
            self.reset()
            self.setStyleSheet("QProgressBar{background-color : red;}")
        else:
            self.setStyleSheet("QProgressBar{}")

        super().setValue(value)


class ToggleButton(QPushButton):
    """
    Custom QPushButton to emulate a proper toggle button.

    Including the change of the button's label upon pushing.

    Parameters
    ----------
    *args : Union[str, List[str], Tuple[str, str]]
        Positional arguments. The first argument should be either a string
        (single label) or a list/tuple of two strings (labels for unchecked/checked states).
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


class EnableAction(QAction):
    """
    A QAction subclass that automatically updates its icon based on checked state.

    This action is designed for enable/disable functionality and automatically
    updates its icon color when the checked state changes.
    """

    def __init__(self, text: str, parent: QObject | None = None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setIconText("Enable")
        self.setIcon(get_matrix_icon("CUSTOM_Power", color=QColor("gray")))
        # Connect toggled signal to update icon automatically
        self.toggled.connect(self._update_icon)

    def _update_icon(self, checked: bool):
        """Update the icon based on checked state."""
        if checked:
            self.setIcon(get_matrix_icon("CUSTOM_Power", color=QColor("forestgreen")))
        else:
            self.setIcon(get_matrix_icon("CUSTOM_Power", color=QColor("gray")))
        # Only call check_enables if all actions are initialized and parent has the method
        parent = self.parent()
        if hasattr(parent, "disable_all_action") and hasattr(parent, "check_enables"):
            getattr(parent, "check_enables")()

    def setChecked(self, a0: bool):
        """Override setChecked to ensure icon is updated."""
        super().setChecked(a0)
        self._update_icon(a0)


class FullInfoAction(QAction):
    """
    A QAction subclass that automatically updates its icon based on checked state.

    This action is designed for full info/less info functionality and automatically
    updates its icon (+ or -) when the checked state changes.
    """

    def __init__(self, text: str, parent: QObject | None = None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setIconText("Full info")
        self.setIcon(get_matrix_icon("CHAR_+"))
        # Connect toggled signal to update icon automatically
        self.toggled.connect(self._update_icon)

    def _update_icon(self, checked: bool):
        """Update the icon based on checked state."""
        if checked:
            self.setIcon(get_matrix_icon("CHAR_-"))
        else:
            self.setIcon(get_matrix_icon("CHAR_+"))
        # Only call check_full_infos if all actions are initialized and parent has the method
        parent = self.parent()
        if hasattr(parent, "full_info_all_action") and hasattr(parent, "check_full_infos"):
            getattr(parent, "check_full_infos")()

    def setChecked(self, a0: bool):
        """Override setChecked to ensure icon is updated."""
        super().setChecked(a0)
        self._update_icon(a0)
