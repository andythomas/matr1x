# This file is part of a software collection for data aquisition (matr1x).
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

from typing import List, Tuple, Union

from PyQt6.QtWidgets import QProgressBar, QPushButton


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
            self.setStyleSheet("QProgressBar" "{" "background-color : red;" "}")
        else:
            self.setStyleSheet("QProgressBar" "{" "}")

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

    def __init__(self, *args: Union[str, List[str], Tuple[str, str]], **kwargs):
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
