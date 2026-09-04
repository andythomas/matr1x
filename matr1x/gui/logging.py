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
"""The logging window and its Qt logging handlers."""

import logging
import re
from typing import ClassVar

from PySide6.QtCore import (
    QObject,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QCloseEvent,
    QColor,
    QHideEvent,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .widgets import ReadOnlyTable

logger = logging.getLogger(__name__)


class _LogSignalHelper(QObject):
    """Provide signals for QTableLogger without conflicts."""

    log_record_received = Signal(list)
    error_received = Signal()


class _QTableLogger(logging.Handler):
    """Provide a table view for the log messages."""

    WARNING_COLOR = QColor("#FF9F43")
    ERROR_COLOR = QColor("#FF6B6B")
    DEBUG_COLOR = QColor("royalblue")

    def __init__(self, widget: QTableWidget, fields: list[str], separator: str) -> None:
        """
        Set all items.

        Parameters
        ----------
        widget: QTableWidget
            The table widget to display the log messages.
        fields: list[str]
            The fields used in the log-record.
        separator: str
            The separator used in the log-record.
        """
        super().__init__()
        self.widget = widget
        self.fields = fields
        self.separator = separator
        self.max_rows = 1000
        self.levelname_column = (
            self.fields.index("levelname") if "levelname" in self.fields else None
        )
        self._signal_helper = _LogSignalHelper()
        self._signal_helper.log_record_received.connect(
            self._add_log_to_table, Qt.ConnectionType.QueuedConnection
        )

    def emit(self, record: logging.LogRecord) -> None:
        """
        Add a log record as a new row in the table.

        This method is thread-safe by emitting a signal that will be
        processed on the main thread.

        Parameters
        ----------
        record: logging.LogRecord
            The log record to add.
        """
        log_line = self.format(record)
        parts = log_line.split(self.separator)
        self._signal_helper.log_record_received.emit(parts)
        if record.levelno > logging.WARNING:
            self._signal_helper.error_received.emit()

    def _add_log_to_table(self, parts: list[str]) -> None:
        """
        Add log parts to table widget (runs on main thread).

        Parameters
        ----------
        parts: list[str]
            The formatted log message parts.
        """
        if self.widget.rowCount() >= self.max_rows:
            self.widget.removeRow(0)
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        row_position = self.widget.rowCount()
        self.widget.insertRow(row_position)
        for column, part in enumerate(parts):
            # a hard crash goes to stderr and is logged in the table
            # -> remove the ansi sequences.
            pure_text = ansi_escape.sub("", str(part))
            item = QTableWidgetItem(pure_text)
            if column == self.levelname_column:
                if part == "ERROR":
                    item.setForeground(QBrush(_QTableLogger.ERROR_COLOR))
                elif part == "WARNING":
                    item.setForeground(QBrush(_QTableLogger.WARNING_COLOR))
                elif part == "DEBUG":
                    item.setForeground(QBrush(_QTableLogger.DEBUG_COLOR))
            self.widget.setItem(row_position, column, item)
        self.widget.scrollToBottom()


class LoggingWindow(QMainWindow):
    """Detached window to display logging messages."""

    LOG_FIELDS: ClassVar[list[str]] = ["asctime", "name", "levelname", "message"]
    LOG_SEPARATOR = "\x1f"

    visibility_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setWindowTitle("Log Messages")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        self.log_table = ReadOnlyTable()
        self.log_table.setColumnCount(len(LoggingWindow.LOG_FIELDS))
        self.log_table.setHorizontalHeaderLabels(
            [field.title() for field in LoggingWindow.LOG_FIELDS]
        )
        self.log_table.setAlternatingRowColors(True)
        self.log_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.log_table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        header = self.log_table.horizontalHeader()
        header.setStretchLastSection(True)
        if len(LoggingWindow.LOG_FIELDS) >= 4:
            self.log_table.setColumnWidth(0, 80)  # asctime
            self.log_table.setColumnWidth(1, 150)  # name
            self.log_table.setColumnWidth(2, 80)  # levelname
        layout.addWidget(self.log_table)
        level_layout = QHBoxLayout()
        level_label = QLabel("Log Level:")
        self.level_combo = QComboBox()
        levels = [
            ("DEBUG", logging.DEBUG),
            ("INFO", logging.INFO),
            ("WARNING", logging.WARNING),
            ("ERROR", logging.ERROR),
            ("CRITICAL", logging.CRITICAL),
        ]
        current_level = logging.getLogger().level
        current_index = 1
        for i, (name, level) in enumerate(levels):
            self.level_combo.addItem(name, level)
            if level == current_level:
                current_index = i
        self.level_combo.setCurrentIndex(current_index)
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)
        level_layout.addWidget(level_label)
        level_layout.addWidget(self.level_combo)
        level_layout.addStretch()
        clear_button = QPushButton("Clear table")
        clear_button.clicked.connect(self._clear)
        level_layout.addWidget(clear_button)
        layout.addLayout(level_layout)
        self.log_handler = _QTableLogger(
            self.log_table, LoggingWindow.LOG_FIELDS, LoggingWindow.LOG_SEPARATOR
        )
        formatter = logging.Formatter(
            LoggingWindow.LOG_SEPARATOR.join(f"%({field})s" for field in LoggingWindow.LOG_FIELDS),
            datefmt="%H:%M:%S",
        )
        self.log_handler.setFormatter(formatter)
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        self.log_handler._signal_helper.error_received.connect(
            self.show, Qt.ConnectionType.QueuedConnection
        )

    def showEvent(self, event: QShowEvent) -> None:
        """Emit visibility state changes when the window shows."""
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def hideEvent(self, event: QHideEvent) -> None:
        """Emit visibility state changes when the window hides."""
        super().hideEvent(event)
        self.visibility_changed.emit(False)

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Prevent destruction when the user presses the close button.

        The logging window is hidden instead to keep the C++ object alive.
        """
        event.ignore()
        self.hide()

    def _on_level_changed(self):
        """Handle logging level change from combobox."""
        selected_level = self.level_combo.currentData()
        root_logger = logging.getLogger()
        root_logger.setLevel(selected_level)

    def _clear(self):
        """Clear the table."""
        self.log_table.clearContents()
        self.log_table.setRowCount(0)
