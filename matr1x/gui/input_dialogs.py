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
"""Modal dialogs for user input requested by a running script.

A script can request user input via the `input` command, which sends
an `InputParameters` envelope to the GUI and blocks until a response
is sent back (e.g. via `MeasurementThread.pass_input`). These dialogs
collect the response. `TimeoutDialogBase` adds an optional timeout
that closes the dialog automatically, and every dialog offers Abort
and Finish buttons that end the script.
"""

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from matr1x.gui.helpers import get_matrix_icon


def parse_numerical_default(
    default_value: str, warn: Callable[[str], None] | None = None
) -> float:
    """Parse a default value string into a float, with warning on failure.

    Parameters
    ----------
    default_value : str
        The default value string to parse.
    warn : callable, optional
        Called with a warning message if the value cannot be parsed.

    Returns
    -------
    float
        The parsed value, or 0.0 if the value is empty or invalid.
    """
    try:
        return float(default_value) if default_value else 0.0
    except ValueError:
        if warn is not None:
            warn(
                f"Warning: Invalid default_value '{default_value}' for numerical input. Using 0.0"
            )
        return 0.0


class TimeoutDialogBase(QDialog):
    """Base class for dialogs with timeout functionality."""

    def __init__(
        self,
        query: str,
        timeout: float | None,
        *,
        parent: QWidget | None = None,
        default_value: Any = "",
    ):
        """
        Initialize the base dialog with timeout functionality.

        Parameters
        ----------
        query : str
            The text to display on the label above the input field.
        timeout : float or None
            Timeout in seconds before dialog automatically
            closes. None means no timeout.
        parent : QWidget, optional
            The parent widget of the dialog.
        default_value : Any, optional
            Default value to show in input field.
        """
        super().__init__(parent)
        self.setWindowTitle("Matrix-script input")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )

        self.default_value = default_value
        self.user_responded = False  # Track if user clicked a button
        self.timeout = timeout if timeout else float("inf")

        self.label = QLabel(query, self)

        # This will be created by subclasses
        self.input_widget = None

        self.timer_label = QLabel("", self)
        self.timer_label.setVisible(self.timeout != float("inf"))

        self.ok_button = QPushButton("Send input", self)

        self.ok_button.clicked.connect(self._button_clicked)
        self.ok_button.clicked.connect(self.accept)

        self.abort_aborted_button = QPushButton("Abort", self)
        self.abort_aborted_button.setIcon(get_matrix_icon("CUSTOM_Stop", color=QColor("#B71C1C")))
        self.abort_finished_button = QPushButton("Finish", self)
        self.abort_finished_button.setIcon(get_matrix_icon("CUSTOM_Stop", color=QColor("#388E3C")))

        self.abort_aborted_button.clicked.connect(self._button_clicked)
        self.abort_aborted_button.clicked.connect(lambda: self.done(2))
        self.abort_finished_button.clicked.connect(self._button_clicked)
        self.abort_finished_button.clicked.connect(lambda: self.done(3))

        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        if self.timeout != float("inf"):
            self.remaining_time = self.timeout * 1000
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_timer)
            self.timer.start(100)  # Update every 100ms for better precision

    def _button_clicked(self):
        """Mark that user has responded to prevent timeout override."""
        self.user_responded = True

    def update_timer(self):
        """Update the timer display and handle timeout."""
        if self.user_responded:
            return

        self.remaining_time -= 100

        if self.remaining_time <= 0:
            if not self.user_responded:
                self.timer.stop()
                self.accept()
            return

        # Convert milliseconds back to seconds for display
        remaining_seconds = self.remaining_time / 1000

        if remaining_seconds < 100:
            self.timer_label.setText(f"Time remaining: {int(remaining_seconds)} seconds")
        else:
            hours = int(remaining_seconds / 3600)
            minutes = int((remaining_seconds % 3600) / 60)
            seconds = int(remaining_seconds % 60)
            if hours > 0:
                self.timer_label.setText(f"Time remaining: {hours}h {minutes}m {seconds}s")
            else:
                self.timer_label.setText(f"Time remaining: {minutes}m {seconds}s")

    def setup_layout(self, answer_buttons: list[QWidget] | None = None):
        """Set up the dialog layout.

        Parameters
        ----------
        answer_buttons : list of QWidget, optional
            Buttons for the answer row. If None, uses ``ok_button``.
        """
        main_layout = QVBoxLayout(self)

        query_group = QGroupBox("Query", self)
        query_layout = QVBoxLayout(query_group)
        query_layout.addWidget(self.label)
        if self.input_widget:
            query_layout.addWidget(self.input_widget)
        query_layout.addWidget(self.timer_label)

        answer_layout = QHBoxLayout()
        if answer_buttons is None:
            answer_layout.addWidget(self.ok_button)
        else:
            for button in answer_buttons:
                answer_layout.addWidget(button)
        query_layout.addLayout(answer_layout)
        main_layout.addWidget(query_group)
        main_layout.addSpacing(12)

        end_group = QGroupBox("End Script", self)
        end_layout = QHBoxLayout(end_group)
        end_layout.addWidget(self.abort_aborted_button)
        end_layout.addWidget(self.abort_finished_button)
        main_layout.addWidget(end_group)

        self.adjustSize()
        self.setFixedSize(self.size())

    def accept(self):
        """Handle dialog acceptance."""
        if hasattr(self, "timer") and self.timer.isActive():
            self.timer.stop()
        super().accept()

    def reject(self):
        """Handle dialog rejection."""
        if hasattr(self, "timer") and self.timer.isActive():
            self.timer.stop()
        super().reject()


