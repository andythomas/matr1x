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
"""
Generate sweeps for matrix via a straightforward GUI.

It heavily relies on numpy.linspace for the creation of the sweep
segments.
"""

import logging
import os
import re
import sys
import time
import traceback
from ast import literal_eval
from collections.abc import Callable
from dataclasses import dataclass
from math import floor
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy
import pyqtgraph as pg
from PySide6.QtCore import QByteArray, QObject, QPoint, QPointF, QSize, Qt, Signal
from PySide6.QtGui import QAction, QColor, QFocusEvent, QKeySequence, QMouseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import matr1x
from matr1x import datetimefmt, system_directories, system_names, usersfolder
from matr1x.control.util import QtGracefulKiller
from matr1x.error_handling import Error, Result, Success, install_error_handler
from matr1x.gui_util import (
    AboutBox,
    CustomViewBox,
    FileDropMixin,
    LoggingWindow,
    MApplication,
    SaferQSettings,
    SystemListWidget,
    check_config,
    create_tray_notification,
    get_application_instance,
    get_matrix_icon,
    open_matrix_toml,
    protected_restore,
    save_messagebox,
    validator,
)
from matr1x.system import MergedSystem
from matr1x.util import (
    create_temp_dir_with_symlinks,
    generate_col_index,
    get_importable_module_name,
)

__all__ = ["MainWindow"]

if sys.platform == "win32":
    try:
        from ctypes import windll

        myappid = "python.matr1x.sweep-generator.version"
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass

logger = logging.getLogger(Path(__file__).name)


# the next two could (should?!) also be static functions of the main window
def calculate_sweep(
    sweep_parameters: list[list[list[float | int]]],
    loop_over: list[int],
    up_down: list[bool],
    repeat: list[int],
) -> Result[list[list[float]], str]:
    """
    Generate a list of sweeps defined by given parameters.

    Parameters
    ----------
    sweep_parameters : list
        List of lists containing the sweep parameters (as 3 item list).
    loop_over : list
        List of integers (<len(loop_over)) defining the looping scheme.
    up_down : list
        List of bools defining if the sweep is going both ways.
    repeat : list
        List of integers defining how often the sweep ranges are repeated.

    Returns
    -------
    list
        List of sweeps that contains all parameters that are to be set. Individual
        sweeps from columns still need to be stretched to equal length (sparse).
        Otherwise, loop over is not handled properly.
    """
    lenA = len(sweep_parameters)
    if len(loop_over) != lenA or len(up_down) != lenA or len(repeat) != lenA:
        return Error("The length of the arrays is not equal.")
    sweeps: list[list[float]] = []
    for indexS, parmSets in zip(range(lenA), sweep_parameters):
        i = 0
        sweeps.append([])
        while i < repeat[indexS]:
            tempSweep = []
            for parm in parmSets:
                # generate the sweepRange using np.linspace, has to be list
                # so += works

                sweepRange = numpy.linspace(float(parm[0]), float(parm[1]), int(parm[2]))
                if any(numpy.isnan(sweepRange)) or any(numpy.isinf(sweepRange)):
                    return Error("Inf or Nan in sweep, check parameters")
                tempSweep += list(sweepRange)
            if up_down[indexS]:
                # if up down is true, add the reversed sweep to the sweep
                tempSweep += list(reversed(tempSweep))
            sweeps[indexS] += tempSweep
            i += 1
    # check if there are loops of loops and detect hirarchy so we
    # can properly generate the sweep
    hirarchy = []
    for i in range(lenA):
        result = check_depth(i, loop_over)
        if isinstance(result, Error):
            # Recursive loop, you should really not do that!
            # (i.e. don't loop col(a) over col(b) over col(a)!)
            return Error("Recursive loop, please check loop over")
        hirarchy.append(result.value)
    hCnt = max(hirarchy)
    while 0 <= hCnt:
        for indexS in range(lenA):
            if indexS == loop_over[indexS]:
                # looping a column over itself is not how it's done!
                loop_over[indexS] = -1
            elif -1 != loop_over[indexS] and hCnt == hirarchy[indexS]:
                # start with highest hirarchy first (i.e. column which is
                # the most fundamental)
                col = loop_over[indexS]
                tempSweep = sweeps[indexS].copy()
                # copy the initial sweep to be looped
                for j in range(len(sweeps[col]) - 1):
                    # for each element in the looped over column append the
                    # initial sweep
                    sweeps[indexS] += tempSweep
                loop_over[indexS] = -1
        hCnt -= 1
    return Success(sweeps)


def check_depth(index: int, array: list, depth: int = 0) -> Result[int, int]:
    """
    Recursive function to determine the hierarchical depth of an item in an array.

    This function checks how deeply nested an item is within a given array structure.
    It recursively follows references until it reaches the deepest level or detects
    a circular reference.

    Parameters
    ----------
    index : int
        Index of the item in array for which the hierarchy is to be determined.
    array : list
        The array defining the hierarchy.
    depth : int, optional
        Recursion depth, does not need to be set when calling the function.

    Returns
    -------
    int
        Hierarchy of the item index within the given array.
    """
    if depth > 50:
        # break the recursion, something went wrong
        return Error(-1)
    if index in array:
        cnt = len([i for i, x in enumerate(array) if x == index])
        # adds the position of the occurences of the index to a list
        if cnt > 1:
            # multiple occurences of index in array
            d = []
            occ = -1
            for _ in range(cnt):
                # follow all branches of the occurences to get the actual
                # maximum hirarchy of the occurence
                occ = array.index(index, occ + 1)
                d.append(check_depth(occ, array, depth + 1))
            return max(d)
        return check_depth(array.index(index), array, depth + 1)
    # if no more occurence is in the array, then return the current depth
    return Success(depth)


@dataclass
class ColumnData:
    """Container for column data."""

    name: list[str]
    unit: list[str]
    sign: list[str]
    color: list[bool]


class CheckBoxFocus(QCheckBox):
    """Reimplement CheckBox with focusInEvent."""

    focusIn = Signal()

    def focusInEvent(self, e: QFocusEvent) -> None:
        """Handle focus in event and emit custom signal."""
        super().focusInEvent(e)
        self.focusIn.emit()


class LineEditFocus(QLineEdit):
    """Reimplement LineEdit with focusInEvent."""

    focusIn = Signal()

    def focusInEvent(self, e: QFocusEvent) -> None:
        """Handle focus in event and emit custom signal."""
        super().focusInEvent(e)
        self.focusIn.emit()


class SpinBoxFocus(QSpinBox):
    """Reimplement QSpinBox with focusInEvent."""

    focusIn = Signal()

    def focusInEvent(self, e: QFocusEvent) -> None:
        """Handle focus in event and emit custom signal."""
        super().focusInEvent(e)
        self.focusIn.emit()


