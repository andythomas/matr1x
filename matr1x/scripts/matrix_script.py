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
"""Allow to write measurement scripts in Python."""

import logging
import platform
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from PySide6.QtCore import (
    QEvent,
    QPoint,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QColor,
    QFontDatabase,
    QKeyEvent,
    QKeySequence,
    QPalette,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import matr1x
from matr1x.editor import CodeEditor
from matr1x.error_handling import Error, install_error_handler
from matr1x.gui_util import (
    AboutBox,
    AutoSlot,
    ConfigEditWidget,
    FileDropMixin,
    LoggingWindow,
    LogWindowMixin,
    MApplication,
    check_config,
    create_matr1x_quit_action,
    create_matrix_settings_action,
    detect_shortcut,
    find_parent_of_type,
    get_matrix_icon,
    open_matrix_toml,
    save_messagebox,
)
from matr1x.models import (
    Datafile,
    Envelope,
    ErrorMessage,
    ExecutionLines,
    Header,
    InputParameters,
    LogEntry,
    MeasuredValues,
    Message,
    Modifier,
    SetValues,
    Telemetry,
)
from matr1x.post_install import (
    check_desktop_integration,
    post_installation,
    remove_desktop_integration,
)
from matr1x.scripts.shared_classes import (
    ContentDockWidget,
    MeasurementItem,
    MeasurementTable,
    MeasurementThread,
    MeasurementUI,
    MetaDataDialog,
    MMainWindow,
    MToolBar,
    Notifier,
    NotifierMessage,
    SaferQSettings,
    SystemListWidget,
)
from matr1x.util import StreamToLogger, generate_script, get_script_prefix_offset

logger = logging.getLogger(__name__)
script_config = matr1x.config.matr1x.scripts.matrix_script


MAX_LINES_STATUS = 10000
# to test what a good limiting value is, use the following:
# ```
# for i in range(1000):
#   print(f"{i}" + 10*"snsnsnsnsn\n" + f"{i}")
#   wait(0.1)
# ```
# By setting the appropriate wait and multiplier, the highest expected
# number of lines/s can be set (here 110 lines/s). With this in place
# run matrix-script until it reaches the limit and see whether the
# display perforamnce of the GUI drops.


help_text = (
    """
MATRIX SCRIPT HELP

The available functions are listed in the following lines. Please use hover (mouseover) """
    """in the left editor window to get more specific information about a particular function. """
    """Furthermore, auto-completion will try to suggest possible parameters.

set_value(value_index/name, value)
trigger_value(value_index/name)
read_value(value_index/name)
wait(seconds, until, message, silent)
input(query, timeout, default_value)
input_bool(query, timeout, default_value)
input_numerical(query, timeout, default_value, min_value, max_value, step, decimals)
end_script(finished)
print(*args, sep, end, file, flush)
init_datafile(filename, comment, append, print_header, ntot,
              reset_meta_data, reset_date)
measure_system(print_setpoint, print_data, print_telemetry)

In addition, the following variables are available. Please use help to get a list of """
    """available parameters and devices. Note that user variable names must not start with """
    """an underscore!

devs  # dictionary that contains all devices
system  # merged system object from the selected systems
meta_data  # dictionary that contains all meta information

---

"""
)

T = TypeVar("T")
R = TypeVar("R")


class CentralWidget(FileDropMixin, QWidget):
    """Enable drag and drop of matrix files."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setValidExtensions([MainWindow.extension])


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
            Timeout in seconds before dialog automatically closes. None means no timeout.
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

        # Termination buttons (abort / finish)
        self.abort_aborted_button = QPushButton("Abort", self)
        self.abort_aborted_button.setIcon(get_matrix_icon("CUSTOM_Stop", color=QColor("#B71C1C")))
        self.abort_finished_button = QPushButton("Finish", self)
        self.abort_finished_button.setIcon(get_matrix_icon("CUSTOM_Stop", color=QColor("#388E3C")))

        self.abort_aborted_button.clicked.connect(self._button_clicked)
        self.abort_aborted_button.clicked.connect(lambda: self.done(2))
        self.abort_finished_button.clicked.connect(self._button_clicked)
        self.abort_finished_button.clicked.connect(lambda: self.done(3))

        # Ensure the dialog stays on top of the main window
        self.setWindowModality(Qt.WindowModality.ApplicationModal)

        # Set up timer if timeout is finite
        if self.timeout != float("inf"):
            self.remaining_time = self.timeout * 1000  # Convert to milliseconds
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

        self.remaining_time -= 100  # Decrement by 100ms

        if self.remaining_time <= 0:
            if not self.user_responded:
                self.timer.stop()
                self.accept()
            return

        # Convert milliseconds back to seconds for display
        remaining_seconds = self.remaining_time / 1000

        # Format the time display
        if remaining_seconds < 100:
            # Show seconds for short timeouts
            self.timer_label.setText(f"Time remaining: {int(remaining_seconds)} seconds")
        else:
            # Show hours:minutes format for longer timeouts
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

        # Query group
        query_group = QGroupBox("Query", self)
        query_layout = QVBoxLayout(query_group)
        query_layout.addWidget(self.label)
        if self.input_widget:
            query_layout.addWidget(self.input_widget)
        query_layout.addWidget(self.timer_label)

        # Answer row (ok_button or custom buttons)
        answer_layout = QHBoxLayout()
        if answer_buttons is None:
            answer_layout.addWidget(self.ok_button)
        else:
            for button in answer_buttons:
                answer_layout.addWidget(button)
        query_layout.addLayout(answer_layout)
        main_layout.addWidget(query_group)
        main_layout.addSpacing(12)

        # End Script group
        end_group = QGroupBox("End Script", self)
        end_layout = QHBoxLayout(end_group)
        end_layout.addWidget(self.abort_aborted_button)
        end_layout.addWidget(self.abort_finished_button)
        main_layout.addWidget(end_group)

        # Fixed dialog size - no resizing
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
    """Modal dialog for text input for matrix-script."""

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
            Timeout in seconds before dialog automatically closes. None means no timeout.
        parent : QWidget, optional
            The parent widget of the dialog.
        default_value : str, optional
            Default value to show in input field.
        """
        super().__init__(query, timeout, parent=parent, default_value=default_value)

        # Create the input widget
        self.input = QLineEdit(self)
        self.input.setPlaceholderText("input to send to script")
        self.input.setText(default_value)
        self.input_widget = self.input

        # Set up the layout
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
    """Modal dialog for numerical input for matrix-script."""

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
            Timeout in seconds before dialog automatically closes. None means no timeout.
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

        # Create the spinbox
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

        # Set up the layout
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
    """Modal dialog for boolean input for matrix-script."""

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
            Timeout in seconds before dialog automatically returns default_value.
            None means no timeout.
        parent : QWidget, optional
            The parent widget of the dialog.
        default_value : str, optional
            Default value to return if timeout occurs. Should be "Yes", "No", or empty.
        """
        self._default_value = (
            default_value.lower() if default_value.lower() in ["yes", "no"] else "yes"
        )
        self._timeout_occurred = False
        self._response = "yes"  # Track which button was clicked
        super().__init__(question, timeout, parent=parent, default_value=self._default_value)

        # Hide the ok_button from TimeoutDialogBase (we use yes/no instead)
        self.ok_button.hide()

        # Create yes/no buttons
        self.yes_button = QPushButton("Yes", self)
        self.no_button = QPushButton("No", self)

        self.yes_button.clicked.connect(lambda: setattr(self, "_response", "yes"))
        self.yes_button.clicked.connect(self._button_clicked)
        self.yes_button.clicked.connect(self.accept)
        self.no_button.clicked.connect(lambda: setattr(self, "_response", "no"))
        self.no_button.clicked.connect(self._button_clicked)
        self.no_button.clicked.connect(self.accept)

        # Build layout with yes/no buttons in answer row
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


class TerminalOutput(QPlainTextEdit):
    """
    Custom class for terminal-like text output.

    Init the class with a mono-spaced font and respect theme.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)
        mono_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono_font.setPointSizeF(self.font().pointSize())
        self.setFont(mono_font)
        self.updateColors()
        MApplication.instance().isDarkSignal.connect(self.updateColors)

    def updateColors(self) -> None:
        """Update terminal colors based on system theme."""
        palette = self.palette()
        text_edit = QPlainTextEdit()
        text_edit.setEnabled(False)
        changed_palette = text_edit.palette()
        palette.setColor(
            QPalette.ColorRole.Base,
            QColor(changed_palette.color(QPalette.ColorRole.Base)),
        )
        self.setPalette(palette)

    def print_colored(self, line: str) -> None:
        """
        Print a colored text.

        Parameters
        ----------
        line : str
            The line to be printed.
        """
        scrollbar = self.verticalScrollBar()
        at_bottom = scrollbar.value() == scrollbar.maximum()
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        text_char_format = QTextCharFormat()
        text_char_format.setForeground(QColor("royalblue"))
        cursor.insertText(line, text_char_format)
        cursor.insertText("\n", QTextCharFormat())
        if at_bottom:
            self.moveCursor(QTextCursor.MoveOperation.End)