class TextInputDialog(TimeoutDialogBase):
    """Modal dialog for text input."""

    def __init__(
        self,
        query: str,
        timeout: float | None,
        *,
        parent: QWidget | None = None,
        default_value: str = "",
    ):
        """
        Initialize the text input dialog with a its GUI elements.

        Parameters
        ----------
        query : str
            The text to display on the label above the input field.
        timeout : float or None
            Timeout in seconds before dialog automatically
            closes. None means no timeout.
        parent : QWidget, optional
            The parent widget of the dialog.
        default_value : str, optional
            Default value to show in input field.
        """
        super().__init__(query, timeout, parent=parent, default_value=default_value)

        self.input = QLineEdit(self)
        self.input.setPlaceholderText("input to send to script")
        self.input.setText(default_value)
        self.input_widget = self.input

        self.setup_layout()

    def get_input_text(self):
        """
        Get the text entered by the user.

        Returns
        -------
        str
            The user input.
        """
        return self.input.text()


class NumericalInputDialog(TimeoutDialogBase):
    """Modal dialog for numerical input."""

    def __init__(
        self,
        query: str,
        timeout: float | None,
        *,
        parent: QWidget | None = None,
        default_value: float = 0.0,
        min_value: float | None = -100e9,
        max_value: float | None = 100e9,
        step: float | None = 1.0,
        decimals: int | None = 2,
    ):
        """
        Initialize the numerical input dialog with its GUI elements.

        Parameters
        ----------
        query : str
            The text to display on the label above the input field.
        timeout : float or None
            Timeout in seconds before dialog automatically
            closes. None means no timeout.
        parent : QWidget, optional
            The parent widget of the dialog.
        default_value : float, optional
            Default value to show in input field.
        min_value : float, optional
            Minimum value for the QDoubleSpinbox. Default is -100e9.
        max_value : float, optional
            Maximum value for the QDoubleSpinbox. Default is 100e9.
        step : float, optional
            Step size for the QDoubleSpinbox. Default is 1.0.
        decimals : int, optional
            Number of decimal places. Default is 2.
        """
        super().__init__(query, timeout, parent=parent, default_value=default_value)

        self.input_spinbox = QDoubleSpinBox(self)
        if min_value is not None:
            self.input_spinbox.setMinimum(min_value)
        if max_value is not None:
            self.input_spinbox.setMaximum(max_value)
        if step is not None:
            self.input_spinbox.setSingleStep(step)
        if decimals is not None:
            self.input_spinbox.setDecimals(decimals)
        if default_value is not None:
            self.input_spinbox.setValue(default_value)
        self.input_spinbox.setToolTip(
            f"Enter a numerical value (Range: {min_value} to {max_value})"
        )
        self.input_widget = self.input_spinbox

        self.setup_layout()

    def get_input_value(self):
        """
        Get the value from the spinbox.

        Returns
        -------
        float
        The user input value.
        """
        return self.input_spinbox.value()


class YesNoAbortDialog(TimeoutDialogBase):
    """Modal dialog for boolean input."""

    def __init__(
        self,
        question: str,
        timeout: float | None,
        *,
        parent: QWidget | None = None,
        default_value: str = "yes",
    ):
        """
        Initialize the yes/no dialog with a question and buttons.

        Parameters
        ----------
        question : str
            The question to display on the label.
        timeout : float or None
            Timeout in seconds before dialog automatically
            returns default_value. None means no timeout.
        parent : QWidget, optional
            The parent widget of the dialog.
        default_value : str, optional
            Default value to return if timeout occurs.
            Should be "Yes", "No", or empty.
        """
        self._default_value = (
            default_value.lower() if default_value.lower() in ["yes", "no"] else "yes"
        )
        self._timeout_occurred = False
        self._response = "yes"  # Track which button was clicked
        super().__init__(question, timeout, parent=parent, default_value=self._default_value)

        # Hide the ok_button from TimeoutDialogBase (we use yes/no instead)
        self.ok_button.hide()

        self.yes_button = QPushButton("Yes", self)
        self.no_button = QPushButton("No", self)

        self.yes_button.clicked.connect(lambda: setattr(self, "_response", "yes"))
        self.yes_button.clicked.connect(self._button_clicked)
        self.yes_button.clicked.connect(self.accept)
        self.no_button.clicked.connect(lambda: setattr(self, "_response", "no"))
        self.no_button.clicked.connect(self._button_clicked)
        self.no_button.clicked.connect(self.accept)

        self.setup_layout(answer_buttons=[self.yes_button, self.no_button])

    def accept(self):
        """Track timeout before accepting."""
        if hasattr(self, "timer") and not self.user_responded:
            self._timeout_occurred = True
        super().accept()

    def get_response(self) -> str:
        """
        Show the dialog and return the user's yes/no response.

        Assumes the caller will handle abort/finish via ``result()``.

        Returns
        -------
        str
            "yes" or "no" (or default_value on timeout).
        """
        self.exec()
        if self._timeout_occurred and not self.user_responded:
            return self._default_value
        return self._response