class QLabelWithColor(QLabel):
    """Allow QLabel with highlight color and mouseclick reaction."""

    clicked = Signal()

    def __init__(self):
        """Init with colored background for bright and dark mode."""
        super().__init__()
        self.color_bright = "#DCF5D4"
        self.color_dark = "#325725"
        self._update_colors()
        get_application_instance().isDarkSignal.connect(self._update_colors)

    def _update_colors(self) -> None:
        """Change color while avoiding recursion."""
        self.stylesheet_bright = f"""
                     QLabel {{
                         background-color: {self.color_bright};
                         color: black;
                     }}
                 """
        self.stylesheet_dark = f"""
                     QLabel {{
                         background-color: {self.color_dark};
                         color: #DBDBDB;
                     }}
                 """
        if get_application_instance().isDark:
            self.setStyleSheet(self.stylesheet_dark)
        else:
            self.setStyleSheet(self.stylesheet_bright)

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        """
        Detect mouse-click for proper column highlighting.

        The column of the click is emitted as a Signal.
        """
        super().mousePressEvent(ev)
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            active_window = MApplication.activeWindow()
            if active_window is not None:
                active_window.setFocus()

    def setColors(self, color_bright: str, color_dark: str) -> None:
        """
        Change the colors for both modes.

        Parameters
        ----------
        color_bright : str
            The six digit hex code for the bright mode color (e.g. #DCF5D4).
        color_dark : str
            The six digit hex code for the dark mode color.
        """
        self.color_bright = color_bright
        self.color_dark = color_dark
        self._update_colors()


@dataclass
class LabelWidgets:
    """The labels for the respective column entries."""

    column: QLabel
    nameunit: QLabel
    start: QLabel
    end: QLabel
    points: QLabel
    append: QWidget
    repeat: QLabel
    doublearrow: QLabel
    updown: QLabel
    loopover: QLabel


@dataclass
class ColumnWidgets:
    """The widgets for the respective column entries."""

    column: QLabelWithColor
    nameunit: QLabelWithColor
    start: LineEditFocus
    end: LineEditFocus
    points: LineEditFocus
    append: QPushButton
    repeat: SpinBoxFocus
    doublearrow: QLabel
    updown: QCheckBox
    loopover: QComboBox


class ColumnGenerator(QObject):
    """Generate the sweep labels and columns."""

    widget_modified = Signal()
    select_grid_column = Signal(int)
    append = Signal(int)

    def __init__(
        self,
        columns: ColumnData,
        column: int = 0,
    ):
        """
        Generate the general labels and the widgets for each column.

        Parameters
        ----------
        columns: ColumnData
            The properties of the columns (name, unit, sign, color).
        column: int
            The current column in the MainWindow.
        """
        super().__init__()
        self.columns = columns
        self.column = column
        self.column_widgets: ColumnWidgets = self.create_widgets()

        placeholder = QWidget()
        placeholder.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        placeholder.setFixedSize(0, 0)

        self.label_widgets: LabelWidgets = LabelWidgets(
            column=QLabel("Column"),
            nameunit=QLabel("Name (Unit)"),
            start=QLabel("Start value"),
            end=QLabel("End value"),
            points=QLabel("Point count"),
            append=placeholder,
            repeat=QLabel("Repeat/ Up-down"),
            doublearrow=QLabel(""),
            updown=QLabel(""),
            loopover=QLabel("Loop over"),
        )

    def create_widgets(self) -> ColumnWidgets:
        """
        Create all widgets for the column.

        Returns
        -------
        ColumnWidgets
            A dataclass containing all the created widgets.
        """
        column_widget = QLabelWithColor()
        column_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column_widget.setText(self.columns.sign[self.column])
        if not self.columns.color[self.column]:
            column_widget.setColors("#D0EBFE", "#1E4962")
        column_widget.clicked.connect(lambda: self.select_grid_column.emit(self.column))

        nameunit_widget = QLabelWithColor()
        nameunit_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name = self.columns.name[self.column].strip()
        unit = self.columns.unit[self.column].strip()
        nameunit_widget.setText(f"{name} ({unit})")
        if not self.columns.color[self.column]:
            nameunit_widget.setColors("#D0EBFE", "#1E4962")
        nameunit_widget.clicked.connect(lambda: self.select_grid_column.emit(self.column))

        start_widget = LineEditFocus()
        start_widget.setAlignment(Qt.AlignmentFlag.AlignRight)
        start_widget.setValidator(validator[float])
        start_widget.focusIn.connect(lambda: self.select_grid_column.emit(self.column))

        end_widget = LineEditFocus()
        end_widget.setAlignment(Qt.AlignmentFlag.AlignRight)
        end_widget.setValidator(validator[float])
        end_widget.focusIn.connect(lambda: self.select_grid_column.emit(self.column))

        points_widget = LineEditFocus()
        points_widget.setAlignment(Qt.AlignmentFlag.AlignRight)
        points_widget.setValidator(validator[numpy.uint])
        points_widget.focusIn.connect(lambda: self.select_grid_column.emit(self.column))

        append_widget = QPushButton("+")
        temp_widget = QLineEdit(None)
        size = temp_widget.sizeHint().height()
        temp_widget.deleteLater()
        append_widget.setFixedSize(size, int(2.9 * size))
        append_widget.clicked.connect(lambda: self.widget_modified.emit())
        append_widget.clicked.connect(lambda: self.append.emit(self.column))

        repeat_widget = SpinBoxFocus()
        repeat_widget.setRange(1, 999)
        repeat_widget.setAlignment(Qt.AlignmentFlag.AlignRight)
        repeat_widget.valueChanged.connect(lambda: self.widget_modified.emit())
        repeat_widget.focusIn.connect(lambda: self.select_grid_column.emit(self.column))

        arrow_icon = get_matrix_icon(
            "CUSTOM_Updown",
            color=QColor("transparent"),
            pencolor=QColor("darkgray"),
        )
        doublearrow_widget = QLabel()
        height = 24
        doublearrow_widget.setPixmap(arrow_icon.pixmap(height, height))

        updown_widget = CheckBoxFocus()
        updown_widget.stateChanged.connect(lambda: self.widget_modified.emit())
        updown_widget.focusIn.connect(lambda: self.select_grid_column.emit(self.column))

        loopover_widget = QComboBox()
        loopover_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        font = loopover_widget.font()
        font.setPointSize(font.pointSize() - 1)
        loopover_widget.setFont(font)
        loopover_widget.currentIndexChanged.connect(lambda: self.widget_modified.emit())
        loopover_widget.activated.connect(lambda: self.select_grid_column.emit(self.column))
        columns = ["None"] + [name.strip() for name in self.columns.name]
        loopover_widget.addItems(columns)

        return ColumnWidgets(
            column=column_widget,
            nameunit=nameunit_widget,
            start=start_widget,
            end=end_widget,
            points=points_widget,
            append=append_widget,
            repeat=repeat_widget,
            doublearrow=doublearrow_widget,
            updown=updown_widget,
            loopover=loopover_widget,
        )


@dataclass
class ActionGroup:
    """Actions to be utilized in the GUI."""

    matrix_settings: QAction
    about: QAction
    show_log: QAction
    new_file: QAction
    load: QAction
    add_system: QAction
    remove_system: QAction
    save: QAction
    save_as: QAction
    append: QAction
    append_to: QAction
    quit: QAction
    sweep: QAction
    toggle_toolbar: QAction
    preview: QAction


