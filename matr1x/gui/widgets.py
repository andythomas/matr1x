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
"""Qt input/display widgets: range widget, file line edit, read-only table."""

from __future__ import annotations

import logging
from typing import (
    TYPE_CHECKING,
)

from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QStyle,
    QTableWidget,
    QToolButton,
    QWidget,
)

from matr1x.error_handling import InternalInvariantError

if TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


class QRangeWidget(QGroupBox):
    """
    Widget that displays a range slider with decrement/increment sliders.

    This widget consists of a range slider with a decrement/increment
    slider on either side and a label on the left.
    """

    value_changed = Signal(int)

    def __init__(self, title, parent=None):
        """
        Initialize the QRangeWidget.

        Parameters
        ----------
        title : str
            Base name displayed on the left together with current
            value of slider and the number of increments.
        parent : QWidget, optional
            Parent widget.
        """
        super().__init__("", parent)
        self.setMinimumHeight(30)
        self.setFixedHeight(30)
        self.base_title = title
        grid = QHBoxLayout()
        self.label = QLabel(title)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.setValue(0)
        self.inc = QToolButton()
        self.inc.setArrowType(Qt.ArrowType.RightArrow)
        self.dec = QToolButton()
        self.dec.setArrowType(Qt.ArrowType.LeftArrow)
        grid.addWidget(self.label)
        grid.addWidget(self.dec)
        grid.addWidget(self.slider, stretch=1)
        grid.addWidget(self.inc)
        grid.setContentsMargins(0, 0, 0, 0)
        self.setLayout(grid)

        self.slider.valueChanged.connect(self._value_changed)
        self.inc.clicked.connect(self._increment)
        self.dec.clicked.connect(self._decrement)

    def _increment(self):
        val = self.value() + 1
        if val <= self.maximum():
            self.slider.setValue(val)

    def _decrement(self):
        val = self.value() - 1
        if val >= 0:
            self.slider.setValue(val)

    def _update_text(self):
        self.label.setText(f"{self.base_title} - {self.value()} ({self.maximum() + 1})")

    def _value_changed(self, val):
        self._update_text()
        self.value_changed.emit(val)

    def set_base_title(self, title):
        """
        Reset the base title to a new value.

        Parameters
        ----------
        title : str
            New base title.
        """
        self.base_title = title

    def set_value(self, val):
        """
        Set current value of slider.

        Parameters
        ----------
        val : int
            New value of slider, out of range values are ignored.
        """
        self.slider.setValue(val)
        self._update_text()

    def value(self):
        """
        Get current value of slider.

        Returns
        -------
        int
            Current value of slider.
        """
        return self.slider.value()

    def set_range(self, minimum, maximum):
        """
        Set range of slider.

        Parameters
        ----------
        minimum : int
            Minimum value of slider.
        maximum : int
            Maximum value of slider.
        """
        self.slider.setRange(minimum, maximum)
        self._update_text()

    def minimum(self):
        """
        Get minimum value of slider.

        Returns
        -------
        int
            Minimum value of slider.
        """
        return self.slider.minimum()

    def maximum(self):
        """
        Get maximum value of slider.

        Returns
        -------
        int
            Maximum value of slider.
        """
        return self.slider.maximum()


class FileLineEdit(QLineEdit):
    """
    Widget that displays a LineEdit with a button that opens a QFileDialog.

    This widget consists of a QLineEdit and a FileDialog. Upon return
    the selected filename is passed to the callback function provided as
    argument
    """

    def __init__(self, callback, parent=None, spec="file"):
        super().__init__(parent)

        self.callback = callback
        self.spec = spec
        # Create the QLineEdit and QPushBottn
        self.dialog_button = QToolButton(self)
        self.dialog_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.dialog_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.dialog_button.setToolTip("Open file dialog")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addStretch()
        layout.addWidget(self.dialog_button)
        self.setLayout(layout)

        self.dialog_button.clicked.connect(self._open_file_dialog)

    def _open_file_dialog(self):
        parent = self.parent()
        if not isinstance(parent, QWidget):
            raise InternalInvariantError("The parent widget must be a QWidget!")
        dialog = QFileDialog(parent)
        if self.spec == "file":
            dialog.setFileMode(QFileDialog.FileMode.AnyFile)
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
            dialog.setOption(QFileDialog.Option.DontConfirmOverwrite)
        else:
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
            dialog.setFileMode(QFileDialog.FileMode.Directory)
            dialog.setOption(QFileDialog.Option.ShowDirsOnly)

        if dialog.exec() and len(dialog.selectedFiles()) > 0:
            # pass value to callback
            self.callback(dialog.selectedFiles()[0])


class ReadOnlyTable(QTableWidget):
    """Enable a read-only table with item copy."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    def copy(self):
        """Copy the currently selected item in the clipboard."""
        index = self.currentIndex()
        if index.isValid():
            QApplication.clipboard().setText(str(index.data()))