if sys.platform == "win32":
    try:
        from ctypes import windll

        myappid = "python.matr1x.matrix-script.version"
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass


@dataclass(frozen=True)
class ActionGroup:
    """Actions to be utilized in the GUI."""

    matrix_settings: QAction
    config: QAction
    new_file: QAction
    load: QAction
    save: QAction
    save_as: QAction
    add_system: QAction
    remove_system: QAction
    quit_app: QAction
    undo: QAction
    redo: QAction
    cut: QAction
    copy: QAction
    paste: QAction
    line_comment: QAction
    zoom_in: QAction
    zoom_out: QAction
    print: QAction
    find: QAction
    start: QAction
    pause: QAction
    abort: QAction
    finish: QAction
    kill: QAction
    preview: QAction
    pep8: QAction
    autocomplete: QAction
    show_log: QAction
    system_help: QAction
    theme_actions: list[QAction]
    theme_group: QActionGroup
    post_install: QAction
    remove_desktop_integration: QAction


@dataclass
class WidgetGroup:
    """Widgets to be used in the GUI."""

    dockable_metadata: ContentDockWidget
    meta_view: MetaDataDialog
    system_list: SystemListWidget
    status_preview: TerminalOutput
    script_edit: CodeEditor
    system_command_help: QDialog
    system_command_text_edit: QTextEdit
    config_editor: ConfigEditWidget
    save_button: QToolButton
    stop_button: QToolButton
    terminal_dock: ContentDockWidget
    table: MeasurementTable
    table_dock: ContentDockWidget
    central_widget: CentralWidget
    python_info: QLabel
    lsp_info: QLabel
    save_pulldown: QMenu
    stop_pulldown: QMenu
    about_box: AboutBox
    measurement_thread: MeasurementThread
    measurement_ui: MeasurementUI
    notifier: Notifier
    progress: QLabel
    progressbar: QProgressBar