class UIBuilder:
    """Create actions, toolbar and menu."""

    def __init__(self, window: QMainWindow):
        self.window: QMainWindow = window
        self.actions: ActionGroup
        self.toolbar: QToolBar
        self.system_list: SystemListWidget
        self._create_actions()
        self._create_toolbar()
        self._create_menu()

    def _create_actions(self) -> None:
        """Create all actions."""
        matrix_settings_action = QAction("Show matrix toml", self.window)
        matrix_settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        matrix_settings_action.setShortcut(QKeySequence.StandardKey.Preferences)
        about_action = QAction("About", self.window)
        about_action.setMenuRole(QAction.MenuRole.AboutRole)
        show_log_action = QAction("Show Log Window", self.window)
        show_log_action.setCheckable(True)
        new_file_action = QAction(get_matrix_icon("SP_FileIcon"), "New", self.window)
        new_file_action.setShortcut(QKeySequence.StandardKey.New)
        new_file_action.setEnabled(False)
        load_action = QAction(get_matrix_icon("SP_DialogOpenButton"), "Open", self.window)
        load_action.setShortcut(QKeySequence.StandardKey.Open)
        add_system_action = QAction(
            get_matrix_icon("CHAR_+", QColor("RoyalBlue")), "Add System", self.window
        )
        remove_system_action = QAction(
            get_matrix_icon("CHAR_-", QColor("RoyalBlue")), "Remove System", self.window
        )
        remove_system_action.setEnabled(False)
        save_action = QAction(get_matrix_icon("SP_DialogSaveButton"), "Save", self.window)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.setEnabled(False)
        save_as_action = QAction(get_matrix_icon("SP_DialogSaveButton"), "Save As...", self.window)
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        append_action = QAction(get_matrix_icon("SP_DialogSaveButton"), "Append", self.window)
        append_to_action = QAction(
            get_matrix_icon("SP_DialogSaveButton"), "Append To...", self.window
        )
        quit_action = QAction("Quit", self.window)
        if os.name == "nt":
            quit_action.setShortcut(QKeySequence.StandardKey.Close)
        else:
            quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        sweep_action = QAction(get_matrix_icon("SP_BrowserReload"), "Draft Sweep", self.window)
        sweep_action.setEnabled(False)
        toggle_toolbar_action = QAction("Show Toolbar", self.window)
        toggle_toolbar_action.setShortcut(QKeySequence("Ctrl+1"))
        toggle_toolbar_action.setCheckable(True)
        toggle_toolbar_action.setChecked(True)
        preview_action = QAction(
            get_matrix_icon("matr1x-matrix-preview.png", QColor("RoyalBlue")),
            "Preview",
            self.window,
        )
        preview_action.setEnabled(False)
        self.actions = ActionGroup(
            matrix_settings=matrix_settings_action,
            about=about_action,
            show_log=show_log_action,
            new_file=new_file_action,
            load=load_action,
            add_system=add_system_action,
            remove_system=remove_system_action,
            save=save_action,
            save_as=save_as_action,
            append=append_action,
            append_to=append_to_action,
            quit=quit_action,
            sweep=sweep_action,
            toggle_toolbar=toggle_toolbar_action,
            preview=preview_action,
        )

    def _create_toolbar(self) -> None:
        """Create the toolbar."""
        self.system_list = SystemListWidget(self.window)
        self.system_list.setMinimumHeight(50)
        self.system_list.setMaximumHeight(50)
        self.save_button = QToolButton()
        self.save_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.save_button.setIcon(get_matrix_icon("SP_DialogSaveButton"))
        self.save_button.setText("Save")
        self.save_button.setDefaultAction(self.actions.save)
        self.save_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        save_pulldown = QMenu(self.window)
        save_pulldown.addAction(self.actions.save_as)
        save_pulldown.addAction(self.actions.append)
        save_pulldown.addAction(self.actions.append_to)
        self.save_button.setMenu(save_pulldown)

        self.toolbar = QToolBar("Toolbar")
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.toolbar.setFloatable(False)
        self.toolbar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        icon_size = get_application_instance().toolbar_icon_size()
        self.toolbar.setIconSize(QSize(icon_size, icon_size))
        self.toolbar.setAllowedAreas(
            Qt.ToolBarArea.TopToolBarArea | Qt.ToolBarArea.BottomToolBarArea
        )
        self.toolbar.addAction(self.actions.new_file)
        self.toolbar.addAction(self.actions.load)
        self.toolbar.addWidget(self.save_button)
        self.toolbar.addAction(self.actions.sweep)
        empty = QWidget()
        empty.setFixedWidth(icon_size)
        empty2 = QWidget()
        empty2.setFixedWidth(icon_size)
        self.toolbar.addWidget(empty)
        self.toolbar.addAction(self.actions.preview)
        self.toolbar.addWidget(empty2)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.actions.add_system)
        self.toolbar.addWidget(self.system_list)
        self.toolbar.addAction(self.actions.remove_system)
        self.window.addToolBar(self.toolbar)

    def _create_menu(self) -> None:
        """Create the main menu."""
        menu = self.window.menuBar()
        file_menu = menu.addMenu("&File")
        file_menu.addAction(self.actions.new_file)
        file_menu.addAction(self.actions.load)
        file_menu.addSeparator()
        file_menu.addAction(self.actions.save)
        file_menu.addAction(self.actions.save_as)
        file_menu.addAction(self.actions.append)
        file_menu.addSeparator()
        file_menu.addAction(self.actions.add_system)
        file_menu.addAction(self.actions.remove_system)
        file_menu.addSeparator()
        file_menu.addAction(self.actions.quit)  # This gets auto-moved on a Mac
        control_menu = menu.addMenu("&Control")
        control_menu.addAction(self.actions.sweep)
        view_menu = menu.addMenu("&View")
        view_menu.addAction(self.actions.toggle_toolbar)
        view_menu.addAction(self.actions.matrix_settings)
        help_menu = menu.addMenu("&Help")
        help_menu.addAction(self.actions.about)
        help_menu.addAction(self.actions.show_log)


