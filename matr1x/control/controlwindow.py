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

from PyQt6.QtCore import QSettings, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QAction, QColor, QIcon, QKeySequence, QShortcut, QTextCursor
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QMainWindow,
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

from matr1x import datetimefmt, logfolder, output_extension, scpi_tcpserver, system
from matr1x.control.util import GuiDict, catchEmitError, var
from matr1x.gui_util import EmittingStream, MApplication, MIcon
from matr1x.util import Get

logger = logging.getLogger(os.path.split(__file__)[-1])


class CollapsibleBox(QWidget):
    """
    A collapsible box widget that can be expanded or collapsed.

    This widget provides a toggleable section with a title button and content area.
    When expanded, it shows the content; when collapsed, it hides the content.

    Attributes
    ----------
        redraw_activity (pyqtSignal): Signal emitted when the box is expanded or collapsed.
    """

    # code inspired from
    # https://github.com/MichaelVoelkel/qt-collapsible-section/blob/master/Section.py
    redraw_activity = pyqtSignal(bool)

    def __init__(self, title: str = "", parent: QWidget = None) -> None:
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
        self.toggle_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
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

    sig_error = pyqtSignal(type, Exception, str)
    activity = pyqtSignal(str)
    deactivate = pyqtSignal(bool)

    def __init__(
        self,
        name,
        guidicts=None,
        extra_cmds=None,
        parent=None,
        package="matr1x",
        logging=False,
        port=scpi_tcpserver.DEFAULT_PORT,
    ):
        # work around a bug in PyQt which can cause a segfault after a Python
        # exception. see issue #357
        os.environ["QT_NO_FT_CACHE"] = "1"

        super().__init__(parent=parent)
        self.setWindowTitle(name)
        self.settings = QSettings(package, name)
        # initialize paramaters
        self.running = False
        self.logging = False
        filename = f"{package}.{name}_{time.strftime(datetimefmt)}{output_extension}"
        if os.name == "nt":
            # Windows does not like : in filenames
            filename = filename.replace(":", "")
        self.logfile = os.path.join(logfolder, filename)
        self.terminate_log = False
        self.terminated_log = False
        self.terminate = False
        self.terminated = False
        self.devInit = False
        self.keep_enabled = []
        # initialize error handling
        self.sig_error.connect(self.handleError)
        # SCPI TCP server placeholders
        self._local_server = None
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
        # harmonize the guidict data structure -> convert all to GuiDict
        for i, guidict in enumerate(self.guidicts):
            if not isinstance(guidict, GuiDict):
                warnings.warn(
                    "Consider rewriting the GUI using the GuiDict class.", FutureWarning
                )

                class _FakeGuiDict(GuiDict):
                    data = guidict

                    def refresh(self, *args, **kwargs):
                        pass

                self.guidicts[i] = _FakeGuiDict()
        for guidict in self.guidicts:
            guidict.refresh_worker.sig_error.connect(self.handleError)
        # set parent reference on guidicts
        for g in self.guidicts:
            g.parent = self
        # initialize GUI
        self.initUI()
        # restore settings of GuiDicts
        for g in self.guidicts:
            g.dock.restoreState()
            g.extend_switch.setChecked(g.dock.extended)
            g.enable_switch.setChecked(not g.dock.disabled)
            g.restoreFeatures()
        # restore geometry settings of main window
        if self.settings.value("size") is not None:
            self.resize(self.settings.value("size"))
        if self.settings.value("pos") is not None:
            self.move(self.settings.value("pos"))
        if self.settings.value("windowState") is not None:
            self.restoreState(self.settings.value("windowState"))
        # restore status visibility
        self.status_box.toggle_button.setChecked(
            self.settings.value("status_visible", False, type=bool)
        )

        # enable saving of geometry by Ctrl+S
        self.saveStateSc = QShortcut(QKeySequence("Ctrl+S"), self)
        self.saveStateSc.activated.connect(self.saveCurrentState)
        for g in self.guidicts:
            self.saveStateSc.activated.connect(g.dock.saveCurrentState)
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

    # GUI functions
    def initUI(self) -> None:
        """
        Initialize GUI -> needs to be extended by subclasses.

        This method sets up the basic structure of the GUI by calling other
        methods to create different parts of the interface.
        """
        layout = self.basicUI()
        self.guidictUI(layout)
        self.extra_layout(layout)
        self.statusloggingUI(layout)

    def toggle_full_info(self, checked: bool, index: int) -> None:
        """
        Change the 'Full Info' view of one of the guidicts.

        Change the icon of the button from + to - according to the state.

        Parameters
        ----------
        checked : bool
            Expand 'Full info' (True) or hide additional info (False).
        index : int
            Number/Index of the guidict.
        """
        if checked:
            self.guidicts[index].extend_switch.setChecked(True)
            self.full_info[index].setIcon(MIcon("CHAR_-"))
        else:
            self.guidicts[index].extend_switch.setChecked(False)
            self.full_info[index].setIcon(MIcon("CHAR_+"))
        self.check_full_infos()

    def toggle_enable(self, checked: bool, index: int) -> None:
        """
        Enable and disable one of the guidicts.

        Change the color of the on/off switch according to the state.

        Parameters
        ----------
        checked : bool
            Switch it On (True) or Off (False).
        index : int
            Number/Index of the guidict.
        """
        if checked:
            self.guidicts[index].enable_switch.setChecked(True)
            self.guidicts[index].dock.show()
            self.enable[index].setIcon(
                MIcon("CUSTOM_Power", color=QColor("forestgreen"))
            )
        else:
            self.guidicts[index].enable_switch.setChecked(False)
            self.enable[index].setIcon(MIcon("CUSTOM_Power", color=QColor("gray")))
        self.check_enables()

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
            self.disable_all_action.setEnabled(True)
        else:
            self.disable_all_action.setEnabled(False)
        if on < total:
            self.enable_all_action.setEnabled(True)
        else:
            self.enable_all_action.setEnabled(False)

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
            self.less_info_all_action.setEnabled(True)
        else:
            self.less_info_all_action.setEnabled(False)
        if on < total:
            self.full_info_all_action.setEnabled(True)
        else:
            self.full_info_all_action.setEnabled(False)

    def enable_all(self) -> None:
        """Enable all guidicts."""
        for index, guidict in enumerate(self.guidicts):
            if guidict.allow_disabling:
                self.toggle_enable(True, index)

    def disable_all(self) -> None:
        """Disable all guidicts."""
        for index, guidict in enumerate(self.guidicts):
            if guidict.allow_disabling:
                self.toggle_enable(False, index)

    def full_info_all(self) -> None:
        """Show full info for all guidicts."""
        for index, guidict in enumerate(self.guidicts):
            has_hiding = any(variable.hide for variable in guidict.values())
            if has_hiding:
                self.toggle_full_info(True, index)

    def less_info_all(self) -> None:
        """Show less info for all guidicts."""
        for index, guidict in enumerate(self.guidicts):
            has_hiding = any(variable.hide for variable in guidict.values())
            if has_hiding:
                self.toggle_full_info(False, index)

    def toggle_activity_indicators(self) -> None:
        """
        Move the activity indicator from the logger to the docks (and back).

        It slightly adjusts the size for the respective options.
        """
        widgets = []
        if self.activity_in_logger:
            for i in range(self.activity_layout.count()):
                item = self.activity_layout.itemAt(i)
                widgets.append(item.widget())
            for i, widget in enumerate(widgets):
                widget.setFixedHeight(10)
                self.guidicts[i].toolbar.addWidget(widget)
                empty = QWidget()
                empty.setFixedWidth(10)
                self.guidicts[i].toolbar.addWidget(empty)
                self.activity_in_logger = False
        else:
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
            self.activity_in_logger = True

    def toggle_toolbar_view(self, checked: bool) -> None:
        """
        Toogles the visibility of all toolbars on and off.

        Parameters
        ----------
        checked : bool
            Show (True) or hide (False).
        """
        for guidict in self.guidicts:
            if checked:
                guidict.toolbar.show()
            else:
                guidict.toolbar.hide()

    def create_menu(self) -> None:
        """
        Create the main menu.

        Add 'Full Info', 'Enable' and 'View' menus to the main menu bar.
        """
        menu = self.menuBar()
        self.file_menu = menu.addMenu("&File")
        self.enable_menu = menu.addMenu("&Enable")
        self.fullinfo_menu = menu.addMenu("&Full info")
        self.view_menu = menu.addMenu("&View")
        self.custom_menu = menu.addMenu("&Custom")

        self.file_menu.addAction(self.quit_action)

        self.full_info = []
        self.enable = []
        self.guidict_view = []
        for i, guidict in enumerate(self.guidicts):
            dict_name = list(guidict.keys())[0]
            # Enable/ Disable
            enable_action = QAction(
                MIcon("CUSTOM_Power", color=QColor("forestgreen")), dict_name, self
            )
            enable_action.setIconText("Enable")
            self.enable.append(enable_action)
            self.enable[i].setCheckable(True)
            if guidict.enable_switch.isChecked():
                self.enable[i].setChecked(True)
            else:
                self.enable[i].setIcon(MIcon("CUSTOM_Power", color=QColor("gray")))
                self.enable[i].setChecked(False)
            self.enable[i].setEnabled(False)
            if guidict.allow_disabling:
                self.enable[i].setEnabled(True)
                self.enable[i].triggered.connect(
                    lambda checked=self.enable[
                        i
                    ].isChecked(), index=i: self.toggle_enable(checked, index)
                )
            guidict.toolbar.addAction(self.enable[i])
            self.enable_menu.addAction(self.enable[i])
            # View toggles
            view_action = QAction(dict_name, self)
            self.guidict_view.append(view_action)
            self.guidict_view[i].setCheckable(True)
            self.guidict_view[i].setChecked(True)
            self.guidict_view[i].triggered.connect(
                lambda checked=self.guidict_view[
                    i
                ].isChecked(), index=i: self.toggle_visible(checked, index)
            )
            self.view_menu.addAction(self.guidict_view[i])
            # Full info toggles
            has_hiding = any(variable.hide for variable in guidict.values())
            full_info_action = QAction(MIcon("CHAR_+"), dict_name, self)
            full_info_action.setIconText("Full info")
            self.full_info.append(full_info_action)
            self.full_info[i].setCheckable(True)
            if guidict.extend_switch.isChecked():
                self.full_info[i].setChecked(True)
                self.full_info[i].setIcon(MIcon("CHAR_-"))
            else:
                self.full_info[i].setChecked(False)
            self.full_info[i].setEnabled(False)
            if has_hiding:
                self.full_info[i].setEnabled(True)
                self.full_info[i].triggered.connect(
                    lambda checked=self.full_info[
                        i
                    ].isChecked(), index=i: self.toggle_full_info(checked, index)
                )
                guidict.extend_switch.toggled.connect(self.full_info[i].setChecked)
            guidict.toolbar.addAction(self.full_info[i])
            self.fullinfo_menu.addAction(self.full_info[i])
            spacer = QWidget()
            spacer.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            guidict.toolbar.addWidget(spacer)
            # Custom menu
            for action in guidict.menu_actions:
                action.setParent(self)
                self.custom_menu.addAction(action)
            if len(guidict.menu_actions) != 0:
                self.custom_menu.addSeparator()

        self.enable_all_action = QAction("Enable all", self)
        self.enable_all_action.triggered.connect(self.enable_all)
        self.disable_all_action = QAction("Disable all", self)
        self.disable_all_action.triggered.connect(self.disable_all)

        self.full_info_all_action = QAction("Full info all", self)
        self.full_info_all_action.triggered.connect(self.full_info_all)
        self.less_info_all_action = QAction("Less info all", self)
        self.less_info_all_action.triggered.connect(self.less_info_all)

        toggle_activity = QAction("Move activity indicators", self)
        toggle_activity.triggered.connect(self.toggle_activity_indicators)

        toggle_toolbar_action = QAction("Show Toolbar", self)
        toggle_toolbar_action.setShortcut(QKeySequence("Ctrl+1"))
        toggle_toolbar_action.setCheckable(True)
        initial_toolbar_view = False
        toggle_toolbar_action.setChecked(initial_toolbar_view)
        self.toggle_toolbar_view(initial_toolbar_view)
        toggle_toolbar_action.triggered.connect(self.toggle_toolbar_view)

        # Build the rest of the menu
        self.enable_menu.addSeparator()
        self.enable_menu.addAction(self.enable_all_action)
        self.enable_menu.addAction(self.disable_all_action)

        self.fullinfo_menu.addSeparator()
        self.fullinfo_menu.addAction(self.full_info_all_action)
        self.fullinfo_menu.addAction(self.less_info_all_action)

        self.view_menu.addSeparator()
        self.view_menu.addAction(toggle_toolbar_action)
        self.view_menu.addAction(toggle_activity)

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
        self.quit_action = QAction("Quit", self)
        if os.name == "nt":
            self.quit_action.setShortcut(QKeySequence.StandardKey.Close)
        else:
            self.quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.quit_action.triggered.connect(self.close)

        icondir = os.path.join(os.path.dirname(__file__), "..", "scripts", "icons")
        self.setWindowIcon(QIcon(os.path.join(icondir, "matr1x-control.png")))
        self.widget = QWidget()
        self.widget.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        self.main_layout = QVBoxLayout()

        self.widget.setLayout(self.main_layout)
        self.main_layout.addStretch()
        self.setCentralWidget(self.widget)
        return self.main_layout

    def guidictUI(self, layout: QLayout) -> None:
        """
        Set up guidict columns (main part of the ControlWindow).

        Parameters
        ----------
        layout : QLayout
            Qt-layout of main window.
        """
        # construct the layout from the GUI dicts
        for guidict in self.guidicts:
            content = guidict.create_GUI()
            self.addDockWidget(Qt.DockWidgetArea.TopDockWidgetArea, content)

    @pyqtSlot()
    def needToAdjustSize(self) -> None:
        """Adjust the size of the main window."""
        self.adjustSize()

    def extra_layout(self, layout: QLayout) -> None:
        """
        Define extra fields needed for specific control GUIs.

        By default, a central panic button is provided which will signal to all
        GUI elements to be put into a safe state.

        Parameters
        ----------
        layout : QLayout
            The layout to which the extra elements will be added.
        """
        elayout = QHBoxLayout()
        self.panicButton = QPushButton("Panic Button")
        self.panicButton.setStyleSheet("background-color: red;")
        self.panicButton.setCheckable(True)
        elayout.addWidget(self.panicButton)
        self.panicButton.clicked.connect(self.panic)
        layout.addLayout(elayout)

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
        layout.addWidget(self.status_box, stretch=1)

        # initialize common widgets
        self.status = QPlainTextEdit(self)
        self.status.setReadOnly(True)
        self.keep_enabled.append(self.status)
        self.activityIndicator = []
        self.activity_layout = QHBoxLayout()
        self.activity_layout.setSpacing(0)
        indicator_width = 17
        if len(self.guidicts) * indicator_width > 200:
            indicator_width = int(200 / len(self.guidicts))
        for idx, guidict in enumerate(self.guidicts):
            ql = QLabel(" ")
            ql.setFixedWidth(indicator_width)
            ql.setFixedHeight(30)
            ql.setStyleSheet("QLabel { background-color: lightgray; }")
            ql.setToolTip(guidict.dock.windowTitle())
            self.activityIndicator.append(ql)
            guidict.refresh_worker.activity.connect(
                lambda c, idx=idx: self.change_single_color(c, idx)
            )
            guidict.refresh_worker.panic.connect(self.panic)
            self.activity_layout.addWidget(ql)
        self.activity_in_logger = True

        self.activity.connect(self.change_color)
        self.deactivate.connect(self.deactivate_gui)
        self.togglelog = QPushButton("start log")
        self.togglelog.setCheckable(True)
        self.togglelog.setMaximumWidth(120)
        selectlog = QPushButton("select log file")
        selectlog.setMaximumWidth(140)
        self.configlog = QPushButton("show log config")
        self.configlog.setCheckable(True)

        self.loglabel = QLabel(os.path.basename(self.logfile))
        self.loglabel.setMaximumWidth(250)
        self.loglabel.setWordWrap(True)
        interval_label = QLabel("log interval (s):")
        self.interval = QSpinBox()
        self.interval.setRange(1, 24 * 3600 + 1)
        self.interval.setValue(60)
        self.interval.setMaximumWidth(70)
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
    @pyqtSlot(bool)
    @pyqtSlot(bool, str)
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
            logger.info(
                f"{time.strftime(datetimefmt)}: "
                f"Panic mode activated due to '{reason}'"
            )
            self.panicButton.setText(f"Panic mode activated due to '{reason}'")
            self.panicButton.setChecked(True)
            for g in self.guidicts:
                g.panic()
        else:
            for g in self.guidicts:
                self.panicButton.setText("Panic Button")
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

    @pyqtSlot(bool)
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

        If this is overloaded its important that the self.devInit property is
        set to True upon successful initialization of the devices.
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
                if len(v.widgets) > 2 and (
                    v.widgets[0].isHidden() is False and v.log is not None
                ):
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
            self.loglabel.setText(os.path.basename(self.logfile))
            # initialize system
            self.S_log.dcdata["Description"] = "Graphical interface logging data"
            self.S_log.dcdata["Type"] = "miscellaneous"
            self.S_log.set(output_file=self.logfile)
            # write new datafile header
            self.S_log.init_datafile("matrix script generated")
            # turn off config and set data
            self.configLog(False)
            self.configlog.setEnabled(False)
            self.configlog.setChecked(False)
            self.togglelog.setText("data log running")
            # start thread
            self.terminate_log = False
            self.terminated_log = False
            self.tlog = threading.Thread(target=self.loggingFunc, daemon=True)
            self.tlog.start()
            self.logging = True
            print(f"{time.strftime(datetimefmt)}: data logging started")

        elif self.logging is True:
            self.S_log.reset()
            self.terminate_log = True
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
            self, "Select log file", logfolder, f"data log files (*{output_extension})"
        )[0]
        self.logfile = filename or self.logfile
        if not self.logfile.endswith(output_extension):
            self.logfile += output_extension
        self.loglabel.setText(os.path.basename(self.logfile))

    @catchEmitError
    def loggingFunc(self) -> None:
        """Perform logging at specified intervals."""
        cnt = 0
        while not self.terminate_log:
            # get interval and initialize counter for seconds
            interval = self.interval.value()
            if 0 == cnt:
                # every interval seconds, perform log
                self.S_log.trigger()
                self.S_log.take_measurement_point(self.logfile)
            # ensure logging is interruptible even while waiting for
            # the next logpoint
            cnt = (cnt + 1) % interval
            time.sleep(1)
        self.terminated_log = True

    @catchEmitError
    def refreshDict(self) -> None:
        """
        Update the GUI fields in the main loop.

        The readout is conducted thread-safe. The main loop terminates
        once self.terminate is set to True and sets self.terminated
        once it's successfully finished.

        This method is typically decorated with an error handler to catch
        and terminate upon an uncaught Python exception.
        """
        # start guidicts and get minimum/maximum period
        # minimal period used as check interval for the shutdown
        min_period = 1
        # maximal period serves as delay for the potential start of the log
        max_period = 1
        for guidict in self.guidicts:
            dockw = guidict.dock
            if not dockw.isVisible():
                guidict.enable_switch.setChecked(False)
                guidict.restoreFeatures()
            else:
                guidict.start()
            min_period = min(min_period, guidict.refresh_period)
            max_period = max(max_period, guidict.refresh_period)
        if self._run_log_on_start:
            # delay log start by one refresh_period with the hope that then all
            # values are initialized
            timer = threading.Timer(max_period, lambda: self.toggleLog(True))
            timer.start()
        while True:
            time.sleep(min_period)
            if self.terminate:
                for guidict in self.guidicts:
                    if guidict.running:
                        guidict.stop()
                break

        # flag for stating that thread has ended
        self.terminated = True

    # general local server and start stop overhead
    def __enter__(self):
        """
        Start refreshing the values in a separate thread and initialize devices.

        This method checks that the devices are initialized and starts a thread
        to continuously refresh the values in the GUI.
        """
        # initialize devices
        print(f"{time.strftime(datetimefmt)}: initializing devices")
        self.connectDev()

        # initialize thread to refresh dicts
        # check if successful
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

            self.t = threading.Thread(target=self.refreshDict, daemon=True)
            self.t.start()
            self.running = True
            self.startServer()

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """
        Stop the refreshDict function and close devices.

        This method is called when exiting the context manager. It handles the
        cleanup process, including stopping the server, terminating the refresh
        thread, and stopping any ongoing logging.
        """
        if exc_type is not None:
            print(exc_type, exc_value, exc_traceback)

        self.stopServer()
        if self.running is True:
            self.terminate = True
            self.running = False
            # wait for refreshDict to terminate
            while self.terminated is False:
                time.sleep(0.01)
        if self.logging is True:
            self.terminate_log = True
            self.logging = False
            # wait for logging to terminate
            while self.terminated_log is False:
                time.sleep(0.01)

    def startServer(self) -> None:
        """
        Start the local TCP server with the driver functions specified in cmds.

        This method initializes and starts a SCPI TCP server using the command list
        defined in the class.
        """
        self._local_server = scpi_tcpserver.SCPI_TCP_Server(
            self.cmd_list, port=self._port
        )
        self._local_server.start()

    def stopServer(self) -> None:
        """
        Stop the local TCP server.

        If a server instance exists, this method stops it and sets the server
        attribute to None.
        """
        if self._local_server is not None:
            self._local_server.stop()
        self._local_server = None

    def change_single_color(self, color: str, idx: int) -> None:
        """
        Change the background color of a single activity indicator.

        Parameters
        ----------
        color : str
            The color to set as background, in a format accepted by Qt stylesheets.
        idx : int
            The index of the activity indicator to change.
        """
        self.activityIndicator[idx].setStyleSheet(
            f"QLabel {{ background-color: {color}; }}"
        )

    @pyqtSlot(str)
    def change_color(self, color: str) -> None:
        """
        Change the background color of all activity indicators.

        Parameters
        ----------
        color : str
            The color to set as background, in a format accepted by Qt stylesheets.
        """
        for ql in self.activityIndicator:
            ql.setStyleSheet(f"QLabel {{ background-color: {color}; }}")

    @pyqtSlot(bool)
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

    @pyqtSlot()
    def saveCurrentState(self):
        """
        Save current window and dock geometry.

        This method saves the current size, position, and state of the window,
        as well as the visibility of the status box. These settings will be
        reloaded upon restart of the Control GUI.

        Note:
        If this should be done on every close, this method should be called
        from the closeEvent.
        """
        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("windowState", self.saveState())
        self.settings.setValue(
            "status_visible", self.status_box.toggle_button.isChecked()
        )

    @pyqtSlot(type, Exception, str)
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
        # end the refreshDict thread
        self.terminate = True
        self.terminate_log = True
        # stop guidicts immediately on error (Prevents a sometimes occuring
        # timeout error)
        for guidict in self.guidicts:
            if guidict.running:
                guidict.stop(wait=False)
        if pointer == "refreshDict":
            # set terminated flag since our main loop is dead
            self.terminated = True
        elif pointer == "loggingFunc":
            self.terminated_log = True
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