class UIBuilder:
    """Create the GUI elements."""

    def __init__(self):
        self.widgets: WidgetGroup = self._create_widgets()
        self.actions: ActionGroup = self._create_actions()
        self.toolbar: MToolBar = self._create_toolbar()
        self.menubar: QMenuBar = self._create_menu()
        self._create_gui()

    def _standard_action(self, name: str, display_name: str | None = None) -> QAction:
        """
        Create and return a standard action such as 'Undo'.

        Also connects the action with a system agnostic shortcut and
        with the corresponding method.

        Parameters
        ----------
        name : str
            The name of the method as in QKeySequence.StandardKey.
        display_name : str, optional
            The name to be displayed in menu and toolbar.

        Returns
        -------
        QAction
            The action.
        """
        if not display_name:
            display_name = name
        action = QAction(display_name)
        action.setShortcut(getattr(QKeySequence.StandardKey, name))
        method_name = name[:1].lower() + name[1:]
        action.triggered.connect(lambda checked, method=method_name: self._standard_method(method))
        return action

    def _standard_method(self, method_name: str) -> None:
        """
        Perform a standard method such as 'undo' on the focussed widget.

        Parameters
        ----------
        method_name : str
            The name of the method.
        """
        focus_widget = MApplication.focusWidget()
        webview = None

        if focus_widget is not None:
            webview = find_parent_of_type(focus_widget, QWebEngineView)
        if isinstance(webview, QWebEngineView):
            focus_widget = webview

        try:
            method = getattr(focus_widget, method_name)
            if callable(method):
                method()
        except AttributeError:
            pass

    def _create_widgets(self) -> WidgetGroup:
        """
        Create all widgets for the GUI.

        Returns
        -------
        WidgetGroup
            The dataclass with all the widgets.
        """
        meta_view = MetaDataDialog()
        dockable_metadata = ContentDockWidget(
            "Metadata",
            "dockable_metadata",
            "SP_FileDialogListView",
            "Ctrl+2",
            meta_view,
            areas=(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea),
        )
        system_list = SystemListWidget()
        status_preview = TerminalOutput()
        status_preview.document().setMaximumBlockCount(MAX_LINES_STATUS)
        progress = QLabel("Measurement idle.")
        progressbar = QProgressBar()
        script_edit = CodeEditor()
        system_command_help = QDialog()
        box_layout = QVBoxLayout()
        system_command_text_edit = QTextEdit()
        system_command_text_edit.setReadOnly(True)
        box_layout.addWidget(system_command_text_edit)
        system_command_help.setLayout(box_layout)
        title = "Selected systems information"
        system_command_help.setWindowTitle(title)
        system_command_help.setWindowModality(Qt.WindowModality.NonModal)
        save_button = QToolButton()
        save_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        save_button.setIcon(get_matrix_icon("SP_DialogSaveButton"))
        save_button.setText("Save")
        stop_button = QToolButton()
        stop_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        stop_button.setIcon(get_matrix_icon("CUSTOM_Stop"))
        stop_button.setText("Abort")
        terminal_dock = ContentDockWidget(
            "Terminal", "terminal_dock", "CHAR_T", "Ctrl+4", status_preview
        )
        table = MeasurementTable()
        table_dock = ContentDockWidget("Table", "table_dock", "CHAR_M", "Ctrl+5", table)
        central_widget = CentralWidget()
        python_info = QLabel(f"Python {platform.python_version()}")
        python_info.setToolTip(f"Python: {sys.version}")
        lsp_info = QLabel(f"LSP: {script_edit.lsp_tc.server.name}")
        lsp_info.setToolTip(f"{script_edit.lsp_tc.server.binary}")
        save_pulldown = QMenu()
        stop_pulldown = QMenu()

        return WidgetGroup(
            dockable_metadata=dockable_metadata,
            meta_view=meta_view,
            system_list=system_list,
            status_preview=status_preview,
            script_edit=script_edit,
            system_command_help=system_command_help,
            system_command_text_edit=system_command_text_edit,
            config_editor=ConfigEditWidget(),
            save_button=save_button,
            stop_button=stop_button,
            terminal_dock=terminal_dock,
            table=table,
            table_dock=table_dock,
            central_widget=central_widget,
            python_info=python_info,
            lsp_info=lsp_info,
            save_pulldown=save_pulldown,
            stop_pulldown=stop_pulldown,
            about_box=AboutBox(
                "Matrix Script",
                get_matrix_icon("matr1x-matrix-script.png"),
                matr1x,
                matr1x.datetimefmt,
            ),
            measurement_thread=MeasurementThread(),
            measurement_ui=MeasurementUI(),
            notifier=Notifier(logger),
            progress=progress,
            progressbar=progressbar,
        )

    def _create_actions(self) -> ActionGroup:
        """
        Create all required actions.

        Returns
        -------
        ActionGroup
            The dataclass with all the actions.
        """
        new_file = QAction(get_matrix_icon("SP_FileIcon"), "New")
        new_file.setShortcut(QKeySequence.StandardKey.New)
        load = QAction(get_matrix_icon("SP_DialogOpenButton"), "Open")
        load.setToolTip("Open a script file.")
        load.setShortcut(QKeySequence.StandardKey.Open)
        save = QAction(get_matrix_icon("SP_DialogSaveButton"), "Save")
        save.setToolTip("Save the under the current filename.")
        save.setShortcut(QKeySequence.StandardKey.Save)
        save_as = QAction(get_matrix_icon("SP_DialogSaveButton"), "Save As...")
        save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.widgets.save_button.setDefaultAction(save)
        self.widgets.save_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.widgets.save_pulldown.addAction(save_as)
        self.widgets.save_button.setMenu(self.widgets.save_pulldown)
        caption = "Toggle Line Comment\t" + script_config.shortcuts.line_comment_display
        line_comment = QAction(caption)
        line_comment.setShortcut(QKeySequence(script_config.shortcuts.line_comment_shortcut))
        print_action = QAction("Print")
        print_action.setShortcut(QKeySequence.StandardKey.Print)
        find = QAction("Find")
        find.setShortcut(QKeySequence.StandardKey.Find)
        preview = QAction(
            get_matrix_icon("matr1x-matrix-preview.png", QColor("RoyalBlue")),
            "Preview",
        )
        preview.setEnabled(False)
        pep8 = QAction("Format with ruff")
        pep8.setShortcut(QKeySequence("Ctrl+8"))
        theme_actions = []
        theme_group = QActionGroup(MApplication.instance())
        theme_group.setExclusionPolicy(QActionGroup.ExclusionPolicy.Exclusive)
        for theme in self.widgets.script_edit.supportedThemes():
            action = QAction(theme)
            action.setCheckable(True)
            if theme == self.widgets.script_edit.supportedThemes()[0]:
                action.setChecked(True)
            action.triggered.connect(
                lambda checked=False, theme=theme: self.widgets.script_edit.setTheme(theme)
            )
            theme_group.addAction(action)
            theme_actions.append(action)
        autocomplete = QAction("Tab completion")
        autocomplete.setCheckable(True)
        autocomplete.setChecked(True)

        return ActionGroup(
            matrix_settings=create_matrix_settings_action(),
            config=self.widgets.config_editor.action,
            new_file=new_file,
            load=load,
            save=save,
            save_as=save_as,
            add_system=self.widgets.system_list.add_action,
            remove_system=self.widgets.system_list.remove_action,
            quit_app=create_matr1x_quit_action(),
            undo=self._standard_action("Undo"),
            redo=self._standard_action("Redo"),
            cut=self._standard_action("Cut"),
            copy=self._standard_action("Copy"),
            paste=self._standard_action("Paste"),
            line_comment=line_comment,
            zoom_in=self._standard_action("ZoomIn", "Zoom in"),
            zoom_out=self._standard_action("ZoomOut", "Zoom Out"),
            print=print_action,
            find=find,
            start=self.widgets.measurement_ui.start,
            pause=self.widgets.measurement_ui.pause,
            abort=self.widgets.measurement_ui.abort,
            finish=self.widgets.measurement_ui.finish,
            kill=self.widgets.measurement_ui.kill,
            preview=preview,
            pep8=pep8,
            autocomplete=autocomplete,
            show_log=LogWindowMixin.create_show_log_action(),
            system_help=QAction("Show System Help"),
            theme_actions=theme_actions,
            theme_group=theme_group,
            post_install=LogWindowMixin.create_post_install_action(),
            remove_desktop_integration=LogWindowMixin.create_remove_desktop_integration_action(),
        )

    def _create_toolbar(self) -> MToolBar:
        """Create the toolbar."""
        toolbar = MToolBar("Toolbar")
        toolbar.addAction(self.actions.new_file)
        toolbar.addAction(self.actions.load)
        toolbar.addWidget(self.widgets.save_button)
        toolbar.addWidget(toolbar.empty)
        self.widgets.measurement_ui.add_to_toolbar(toolbar)
        toolbar.addWidget(toolbar.empty)
        toolbar.addAction(self.actions.preview)
        toolbar.addWidget(toolbar.empty)
        toolbar.addSeparator()
        self.widgets.system_list.add_to_toolbar(toolbar)
        toolbar.addSeparator()
        toolbar.addAction(self.widgets.dockable_metadata.action)
        toolbar.addAction(self.actions.config)
        return toolbar

    def _create_menu(self) -> QMenuBar:
        """Create the main menu."""
        menu = QMenuBar()
        file = menu.addMenu("&File")
        file.addAction(self.actions.new_file)
        file.addAction(self.actions.load)
        file.addSeparator()
        file.addAction(self.actions.save)
        file.addAction(self.actions.save_as)
        file.addSeparator()
        self.widgets.system_list.add_actions_to_menu(file)
        file.addSeparator()
        file.addAction(self.actions.print)
        file.addSeparator()
        file.addAction(self.actions.quit_app)  # This gets auto-moved on a Mac
        edit = menu.addMenu("&Edit")
        edit.addAction(self.actions.undo)
        edit.addAction(self.actions.redo)
        edit.addSeparator()
        edit.addAction(self.actions.cut)
        edit.addAction(self.actions.copy)
        edit.addAction(self.actions.paste)
        edit.addSeparator()
        edit.addAction(self.actions.find)
        edit.addSeparator()
        edit.addAction(self.actions.line_comment)
        edit.addSeparator()
        edit.addAction(self.actions.pep8)
        editor = menu.addMenu("&Editor")
        theme = editor.addMenu("Theme")
        for action in self.actions.theme_actions:
            theme.addAction(action)
        editor.addSeparator()
        editor.addAction(self.actions.zoom_in)
        editor.addAction(self.actions.zoom_out)
        editor.addSeparator()
        editor.addAction(self.actions.autocomplete)
        control = menu.addMenu("&Control")
        self.widgets.measurement_ui.add_to_menu(control)
        control.addSeparator()
        control.addAction(self.actions.preview)
        view = menu.addMenu("&View")
        view.addAction(self.toolbar.action)
        view.addAction(self.widgets.dockable_metadata.action)
        view.addAction(self.actions.config)
        view.addAction(self.widgets.terminal_dock.action)
        view.addAction(self.widgets.table_dock.action)
        view.addSeparator()
        view.addAction(self.actions.matrix_settings)
        help_menu = menu.addMenu("&Help")
        help_menu.addAction(self.actions.system_help)
        LogWindowMixin.add_common_help_actions(help_menu, self.actions)
        help_menu.addAction(self.widgets.about_box.action)
        return menu

    def _create_gui(self) -> None:
        """Create and set up the main GUI."""
        layout = QVBoxLayout(self.widgets.central_widget)
        layout.addWidget(self.widgets.notifier)
        layout.setSpacing(6)
        layout.setContentsMargins(11, 4, 11, 11)
        layout.addWidget(self.widgets.script_edit, 1)
        infobar = QVBoxLayout()
        info_row = QHBoxLayout()
        info_row.addWidget(self.widgets.progress, 1)
        info_row.addWidget(self.widgets.python_info)
        info_row.addWidget(QLabel("  |  "))
        info_row.addWidget(self.widgets.lsp_info)
        infobar.addLayout(info_row)
        infobar.addWidget(self.widgets.progressbar)
        layout.addLayout(infobar, 0)