class SweepPreviewPopup(QDialog):
    """
    Show the sweep as list and as plot in a pop-up.

    Parameters
    ----------
    index : int
        index of column in sweep to be displayed on startup
    sweep : list
        list of sweeps for each column
    col : ColumnData
        column names, units and parameter identifiers
    """

    def __init__(
        self,
        parent: QWidget | None,
        index: int,
        sweep: list[list[float]],
        col: ColumnData,
    ):
        super().__init__(parent)
        self.sweep = sweep
        self.columns = col

        self.data_table = QTableWidget()
        self.data_table.setColumnCount(1)
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setHorizontalHeaderLabels(["Value"])
        header = self.data_table.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.Stretch)
        self.posLabel = QLabel(f"x: {0:e}\ny: {0:e}")

        comboBox = QComboBox()
        columns = []
        for c, cs in zip(self.columns.name, self.columns.sign):
            columns.append(cs + " - " + c.strip())
        comboBox.addItems(columns)
        comboBox.setCurrentIndex(index)
        comboBox.currentIndexChanged.connect(self.indexChanged)

        self.vb = CustomViewBox()
        self.pw = pg.PlotWidget(viewBox=self.vb, name="plot1", enableMenu=False)
        self.plt = self.pw.plot(
            symbolPen=(65, 105, 225),
            symbolBrush=(65, 105, 225),
        )
        self.plt.setPen((65, 105, 225), width=3)
        get_application_instance().isDarkSignal.connect(self.update_colors)
        self.proxy = pg.SignalProxy(
            self.pw.getViewBox().scene().sigMouseMoved, rateLimit=30, slot=self.mouse_moved
        )
        self.update_colors()

        self.plot_list_range_x(index)
        self.update_data_table(index)

        left_layout = QVBoxLayout()
        left_layout.addWidget(comboBox)
        left_layout.addWidget(self.data_table)
        right_layout = QVBoxLayout()
        right_layout.addWidget(self.posLabel)
        right_layout.addWidget(self.pw)
        main_layout = QHBoxLayout()
        main_layout.addLayout(left_layout, 0)
        main_layout.addLayout(right_layout, 1)
        self.setLayout(main_layout)
        self.show()

    def update_colors(self) -> None:
        """Update colors according to the theme."""
        if get_application_instance().isDark:
            self.pw.setBackground("k")
            self.pw.getAxis("left").setPen("w")
            self.pw.getAxis("bottom").setPen("w")
            self.pw.getAxis("left").setTextPen("w")
            self.pw.getAxis("bottom").setTextPen("w")
        else:
            self.pw.setBackground("w")
            self.pw.getAxis("left").setPen("k")
            self.pw.getAxis("bottom").setPen("k")
            self.pw.getAxis("left").setTextPen("k")
            self.pw.getAxis("bottom").setTextPen("k")

    def indexChanged(self, newIndex: int) -> None:
        """
        Show the interface for new index if index is changed.

        Parameters
        ----------
        newIndex : int
            The updated index.
        """
        self.plot_list_range_x(newIndex)
        self.update_data_table(newIndex)

    def update_data_table(self, index: int) -> None:
        """
        Update the table to show the current sweep.

        Parameters
        ----------
        index : int
            The index of the sweep to be displayed.
        """
        self.data_table.setRowCount(len(self.sweep[index]))
        for index, item in zip(range(len(self.sweep[index])), self.sweep[index]):
            value = QTableWidgetItem(str(item))
            value.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.data_table.setItem(index, 0, value)

    def mouse_moved(self, event: tuple[QPointF]) -> None:
        """Implement event to update cursor position while pointer is in plot."""
        mousePoint = self.vb.mapSceneToView(event[0])
        self.posLabel.setText(f"x: {mousePoint.x():e}\ny: {mousePoint.y():e}")

    def plot_list_range_x(self, index: int) -> None:
        """Update the plot to show sweep[index] against its range."""
        self.pw.getAxis("left").textWidth = 0
        length = len(self.sweep[index])
        self.plt.setData(x=numpy.linspace(0, length, length), y=self.sweep[index], symbol="o")

        self.pw.setLabel("bottom", "index")
        self.pw.setLabel(
            "left",
            (self.columns.name[index].strip() + " [" + self.columns.unit[index].strip() + "]"),
        )


