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
"""
Provides a base class for creating control GUIs for data acquisition systems.

This module includes functionality for:
- Setting up a GUI with collapsible sections
- Managing multiple GuiDict objects for different parts of the interface
- Handling device connections and communication
- Implementing data logging capabilities
- Creating a local SCPI TCP server for remote control
- Error handling and GUI state management

The ControlWindow class serves as a foundation for building specific control interfaces
for various data acquisition setups.
"""

import ast
import logging
import numbers
import os
import pickle
import sys
import threading
import time
import warnings
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QByteArray, QPoint, QSize, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QColor, QIcon, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from matr1x import config as matrixconfig
from matr1x import datetimefmt, logfolder, output_extension, scpi_tcpserver, system
from matr1x.control.util import GuiDict, catchEmitError, var
from matr1x.error_handling import expect_not_none
from matr1x.gui_util import (
    EmittingStream,
    LoggingWindow,
    MApplication,
    SaferQSettings,
    check_config,
    get_matrix_icon,
    open_matrix_toml,
    protected_restore,
)
from matr1x.util import Get

logger = logging.getLogger(Path(__file__).name)


class CollapsibleBox(QWidget):
    """
    A collapsible box widget that can be expanded or collapsed.

    This widget provides a toggleable section with a title button and content area.
    When expanded, it shows the content; when collapsed, it hides the content.

    Attributes
    ----------
        redraw_activity (Signal): Signal emitted when the box is expanded or collapsed.
    """

    # code inspired from
    # https://github.com/MichaelVoelkel/qt-collapsible-section/blob/master/Section.py
    redraw_activity = Signal(bool)

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        """
        Initialize the CollapsibleBox widget.

        Parameters
        ----------
        title : str, optional
            The title of the collapsible box, by default ""
        parent : QWidget, optional
            The parent widget, by default None
        """
        super().__init__(parent)
        self.toggle_button = QToolButton(self)
        self.header_line = QFrame(self)
        self.content_widget = QScrollArea(self)
        self.main_layout = QVBoxLayout()

        self.toggle_button.setStyleSheet("QToolButton {border: none;}")
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)

        self.header_line.setFrameShape(QFrame.Shape.HLine)
        self.header_line.setFrameShadow(QFrame.Shadow.Sunken)
        self.header_line.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Maximum
        )

        self.content_widget.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed
        )

        # start out collapsed
        self.content_widget.setMaximumHeight(0)
        self.content_widget.setMinimumHeight(0)

        self.main_layout.setSpacing(0)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        hline = QHBoxLayout()
        hline.addWidget(self.toggle_button, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        hline.addWidget(self.header_line)
        self.main_layout.addLayout(hline)
        self.main_layout.addWidget(self.content_widget)
        self.setLayout(self.main_layout)

        self.toggle_button.toggled.connect(self.toggle)

    def toggle(self, collapsed: bool) -> None:
        """
        Toggle the visibility of the content widget.

        Parameters
        ----------
        collapsed : bool
            True if the widget is being expanded, False if being collapsed
        """
        if collapsed:
            self.toggle_button.setArrowType(Qt.ArrowType.DownArrow)
            self.content_widget.setMaximumHeight(self.content_height + 1000)
            self.content_widget.setVisible(True)
            self.setMinimumHeight(self.collapsed_height)
            self.setMaximumHeight(self.combined_height + 1000)
            self.content_widget.setSizePolicy(
                QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding
            )
        else:
            self.content_widget.setSizePolicy(
                QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed
            )
            self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
            self.content_widget.setMaximumHeight(0)
            self.setMinimumHeight(self.collapsed_height)
            self.setMaximumHeight(self.collapsed_height)
            self.content_widget.setVisible(False)
        self.updateGeometry()
        self.redraw_activity.emit(collapsed)

    def setContentLayout(self, layout: QLayout) -> None:
        """
        Set the layout for the content widget.

        Parameters
        ----------
        layout : QLayout
            The layout to be set for the content widget
        """
        lay = self.content_widget.layout()
        del lay
        self.content_widget.setLayout(layout)
        self.content_height = self.content_widget.sizeHint().height()
        self.collapsed_height = self.sizeHint().height()  # - self.content_height
        self.combined_height = self.content_height + self.collapsed_height


@dataclass(frozen=True)
class ActionGroup:
    """Actions to be utilized in the GUI."""

    enable_all: QAction
    disable_all: QAction
    full_info_all: QAction
    less_info_all: QAction
    show_activity: QAction
    show_toolbar: QAction
    show_toml: QAction
    show_log: QAction
    quit: QAction


@dataclass(frozen=True)
class MenuGroup:
    """The menus to be utilized in the GUI."""

    file: QMenu
    enable: QMenu
    fullinfo: QMenu
    view: QMenu
    custom: QMenu
    help: QMenu


@dataclass(frozen=True)
class WidgetGroup:
    """Widgets to be used in the GUI."""

    panic: QPushButton


class UIBuilder:
    """Provide actions."""

    def __init__(self, window: QMainWindow) -> None:
        self.window: QMainWindow = window
        self.widgets = self._create_widgets()
        self.actions = self._create_actions()
        self.menus = self._create_menus()

    def _create_widgets(self) -> WidgetGroup:
        """Create the widgets."""
        panicButton = QPushButton("Panic Button")
        panicButton.setStyleSheet("background-color: red;")
        panicButton.setCheckable(True)
        return WidgetGroup(
            panic=panicButton,
        )

    def _create_actions(self) -> ActionGroup:
        """Create most QActions for the control."""
        enable_all = QAction("Enable all", self.window)
        disable_all = QAction("Disable all", self.window)
        full_info_all = QAction("Full info all", self.window)
        less_info_all = QAction("Less info all", self.window)
        show_toolbar = QAction("Show Toolbar")
        show_toolbar.setShortcut(QKeySequence("Ctrl+1"))
        show_toolbar.setCheckable(True)
        show_activity = QAction("Show activity", self.window)
        show_toml = QAction("Show matrix toml", self.window)
        show_toml.setMenuRole(QAction.MenuRole.PreferencesRole)
        show_toml.setShortcut(QKeySequence.StandardKey.Preferences)
        show_log = QAction("Show Log Window", self.window)
        show_log.setCheckable(True)
        quit_app = QAction("Quit", self.window)
        if os.name == "nt":
            quit_app.setShortcut(QKeySequence.StandardKey.Close)
        else:
            quit_app.setShortcut(QKeySequence.StandardKey.Quit)
        return ActionGroup(
            enable_all=enable_all,
            disable_all=disable_all,
            full_info_all=full_info_all,
            less_info_all=less_info_all,
            show_toolbar=show_toolbar,
            show_activity=show_activity,
            show_toml=show_toml,
            show_log=show_log,
            quit=quit_app,
        )

    def _create_menus(self) -> MenuGroup:
        """Create the main menu."""
        menu = self.window.menuBar()
        file = menu.addMenu("&File")
        enable = menu.addMenu("&Enable")
        fullinfo = menu.addMenu("&Full info")
        view = menu.addMenu("&View")
        custom = menu.addMenu("&Custom")
        help_me = menu.addMenu("&Help")
        return MenuGroup(
            file=file,
            enable=enable,
            fullinfo=fullinfo,
            view=view,
            custom=custom,
            help=help_me,
        )


class EnableAction(QAction):
    """
    A QAction subclass that automatically updates its icon based on checked state.

    This action is designed for enable/disable functionality and automatically
    updates its icon color when the checked state changes.
    """

    def __init__(self, text: str, parent: "ControlWindow"):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setIconText("Enable")
        self.setIcon(get_matrix_icon("CUSTOM_Power", color=QColor("gray")))
        self.controlwindow: ControlWindow = parent
        self.toggled.connect(self._update_icon)

    def _update_icon(self, checked: bool):
        """Update the icon based on checked state."""
        if checked:
            self.setIcon(get_matrix_icon("CUSTOM_Power", color=QColor("forestgreen")))
        else:
            self.setIcon(get_matrix_icon("CUSTOM_Power", color=QColor("gray")))
        self.controlwindow.check_enables()

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

    def __init__(self, text: str, parent: "ControlWindow"):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setIconText("Full info")
        self.setIcon(get_matrix_icon("CHAR_+"))
        self.controlwindow: ControlWindow = parent
        self.toggled.connect(self._update_icon)

    def _update_icon(self, checked: bool):
        """Update the icon based on checked state."""
        if checked:
            self.setIcon(get_matrix_icon("CHAR_-"))
        else:
            self.setIcon(get_matrix_icon("CHAR_+"))
        self.controlwindow.check_full_infos()

    def setChecked(self, a0: bool):
        """Override setChecked to ensure icon is updated."""
        super().setChecked(a0)
        self._update_icon(a0)


class ControlWindow(QMainWindow):
    """
    Base class for control GUIs.

    This class prepares a lot of things behind the scenes for use in typical
    control GUIs.

    Parameters
    ----------
    name : str
        Identifier string of the control GUI.
    guidicts : One GuiDict or a list or tuple of GuiDict
        GuiDict object(s) which build the basis of the controlGUI.
    extra_cmds : dict, optional
        Dictionary of commands offered for the measurement system. Commands from
        the GuiDict object are merged together with this list.
    parent : QWidget, optional
        Qt parent widget.
    package : str, optional
        Package name used in the generated log files.
    logging : bool or int, optional
        Flag to enable logging on startup of the control GUI. If a numerical
        value is given, the integer part of it will be used as interval (in
        seconds) for the logging function.
    port : int, optional
        TCP port number for the control GUI SCPI server socket.
    """

    sig_error = Signal(type, Exception, str)
    activity = Signal(str)
    deactivate = Signal(bool)

    def __init__(
        self,
        name: str,
        guidicts=None,
        extra_cmds: dict | None = None,
        parent: QWidget | None = None,
        package: str = "matr1x",
        logging=False,
        port=scpi_tcpserver.DEFAULT_PORT,
    ):
        # work around a bug in PyQt which can cause a segfault after a Python
        # exception. see issue #357
        os.environ["QT_NO_FT_CACHE"] = "1"

        super().__init__(parent=parent)

        # Initialize logging window
        self.log_window = LoggingWindow(parent=self)
        self.log_window.hide()
        logger.info("Control window '%s' starting", name)

        self.setWindowTitle(name)
        self.settings = SaferQSettings(package, name)
        # initialize parameters
        self.running = False
        self.logging = False
        filename = f"{package}.{name}_{time.strftime(datetimefmt)}{output_extension}"
        if os.name == "nt":
            # Windows does not like : in filenames
            filename = filename.replace(":", "")
        self.logfile: Path = Path(logfolder) / filename
        self._log_stop_event = threading.Event()
        self._log_interval_updated = threading.Event()
        self._log_stopped_event = threading.Event()
        self._log_stopped_event.set()
        self._log_thread: threading.Thread | None = None
        self._legacy_refresh_thread: threading.Thread | None = None
        self._legacy_refresh_stopped = threading.Event()
        self._legacy_refresh_stopped.set()
        self.terminate = False
        self.terminated = False
        self.devInit = False
        self.keep_enabled = []
        self.activity_layout: QHBoxLayout
        self._log_interval = 60
        # initialize error handling
        self.sig_error.connect(self.handleError)
        # SCPI TCP server placeholders
        self._local_server: scpi_tcpserver.SCPI_TCP_Server | None = None
        self._port = port
        # initialize data logging system
        self.S_log = system.System()
        self.S_log.__name__ = f"{package}.{name}_control_logging_system"
        # initialize data logging dictionaries
        if guidicts:
            if isinstance(guidicts, (list, tuple)):
                self.guidicts = list(guidicts)
            else:
                self.guidicts = [guidicts]
        else:
            self.guidicts = []
        self._harmonize_guidicts()
        # initialize GUI
        self.initUI()
        protected_restore(self._restore_gui_settings)
        # set outputStream as stdout (i.e. all output is written to status)
        self.output_stream = EmittingStream()
        self.output_stream.text_written.connect(self.output_written)
        sys.stdout = self.output_stream

        # merge the guidicts Systems
        if not hasattr(self, "S"):
            self.S = system.MergedSystem([g.S for g in self.guidicts])
        # store commands
        self.cmd_list = {
            ":conf": Get(
                lambda b: pickle.loads(ast.literal_eval(b)).decode(),
                lambda: pickle.dumps(self.S.query(), protocol=0),
            )
        }
        if extra_cmds:
            self.cmd_list.update(extra_cmds)

        # add the menu bar
        self.create_menu()

        # restore toolbar and activity indicator states after menu creation
        protected_restore(self._restore_view_settings)

        # show the GUI
        self.show()

        # connect signals so that at least one dock remains visible! (needs to be done after show!)
        for g in self.guidicts:
            g.dock.topLevelChanged.connect(self.needToAdjustSize)

        # enable logging if requested by arguments
        self._run_log_on_start = False
        if logging:
            self._run_log_on_start = True
            if not isinstance(logging, bool) and isinstance(logging, numbers.Number):
                self.interval.setValue(logging)

    def _harmonize_guidicts(self):
        """
        Harmonize the GuiDict entries to a consistent format.

        Performs two main operations:
        1. Converts dictionary entries to 'var' objects if they aren't already
        2. Ensures all guidicts are of GuiDict type, wrapping plain dictionaries
           in a compatible GuiDict class if necessary

        This method enables backwards compatibility with older code where guidicts
        might be simple dictionaries rather than GuiDict objects.

        Notes
        -----
        This method also sets parent references on all guidicts and connects their
        error signals to the main error handler.
        """
        # harmonize guidict entries to 'var'-objects
        for guidict in self.guidicts:
            for key, entry in guidict.items():
                if not isinstance(entry, var):
                    kwargs = {}
                    if isinstance(entry[0], var):
                        kwargs["dtype"] = (
                            guidict[key][0].variableType,
                            guidict[key][0].outType,
                        )
                        value = entry[0].value
                    else:
                        kwargs["dtype"] = entry[0]
                        value = None
                    if isinstance(entry[1][-1], bool):
                        kwargs["columns"] = entry[1][:-1]
                        kwargs["log"] = entry[1][-1]
                    else:
                        kwargs["columns"] = entry[1]
                    if len(entry) > 2:
                        kwargs["unit"] = entry[2]
                    guidict[key] = var(**kwargs)
                    guidict[key]._value = value

        self._convert_to_guidict()

        for guidict in self.guidicts:
            guidict.refresh_worker.sig_error.connect(self.handleError)
        # set parent reference on guidicts
        for g in self.guidicts:
            g.parent = self

    def _convert_to_guidict(self):
        """Harmonize the data structure -> convert all to GuiDict."""
        for i, guidict in enumerate(self.guidicts):
            if not isinstance(guidict, GuiDict):
                warnings.warn("Consider rewriting the GUI using the GuiDict class.", FutureWarning)

                class _FakeGuiDict(GuiDict):
                    data = guidict

                    def refresh(self, *args, **kwargs):
                        pass

                self.guidicts[i] = _FakeGuiDict()

    def _restore_gui_settings(self):
        """
        Restore previously saved GUI settings from persistent storage.

        This method restores various GUI elements to their previous states,
        including:
        - GuiDict state and features
        - Window geometry (size, position)
        - Window state (layout of docks and toolbars)
        - Visibility of the status box

        The settings are loaded from QSettings storage that was initialized
        during the class construction.

        Notes
        -----
        This method is called during initialization of the ControlWindow
        and should not be called directly.
        """
        # restore settings of GuiDicts
        for g in self.guidicts:
            g.dock.restoreState()
            g.extend_switch.setChecked(g.dock.extended)
            g.enable_switch.setChecked(not g.dock.disabled)
            g.restoreFeatures()
        # restore geometry settings of main window
        self.resize(self.settings.safer_value("size", self.size(), type=QSize))
        self.move(self.settings.safer_value("pos", self.pos(), type=QPoint))
        self.restoreState(
            self.settings.safer_value("windowState", self.saveState(), type=QByteArray)
        )
        # restore status visibility
        self.status_box.toggle_button.setChecked(
            self.settings.safer_value("status_visible", False, type=bool)
        )
        # restore log window geometry
        self.log_window.move(
            self.settings.safer_value("log_window/position", self.log_window.pos(), type=QPoint)
        )
        self.log_window.resize(
            self.settings.safer_value("log_window/size", self.log_window.size(), type=QSize)
        )

    def _restore_view_settings(self):
        """Restore view-related settings after menu has been created."""
        # restore toolbar visibility
        toolbar_visible = self.settings.safer_value("toolbar_visible", False, type=bool)
        self.ui.actions.show_toolbar.setChecked(toolbar_visible)
        self.set_toolbar_visible(toolbar_visible)
        # restore activity indicator location
        saved_activity_in_logger = self.settings.safer_value("activity_in_logger", True, type=bool)
        self.set_activity_in_logger(saved_activity_in_logger)

    # GUI functions
    def initUI(self) -> None:
        """
        Initialize GUI -> needs to be extended by subclasses.

        This method sets up the basic structure of the GUI by calling
        other methods to create different parts of the interface.
        """
        self.ui = UIBuilder(self)
        self.create_connections()
        layout = self.basicUI()
        for guidict in self.guidicts:
            content = guidict.create_GUI()
            self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, content)
        layout.addWidget(self.ui.widgets.panic)
        self.statusloggingUI(layout)
        check_config(matrixconfig)

    def create_connections(self) -> None:
        """Connect actions and widgets with application logic."""
        self.ui.actions.enable_all.triggered.connect(self.enable_all)
        self.ui.actions.disable_all.triggered.connect(self.disable_all)
        self.ui.actions.full_info_all.triggered.connect(self.full_info_all)
        self.ui.actions.less_info_all.triggered.connect(self.less_info_all)
        self.ui.actions.show_toolbar.triggered.connect(self.set_toolbar_visible)
        self.ui.actions.show_toml.triggered.connect(open_matrix_toml)
        self.ui.actions.show_log.triggered.connect(self.toggle_log_window)
        self.ui.actions.quit.triggered.connect(self.close)
        self.ui.widgets.panic.clicked.connect(self.panic)

    def toggle_visible(self, checked: bool, index: int) -> None:
        """
        Show and hide one of the guidicts.

        Parameters
        ----------
        checked : bool
            Visible (True) or hidden (False).
        index : int
            Number/Index of the guidict.
        """
        if checked:
            self.guidicts[index].dock.show()
        else:
            self.guidicts[index].dock.hide()

    def check_enables(self) -> None:
        """Determine if 'en/disable all' should be available."""
        on = 0
        off = 0
        total = 0
        for guidict in self.guidicts:
            if guidict.allow_disabling:
                total += 1
                if guidict.enable_switch.isChecked():
                    on += 1
                else:
                    off += 1
        if off < total:
            self.ui.actions.disable_all.setEnabled(True)
        else:
            self.ui.actions.disable_all.setEnabled(False)
        if on < total:
            self.ui.actions.enable_all.setEnabled(True)
        else:
            self.ui.actions.enable_all.setEnabled(False)

    def check_full_infos(self) -> None:
        """Determine if 'all/none full-info' should be available."""
        on = 0
        off = 0
        total = 0
        for guidict in self.guidicts:
            has_hiding = any(variable.hide for variable in guidict.values())
            if has_hiding:
                total += 1
                if guidict.extend_switch.isChecked():
                    on += 1
                else:
                    off += 1
        if off < total:
            self.ui.actions.less_info_all.setEnabled(True)
        else:
            self.ui.actions.less_info_all.setEnabled(False)
        if on < total:
            self.ui.actions.full_info_all.setEnabled(True)
        else:
            self.ui.actions.full_info_all.setEnabled(False)

    def enable_all(self) -> None:
        """Enable all guidicts."""
        for guidict in self.guidicts:
            if guidict.allow_disabling:
                guidict.enable_switch.setChecked(True)

    def disable_all(self) -> None:
        """Disable all guidicts."""
        for guidict in self.guidicts:
            if guidict.allow_disabling:
                guidict.enable_switch.setChecked(False)

    def full_info_all(self) -> None:
        """Show full info for all guidicts."""
        for guidict in self.guidicts:
            has_hiding = any(variable.hide for variable in guidict.values())
            if has_hiding:
                guidict.extend_switch.setChecked(True)

    def less_info_all(self) -> None:
        """Show less info for all guidicts."""
        for guidict in self.guidicts:
            has_hiding = any(variable.hide for variable in guidict.values())
            if has_hiding:
                guidict.extend_switch.setChecked(False)

    def set_activity_in_logger(self, in_logger: bool) -> None:
        """
        Set the location of activity indicators.

        Parameters
        ----------
        in_logger : bool
            If True, show activity indicators in the logger area.
            If False, show activity indicators in individual toolbars.
        """
        widgets: list[QWidget] = []
        # Determine current state by checking where activity indicators actually are
        current_state = self.activity_layout.count() > 0

        # Only do work if state is actually changing
        if current_state == in_logger:
            return

        if not in_logger:  # Move from logger to toolbars
            for i in range(self.activity_layout.count()):
                item = self.activity_layout.itemAt(i)
                w = expect_not_none(item.widget(), "No widget was returned.")
                widgets.append(w)
            for i, widget in enumerate(widgets):
                widget.setFixedHeight(10)
                self.guidicts[i].toolbar.addWidget(widget)
                empty = QWidget()
                empty.setFixedWidth(10)
                self.guidicts[i].toolbar.addWidget(empty)
        else:  # Move from toolbars to logger
            for guidict in self.guidicts:
                items = len(guidict.toolbar.actions())
                for i, action in enumerate(guidict.toolbar.actions()):
                    if i == items - 2:
                        widgets.append(guidict.toolbar.widgetForAction(action))
                        guidict.toolbar.removeAction(action)
                    if i == items - 1:
                        guidict.toolbar.removeAction(action)
            for widget in widgets:
                widget.setFixedHeight(30)
                self.activity_layout.addWidget(widget)
                widget.show()

        # Update action state to reflect new location
        self.activity_in_logger_action.setChecked(in_logger)

    def set_toolbar_visible(self, visible: bool) -> None:
        """
        Set the visibility of all toolbars.

        Parameters
        ----------
        visible : bool
            Show (True) or hide (False).
        """
        for guidict in self.guidicts:
            if visible:
                guidict.toolbar.show()
            else:
                guidict.toolbar.hide()

    def toggle_log_window(self):
        """Toggle the visibility of the logging window."""
        if self.log_window.isVisible():
            self.log_window.hide()
            self.ui.actions.show_log.setChecked(False)
            self.ui.actions.show_log.setText("Show Log Window")
        else:
            self.log_window.show()
            self.log_window.raise_()
            self.log_window.activateWindow()
            self.ui.actions.show_log.setChecked(True)
            self.ui.actions.show_log.setText("Hide Log Window")

    def create_menu(self) -> None:
        """
        Create the main menu.

        Add 'Full Info', 'Enable' and 'View' menus to the main menu bar.
        """
        self.ui.menus.file.addAction(self.ui.actions.quit)

        self.guidict_view = []
        for i, guidict in enumerate(self.guidicts):
            dict_name = list(guidict.keys())[0]
            # Enable/ Disable
            enable_action = EnableAction(dict_name, self)

            # Connect directly to GuiDict enable_switch
            enable_action.setChecked(guidict.enable_switch.isChecked())
            enable_action.setEnabled(guidict.allow_disabling)

            if guidict.allow_disabling:
                enable_action.triggered.connect(
                    lambda checked, g=guidict: g.enable_switch.setChecked(checked)
                )
                # Connect GuiDict enable_switch changes back to the action
                guidict.enable_switch.toggled.connect(enable_action.setChecked)

            guidict.toolbar.addAction(enable_action)
            self.ui.menus.enable.addAction(enable_action)
            # View toggles
            view_action = QAction(dict_name, self)
            self.guidict_view.append(view_action)
            self.guidict_view[i].setCheckable(True)
            self.guidict_view[i].setChecked(True)
            self.guidict_view[i].triggered.connect(
                lambda checked=self.guidict_view[i].isChecked(), index=i: self.toggle_visible(
                    checked, index
                )
            )
            self.ui.menus.view.addAction(self.guidict_view[i])

            # Full info toggles
            has_hiding = any(variable.hide for variable in guidict.values())
            full_info_action = FullInfoAction(dict_name, self)

            # Connect directly to GuiDict extend_switch
            full_info_action.setChecked(guidict.extend_switch.isChecked())
            full_info_action.setEnabled(has_hiding)

            if has_hiding:
                full_info_action.triggered.connect(
                    lambda checked, g=guidict: g.extend_switch.setChecked(checked)
                )
                # Connect GuiDict extend_switch changes back to the action
                guidict.extend_switch.toggled.connect(full_info_action.setChecked)

            guidict.toolbar.addAction(full_info_action)
            self.ui.menus.fullinfo.addAction(full_info_action)
            spacer = QWidget()
            spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            guidict.toolbar.addWidget(spacer)
            # Custom menu
            for action in guidict.menu_actions:
                action.setParent(self)
                self.ui.menus.custom.addAction(action)
            if len(guidict.menu_actions) != 0:
                self.ui.menus.custom.addSeparator()

        self.activity_in_logger_action = QAction("Activity in Logger")
        self.activity_in_logger_action.setShortcut(QKeySequence("Ctrl+0"))
        self.activity_in_logger_action.setCheckable(True)
        # Default to True (activity indicators start in logger)
        self.activity_in_logger_action.setChecked(True)
        self.activity_in_logger_action.triggered.connect(
            lambda checked: self.set_activity_in_logger(checked)
        )

        # Build the rest of the menu
        self.ui.menus.enable.addSeparator()
        self.ui.menus.enable.addAction(self.ui.actions.enable_all)
        self.ui.menus.enable.addAction(self.ui.actions.disable_all)

        self.ui.menus.fullinfo.addSeparator()
        self.ui.menus.fullinfo.addAction(self.ui.actions.full_info_all)
        self.ui.menus.fullinfo.addAction(self.ui.actions.less_info_all)

        self.ui.menus.view.addSeparator()
        self.ui.menus.view.addAction(self.ui.actions.show_toolbar)
        self.ui.menus.view.addAction(self.ui.actions.show_activity)
        self.ui.menus.view.addAction(self.ui.actions.show_toml)

        self.ui.menus.help.addAction(self.ui.actions.show_log)

        self.check_enables()
        self.check_full_infos()

    def basicUI(self) -> QVBoxLayout:
        """
        Declare main GUI components, set icon and general menu action.

        Returns
        -------
        QVBoxLayout
            The main layout of the GUI.
        """
        # General menu bar items

        icondir = Path(__file__).parent.parent / "scripts" / "icons"
        self.setWindowIcon(QIcon(str(icondir / "matr1x-control.png")))
        self.widget = QWidget()
        self.widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.main_layout = QVBoxLayout()

        self.widget.setLayout(self.main_layout)
        self.main_layout.addStretch()
        self.setCentralWidget(self.widget)
        return self.main_layout

    @Slot()
    def needToAdjustSize(self) -> None:
        """Adjust the size of the main window."""
        self.adjustSize()

    def statusloggingUI(self, layout: QLayout) -> None:
        """
        Set up status and logging user interface.

        This method creates and configures the widgets for status display
        and logging controls.

        Parameters
        ----------
        layout : QLayout
            The layout to which the status and logging UI will be added.
        """
        self.status_box = CollapsibleBox("Logging and Status", parent=self)
        self.status_box.redraw_activity.connect(self.readjustSize)
        layout.addWidget(self.status_box)

        # initialize common widgets
        self.status = QPlainTextEdit(self)
        self.status.setReadOnly(True)
        self.keep_enabled.append(self.status)
        self.activityIndicator = []
        self._pending_updates = {}  # {idx: color}
        self.activity_layout = QHBoxLayout()
        self.activity_layout.setSpacing(0)
        indicator_width = 17
        if len(self.guidicts) * indicator_width > 200:
            indicator_width = int(200 / len(self.guidicts))
        for idx, guidict in enumerate(self.guidicts):
            ql = QLabel(" ")
            ql.setFixedWidth(indicator_width)
            ql.setFixedHeight(30)
            ql.setAutoFillBackground(True)  # Add this
            palette = ql.palette()
            palette.setColor(ql.backgroundRole(), QColor("lightgray"))
            ql.setPalette(palette)
            ql.setToolTip(guidict.dock.windowTitle())
            self.activityIndicator.append(ql)
            guidict.refresh_worker.activity.connect(
                lambda c, idx=idx: self.change_single_color(c, idx)
            )
            guidict.refresh_worker.panic.connect(self.panic)
            self.activity_layout.addWidget(ql)

        # Timer to process pending updates
        self._process_timer = QTimer()
        self._process_timer.timeout.connect(self._process_updates)
        self._process_timer.start(100)  # 10 FPS

        self.activity.connect(self.change_color)
        self.deactivate.connect(self.deactivate_gui)
        self.togglelog = QPushButton("start log")
        self.togglelog.setCheckable(True)
        self.togglelog.setMaximumWidth(120)
        selectlog = QPushButton("select log file")
        selectlog.setMaximumWidth(140)
        self.configlog = QPushButton("show log config")
        self.configlog.setCheckable(True)

        self.loglabel = QLabel(self.logfile.name)
        self.loglabel.setMaximumWidth(250)
        self.loglabel.setWordWrap(True)
        interval_label = QLabel("log interval (s):")
        self.interval = QSpinBox()
        self.interval.setRange(1, 24 * 3600 + 1)
        self.interval.setValue(60)
        self.interval.setMaximumWidth(70)
        self._log_interval = self.interval.value()
        self.interval.valueChanged.connect(self._update_log_interval)
        clearlog = QPushButton("Clear Output")
        self.togglelog.clicked.connect(self.toggleLog)
        selectlog.clicked.connect(self.selectLog)
        self.configlog.clicked.connect(self.configLog)
        clearlog.clicked.connect(self.status.clear)

        # add status and logging widgets
        self.status_grid = QHBoxLayout()
        leftcolumn = QVBoxLayout()
        self.status_grid.addLayout(leftcolumn)
        line1 = QHBoxLayout()
        leftcolumn.addLayout(line1)
        line1.addLayout(self.activity_layout)
        line1.addStretch()
        line2 = QHBoxLayout()
        leftcolumn.addLayout(line2)
        line2.addWidget(interval_label)
        line2.addWidget(self.interval)
        line2.addStretch()
        line3 = QHBoxLayout()
        leftcolumn.addLayout(line3)
        line3.addWidget(self.configlog)
        line3.addStretch()
        line4 = QHBoxLayout()
        leftcolumn.addLayout(line4)
        line4.addWidget(selectlog)
        line4.addWidget(self.togglelog)
        line4.addStretch()
        leftcolumn.addWidget(self.loglabel)
        leftcolumn.addStretch()
        lastline = QHBoxLayout()
        leftcolumn.addLayout(lastline)
        lastline.addStretch()
        lastline.addWidget(clearlog)

        rightcolumn = QVBoxLayout()
        rightcolumn.addWidget(self.status)
        self.status_grid.addLayout(rightcolumn, stretch=1)
        self.status_box.setContentLayout(self.status_grid)
        self.status_box.toggle(False)

    @staticmethod
    def copyValues(copyDict: dict) -> None:
        """
        Copy the values of a guiDict from the first to the second column.

        This method is deprecated. It is now part of GuiDict. Its use should
        vanish in the future.

        Parameters
        ----------
        copyDict : dict
            guiDict for which the values shall be copied
        """
        warnings.warn(
            "copyValues is deprecated. Consider using GuiDict.copy_values.",
            FutureWarning,
        )
        for variable in copyDict.values():
            variable.copy_value()

    @catchEmitError
    @Slot(bool)
    @Slot(bool, str)
    def panic(self, checked: bool, reason: str = "Panic button") -> None:
        """
        Signal panic mode to guidicts if the button is checked.

        Parameters
        ----------
        checked : bool
            Whether the panic button is checked
        reason : str, optional
            Reason for panic mode, by default "Panic button"
        """
        if checked:
            logger.info("%s: Panic mode activated due to '%s'", time.strftime(datetimefmt), reason)
            self.ui.widgets.panic.setText(f"Panic mode activated due to '{reason}'")
            self.ui.widgets.panic.setChecked(True)
            for g in self.guidicts:
                g.panic()
        else:
            for g in self.guidicts:
                self.ui.widgets.panic.setText("Panic Button")
                g.unpanic()

    def output_written(self, text: str) -> None:
        """
        Append the most recent text to the end of the display.

        Ensures that the cursor remains at the end.

        Parameters
        ----------
        text : str
            Text to be appended
        """
        if text.strip("\n") != "":
            self.status.appendPlainText(text.strip("\n"))
            try:
                self.status.moveCursor(QTextCursor.MoveOperation.End)
            except Exception:  # upon cleanup after exception this can fail
                pass

    @Slot(bool)
    def readjustSize(self, expanding: bool = False) -> None:
        """
        Resize window when the status and logging tab is minimized.

        Parameters
        ----------
        expanding : bool, optional
            Whether the window is expanding, by default False
        """
        self.widget.adjustSize()
        if not expanding:
            # if we are shrinking the window and disabling the control, hide
            # the logging-config buttons
            self.configLog(False)
            self.configlog.setChecked(False)
            # make window smaller in vertial direction
            minw, maxw = self.minimumWidth(), self.maximumWidth()
            self.setFixedWidth(self.width())
            self.adjustSize()
            self.setMinimumWidth(minw)
            self.setMaximumWidth(maxw)

    # device communication and related functions
    @catchEmitError
    def connectDev(self) -> None:
        """
        Initialize device connections.

        If this is overloaded its important that the self.devInit
        property is set to True upon successful initialization of the
        devices.
        """
        if self.devInit is False:
            if self.S:
                self.S.set()
            self.devInit = True

    def configLog(self, checked: bool) -> None:
        """
        Configure logging settings for GUI elements.

        Parameters
        ----------
        checked : bool
            Whether logging is enabled
        """
        for guidict in self.guidicts:
            guidict.showlog = checked
            for v in guidict.values():
                # check that widget is not only a label, is not hidden
                # and is actually a value that should be logged
                if len(v.widgets) > 2 and (v.widgets[0].isHidden() is False and v.log is not None):
                    v.widgets[-1].setVisible(checked)

    def toggleLog(self, checkstate: bool) -> None:
        """
        Toggle data logging on or off.

        Parameters
        ----------
        checkstate : bool
            Whether logging should be enabled
        """
        self.togglelog.setChecked(checkstate)
        # clear system of all parameters
        self.S_log.clear_parameters()
        # add timestamp to system
        self.S_log.add_param("timeUTC", "s", getter=time.time)
        # set up system with selected values
        for i, guidict in enumerate(self.guidicts):
            for key in guidict:
                variable = guidict[key]
                # make sure it is a loggable widget
                if len(variable.widgets) > 2 and variable.log is not None:
                    if variable.widgets[-1].checkState() == Qt.CheckState.Checked:
                        # make sure check state is True and if so add to
                        # logged parameters
                        self.S_log.add_param(
                            f"dict{i}/{key}", "", getter=lambda v=variable: v.value
                        )
        if len(self.S_log.parameters) == 1:
            print("No logging parameters were selected")
            return
        if self.logging is False:
            # generate new log filename
            self.logfile = self.S_log.generate_datafilename(outputfile=self.logfile)
            self.loglabel.setText(self.logfile.name)
            # initialize system
            self.S_log.dcdata["Description"] = "Graphical interface logging data"
            self.S_log.dcdata["Type"] = "miscellaneous"
            # update date to reflect logging start time instead of GUI start time
            self.S_log.dcdata["date"] = time.strftime(datetimefmt, time.localtime())
            self.S_log.set(output_file=self.logfile)
            # write new datafile header
            self.S_log.init_datafile("matrix script generated")
            # turn off config and set data
            self.configLog(False)
            self.configlog.setEnabled(False)
            self.configlog.setChecked(False)
            self.togglelog.setText("data log running")
            # start thread
            self._log_stop_event.clear()
            self._log_stopped_event.clear()
            self._log_thread = threading.Thread(target=self.loggingFunc, daemon=True)
            self._log_thread.start()
            self.logging = True
            print(f"{time.strftime(datetimefmt)}: data logging started")

        elif self.logging is True:
            self.S_log.reset()
            self._stop_logging_thread()
            self.logging = False
            # reset GUI
            self.configlog.setEnabled(True)
            self.togglelog.setText("start data log")
            print(f"{time.strftime(datetimefmt)}: data logging stopped")

    def selectLog(self, *args) -> None:
        """
        Allow selecting a logfile.

        Parameters
        ----------
        *args
            Variable length argument list
        """
        filename = QFileDialog.getSaveFileName(
            self, "Select log file", str(logfolder), f"data log files (*{output_extension})"
        )[0]

        # If no file was selected, keep the current logfile
        if not filename:
            return

        # Check if logging is currently running
        was_logging = self.logging

        # If logging is running, stop it first
        if was_logging:
            self.toggleLog(False)

        # Update the logfile
        self.logfile = Path(filename)
        self.logfile = self.logfile.with_suffix(output_extension)
        self.loglabel.setText(self.logfile.name)

        # If logging was running, restart it with the new file
        if was_logging:
            self.toggleLog(True)

    @catchEmitError
    def loggingFunc(self) -> None:
        """Perform logging at specified intervals."""
        cnt = 0
        interval = max(1, self._log_interval)
        try:
            while not self._log_stop_event.is_set():
                if self._log_interval_updated.is_set():
                    self._log_interval_updated.clear()
                    interval = max(1, self._log_interval)
                if cnt == 0:
                    self.S_log.trigger()
                    self.S_log.take_measurement_point(self.logfile)
                cnt = (cnt + 1) % interval
                if self._log_stop_event.wait(1):
                    break
        finally:
            self._log_stopped_event.set()

    @Slot(int)
    def _update_log_interval(self, value: int) -> None:
        """Store the most recent logging interval for use in worker threads."""
        self._log_interval = max(1, value)
        self._log_interval_updated.set()

    def _stop_logging_thread(self, timeout: float = 2.0) -> None:
        """
        Request the logging thread to stop and wait for confirmation.

        Parameters
        ----------
        timeout : float, optional
            Maximum wait time in seconds for the logging thread to terminate.
        """
        self._log_stop_event.set()
        thread = self._log_thread
        if thread is None:
            self._log_stopped_event.set()
            return
        if self._log_stopped_event.wait(timeout):
            thread.join()
        else:
            logger.warning("logging thread did not terminate within %.1f s", timeout)
        self._log_thread = None

    @catchEmitError
    def refreshDict(self) -> None:
        """
        Initialize GuiDicts and align them with their dock visibility.

        The setup runs on the GUI thread and ensures that only visible guidicts
        are started. Optionally, a delayed log start is scheduled to give all
        guidicts time to populate their values.
        """
        max_period = 1
        for guidict in self.guidicts:
            dockw = guidict.dock
            if not dockw.isVisible():
                guidict.enable_switch.setChecked(False)
                guidict.restoreFeatures()
            else:
                guidict.start()
            max_period = max(max_period, guidict.refresh_period)
        if self._run_log_on_start:
            QTimer.singleShot(int(max_period * 1000), lambda: self.toggleLog(True))
        self.terminated = False

    def _stop_guidicts(self, wait: bool = True) -> None:
        """Stop all guidicts and update the terminated flag."""
        for guidict in self.guidicts:
            guidict.stop(wait=wait)
        self.terminated = True

    def _has_custom_refresh(self) -> bool:
        """Return True if the subclass overrides refreshDict."""
        return type(self).refreshDict is not ControlWindow.refreshDict

    def _start_legacy_refresh_thread(self) -> None:
        """Launch the legacy refresh loop in a worker thread if needed."""
        if self._legacy_refresh_thread and self._legacy_refresh_thread.is_alive():
            return
        self._legacy_refresh_stopped.clear()
        self._legacy_refresh_thread = threading.Thread(
            target=self._legacy_refresh_entrypoint,
            name=f"{self.__class__.__name__}-refresh",
            daemon=True,
        )
        self._legacy_refresh_thread.start()

    def _legacy_refresh_entrypoint(self) -> None:
        """Execute the legacy refresh loop and signal when it terminates."""
        try:
            self.refreshDict()
        finally:
            self._legacy_refresh_stopped.set()

    def _stop_legacy_refresh_thread(self, timeout: float = 5.0) -> None:
        """
        Stop the legacy refresh thread and wait for it to terminate.

        Parameters
        ----------
        timeout : float, optional
            Maximum time in seconds to wait for the thread to finish. Defaults to 5.0.
        """
        thread = self._legacy_refresh_thread
        if thread is None:
            return
        finished = self._legacy_refresh_stopped.wait(timeout)
        if finished:
            thread.join()
        else:
            logger.warning("refresh thread did not terminate within %.1f s", timeout)
        self._legacy_refresh_thread = None

    # general local server and start stop overhead
    def __enter__(self):
        """Initialize devices, start GuiDict workers, and launch the SCPI server."""
        # initialize devices
        print(f"{time.strftime(datetimefmt)}: initializing devices")
        self.connectDev()

        # start guidicts if devices initialized successfully
        if self.devInit is True:
            # merge all cmds from the GuiDicts and the extra cmds

            class extraGuiDict(GuiDict):
                cmds = self.cmd_list

                def refresh(self, *args, **kwargs):
                    pass

            extra_gui_dict = extraGuiDict()
            extra_gui_dict.set_cmd_funcs(window_obj=self, system=self.S)
            self.cmd_list = extra_gui_dict.cmds
            for guidict in self.guidicts:
                for name in guidict.cmds.keys():
                    if name in self.cmd_list:
                        raise ValueError(
                            f"command {name} from {guidict} is already present."
                            "A command name must be unique!"
                        )
                self.cmd_list.update(guidict.cmds)

            ControlWindow.refreshDict(self)
            if self._has_custom_refresh():
                self._start_legacy_refresh_thread()
            self.running = True
            self.startServer()

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """Stop GuiDict workers, close devices, and stop the logging thread."""
        if exc_type is not None:
            print(exc_type, exc_value, exc_traceback)

        self.stopServer()
        if self.running is True:
            self.terminate = True
            self.running = False
            self._stop_guidicts()
            self._stop_legacy_refresh_thread()
        if self.logging is True:
            self.logging = False
            self._stop_logging_thread()

    def startServer(self) -> None:
        """
        Start the local TCP server with the driver functions specified in cmds.

        This method initializes and starts a SCPI TCP server using the
        command list defined in the class.
        """
        self._local_server = scpi_tcpserver.SCPI_TCP_Server(self.cmd_list, port=self._port)
        self._local_server.start()

    def stopServer(self) -> None:
        """
        Stop the local TCP server.

        If a server instance exists, this method stops it and sets the
        server attribute to None.
        """
        if self._local_server is not None:
            self._local_server.stop()
        self._local_server = None

    @Slot(str, int)
    def change_single_color(self, color: str, idx: int) -> None:
        """
        Change the background color of a single activity indicator.

        Parameters
        ----------
        color : str
            The color to set as background as in QColor(color).
        idx : int
            The index of the activity indicator to change.
        """
        self._pending_updates[idx] = color

    @Slot(str)
    def change_color(self, color: str) -> None:
        """
        Change the background color of all activity indicators.

        Parameters
        ----------
        color : str
            The color to set as background as in QColor(color).
        """
        for idx, ql in enumerate(self.activityIndicator):
            self._pending_updates[idx] = color

    def _process_updates(self):
        """Process all pending updates."""
        if not self._pending_updates:
            return

        # Get all pending updates and clear the dict
        updates = self._pending_updates.copy()
        self._pending_updates.clear()

        # Apply all updates
        for idx, color in updates.items():
            if idx < len(self.activityIndicator):
                label = self.activityIndicator[idx]
                palette = label.palette()
                palette.setColor(label.backgroundRole(), QColor(color))
                label.setPalette(palette)

    @Slot(bool)
    def deactivate_gui(self, flag: bool) -> None:
        """
        Disable all GUI elements.

        This method is typically called after an error occurs to prevent further
        interaction with the GUI.

        Parameters
        ----------
        flag : bool
            If True, disables the GUI elements. If False, no action is taken.
        """
        if flag:
            # disable all GUI elements but look at execption list
            for g in self.guidicts:
                # disable all GUI elements but look at execption list
                g.dock.setEnabled(False)
                # GuiDict disable themselves, but repeat it here for backward
                # compatibility
                for v in g.values():
                    for widget in v.widgets:
                        widget.setEnabled(False)
            for i in reversed(range(self.status_grid.count())):
                w = self.status_grid.itemAt(i).widget()
                if w:
                    w.setEnabled(False)
            for widget in self.keep_enabled:
                widget.setEnabled(True)

    @Slot()
    def save_window_state(self) -> None:
        """
        Save current window and dock geometry.

        This method saves the current size, position, and state of the window,
        as well as the visibility of the status box, toolbar visibility state,
        and activity indicator location. These settings will be reloaded upon
        restart of the Control GUI.

        Note:
        This method is automatically called from closeEvent() when the window
        is closed to ensure settings are always saved.
        """
        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("windowState", self.saveState())
        self.settings.setValue("status_visible", self.status_box.toggle_button.isChecked())
        self.settings.setValue("toolbar_visible", self.ui.actions.show_toolbar.isChecked())
        self.settings.setValue("activity_in_logger", self.activity_in_logger_action.isChecked())
        self.settings.setValue("log_window/position", self.log_window.pos())
        self.settings.setValue("log_window/size", self.log_window.size())

    def closeEvent(self, a0: QCloseEvent) -> None:
        """
        Handle window close event by automatically saving current state.

        Parameters
        ----------
        event : QCloseEvent
            The close event
        """
        # Save window and dock states
        self.save_window_state()
        for g in self.guidicts:
            g.dock.saveCurrentState()

        # Clean up logging window
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.log_window.log_handler)
        self.log_window.deleteLater()

        # Accept the close event
        super().closeEvent(a0)

    @Slot(type, Exception, str)
    def handleError(self, exc_type, exc_value, pointer):
        """
        Signal slot to handle showing the error message and disabling the GUI.

        Parameters
        ----------
        exc_type : type
            The type of the exception.
        exc_value : Exception
            The exception instance.
        pointer : str
            A string indicating where the error occurred.
        """
        # stop guidicts; block briefly so worker threads actually terminate
        self.terminate = True
        self._stop_guidicts()
        self._stop_legacy_refresh_thread(timeout=0.5)
        self._log_stop_event.set()
        if pointer == "loggingFunc":
            self._log_stopped_event.set()
        self.activity.emit("lightgray")
        self.deactivate.emit(True)
        qApp = MApplication.instance()
        qApp.processEvents()
        # stop SCPI server to reflect that something is wrong instead of
        # returning the same reading over and over
        self.stopServer()
        # open a popup window to inform about the error
        _ = QMessageBox.critical(
            self,
            f"Error in {pointer}",
            f"""The following error was raised in {pointer}:
{repr(exc_value)}
Please investigate the error and eventually restart the graphical user interface""",
        )
        ret = qApp.exec()
        if ret != -1:
            sys.exit(ret + 1)