class MainWindow(LogWindowMixin, MMainWindow):
    """
    Run the logical code.

    Parameters
    ----------
    filename: str, optional
        The file to load automatically.
    """

    extension = ".matrix"

    def __init__(self, filename: Path | None = None):
        super().__init__()
        self.in_pytest = False
        self.log_window = LoggingWindow(parent=self)  # Immediately needed, not moved to widgets!
        self.log_window.hide()
        logger.info("matrix-script starting")
        self.scriptname: Path | None = None
        self.line_offset = get_script_prefix_offset()
        self.measurement_file: Path
        self.is_running = False
        self.measurement_failed = False
        self.shortcut_dir: tempfile.TemporaryDirectory[str] | None = None
        self.last_filename: Path | None = None
        self.settings = SaferQSettings("matr1x", "script")
        self._output_buffer: list[str] = []
        self._output_timer = QTimer()
        self._output_timer.timeout.connect(self._flush_output_buffer)
        self._output_timer.setSingleShot(False)
        self._output_timer.setInterval(50)
        self.setWindowIcon(get_matrix_icon("matr1x-matrix-script.png"))
        self.ui: UIBuilder = UIBuilder()
        self.ui.actions.start.setEnabled(True)
        self.ui.widgets.script_edit.setValidExtensions([self.extension])
        self.setMenuBar(self.ui.menubar)
        self.addToolBar(self.ui.toolbar)
        self.install_metadata_config_docks(
            self.ui.widgets.dockable_metadata,
            self.ui.widgets.config_editor,
        )
        self.setCentralWidget(self.ui.widgets.central_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.ui.widgets.table_dock)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.ui.widgets.terminal_dock)
        self.create_connections()
        self.ui.widgets.script_edit.setFocus()  # this does not do anything?!
        self.update_window_title()
        check_config(matr1x.config, self.ui.widgets.notifier)
        sys.stdout = StreamToLogger(logger, logging.INFO)
        sys.stderr = StreamToLogger(logger, logging.ERROR)
        if filename is not None:
            self.load_from_filename(filename)
        else:
            self.update_systems()
        self.ui.widgets.status_preview.appendPlainText(help_text)
        check_desktop_integration()

    def create_connections(self) -> None:
        """Connect actions and widgets with application logic."""
        self.ui.actions.matrix_settings.triggered.connect(open_matrix_toml)
        self.ui.actions.new_file.triggered.connect(self.new_file)
        self.ui.actions.load.triggered.connect(self.load_from_file)
        self.ui.actions.save.triggered.connect(self.save_file)
        self.ui.actions.save_as.triggered.connect(self.save_file_as)
        self.ui.widgets.system_list.changed.connect(self.update_systems)
        self.ui.widgets.config_editor.model.dataChanged.connect(self.update_start_action_state)
        self.ui.widgets.config_editor.model.validationChanged.connect(
            self.update_start_action_state
        )
        self.ui.widgets.config_editor.model.modelReset.connect(self.update_start_action_state)
        self.ui.actions.print.triggered.connect(self.print_document)
        self.ui.actions.quit_app.triggered.connect(self.close)
        self.ui.actions.find.triggered.connect(self.ui.widgets.script_edit.show_find)
        self.ui.actions.line_comment.triggered.connect(
            self.ui.widgets.script_edit.toggleLineComment
        )
        self.ui.actions.pep8.triggered.connect(self.ui.widgets.script_edit.formatCode)
        self.ui.actions.autocomplete.toggled.connect(
            self.ui.widgets.script_edit.enableTabCompletion
        )
        self.ui.actions.start.triggered.connect(self.start_process)
        self.ui.actions.pause.triggered.connect(lambda: self.ui.widgets.measurement_thread.pause())
        self.ui.actions.abort.triggered.connect(
            lambda: self.ui.widgets.measurement_thread.abort("a")
        )
        self.ui.actions.finish.triggered.connect(
            lambda: self.ui.widgets.measurement_thread.abort("f")
        )
        self.ui.actions.kill.triggered.connect(self.kill_thread)
        self.ui.actions.preview.triggered.connect(self.preview_data)
        self.ui.actions.system_help.triggered.connect(self.show_system_commands)
        self.ui.actions.post_install.triggered.connect(post_installation)
        self.ui.actions.remove_desktop_integration.triggered.connect(remove_desktop_integration)
        self.ui.actions.show_log.triggered.connect(self.toggle_log_window)
        self.log_window.visibility_changed.connect(
            lambda visible: self._on_log_window_visibility_changed(visible, self.ui.actions)
        )
        self._on_log_window_visibility_changed(self.log_window.isVisible(), self.ui.actions)
        self.ui.widgets.script_edit.contentModified.connect(self.update_window_title)
        self.ui.widgets.script_edit.file_dropped.connect(self._load_file_from_signal)
        self.ui.widgets.system_list.message.connect(self.ui.widgets.notifier.show_message)
        self.ui.widgets.system_list.changed.connect(
            lambda: self.ui.widgets.script_edit.setModified(True)
        )
        self.ui.widgets.central_widget.file_dropped.connect(self._load_file_from_signal)

    def update_start_action_state(self, *_args) -> None:
        """Enable Start only when the editor configuration is valid."""
        if self.is_running:
            self.ui.actions.start.setEnabled(False)
            self.ui.actions.start.setToolTip("A measurement is currently running.")
            return

        config_validation = self.ui.widgets.config_editor.validate_config()
        if isinstance(config_validation, Error):
            self.ui.widgets.config_editor.show_for_validation_errors()
            self.ui.actions.start.setEnabled(False)
            self.ui.actions.start.setToolTip(
                "Fix the invalid configuration entries before running:\n\n"
                + config_validation.error
            )
            return

        self.ui.actions.start.setEnabled(True)
        self.ui.actions.start.setToolTip("Start the measurement.")

    @AutoSlot
    def process_data(self, env: Envelope) -> None:
        """Process the data from the measurement thread."""
        data = env.payload
        if isinstance(data, Telemetry):
            self.ui.widgets.progressbar.setMaximum(data.points)
            self.ui.widgets.progressbar.setValue(data.point)
            if data.remaining is not None:
                self.ui.widgets.progress.setText(str(data))
            if data.to_stdout:
                self.write_output(str(data) + "\n")
        elif isinstance(data, (Header, SetValues, MeasuredValues)):
            self.ui.widgets.table.apply(data)
            if data.to_stdout:
                self.write_output(str(data) + "\n")
        elif isinstance(data, ExecutionLines):
            self.ui.widgets.script_edit.highlight([line - self.line_offset for line in data.lines])
        elif isinstance(data, Datafile):
            self.update_filename(data.datafile)
        elif isinstance(data, InputParameters):
            self._get_script_input(data)
        elif isinstance(data, Message):
            if data.modifier == Modifier.DELETE_CURRENT_LINE:
                self.write_output("\r" + data.message + data.end)
            else:
                self.write_output(data.message + data.end)
        elif isinstance(data, ErrorMessage):
            self.show_message(NotifierMessage(data.error, level=logging.ERROR))
            self.measurement_failed = True
        elif isinstance(data, LogEntry):
            data.log_record(logger)

    def show_message(self, message: NotifierMessage) -> None:
        """
        Show a problem in the notifier and in the terminal output.

        Parameters
        ----------
        message : NotifierMessage
            The problem to report.
        """
        self.ui.widgets.notifier.show_message(message)
        self.ui.widgets.status_preview.print_colored(message.text)

    def print_document(self) -> None:
        """Print the script."""
        text_edit = QTextEdit()  # go via QTextEdit functions for better portability
        text_edit.setText(self.ui.widgets.script_edit.toPlainText())
        printer = QPrinter()
        if QPrintDialog(printer, self).exec():
            text_edit.print_(printer)

    def save_window_state(self) -> None:
        """Save application configuration until next startup."""
        self.settings.setValue("created", 1)
        self.save_layout_state(self.settings)

        self.settings.beginGroup("script_edit")
        self.settings.setValue("monaco_zoom", self.ui.widgets.script_edit.zoomFactor())
        self.settings.setValue("theme", self.ui.actions.theme_group.checkedAction().text())
        self.settings.setValue("autocomplete", self.ui.actions.autocomplete.isChecked())
        self.settings.endGroup()

        self.save_log_window_state(self.settings)

        # Only save help dialog size and position if it has been shown at least once
        if hasattr(self, "_help_dialog_shown") and self._help_dialog_shown:
            self.settings.beginGroup("system_command_help")
            self.settings.setValue("size", self.ui.widgets.system_command_help.size())
            self.settings.setValue("position", self.ui.widgets.system_command_help.pos())
            self.settings.endGroup()

    def restore_window_state(self) -> None:
        """Restore app configuration from the previous use."""
        self.restore_layout_state(self.settings)

        # Check if there is a settings file. This improves the robustness
        # against strange side effect, caused by the default values.
        if self.settings.contains("created"):
            self.settings.beginGroup("script_edit")
            self.ui.widgets.script_edit.setZoomFactor(
                self.settings.safer_value("monaco_zoom", 1, type=float)
            )
            last_theme = self.settings.safer_value("theme", "", type=str)
            for theme in self.ui.actions.theme_actions:
                if theme.text() == last_theme:
                    theme.setChecked(True)
                    self.ui.widgets.script_edit.setTheme(last_theme)
            self.ui.actions.autocomplete.setChecked(
                self.settings.safer_value("autocomplete", True, type=bool)
            )
            self.settings.endGroup()
            self.restore_log_window_state(self.settings)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        Allow to modify systems list with keyboard shortcuts.

        Parameters
        ----------
        event: QKeyEvent
            The key-combination to be evaluated.
        """
        if self.ui.widgets.system_list.hasFocus():
            if detect_shortcut(event, QKeySequence(QKeySequence.StandardKey.Delete)):
                self.ui.widgets.system_list.delete_systems()
            if detect_shortcut(event, QKeySequence(Qt.Key.Key_Backspace)):
                self.ui.widgets.system_list.delete_systems()
        super().keyPressEvent(event)

    def closeEvent(self, event: QEvent) -> None:
        """
        Close app and ask user if script should be saved.

        If a script is running, the event is ignored and an explanation
        is given. If the script was modified without saving and not
        empty, a dialog asks how to proceed.

        Parameters
        ----------
        event : QEvent
            The received 'close event'
        """
        if self.is_running:
            QMessageBox.critical(
                QWidget(),
                "Script running!",
                """Please wait for the script to finish. Alternatively,
                stop or kill the script before exiting 'Matrix Script'!""",
            )
            event.ignore()
            return
        if (
            self.ui.widgets.script_edit.isModified()
            and self.ui.widgets.script_edit.toPlainText() != ""
            and not self.in_pytest
        ) and not save_messagebox(self, self.save_file):
            event.ignore()
            return
        self.save_window_state()
        self.ui.widgets.script_edit.lsp_tc.stop()
        self.ui.widgets.script_edit.server.stop()
        # QWebEngineView: Disconnect the webpage to prevent memory leaks
        if hasattr(self.ui.widgets.script_edit, "page") and self.ui.widgets.script_edit.page():
            self.ui.widgets.script_edit.page().loadFinished.disconnect()
            self.ui.widgets.script_edit.page().deleteLater()
        self.ui.widgets.script_edit.deleteLater()
        self.cleanup_log_window()
        self.ui.widgets.system_command_help.close()
        event.accept()

    def preview_data(self) -> None:
        """Launch matrix-preview with current measurement file."""
        preview = [
            sys.executable,
            "-c",
            (
                f"from matr1x.scripts import matrix_preview; "
                f"matrix_preview.main(file=r'{self.measurement_file}')"
            ),
        ]
        subprocess.Popen(preview)

    def _load_file_from_signal(self, filename: str) -> None:
        """Convert string to Path for opening file."""
        self.load_from_filename(Path(filename))

    def update_window_title(self) -> None:
        """Indicate if the file was edited with an asterisk."""
        text = "Matrix Script"
        if self.ui.widgets.script_edit.isModified():
            text += ": *"
        elif self.scriptname:
            text += ": "
        if self.scriptname:
            text += self.scriptname.name
        elif self.ui.widgets.script_edit.isModified():
            text += "<unsaved>"
        self.setWindowTitle(text)

    @AutoSlot
    def _get_script_input(self, params: InputParameters) -> None:
        """
        Open a dialog and forward input to the script.

        Parameters
        ----------
        params: InputParameters
            Object containing all input parameters including query,
            input_type, timeout, default_value, min_value, max_value,
            step, and decimals.
        """
        if params.input_type == "string":
            dialog = TextInputDialog(
                params.query,
                parent=self,
                timeout=params.timeout,
                default_value=params.default_value,
            )
            dialog.exec()
            ret = dialog.get_input_text()
        elif params.input_type == "bool":
            dialog = YesNoAbortDialog(
                params.query,
                timeout=params.timeout,
                parent=self,
                default_value=params.default_value,
            )
            ret = dialog.get_response()
        elif params.input_type == "numerical":
            numerical_default_value = self._parse_numerical_default(params.default_value)
            dialog = NumericalInputDialog(
                params.query,
                parent=self,
                timeout=params.timeout,
                default_value=numerical_default_value,
                min_value=params.min_value,
                max_value=params.max_value,
                step=params.step,
                decimals=params.decimals,
            )
            dialog.exec()
            ret = str(dialog.get_input_value())
        else:
            ret = ""

        if self._handle_dialog_result(dialog) is not None:
            return
        self.ui.widgets.measurement_thread.pass_input(ret)

    def _handle_dialog_result(self, dialog: TimeoutDialogBase) -> str | None:
        """
        Handle the result of a dialog and abort the script if needed.

        Returns
        -------
        None
            If the user accepted the dialog (input should be passed to script).
        str
            The abort character ("a" or "f") if the user clicked Abort or Finish.
        """
        result = dialog.result()
        if result == QDialog.DialogCode.Accepted:
            return None
        if result == 3:
            self.ui.widgets.measurement_thread.abort("f")
            return "f"
        self.ui.widgets.measurement_thread.abort("a")
        return "a"

    def _parse_numerical_default(self, default_value: str) -> float:
        """Parse a default value string into a float, with warning on failure."""
        try:
            return float(default_value) if default_value else 0.0
        except ValueError:
            self.ui.widgets.status_preview.appendPlainText(
                f"Warning: Invalid default_value '{default_value}' for numerical input. Using 0.0",
            )
            return 0.0

    def kill_thread(self) -> None:
        """Kill the thread."""
        self.ui.widgets.measurement_thread.kill()
        self.show_message(
            NotifierMessage(
                "Script terminated by user - file integrity might be compromised",
                level=logging.WARNING,
            )
        )

    def update_system_commands(self) -> None:
        """Update the help info about the current system(s)."""
        system_info = self.ui.widgets.system_list.system_info
        bg_color = "#565656" if MApplication.instance().isDark else "#f0f0f0"
        th = '<th style="text-align: left;">{}</th>'.format
        table_open = (
            '<table border="1" cellpadding="5" cellspacing="0" '
            'style="border-collapse: collapse; text-align: left; margin-bottom: 20px;">'
            f'<tr style="background-color: {bg_color}; text-align: left;">'
        )
        systems = "".join(f"{s}<br>" for s in self.ui.widgets.system_list.systems)
        systems = systems if systems else "None<br>"
        classes = ", ".join(system_info.classes) if system_info.classes else "None"
        text = (
            f"The following systems were selected:<br><b>{systems}<br></b>"
            f"They consist of the following classes:<br><b>{classes}<br></b>"
            "<br>These systems provide the following:<br>"
        )
        if system_info.parameters:
            rows = "".join(
                f"<tr><td>{p.index}</td>"
                f"<td>{f'<b>{p.name}</b>' if p.settable else p.name}</td></tr>"
                for p in system_info.parameters.values()
            )
            text += (
                f"<h3>Parameters</h3>Settable items in <b>boldface</b>"
                f"{table_open}{th('Index')}{th('Name')}</tr>{rows}</table>"
            )
        if system_info.devices:
            rows = "".join(
                f"<tr><td><b>{d.name}</b></td><td>{d.description}</td></tr>"
                for d in system_info.devices.values()
            )
            text += (
                f"<h3>Devices</h3>{table_open}{th('Name')}{th('Description')}</tr>{rows}</table>"
            )
        shared = th("Prefix") + th("Name") + th("Signature")
        if system_info.methods:
            rows = "".join(
                f"<tr><td>{m.prefix}</td><td><b>{m.name}</b></td>"
                f"<td>{m.signature}</td><td>{m.doc_summary}</td></tr>"
                for m in system_info.methods.values()
            )
            text += f"<h3>System Methods</h3>{table_open}{shared}"
            text += f"{th('Docstring summary')}</tr>{rows}</table>"
        if system_info.variables:
            rows = "".join(
                f"<tr><td>{v.prefix}</td><td><b>{v.name}</b></td><td>{v.signature}</td></tr>"
                for v in system_info.variables.values()
            )
            text += f"<h3>System Variables</h3>{table_open}{shared}</tr>{rows}</table>"
        text += "<br>"
        self.ui.widgets.system_command_text_edit.setText(text)

    def show_system_commands(self) -> None:
        """Print information about current system(s) in a help window."""
        self.ui.widgets.system_command_help.setMinimumSize(
            self.ui.widgets.system_command_help.sizeHint()
        )

        # Load size and position from settings (only if not already visible)
        if not self.ui.widgets.system_command_help.isVisible():
            self.settings.beginGroup("system_command_help")
            saved_size = self.settings.safer_value(
                "size", self.ui.widgets.system_command_help.sizeHint(), type=QSize
            )
            saved_position = self.settings.safer_value(
                "position", self.ui.widgets.system_command_help.pos(), type=QPoint
            )
            self.settings.endGroup()
            self.ui.widgets.system_command_help.resize(saved_size)
            self.ui.widgets.system_command_help.move(saved_position)

        self.ui.widgets.system_command_help.show()
        self.ui.widgets.system_command_help.raise_()
        # Mark that the help dialog has been shown at least once
        self._help_dialog_shown = True

    def write_output(self, text: str) -> None:
        """
        Buffer text and update GUI periodically to prevent crashes.

        Parameters
        ----------
        text: str
            Text to be appended.
        """
        self._output_buffer.append(text)
        if not self._output_timer.isActive():
            self._output_timer.start()

    def _flush_output_buffer(self) -> None:
        """Flush buffered text to the GUI."""
        if not self._output_buffer:
            self._output_timer.stop()
            return

        combined_text = "".join(self._output_buffer)
        self._output_buffer.clear()

        # Operate on a disposable cursor so we do not move the user's cursor/selection.
        # Handle plain text and control characters in one path, because buffered writes
        # can split "\r" from the text it is meant to overwrite.
        edit = self.ui.widgets.status_preview
        scrollbar = edit.verticalScrollBar()
        at_bottom = scrollbar.value() == scrollbar.maximum()
        doc = self.ui.widgets.status_preview.document()
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.beginEditBlock()
        parts = re.split(r"([\r\n])", combined_text)
        for index in range(0, len(parts), 2):
            text = parts[index]
            if text:
                cursor.insertText(text)

            if index + 1 >= len(parts):
                continue

            if parts[index + 1] == "\r":
                cursor.movePosition(
                    QTextCursor.MoveOperation.StartOfBlock,
                    QTextCursor.MoveMode.KeepAnchor,
                )
                cursor.removeSelectedText()
            else:
                cursor.insertBlock()
        cursor.endEditBlock()
        if at_bottom:
            edit.moveCursor(QTextCursor.MoveOperation.End)
        if not self._output_buffer:
            self._output_timer.stop()

    def update_filename(self, path: str) -> None:
        """
        Update the current measurement filename.

        Parameters
        ----------
        path: str
            Path to current measurement file.
        """
        self.measurement_file = Path(path)
        self.ui.actions.preview.setEnabled(True)

    def enable_buttons(self, flag: bool) -> None:
        """
        Switch the buttons to either running or stopped mode.

        Parameters
        ----------
        flag : bool
            True means script is running
        """
        self.is_running = flag
        if flag:
            self.ui.actions.start.setEnabled(False)
            self.ui.actions.start.setToolTip("A measurement is currently running.")
        else:
            self.update_start_action_state()
        self.ui.actions.pause.setEnabled(flag)
        if self.ui.actions.pause.isChecked():
            self.ui.actions.pause.setChecked(False)
        self.ui.actions.abort.setEnabled(flag)
        self.ui.actions.finish.setEnabled(flag)
        self.ui.actions.kill.setEnabled(flag)
        self.ui.widgets.script_edit.setReadOnly(flag)
        self.ui.actions.new_file.setEnabled(not flag)
        self.ui.actions.load.setEnabled(not flag)
        self.ui.actions.system_help.setEnabled(not flag)
        self.ui.widgets.system_list.setEnabled(not flag)
        self.ui.widgets.meta_view.setEnabled(not flag)

    def process_finished(self) -> None:
        """
        Handle GUI changes and clean up thread after it has finished.

        Return buttons to original state, delete the finished process.
        """
        self.ui.widgets.script_edit.removeHighlight()
        self.enable_buttons(False)
        self._flush_output_buffer()
        self.ui.widgets.progressbar.setValue(0)
        self.ui.widgets.progress.setText("Measurement idle.")
        self.ui.widgets.table.reset()
        if self.measurement_failed:
            self.ui.widgets.status_preview.print_colored("\nExecution failed")
        else:
            self.ui.widgets.status_preview.print_colored("\nExecution finished")
        del self.ui.widgets.measurement_thread

    def run_linter(self) -> int:
        """
        Call the linter for the editor view.

        Returns
        -------
        int
            The number of issues.
        """
        self.ui.widgets.script_edit.setSystemInfo(self.ui.widgets.system_list.system_info)
        return self.ui.widgets.script_edit.returnIssues()

    def start_process(self) -> None:
        """
        Start the matrix_script process.

        Disable/enable buttons to reflect run state and get selected
        systems. Then runs the script defined in the edit.
        """
        config_validation = self.ui.widgets.config_editor.validate_config()
        if isinstance(config_validation, Error):
            self.ui.widgets.config_editor.show_for_validation_errors()
            self.update_start_action_state()
            return
        if (
            self.run_linter() > 0 and not self.in_pytest
        ):  # run linter to make sure there are no errors
            self.ui.widgets.status_preview.print_colored(
                "Script execution was halted because of linter errors"
            )
            MApplication.instance().processEvents()
            a = QMessageBox(parent=self)  # open a popup window to inform about the error
            a.setText("Linter error")
            a.setInformativeText("Error found in script, continue anyway?")
            a.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            a.setDefaultButton(QMessageBox.StandardButton.Ok)
            ret = a.exec()
            if ret == QMessageBox.StandardButton.Cancel:
                return
        self.measurement_failed = False
        self.ui.widgets.progressbar.setValue(0)
        self.ui.widgets.progress.setText("Measurement started.")
        self.ui.widgets.table.reset()
        self.ui.widgets.status_preview.print_colored("### Running script now")
        user_script = self.ui.widgets.script_edit.toPlainText()
        script = generate_script(user_script)
        metadata = self.ui.widgets.meta_view.metadata
        outputfile = str(self.scriptname) if self.scriptname else ""
        script_item = MeasurementItem(
            kind="script",
            input_file=script,
            output_file=outputfile,
            metadata=metadata,  # ty:ignore[invalid-argument-type]
            config=self.ui.widgets.config_editor.get_config_dict(),
            systems=self.ui.widgets.system_list.systems,
        )
        self.ui.widgets.measurement_thread = MeasurementThread()
        self.ui.widgets.measurement_thread.set_parameters(script_item)
        self.ui.widgets.measurement_thread.finished.connect(self.process_finished)
        self.ui.widgets.measurement_thread.data_received.connect(self.process_data)

        logger.info("The following user script is started:\n%s", user_script)
        self.ui.widgets.measurement_thread.start()
        self.enable_buttons(True)

    def update_systems(self, update_config: bool = True) -> None:
        """
        Update the systems list and config editor.

        Parameters
        ----------
        update_config: bool
            Whether to update the config editor.
        """
        retained_config = self.ui.widgets.config_editor.get_config_dict()
        # only systems that are part of matrix or ifwlib can be configured via files
        configurable = [
            system for system in self.ui.widgets.system_list.systems if not Path(system).exists()
        ]
        matr1x.reload_config()
        if update_config:
            self.ui.widgets.config_editor.set_systemfile(configurable)
            self.ui.widgets.config_editor.set_full_system_list(self.ui.widgets.system_list.systems)
            self.ui.widgets.config_editor.set_system_info(self.ui.widgets.system_list.system_info)
            self.ui.widgets.config_editor.update_data()
            self.ui.widgets.config_editor.apply_config_dict(retained_config)
            self.update_start_action_state()
        # Update system commands with cached info
        self.update_system_commands()
        if self.ui.widgets.system_command_help.isVisible():
            self.show_system_commands()
        self.run_linter()

    def save_file_as(self) -> bool:
        """
        Ask for the filename and calls write_file().

        Returns
        -------
        bool
            True (Sucess) or False (Error).
        """
        filename = QFileDialog.getSaveFileName(
            self,
            "Specify filename to save",
            str(matr1x.usersfolder if not self.scriptname else Path(self.scriptname).parent),
            f"matrix files (*{self.extension})",
        )
        filename = Path(filename[0])
        if filename == Path():
            return False
        else:
            return self.write_file(filename)

    def save_file(self) -> bool:
        """
        Try to save under the last name and call write_file().

        If no last filename exists calls save_file_as().

        Returns
        -------
        bool
            True (Sucess) or False (Error).
        """
        if not self.last_filename:
            return self.save_file_as()
        else:
            return self.write_file(self.last_filename)

    def write_file(self, filename: Path) -> bool:
        """
        Save script to file and write system information to header.

        Returns
        -------
        bool
            True (Sucess) or False (Error).
        """
        if filename.suffix != self.extension:
            filename = filename.with_suffix(self.extension)
        try:
            output_file = filename.open("w")
        except OSError:
            self.show_message(NotifierMessage("File cannot be written.", level=logging.ERROR))
            return False
        self.scriptname = filename
        self.update_systems(update_config=False)
        # set new script in editor and save it to the file
        newscript = self.generate_save_content()
        self.ui.widgets.script_edit.setPlainText(newscript)
        output_file.write(newscript)
        output_file.close()
        self.last_filename = filename
        self.ui.widgets.script_edit.setModified(False)
        self.update_window_title()
        return True

    def generate_save_content(self) -> str:
        """
        Add the systems in the header of a script.

        Returns
        -------
        str
            The script including the generated header.
        """
        system_list = self.ui.widgets.system_list
        flat_parameters = system_list.system_info.flat_parameters
        header_lines = [
            "# system def : " + ",".join(str(s) for s in system_list.systems),
            "# system names : " + ",".join(p.name for p in flat_parameters),
            "# system units : " + ",".join(p.unit for p in flat_parameters),
            "# file v8, time stamp : " + time.strftime(matr1x.datetimefmt, time.localtime()),
        ]
        script = self.ui.widgets.script_edit.toPlainText().rstrip()
        body_lines = [
            line
            for i, line in enumerate(script.splitlines())
            if not (i < 4 and line.startswith(("# system ", "# file v")))
        ]
        return "\n".join(header_lines + body_lines) + "\n"

    def load_from_filename(self, filename: Path) -> None:
        """
        Load the script from file denoted by filename.

        Also, make sure that header information specified still agree
        with the corresponding system.

        Parameters
        ----------
        filename: Path
            The file to load.
        """
        try:
            input_file = filename.open()
        except OSError:
            self.show_message(NotifierMessage("File cannot be opened", level=logging.WARNING))
            return
        self.scriptname = filename
        code = ""
        self.ui.widgets.system_list.clear()
        #
        # system files
        #
        line = input_file.readline()
        if "# system def : " in line:
            # load system from definition in file
            system_line = line.replace("# system def : ", "").strip()
            systems = [s.strip() for s in system_line.split(",") if s.strip()]
            self.ui.widgets.system_list.add_systems(systems)
            system_info = self.ui.widgets.system_list.system_info
            flat_parameters = system_info.flat_parameters
            column_names = [p.name for p in flat_parameters]
            units = [p.unit for p in flat_parameters]
        else:
            self.show_message(
                NotifierMessage(
                    "No system defined in script, please choose system(s)",
                    level=logging.WARNING,
                )
            )
        code += line
        #
        # system columns definiton
        #
        line = input_file.readline()
        code += line
        # make sure that system column definition agrees with
        # current system
        if "# system names : " in line:
            system_names = line.strip().replace("# system names : ", "")
            current_columns = [str(col).strip() for col in column_names]
            # Handle both "," and ", " as separators since compound columns use ", "
            loaded_columns = []
            for col in system_names.split(","):
                col = col.strip()
                if col:
                    loaded_columns.append(col)
            if current_columns != loaded_columns:
                self.ui.widgets.status_preview.print_colored(
                    "Column names have changed between generation "
                    "of script and now, please make sure that "
                    "columns are set correctly before running the "
                    "script"
                )
        else:
            self.ui.widgets.status_preview.print_colored(
                "Could not verify column names, please verify that columns have not changed"
            )
        #
        # system unit definiton
        #
        line = input_file.readline()
        code += line
        # make sure that system unit definition agrees with
        # current system
        if "# system units : " in line:
            system_units = line.strip().replace("# system units : ", "")
            current_units = [str(unit).strip() for unit in units]
            # Handle both "," and ", " as separators since compound columns use ", "
            loaded_units = []
            for unit in system_units.split(","):
                loaded_units.append(unit.strip())
            if current_units != loaded_units:
                self.ui.widgets.status_preview.print_colored(
                    "Column units have changed between generation "
                    "of script and now, please make sure that "
                    "columns are set correctly before running the "
                    "script"
                )
        else:
            self.ui.widgets.status_preview.print_colored(
                "Could not verify column units, please verify that columns have not changed"
            )
        #
        # read actual code
        #
        for i, line in enumerate(input_file):
            code += line
        input_file.close()
        self.ui.widgets.script_edit.setPlainText(code)
        self.ui.widgets.script_edit.setModified(False)
        self.last_filename = filename
        self.update_window_title()

    def load_from_file(self) -> None:
        """Open file dialog and call load_from_filename."""
        # First, check if unsaved changes exist
        if (
            self.ui.widgets.script_edit.isModified()
            and not self.in_pytest
            and not save_messagebox(self, self.save_file)
        ):
            return
        filename = QFileDialog.getOpenFileName(
            self,
            "Select filename to open",
            str(matr1x.usersfolder if not self.scriptname else Path(self.scriptname).parent),
            f"matrix files (*{self.extension})",
        )
        filename = Path(filename[0])
        if filename != Path():
            self.load_from_filename(filename)

    def new_file(self) -> None:
        """Start over with a blank script."""
        if (
            self.ui.widgets.script_edit.isModified()
            and not self.in_pytest
            and not save_messagebox(self, self.save_file)
        ):
            return
        self.last_filename = None
        self.scriptname = None
        self.ui.widgets.script_edit.setPlainText("")
        self.ui.widgets.script_edit.setModified(False)


def main() -> None:
    """Set the basic GUI parameters and run."""
    install_error_handler()
    app = MApplication(sys.argv)
    appname = "matrix-script"
    app.setDesktopFileName(appname)
    ex = MainWindow(filename=Path(sys.argv[1]) if len(sys.argv) >= 2 else None)
    ex.show()
    ex.restore_window_state()
    # handle MacOS specific FileOpenEvent from MApplication
    app.connect_file_handler(ex._load_file_from_signal)
    ret = app.exec()
    sys.exit(ret)