class MainWindow(FileDropMixin, QMainWindow):
    """Define main layout, run everything."""

    extension = ".sw8"
    window_title_dirty = Signal()

    def __init__(
        self,
        filename: Path | None = None,
        system=None,
        inputcb: Callable[[str], None] | None = None,
    ):
        """
        Init the main window.

        Parameters
        ----------
        filename : str
            Sweep file to load for editing.
        system : str
            Path to system(s) for which an input file should be generated.
        inputcb : function handle
            Callback function used to return the filename of the generated file.
        """
        super().__init__()
        self.log_window = LoggingWindow(parent=self)
        self.log_window.hide()
        logger.info("sweep-generator starting")

        self.setWindowIcon(get_matrix_icon("matr1x-sweep-generator.png"))

        # file handling helpers
        self.system: MergedSystem | None = system
        self.inputcb: Callable[[str], None] | None = inputcb
        self.last_loaded_system: str | None = None
        self.last_filename: Path | None = None
        self.dirty: bool = False
        self.shortcut_dir: TemporaryDirectory | None = None

        self.settings = SaferQSettings("matr1x", "sweep-generator")

        self.window_title_dirty.connect(lambda: self.update_window_title(dirty=True))

        self.columns = ColumnData(name=[], unit=[], sign=[], color=[])

        # sweep variables
        self.loop_over = []
        self.up_down = []
        self.repeat = []
        self.sweep_params = []
        self.systemFilename = ""

        # gui variables
        self.preview_column = 0

        # initialize generic (system independent) part of ui
        self.outputList: list
        self.populated = False
        self.init_ui()

        self.setAcceptDrops(True)
        self.setValidExtensions([self.extension])
        self.file_dropped.connect(lambda file: self.open_file(Path(file)))

        # If filename is passed as command line argument
        if filename is not None:
            if self.is_valid_extension(filename):
                self.open_file(filename)
                self.last_filename = filename

    def closeEvent(self, a0) -> None:
        """
        Store settings before closing app.

        If the script was modified without saving, a dialog asks how to
        proceed.
        """
        if self.dirty:
            ret = save_messagebox(self)
            if ret == QMessageBox.StandardButton.Cancel:
                a0.ignore()
                return
            if ret == QMessageBox.StandardButton.Save:
                if not self.save_file():
                    # if save fails, do not close.
                    a0.ignore()
                    return
        self.save_window_state()
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.log_window.log_handler)
        self.log_window.deleteLater()
        a0.accept()

    def save_window_state(self) -> None:
        """
        Save application configuration until next startup.

        For convenience, main window geometry, toolbar placement and
        logger position and size are saved.
        """
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("toolbar_position", self.toolBarArea(self.ui.toolbar).value)
        self.settings.setValue("log_window/position", self.log_window.pos())
        self.settings.setValue("log_window/size", self.log_window.size())

    def restore_window_state(self) -> None:
        """
        Restore application configuration to look similar to the previous use.

        Main window geometry and toolbar placement are restored.
        """
        self.resize(self.sizeHint())  # Just in case it is the first start
        self.restoreGeometry(
            self.settings.safer_value("geometry", defaultValue=QByteArray(), type=QByteArray)
        )
        toolbar_pos = self.settings.safer_value(
            "toolbar_position", Qt.ToolBarArea.TopToolBarArea.value, type=int
        )
        self.addToolBar(Qt.ToolBarArea(toolbar_pos), self.ui.toolbar)
        self.log_window.move(
            self.settings.safer_value("log_window/position", self.log_window.pos(), type=QPoint)
        )
        self.log_window.resize(
            self.settings.safer_value("log_window/size", self.log_window.size(), type=QSize)
        )

    def toggle_toolbar_view(self, checked: bool) -> None:
        """
        Toogles the visibility of the toolbar on and off.

        Parameters
        ----------
        checked: bool
            Show (True) or hide (False) the toolbar.
        """
        if checked:
            self.ui.toolbar.show()
        else:
            self.ui.toolbar.hide()

    def toggle_log_window(self) -> None:
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

    def init_ui(self) -> None:
        """Generate the main GUI."""
        self.setWindowTitle("Sweep Generator")
        # Start the layout
        self.grid = QGridLayout()
        self.grid.setVerticalSpacing(5)
        self.grid.setHorizontalSpacing(10)
        main_layout = QVBoxLayout()
        main_layout.addLayout(self.grid)
        self.utility_layout = QVBoxLayout()
        main_layout.addLayout(self.utility_layout)
        self.main_widget = QWidget()
        self.main_widget.setLayout(main_layout)
        self.setCentralWidget(self.main_widget)
        # generate sweep grid labels and layout
        self.sweep_table = QTableWidget()
        self.sweep_table.setColumnCount(4)
        self.sweep_table.setHorizontalHeaderLabels(["Start", "Stop", "Points", "Delete"])
        header = self.sweep_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.sweep_table.verticalHeader().hide()
        self.sweep_preview = QTableWidget()
        self.sweep_preview.setColumnCount(1)
        self.sweep_preview.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.sweep_preview.setAlternatingRowColors(True)
        self.sweep_preview.setHorizontalHeaderLabels(["Preview of the generated sweep-parameters"])
        header = self.sweep_preview.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.Stretch)
        table_width = self.sweep_preview.viewport().width()
        self.sweep_preview.setColumnWidth(0, table_width)
        central_view = QHBoxLayout()
        central_view.addWidget(self.sweep_preview)
        central_view.addWidget(self.sweep_table)
        self.utility_layout.addLayout(central_view)
        self.ui = UIBuilder(self)
        self.ui.actions.matrix_settings.triggered.connect(open_matrix_toml)
        self.ui.actions.about.triggered.connect(self.info_box)
        self.ui.actions.show_log.triggered.connect(self.toggle_log_window)
        self.ui.actions.new_file.triggered.connect(self.new_file)
        self.ui.actions.load.triggered.connect(self.gui_from_sweep)
        self.ui.actions.add_system.triggered.connect(self.add_system)
        self.ui.actions.remove_system.triggered.connect(self.delete_selected_system)
        self.ui.actions.save.triggered.connect(self.save_file)
        self.ui.actions.save_as.triggered.connect(lambda: self.save_file(dialog=True))
        self.ui.actions.append.triggered.connect(lambda: self.save_file(append=True))
        self.ui.actions.append_to.triggered.connect(
            lambda: self.save_file(append=True, dialog=True)
        )
        self.ui.actions.quit.triggered.connect(self.close)
        self.ui.actions.sweep.triggered.connect(self.print_sweep_to_preview)
        self.ui.actions.toggle_toolbar.triggered.connect(self.toggle_toolbar_view)
        self.ui.actions.preview.triggered.connect(self.preview_sweep)
        self.ui.system_list.orderChanged.connect(self.filename_changed)
        self.ui.toolbar.visibilityChanged.connect(self.ui.actions.toggle_toolbar.setChecked)
        check_config(matr1x.config)

    def info_box(self) -> None:
        """Display an 'about this app' widget."""
        box = AboutBox(
            "Sweep Generator",
            get_matrix_icon("matr1x-sweep-generator.png"),
            matr1x,
            matr1x.datetimefmt,
        )
        box.exec()

    def is_valid_extension(self, file_path: Path) -> bool:
        """Return True if extension is valid."""
        pattern = re.compile(r"\.\d+t$")
        # remove this method with next major update, i.e. Matrix v9
        # also simplifies FileDropMixin
        if pattern.search(str(file_path)) is not None:
            return True
        elif file_path.suffix == self.extension:
            return True
        else:
            return False

    def reset_layout(self) -> None:
        """Reset layout to clean state."""
        if self.populated:
            self.sweep_params = []
            self.columns.name.clear()
            self.columns.unit.clear()
            self.columns.sign.clear()
            self.clear_layout(self.grid)
            self.sweep_table.setRowCount(0)
            self.sweep_preview.setRowCount(0)

    def filename_changed(self) -> bool:
        """
        Import new system because a filename changed.

        Returns
        -------
        bool
            True on success and False on error during import.
        """
        if any(sublist for sublist in self.sweep_params):
            create_tray_notification(
                "Sweep reset", "All previous sweep parameters have been cleared.", self
            )
        filenames = [
            self.ui.system_list.item(j).text() for j in range(self.ui.system_list.count())
        ]
        if 0 == len(filenames):
            self.reset_layout()
            self.ui.actions.new_file.setEnabled(False)
            self.ui.actions.save.setEnabled(False)
            self.ui.actions.save_as.setEnabled(False)
            self.ui.actions.append.setEnabled(False)
            self.ui.actions.sweep.setEnabled(False)
            self.ui.actions.preview.setEnabled(False)
            self.ui.actions.remove_system.setEnabled(False)
            return False
        self.ui.actions.new_file.setEnabled(True)
        self.ui.actions.save.setEnabled(True)
        self.ui.actions.save_as.setEnabled(True)
        self.ui.actions.append.setEnabled(True)
        self.ui.actions.sweep.setEnabled(True)
        self.ui.actions.preview.setEnabled(True)
        self.ui.actions.remove_system.setEnabled(True)
        modulestr = ""
        # update entries in GUI list
        for j, systemfile in enumerate(filenames):
            self.ui.system_list.item(j).setText(systemfile)
        self.systemFilename = ",".join(filenames)
        try:
            self.system = MergedSystem.from_files(filenames)
        except Exception as e:
            if isinstance(e, ModuleNotFoundError):
                error_text = '<p style="color:red">Please check the path to the system files and '
                error_text += "whether all required dependencies are present.</p>"
            else:
                error_text = "The following error was raised during system "
                error_text += "import, please check the system for errors.\n\n"
            tbinfo = traceback.format_exception(type(e), e, e.__traceback__)
            tbstr = "".join(tbinfo)
            error_text += "" + tbstr
            QMessageBox.warning(self, "Import error.", error_text.replace("\n", "<br>"))
            return False
        for file in filenames:
            modulestr += Path(file).stem + ","
        # update gui using the system specifications
        self.process_system_import()
        return True

    def process_system_import(self) -> None:
        """Process specified system imports and populate layout."""
        if self.system is None:
            QMessageBox.warning(
                self,
                "Import error!",
                "No system files given.",
            )
            return
        if len(self.system.columns) != len(self.system.units):
            # simple sanity check
            QMessageBox.warning(
                self,
                "Import error!",
                "Lists with columns, units and settables of unequal length, check system file.",
            )
            return
        self.reset_layout()
        # store old columns
        old_cols = self.columns.name
        # Initalize sweep lists
        self.columns.sign = []
        # generate list of settable parameters
        settables, self.columns.name, self.columns.unit = self.system.settable_columns()
        for i, (settable, col) in enumerate(zip(settables, self.system.columns)):
            # add a column for each settable parameter in the system
            if settable is True:
                if isinstance(col, (tuple, list)):
                    # if parameter has multiple values, add multiple columns
                    for c in col:
                        self.columns.sign.append(generate_col_index(i))
                else:
                    self.columns.sign.append(generate_col_index(i))

        self.columns.color = self._generate_alternating_colors()

        # columns are initialized, get already available columns from
        # the old columns, save the sweep params and their new location
        save_sweep_params = {}
        for index, old_col in enumerate(old_cols):
            if old_col in self.columns.name:
                newloc = self.columns.name.index(old_col)
                save_sweep_params[newloc] = self.sweep_params[index]
        # generate empty list of list for the sweep parameters
        self.sweep_params = []
        for pos in range(len(self.columns.name)):
            if pos in save_sweep_params.keys():
                # if parameter was already defined before, keep sweep params
                self.sweep_params.append(save_sweep_params[pos])
            else:
                # otherwise, set empty list
                self.sweep_params.append([])
        self.populate_layout()
        self.populated = True

    def add2grid(self, widgets: LabelWidgets | ColumnWidgets, row: int = 0, column: int = 0):
        """
        Add widgets to grid.

        Note
        ----
        The grid requires 5 rows for every parameter set:
        column, nameunit, parameters, modifiers and combobox.

        Parameters
        ----------
        widgets: LabelWidgets | ColumnWidgets
            The dataclass containing widgets.
        row: int, optional
            The row of the parameters.
        column: int, optional
            The column of the parameters, which is the same as the grid.
        """
        row = row * 5
        self.grid.addWidget(widgets.column, row, column)
        self.grid.addWidget(widgets.nameunit, row + 1, column)
        parameters = QVBoxLayout()
        parameters.setSpacing(3)
        parameters.addWidget(widgets.start)
        parameters.addWidget(widgets.end)
        parameters.addWidget(widgets.points)
        quart = QHBoxLayout()
        quart.setSpacing(8)
        quart.addLayout(parameters)
        quart.addWidget(widgets.append)
        widgets.append.setDisabled(True)
        self.grid.addLayout(quart, row + 2, column)
        modifiers = QHBoxLayout()
        modifiers.setSpacing(5)
        if not isinstance(widgets.updown, QLabel):
            modifiers.addWidget(widgets.repeat, stretch=1)
        else:
            modifiers.addWidget(widgets.repeat)
        modifiers.addWidget(widgets.doublearrow)
        modifiers.addWidget(widgets.updown)
        self.grid.addLayout(modifiers, row + 3, column)
        combobox = QVBoxLayout()
        combobox.addWidget(widgets.loopover)
        combobox.addWidget(QLabel(" "))
        self.grid.addLayout(combobox, row + 4, column)

    def _generate_alternating_colors(self) -> list[bool]:
        """
        Generate alternating colors for column entries.

        Returns
        -------
        list[bool]
            True and False alternate when entry differs from previous.
        """
        colors = []
        if len(self.columns.sign) > 0:
            current_color = True
            last_sign = self.columns.sign[0]
            colors.append(current_color)
            for i in range(1, len(self.columns.sign)):
                if self.columns.sign[i] != last_sign:
                    current_color = not current_color
                    last_sign = self.columns.sign[i]
                colors.append(current_color)
        return colors

    def populate_layout(self) -> None:
        """Populate sweep control and data fields."""
        self.grid_widgets = []
        column_generator = ColumnGenerator(self.columns)
        self.add2grid(column_generator.label_widgets)

        for column in range(len(self.columns.name)):
            column_generator = ColumnGenerator(self.columns, column)
            column_generator.widget_modified.connect(self.window_title_dirty.emit)
            column_generator.select_grid_column.connect(self.populate_sweep_grid)
            column_generator.append.connect(self.append_sweep_col)
            sweep_widgets = column_generator.column_widgets
            sweep_widgets.start.textChanged.connect(
                lambda text, col=column: self.update_append(text, col)
            )
            sweep_widgets.end.textChanged.connect(
                lambda text, col=column: self.update_append(text, col)
            )
            sweep_widgets.points.textChanged.connect(
                lambda text, col=column: self.update_append(text, col)
            )
            self.grid_widgets.append(sweep_widgets)

        max_column_width = self.grid_widgets[0].loopover.minimumSizeHint().width()
        # calculate how many columns fit the screen horizontally
        max_width = max_column_width + self.grid.horizontalSpacing()
        left, top, right, bottom = self.grid.getContentsMargins()  # type: ignore
        screen_width = self.screen().availableGeometry().width() - left - right
        column_fit = screen_width // max_width - 1

        for column in range(len(self.columns.name)):
            row = (column + 1) // (column_fit + 1)
            grid_column = (column + 1) % (column_fit + 1)
            self.add2grid(self.grid_widgets[column], row, grid_column)

    def update_append(self, text: str, column: int) -> None:
        """
        Update the append button if all 3 required fields are filled.

        Parameters
        ----------
        column : int
            The column of the append button.
        """
        if (
            self.grid_widgets[column].start.text().strip()
            and self.grid_widgets[column].end.text().strip()
            and self.grid_widgets[column].points.text().strip()
        ):
            self.grid_widgets[column].append.setEnabled(True)
        else:
            self.grid_widgets[column].append.setEnabled(False)

    def preview_sweep(self) -> None:
        """Display a popup with the sweep given in the column (as plot and list)."""
        sweep = self.generate_sweep()
        if sweep is None:
            return
        popup = SweepPreviewPopup(
            self,
            self.preview_column,
            sweep,
            self.columns,
        )
        popup.show()

    def print_sweep_to_preview(self) -> None:
        """Print the complete set of sweeps to self.sweep_preview."""
        sweep = self.generate_sweep()
        if sweep is None:
            return
        # get length of longest sweep and
        # make sure all sweeps in a group are of equal length
        # this is how the looping over different column is implemented here
        max_length = []
        for i in range(len(sweep)):
            # make sure that values that belong to the same parameter have the
            # same length
            if self.columns.sign[i] == self.columns.sign[i - 1] and len(sweep[i]) != len(
                sweep[i - 1]
            ):
                error_text = "Not all parameters for that instrument have the same length."
                error_text += "Please correct your sweep parameters in instrument "
                error_text += f"{self.columns.sign[i]} "
                error_text += f" -> {self.columns.name[i]}. If a parameter accepts multiple "
                error_text += (
                    "values, the different values for that parameter must have the same length."
                )
                QMessageBox.warning(self, "Parameter error!", error_text)
                return
            max_length.append(len(sweep[i]))

        max_length = max(max_length)

        # calculate necessary multiplicators to stretch the sweeps
        # if sweep lenghts are not multiples of each other something is wrong
        mult = []
        for i in range(len(sweep)):
            if [] == sweep[i]:
                mult.append(0)
            elif max_length % len(sweep[i]):
                error_text = (
                    "Sweep_parameters seem unsuitable for measurements, lengths not multiples. "
                )
                error_text += "Check that loops are set correctly."
                QMessageBox.warning(self, "Sweep parameters incompatible!", error_text)
                return
            else:
                mult.append(max_length / len(sweep[i]))

        # initialize outputList, here the strings for the lines will be input
        # this is equivalent to what goes into the file
        self.outputList = []
        self.sweep_preview.setRowCount(max_length)
        for i in range(max_length):
            string: list[str] = []
            for j, swp in enumerate(sweep):
                if 0 != mult[j] and not i % mult[j]:
                    # here the values are stretched to the correct "length" if
                    # the loop_over parameter is considered
                    if self.columns.sign[j] == self.columns.sign[j - 1] and len(sweep) > 1:
                        # Parameter has multiple values
                        string.append(str(swp[floor(i / mult[j])]))
                    else:
                        # Parameter has single value
                        string.append(
                            "-" + self.columns.sign[j] + " " + str(swp[floor(i / mult[j])])
                        )
                string.append("   ")
            line = "".join(string)
            value = QTableWidgetItem(line[:1000])
            self.sweep_preview.setItem(i, 0, value)
            # replace excess spaces from file and print, could be removed
            self.outputList.append(line.replace("   ", " ") + "\n")

    def update_window_title(self, dirty: bool = False) -> None:
        """
        Indicate with an asterisk if the file was edited.

        Parameters
        ----------
        dirty : bool
            The file was edited (True) or, e.g., recently saved (False).
        """
        self.dirty = dirty
        text = "Sweep Generator"
        if dirty:
            text += ": *"
        elif self.last_filename:
            text += ": "
        if self.last_filename:
            text += self.last_filename.name
        elif dirty:
            text += "<unsaved>"
        self.setWindowTitle(text)

    def _write_file_to_disk(self, filename: Path, append: bool) -> bool:
        """
        Write the generated sweep to disk.

        Parameters
        ----------
        append : bool, optional
            Append the file (True) or create/ overwrite the file (False).

        Returns
        -------
        bool
            Saved (True) or errored (False)
        """
        self.print_sweep_to_preview()
        if filename.suffix != self.extension:
            filename = filename.with_suffix(self.extension)
        try:
            if append:
                outputFile = filename.open("a")
            else:
                outputFile = filename.open("w")
        except OSError:
            QMessageBox.warning(self, "Error!", "File can not be opened.")
            return False
        # get telemetry and append to file
        timestamp = time.strftime(f"{datetimefmt} \n", time.localtime())
        if not append:
            outputFile.write("# v8 input file for matrix program generated by sweep-generator")
            outputFile.write("\n# system filename : ")
            outputFile.write(self.systemFilename)
            outputFile.write("\n# settable columns : ")
            outputFile.write(",".join(self.columns.name))
            outputFile.write("\n# settable units : ")
            outputFile.write(",".join(self.columns.unit))
            outputFile.write("\n# settable column label : ")
            outputFile.write(",".join(self.columns.sign))
            outputFile.write("\n# params : ")
            outputFile.write(str(self.sweep_params))
            outputFile.write("\n# loop_over : ")
            outputFile.write(str(self.loop_over))
            outputFile.write("\n# up_down : ")
            outputFile.write(str(self.up_down))
            outputFile.write("\n# repeat : ")
            outputFile.write(str(self.repeat))
            outputFile.write("\n# time stamp : ")
            outputFile.write(timestamp)
        for line in self.outputList:
            outputFile.write(line)
        outputFile.close()
        self.last_filename = filename
        self.update_window_title(dirty=False)
        if self.inputcb is not None:
            self.inputcb(str(filename))
        return True

    def save_file(self, append: bool = False, dialog: bool = False) -> bool:
        """
        Save the generated sweep to a file.

        Parameters
        ----------
        append : bool, optional
            Append the file (True) or create/ overwrite the file (False).
        dialog : bool, optional
            Do (True) or do not (False) show a dialog to chose a filename.

        Returns
        -------
        bool
            Saved (True) or cancelled (False)
        """
        if dialog or not self.last_filename:
            prefilled_file = self.last_filename if self.last_filename != "" else usersfolder
            if append:
                filename = QFileDialog.getOpenFileName(
                    self,
                    "Select file to append to",
                    str(prefilled_file),
                    f"Sweep 8 files (*{self.extension})",
                )
            else:
                filename = QFileDialog.getSaveFileName(
                    self,
                    "Select output file",
                    str(prefilled_file),
                    f"Sweep 8 files (*{self.extension})",
                )
            if filename[0] != "":
                self.last_filename = Path(filename[0])
            else:
                return False
        return self._write_file_to_disk(self.last_filename, append)

    def append_sweep_col(self, column: int) -> None:
        """
        Add defined sweep parameters to self.sweep_params and populate sweep table.

        Parameters
        ----------
        column : int
            The column index (0-based).
        """
        param_set = []
        param_set.append(self.grid_widgets[column].start.text())
        param_set.append(self.grid_widgets[column].end.text())
        param_set.append(self.grid_widgets[column].points.text())
        self.sweep_params[column].append(param_set)
        self.grid_widgets[column].start.setText("")
        self.grid_widgets[column].end.setText("")
        self.grid_widgets[column].points.setText("")
        # update the sweep grid for the active column (should now display
        # the new parameter set)
        self.populate_sweep_grid(column)

    def populate_sweep_grid(self, actual_column: int) -> None:
        """
        Display the actual sweep parameters.

        Parameters
        ----------
        actual_column : int
            The column that is selected (0-based index).
        """
        self.preview_column = actual_column
        for column in range(len(self.columns.name)):
            col_sign_label = self.grid_widgets[column].column
            col_nameunit = self.grid_widgets[column].nameunit
            if column == actual_column:
                col_sign_label.setFrameStyle(QLabel.Shape.Panel | QLabel.Shadow.Sunken)
                col_sign_label.setLineWidth(2)
                col_nameunit.setFrameStyle(QLabel.Shape.Panel | QLabel.Shadow.Sunken)
                col_nameunit.setLineWidth(2)
            else:
                col_sign_label.setFrameStyle(QLabel.Shape.NoFrame)
                col_nameunit.setFrameStyle(QLabel.Shape.NoFrame)
        self.sweep_table.setRowCount(len(self.sweep_params[actual_column]))

        for row, param_set in enumerate(self.sweep_params[actual_column]):
            for i in range(3):
                line_edit = QLineEdit(self)
                line_edit.setText(str(param_set[i]))
                if i == 2:
                    line_edit.setValidator(validator[numpy.uint])
                else:
                    line_edit.setValidator(validator[float])
                line_edit.editingFinished.connect(
                    lambda line_edit=line_edit,
                    actual_column=actual_column,
                    row=row,
                    i=i: self.sweep_params[actual_column][row].__setitem__(i, line_edit.text())
                )
                line_edit.textChanged.connect(lambda: self.window_title_dirty.emit())
                line_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
                self.sweep_table.setCellWidget(row, i, line_edit)
            delete_button = QPushButton("-")
            delete_button.clicked.connect(
                lambda _, actual_column=actual_column, row=row: self.remove_sweep_param(
                    actual_column, row
                )
            )
            delete_button.clicked.connect(lambda: self.window_title_dirty.emit())
            wrapper = QWidget()
            layout = QHBoxLayout(wrapper)
            layout.addWidget(delete_button)
            layout.setContentsMargins(5, 5, 5, 5)
            layout.setAlignment(delete_button, Qt.AlignmentFlag.AlignCenter)
            self.sweep_table.setCellWidget(row, 3, wrapper)

    def remove_sweep_param(self, col: int, row: int) -> None:
        """
        Remove a set of linspace parameters from sweep_params at the correct position.

        Parameters
        ----------
        col : int
            The currently selected matrix column (0-based index).
        row : int
            The row of the table to be deleted.
        """
        del self.sweep_params[col][row]
        self.populate_sweep_grid(col)

    def clear_layout(self, layout) -> None:
        """Clear all child widgets from layout."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.spacerItem():
                pass
            else:
                self.clear_layout(item)

    def add_system(self, filenames: list | None = None) -> None:
        """
        Add a system file to the system list and initiate import.

        Opens a QFileDialog with filter system*.py.
        """
        directory = system_directories[-1]
        if not self.shortcut_dir and len(system_names) > 1:
            self.shortcut_dir = create_temp_dir_with_symlinks(system_names, system_directories)
        if self.shortcut_dir:
            directory = Path(self.shortcut_dir.name) / system_names[-1]
        if self.last_loaded_system:
            directory = Path(self.last_loaded_system).parent
        # get filenames from dialog
        if not filenames:
            filenames = QFileDialog.getOpenFileNames(
                self, "Select system file", str(directory), "system files (system*.py)"
            )[0]
        if filenames == []:
            return
        for filename in filenames:
            self.last_loaded_system = filename
            filename = str(Path(filename).resolve())
            module_name = get_importable_module_name(filename)
            if module_name:
                self.ui.system_list.addItem(module_name)
            else:
                self.ui.system_list.addItem(filename)
        self.window_title_dirty.emit()
        if not self.filename_changed():
            for filename in filenames:
                self.ui.system_list.takeItem(self.ui.system_list.count() - 1)
        if self.ui.system_list.count() != 0:
            self.ui.actions.remove_system.setEnabled(True)

    def delete_selected_system(self) -> None:
        """Remove selected or last system from the system list."""
        selected = self.ui.system_list.selectedItems()
        if len(selected) > 0:
            self.ui.system_list.takeItem(self.ui.system_list.row(selected[0]))
        elif 0 < self.ui.system_list.count():
            self.ui.system_list.takeItem(self.ui.system_list.count() - 1)
        else:
            return
        if self.ui.system_list.count() == 0:
            self.ui.actions.remove_system.setEnabled(False)
        self.filename_changed()
        self.window_title_dirty.emit()

    def generate_sweep(self) -> list[list[float]] | None:
        """
        GUI functionality to populate all lists necessary for sweep generation.

        After that generates the sweep from the parameters (still needs
        to be stretched)
        """
        self.loop_over = []
        self.up_down = []
        self.repeat = []

        for col in range(len(self.columns.name)):
            self.loop_over.append(self.grid_widgets[col].loopover.currentIndex() - 1)
            updownstate = self.grid_widgets[col].updown.checkState()
            if updownstate == Qt.CheckState.Checked:
                self.up_down.append(2)
            else:
                self.up_down.append(0)
            self.repeat.append(self.grid_widgets[col].repeat.value())

        # all lists are up to date, now generate sweep lists
        sweep = calculate_sweep(
            self.sweep_params, self.loop_over.copy(), self.up_down, self.repeat
        )
        if isinstance(sweep, Error):
            QMessageBox.warning(
                self,
                "Sweep generation failed:",
                f"{sweep.error}",
            )
            return
        return sweep.value

    def gui_from_sweep(self) -> None:
        """Open a QFileDialog to open an existing sweep file."""
        # get filename from dialog
        prefilled_file = self.last_filename if self.last_filename is not None else usersfolder
        filename = QFileDialog.getOpenFileName(
            self,
            "Select input file",
            str(prefilled_file),
            f"Sweep 8 files (*{self.extension});;t files (*.*t)",  # Delete old extension in MA9
        )[0]
        if filename:
            self.open_file(filename)

    def open_file(self, filename: Path | str) -> None:
        """
        Load a sweep file.

        Load system from file, define read out parameters to parse and
        display the sweep in the corresponding preview.

        Parameters
        ----------
        filename : str
            Sweep file to open.
        """
        params = {
            "# params : ": [],
            "# loop_over : ": [],
            "# functions : ": [],
            "# up_down : ": [],
            "# repeat : ": [],
        }
        self.ui.system_list.clear()
        with Path(filename).open() as infile:
            for line in infile:
                regex = r"^# [Ss]ystem filename : (.+)"
                if match := re.match(regex, line.strip()):
                    self.ui.system_list.addItems(match.group(1).split(","))
                    if not self.filename_changed():
                        return
                for key in params.keys():
                    if key in line:
                        # read the parameters from the corresponding line
                        line = line.strip().replace(key, "")
                        params[key] = literal_eval(line)
        # 'Functions' is depracated. Old files read and issue a warning if the functionality
        # is used. Otherwise they just load. Delete the this backward compatibility for Matrix v9.
        # Andy 20250306
        if len(params.values()) == 5:  # old filename
            (
                self.sweep_params,
                self.loop_over,
                functions,
                self.up_down,
                self.repeat,
            ) = params.values()
        else:
            (self.sweep_params, self.loop_over, self.up_down, self.repeat) = params.values()
            functions = None
        if functions and any(function != "None" for function in functions):
            warning_text = (
                "This file uses the removed 'function' functionality."
                "Please use matrix-script. File did not load!"
            )
            QMessageBox.warning(
                self,
                "Open file error.",
                warning_text,
            )
            return
        # initialize layout with values specified in file
        for col in range(len(self.columns.name)):
            self.grid_widgets[col].loopover.setCurrentIndex(self.loop_over[col] + 1)
            self.grid_widgets[col].updown.setCheckState(Qt.CheckState(self.up_down[col]))
            self.grid_widgets[col].repeat.setValue(self.repeat[col])
        self.last_filename = Path(filename)
        self.update_window_title()
        self.print_sweep_to_preview()

    def new_file(self) -> None:
        """
        Prepare a completely new sweep.

        Delete all existing sweep parameters, update the sweep grid
        accordingly and empty the sweep preview. Also reset all input
        fields to their original states.
        """
        if self.dirty:
            ret = save_messagebox(self)
            if ret == QMessageBox.StandardButton.Cancel:
                return
            if ret == QMessageBox.StandardButton.Save:
                saved = self.save_file()
                if not saved:
                    return
        self.sweep_params = []
        for col in range(len(self.columns.name)):
            self.sweep_params.append([])
            self.grid_widgets[col].start.setText("")
            self.grid_widgets[col].end.setText("")
            self.grid_widgets[col].points.setText("")
            self.grid_widgets[col].repeat.setValue(1)
            self.grid_widgets[col].updown.setChecked(False)
            self.grid_widgets[col].loopover.setCurrentIndex(0)
            self.populate_sweep_grid(col)
        self.print_sweep_to_preview()
        self.grid_widgets[0].start.setFocus()
        self.last_filename = None
        self.update_window_title(dirty=False)


def main():
    """Set the basic GUI parameters and run."""
    install_error_handler()
    app = MApplication(sys.argv)
    app.setDesktopFileName("sweep-generator")
    with QtGracefulKiller():
        if len(sys.argv) < 2:
            mw = MainWindow()
        else:
            mw = MainWindow(filename=Path(sys.argv[1]))
        mw.show()
        app.connect_file_handler(mw.open_file)  # MacOS specific FileOpenEvent
        protected_restore(mw.restore_window_state)
        ret = app.exec()
    sys.exit(ret)
