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
Generate sweeps for matrix via a straightforward GUI.

It heavily relies on numpy.linspace for the creation of the sweep
segments.
"""

import logging
import re
import sys
import time
from ast import literal_eval
from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from math import floor
from pathlib import Path
from typing import Any

import numpy
import pyqtgraph as pg
from pydantic import BaseModel, Field
from PySide6.QtCore import QObject, QPointF, Qt, Signal
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
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import matr1x
from matr1x import datetimefmt, usersfolder
from matr1x.error_handling import (
    Error,
    InternalInvariantError,
    Result,
    Success,
    install_error_handler,
)
from matr1x.gui_util import (
    AboutBox,
    AutoSlot,
    CustomViewBox,
    FileDropMixin,
    LoggingWindow,
    LogWindowMixin,
    MApplication,
    check_config,
    clear_layout,
    create_matr1x_quit_action,
    create_matrix_settings_action,
    get_matrix_icon,
    open_matrix_toml,
    save_messagebox,
    validator,
)
from matr1x.models import SystemInfo
from matr1x.post_install import (
    check_desktop_integration,
    post_installation,
    remove_desktop_integration,
)
from matr1x.scripts.shared_classes import (
    MMainWindow,
    MToolBar,
    Notifier,
    NotifierMessage,
    SaferQSettings,
    SystemListWidget,
)
from matr1x.util import generate_col_index

__all__ = ["MainWindow"]

if sys.platform == "win32":
    try:
        from ctypes import windll

        myappid = "python.matr1x.sweep-generator.version"
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DataFile:
    """Container for data file information."""

    header: str
    lines: list[str]


class ColumnData(BaseModel):
    """Container for column data."""

    name: list[str] = Field(default_factory=list)
    unit: list[str] = Field(default_factory=list)
    sign: list[str] = Field(default_factory=list)

    parameter: list[list[list[float | int | str]]] = Field(default_factory=list)
    loop_over: list[int] = Field(default_factory=list)
    up_down: list[int] = Field(default_factory=list)
    repeat: list[int] = Field(default_factory=list)

    filenames: list[str] = Field(default_factory=list)

    def __setattr__(self, name: str, value: Any):
        """Invalidate the caches when updates occur."""
        super().__setattr__(name, value)
        if name == "sign":
            self.__dict__.pop("color", None)

    @cached_property
    def color(self) -> list[bool]:
        """Calculate the color based on the sign of the parameter."""
        if not self.sign:
            return []
        colors = [True]
        for prev, curr in zip(self.sign, self.sign[1:]):
            colors.append(colors[-1] if curr == prev else not colors[-1])
        return colors

    def generate_file(self, version: int = 8) -> Result[DataFile, str]:
        """Generate a sweep file for the given version."""
        sweep = self.calculate_sweep()
        if isinstance(sweep, Error):
            return Error(f"Sweep generation failed: {sweep.error}")
        sweep = sweep.value
        if sweep == []:
            return Success(DataFile(header="", lines=[]))
        max_length = self._determine_max_length(sweep)
        if isinstance(max_length, Error):
            return Error(f"Max length determination failed: {max_length.error}")
        max_length = max_length.value
        multiplier = self._generate_stretch(sweep, max_length)
        if isinstance(multiplier, Error):
            return Error(f"Stretch generation failed: {multiplier.error}")
        multiplier = multiplier.value
        header = self._generate_header()
        lines = self._generate_body(sweep, max_length, multiplier)
        return Success(DataFile(header=header, lines=lines))

    def _generate_header(self) -> str:
        """Generate the header of the sweep file."""
        timestamp = time.strftime(f"{datetimefmt} \n", time.localtime())
        header = (
            f"# v8 input file for matrix program generated by sweep-generator\n"
            f"# system filename : {','.join(self.filenames)}\n"
            f"# settable columns : {','.join(self.name)}\n"
            f"# settable units : {','.join(self.unit)}\n"
            f"# settable column label : {','.join(self.sign)}\n"
            f"# params : {self.parameter}\n"
            f"# loop_over : {self.loop_over}\n"
            f"# up_down : {self.up_down}\n"
            f"# repeat : {self.repeat}\n"
            f"# time stamp : {timestamp}"
        )
        return header

    def _generate_body(
        self, sweep: list[list[float]], max_length: int, multiplier: list[int]
    ) -> list[str]:
        """Generate the body of the sweep file."""
        lines = []
        for i in range(max_length):
            parts = []
            for j, (swp, m) in enumerate(zip(sweep, multiplier)):
                if m == 0 or i % m != 0:
                    parts.append("   ")
                    continue
                idx = floor(i / m)
                value = swp[idx]
                same_parameter = j > 0 and self.sign[j] == self.sign[j - 1] and len(sweep) > 1
                if same_parameter:
                    parts.append(str(value))
                else:
                    parts.append(f"-{self.sign[j]} {value}")
                parts.append("   ")
            lines.append("".join(parts))
        return lines

    def _determine_max_length(self, sweep: list[list[float]]) -> Result[int, str]:
        """Validate that all sweeps in a group are of equal length."""
        max_length = []
        for i in range(len(sweep)):
            if self.sign[i] == self.sign[i - 1] and len(sweep[i]) != len(sweep[i - 1]):
                error_text = "Not all parameters for that instrument have the same length."
                error_text += "Please correct your sweep parameters in instrument "
                error_text += f"{self.sign[i]} "
                error_text += f" -> {self.name[i]}. If a parameter accepts multiple "
                error_text += (
                    "values, the different values for that parameter must have the same length."
                )
                return Error(f"Parameter length different! {error_text}")
            max_length.append(len(sweep[i]))
        return Success(max(max_length))

    def _generate_stretch(self, sweep: list[list[float]], max_length: int) -> Result[list, str]:
        """Calculate necessary multiplicators to stretch the sweeps."""
        # if sweep lenghts are not multiples of each other something is wrong
        mult = []
        for i in range(len(sweep)):
            if sweep[i] == []:
                mult.append(0)
            elif max_length % len(sweep[i]):
                error_text = (
                    "Sweep_parameters seem unsuitable for measurements, lengths not multiples. "
                )
                error_text += "Check that loops are set correctly."
                return Error(f"Sweep parameters incompatible! {error_text}")
            else:
                mult.append(max_length / len(sweep[i]))
        return Success(mult)

    def clear(self) -> None:
        """Delete all fields and invalidate the color cache."""
        for field_name in type(self).model_fields:
            value = getattr(self, field_name)
            value.clear()
        self.__dict__.pop("color", None)

    def calculate_sweep(self) -> Result[list[list[float]], str]:
        """
        Generate a list of sweeps defined by given parameters.

        Returns
        -------
        list
            List of sweeps that contains all parameters that are to be
            set.
        """
        loop_over = self.loop_over.copy()
        lenA = len(self.parameter)
        if lenA == 0:
            return Success([])
        if len(loop_over) != lenA or len(self.up_down) != lenA or len(self.repeat) != lenA:
            return Error("The length of the arrays is not equal.")
        sweeps: list[list[float]] = []
        for indexS, parmSets in zip(range(lenA), self.parameter):
            i = 0
            sweeps.append([])
            while i < self.repeat[indexS]:
                tempSweep = []
                for parm in parmSets:
                    # generate the sweepRange using np.linspace, has to be list
                    # so += works

                    sweepRange = numpy.linspace(float(parm[0]), float(parm[1]), int(parm[2]))
                    if any(numpy.isnan(sweepRange)) or any(numpy.isinf(sweepRange)):
                        return Error("Inf or Nan in sweep, check parameters")
                    tempSweep += list(sweepRange)
                if self.up_down[indexS]:
                    # if up down is true, add the reversed sweep to the sweep
                    tempSweep += list(reversed(tempSweep))
                sweeps[indexS] += tempSweep
                i += 1
        # check if there are loops of loops and detect hirarchy so we
        # can properly generate the sweep
        hirarchy = []
        for i in range(lenA):
            result = self.check_depth(i)
            if isinstance(result, Error):
                # Recursive loop, you should really not do that!
                # (i.e. don't loop col(a) over col(b) over col(a)!)
                return Error("Recursive loop, please check loop over")
            hirarchy.append(result.value)
        hCnt = max(hirarchy)
        while hCnt >= 0:
            for indexS in range(lenA):
                if indexS == loop_over[indexS]:
                    # looping a column over itself is not how it's done!
                    loop_over[indexS] = -1
                elif loop_over[indexS] != -1 and hCnt == hirarchy[indexS]:
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

    def check_depth(self, index: int, depth: int = 0) -> Result[int, int]:
        """
        Determine the hierarchical depth of an item in an array.

        This function checks how deeply nested an item is within a given
        array structure. It recursively follows references until it
        reaches the deepest level or detects a circular reference.

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
            return Error(-1)
        occurrences = [i for i, x in enumerate(self.loop_over) if x == index]
        if not occurrences:
            return Success(depth)
        depths = []
        for pos in occurrences:
            result = self.check_depth(pos, depth + 1)
            if isinstance(result, Error):
                return Error(-1)
            depths.append(result.value)
        return Success(max(depths))


class FocusInMixin:
    """Add focusInEvent to QWidgets without it."""

    focusIn = Signal()

    def focusInEvent(self, e: QFocusEvent) -> None:
        super().focusInEvent(e)  # ty: ignore[unresolved-attribute]
        self.focusIn.emit()


class CheckBoxFocus(FocusInMixin, QCheckBox):
    """Reimplement CheckBox with focusInEvent."""


class LineEditFocus(FocusInMixin, QLineEdit):
    """Reimplement LineEdit with focusInEvent."""


class SpinBoxFocus(FocusInMixin, QSpinBox):
    """Reimplement QSpinBox with focusInEvent."""


class QLabelWithColor(QLabel):
    """Allow QLabel with highlight color and mouseclick reaction."""

    clicked = Signal()

    def __init__(self):
        """Init with colored background for bright and dark mode."""
        super().__init__()
        self.color_bright = "#DCF5D4"
        self.color_dark = "#325725"
        self._update_colors()
        MApplication.instance().isDarkSignal.connect(self._update_colors)

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
        if MApplication.instance().isDark:
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
    """
    Generate the sweep column widgets.

    Parameters
    ----------
    columns: ColumnData
        The properties of the columns (name, unit, sign, color).
    column: int
        Index of the current column in the MainWindow.
    """

    widget_modified: Signal = Signal()
    select_grid_column: Signal = Signal(int)
    append: Signal = Signal(int)
    up_down_changed: Signal = Signal()
    repeat_changed: Signal = Signal()
    loop_over_changed: Signal = Signal()

    def __init__(self, columns: ColumnData, column: int):
        super().__init__()
        self.columns: ColumnData = columns
        self.column: int = column
        self.column_widgets: ColumnWidgets = self._create_widgets()

    @staticmethod
    def label_widgets() -> LabelWidgets:
        """
        Create the header label widgets for the sweep grid.

        Returns
        -------
        LabelWidgets
            A dataclass containing all header label widgets.
        """
        placeholder = QWidget()
        placeholder.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        placeholder.setFixedSize(0, 0)

        return LabelWidgets(
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

    def _create_widgets(self) -> ColumnWidgets:
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
        size = QLineEdit().sizeHint().height()
        append_widget.setFixedSize(size, int(2.9 * size))
        append_widget.clicked.connect(lambda: self.widget_modified.emit())
        append_widget.clicked.connect(lambda: self.append.emit(self.column))

        repeat_widget = SpinBoxFocus()
        repeat_widget.setRange(1, 999)
        repeat_widget.setAlignment(Qt.AlignmentFlag.AlignRight)
        repeat_widget.valueChanged.connect(lambda: self.widget_modified.emit())
        repeat_widget.focusIn.connect(lambda: self.select_grid_column.emit(self.column))
        repeat_widget.valueChanged.connect(lambda: self.repeat_changed.emit())

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
        updown_widget.stateChanged.connect(lambda: self.up_down_changed.emit())

        loopover_widget = QComboBox()
        loopover_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        font = loopover_widget.font()
        font.setPointSize(font.pointSize() - 1)
        loopover_widget.setFont(font)
        loopover_widget.currentIndexChanged.connect(lambda: self.widget_modified.emit())
        loopover_widget.activated.connect(lambda: self.select_grid_column.emit(self.column))
        columns = ["None"] + [name.strip() for name in self.columns.name]
        loopover_widget.addItems(columns)
        loopover_widget.currentIndexChanged.connect(lambda: self.loop_over_changed.emit())

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
class WidgetGroup:
    """Non-column widgets to be used in the GUI."""

    sweep_preview: QTableWidget
    sweep_table: QTableWidget
    central_widget: QWidget
    system_list: SystemListWidget
    notifier: Notifier
    about_box: AboutBox


@dataclass
class ActionGroup:
    """Actions to be utilized in the GUI."""

    matrix_settings: QAction
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
    preview: QAction
    post_install: QAction
    remove_desktop_integration: QAction


class UIBuilder:
    """Create the GUI elements."""

    def __init__(self):
        self.widgets: WidgetGroup = self._create_widgets()
        self.actions: ActionGroup = self._create_actions()
        self.toolbar: MToolBar = self._create_toolbar()
        self.menubar: QMenuBar = self._create_menu()
        self.grid: QGridLayout = self._create_gui()

    def _create_widgets(self) -> WidgetGroup:
        """Create all widgets."""
        sweep_table = QTableWidget()
        sweep_table.setColumnCount(4)
        sweep_table.setHorizontalHeaderLabels(["Start", "Stop", "Points", "Delete"])
        header = sweep_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        sweep_table.verticalHeader().hide()

        sweep_preview = QTableWidget()
        sweep_preview.setColumnCount(1)
        sweep_preview.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        sweep_preview.setAlternatingRowColors(True)
        sweep_preview.setHorizontalHeaderLabels(["Preview of the generated sweep-parameters"])
        header = sweep_preview.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.Stretch)
        table_width = sweep_preview.viewport().width()
        sweep_preview.setColumnWidth(0, table_width)

        system_list = SystemListWidget()

        notifier = Notifier(logger)

        return WidgetGroup(
            sweep_preview=sweep_preview,
            sweep_table=sweep_table,
            central_widget=QWidget(),
            system_list=system_list,
            notifier=notifier,
            about_box=AboutBox(
                "Sweep Generator",
                get_matrix_icon("matr1x-sweep-generator.png"),
                matr1x,
                matr1x.datetimefmt,
            ),
        )

    def _create_actions(self) -> ActionGroup:
        """Create all actions."""
        new_file = QAction(get_matrix_icon("SP_FileIcon"), "New")
        new_file.setShortcut(QKeySequence.StandardKey.New)
        load = QAction(get_matrix_icon("SP_DialogOpenButton"), "Open")
        load.setShortcut(QKeySequence.StandardKey.Open)
        save = QAction(get_matrix_icon("SP_DialogSaveButton"), "Save")
        save.setShortcut(QKeySequence.StandardKey.Save)
        save.setEnabled(False)
        save_as = QAction(get_matrix_icon("SP_DialogSaveButton"), "Save As...")
        save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as.setEnabled(False)
        append = QAction(get_matrix_icon("SP_DialogSaveButton"), "Append")
        append_to = QAction(get_matrix_icon("SP_DialogSaveButton"), "Append To...")
        append.setEnabled(False)
        append_to.setEnabled(False)
        sweep = QAction(get_matrix_icon("SP_BrowserReload"), "Draft Sweep")
        sweep.setEnabled(False)
        preview = QAction(
            get_matrix_icon("matr1x-matrix-preview.png", QColor("RoyalBlue")), "Preview"
        )
        preview.setEnabled(False)
        return ActionGroup(
            matrix_settings=create_matrix_settings_action(),
            show_log=LogWindowMixin.create_show_log_action(),
            new_file=new_file,
            load=load,
            add_system=self.widgets.system_list.add_action,
            remove_system=self.widgets.system_list.remove_action,
            save=save,
            save_as=save_as,
            append=append,
            append_to=append_to,
            quit=create_matr1x_quit_action(),
            sweep=sweep,
            preview=preview,
            post_install=LogWindowMixin.create_post_install_action(),
            remove_desktop_integration=LogWindowMixin.create_remove_desktop_integration_action(),
        )

    def _create_toolbar(self) -> MToolBar:
        """Create the toolbar."""
        save_button = QToolButton()
        save_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        save_button.setIcon(get_matrix_icon("SP_DialogSaveButton"))
        save_button.setText("Save")
        save_button.setDefaultAction(self.actions.save)
        save_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        save_pulldown = QMenu(save_button)
        save_pulldown.addAction(self.actions.save_as)
        save_pulldown.addAction(self.actions.append)
        save_pulldown.addAction(self.actions.append_to)
        save_button.setMenu(save_pulldown)
        toolbar = MToolBar("Toolbar")
        toolbar.addAction(self.actions.new_file)
        toolbar.addAction(self.actions.load)
        toolbar.addWidget(save_button)
        toolbar.addAction(self.actions.sweep)
        toolbar.addWidget(toolbar.empty)
        toolbar.addAction(self.actions.preview)
        toolbar.addWidget(toolbar.empty)
        toolbar.addSeparator()
        self.widgets.system_list.add_to_toolbar(toolbar)
        return toolbar

    def _create_menu(self) -> QMenuBar:
        """Create the main menu."""
        menu_bar = QMenuBar()
        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.actions.new_file)
        file_menu.addAction(self.actions.load)
        file_menu.addSeparator()
        file_menu.addAction(self.actions.save)
        file_menu.addAction(self.actions.save_as)
        file_menu.addAction(self.actions.append)
        file_menu.addSeparator()
        self.widgets.system_list.add_actions_to_menu(file_menu)
        file_menu.addSeparator()
        file_menu.addAction(self.actions.quit)  # This gets auto-moved on a Mac
        control_menu = menu_bar.addMenu("&Control")
        control_menu.addAction(self.actions.sweep)
        view_menu = menu_bar.addMenu("&View")
        view_menu.addAction(self.toolbar.action)
        view_menu.addSeparator()
        view_menu.addAction(self.actions.matrix_settings)
        help_menu = menu_bar.addMenu("&Help")
        LogWindowMixin.add_common_help_actions(help_menu, self.actions)
        help_menu.addAction(self.widgets.about_box.action)

        return menu_bar

    def _create_gui(self) -> QGridLayout:
        """Create and set up the main GUI."""
        grid = QGridLayout()
        grid.setVerticalSpacing(5)
        grid.setHorizontalSpacing(10)
        lower_view = QHBoxLayout()
        lower_view.addWidget(self.widgets.sweep_preview)
        lower_view.addWidget(self.widgets.sweep_table)
        central_layout = QVBoxLayout()
        central_layout.addWidget(self.widgets.notifier)
        central_layout.addLayout(grid)
        central_layout.addLayout(lower_view)
        self.widgets.central_widget.setLayout(central_layout)
        return grid


class SweepPreviewPopup(QDialog):
    """
    Show the sweep as list and plot in a pop-up.

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
        col: ColumnData,
    ):
        super().__init__(parent)
        self.columns: ColumnData = col
        sweep = self.columns.calculate_sweep()
        if isinstance(sweep, Error):
            InternalInvariantError("SweepPreviewPopup should not be called with an Error.")
        else:
            self.sweep = sweep.value
        self.data_table: QTableWidget = QTableWidget()
        self.data_table.setColumnCount(1)
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setHorizontalHeaderLabels(["Value"])
        header = self.data_table.horizontalHeader()
        header.setSectionResizeMode(0, header.ResizeMode.Stretch)
        self.posLabel: QLabel = QLabel(f"x: {0:e}\ny: {0:e}")
        comboBox = QComboBox()
        columns = []
        for c, cs in zip(self.columns.name, self.columns.sign):
            columns.append(cs + " - " + c.strip())
        comboBox.addItems(columns)
        comboBox.setCurrentIndex(index)
        comboBox.currentIndexChanged.connect(self.indexChanged)
        self.vb = CustomViewBox()
        self.pw: pg.PlotWidget = pg.PlotWidget(viewBox=self.vb, name="plot1", enableMenu=False)
        self.plt = self.pw.plot(
            symbolPen=(65, 105, 225),
            symbolBrush=(65, 105, 225),
        )
        self.plt.setPen((65, 105, 225), width=3)
        MApplication.instance().isDarkSignal.connect(self.update_colors)
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
        if MApplication.instance().isDark:
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


class MainWindow(FileDropMixin, LogWindowMixin, MMainWindow):
    """
    Run the logic of the sweep generator.

    Parameters
    ----------
    filename : str
        Sweep file to load for editing.
    inputcb : function handle
        Callback function used to return the filename of the generated file.
    log_window : LoggingWindow, optional
        Logging window to use for displaying log messages.
    """

    extension = ".sw8"
    window_title_dirty = Signal()

    def __init__(
        self,
        filename: Path | None = None,
        *,
        inputcb: Callable[[str], None] | None = None,
        log_window: LoggingWindow | None = None,
    ):
        super().__init__()
        self.in_pytest: bool = False
        self._owns_log_window = log_window is None
        if log_window is None:
            self.log_window = LoggingWindow(parent=self)
            self.log_window.hide()
        else:
            self.log_window = log_window
        logger.info("sweep-generator starting")

        self.inputcb: Callable[[str], None] | None = inputcb
        self.last_filename: Path | None = None
        self.dirty: bool = False
        self.columns: ColumnData = ColumnData()
        self.settings: SaferQSettings = SaferQSettings("matr1x", "sweep-generator")
        self.preview_column: int = 0
        self.grid_widgets: list[ColumnWidgets]

        self.setWindowTitle("Sweep Generator")
        self.setWindowIcon(get_matrix_icon("matr1x-sweep-generator.png"))
        self.ui: UIBuilder = UIBuilder()
        self.setCentralWidget(self.ui.widgets.central_widget)
        self.addToolBar(self.ui.toolbar)
        self.setMenuBar(self.ui.menubar)
        self.setAcceptDrops(True)
        self.setValidExtensions([self.extension])
        self.create_connections()
        check_config(matr1x.config)
        check_desktop_integration()

        if filename is not None:
            if self.is_valid_extension(filename):
                self.open_file(filename)
                self.last_filename = filename
        else:
            self.update_systems()

    def closeEvent(self, a0) -> None:
        """
        Store settings before closing app.

        If the script was modified without saving, a dialog asks how to
        proceed.
        """
        if self.dirty and not self.in_pytest:
            if not save_messagebox(self, self.save_file):
                a0.ignore()
                return
        self.save_window_state()
        self.cleanup_log_window(enabled=self._owns_log_window)
        a0.accept()

    def save_window_state(self) -> None:
        """Save application configuration until next startup."""
        self.save_layout_state(self.settings)
        self.save_log_window_state(self.settings, enabled=self._owns_log_window)

    def restore_window_state(self) -> None:
        """Restore application configuration from the previous use."""
        self.restore_layout_state(self.settings)
        self.restore_log_window_state(self.settings, enabled=self._owns_log_window)

    def create_connections(self) -> None:
        """Connect actions and widgets with application logic."""
        self.ui.actions.matrix_settings.triggered.connect(open_matrix_toml)
        self.ui.actions.post_install.triggered.connect(post_installation)
        self.ui.actions.remove_desktop_integration.triggered.connect(remove_desktop_integration)
        self.ui.actions.show_log.triggered.connect(self.toggle_log_window)
        self.log_window.visibility_changed.connect(
            lambda visible: self._on_log_window_visibility_changed(visible, self.ui.actions)
        )
        self._on_log_window_visibility_changed(self.log_window.isVisible(), self.ui.actions)
        self.ui.actions.new_file.triggered.connect(self.new_file)
        self.ui.actions.load.triggered.connect(self.load_file)
        self.ui.widgets.system_list.changed.connect(self.update_systems)
        self.ui.actions.save.triggered.connect(self.save_file)
        self.ui.actions.save_as.triggered.connect(lambda: self.save_file(dialog=True))
        self.ui.actions.append.triggered.connect(lambda: self.save_file(append=True))
        self.ui.actions.append_to.triggered.connect(
            lambda: self.save_file(append=True, dialog=True)
        )
        self.ui.actions.quit.triggered.connect(self.close)
        self.ui.actions.sweep.triggered.connect(self.generate_datafile)
        self.ui.actions.preview.triggered.connect(self.preview_sweep)
        self.file_dropped.connect(lambda file: self.open_file(Path(file)))
        self.window_title_dirty.connect(lambda: self.update_window_title(dirty=True))
        self.ui.widgets.system_list.message.connect(self.ui.widgets.notifier.show_message)
        self.ui.widgets.system_list.changed.connect(lambda: self.update_window_title(dirty=True))

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
        self.columns.clear()
        clear_layout(self.ui.grid)
        self.ui.widgets.sweep_table.setRowCount(0)
        self.ui.widgets.sweep_preview.setRowCount(0)

    @AutoSlot
    def on_up_down_changed(self) -> None:
        """Handle up/down widget state changes."""
        up_down = []
        for col in range(len(self.columns.name)):
            updownstate = self.grid_widgets[col].updown.checkState()
            up_down.append(2) if updownstate == Qt.CheckState.Checked else up_down.append(0)
        self.columns.up_down = up_down

    @AutoSlot
    def on_repeat_changed(self) -> None:
        """Handle repeat widget state changes."""
        repeat = []
        for col in range(len(self.columns.name)):
            repeat.append(self.grid_widgets[col].repeat.value())
        self.columns.repeat = repeat

    @AutoSlot
    def on_loop_over_changed(self) -> None:
        """Handle loop over widget state changes."""
        loop_over = []
        for col in range(len(self.columns.name)):
            loop_over.append(self.grid_widgets[col].loopover.currentIndex() - 1)
        self.columns.loop_over = loop_over

    def update_systems(self) -> bool:
        """
        Import new system because a filename changed.

        Returns
        -------
        bool
            True on success and False on error during import.
        """
        if any(self.columns.parameter):
            self.ui.widgets.notifier.show_message(
                NotifierMessage(
                    "All previous sweep parameters have been cleared.", logging.WARNING
                )
            )
        self.reset_layout()
        self._apply_system_info_to_columns(self.ui.widgets.system_list.system_info)
        self.populate_layout()
        return True

    def _apply_system_info_to_columns(self, system_info: SystemInfo) -> None:
        """
        Update column data to match the current system.

        Derives column names, units, and signs from the flattened
        parameters. Sweep parameters for columns that exist in both the
        old and new system are preserved; all other columns start empty.
        """
        old_cols = self.columns.name
        settable_parameters = [p for p in system_info.flat_parameters if p.settable]
        self.columns.name = [p.name for p in settable_parameters]
        self.columns.unit = [p.unit for p in settable_parameters]
        self.columns.sign = [generate_col_index(p.index) for p in settable_parameters]
        save_sweep_params = {}
        for index, old_col in enumerate(old_cols):
            if old_col in self.columns.name:
                newloc = self.columns.name.index(old_col)
                save_sweep_params[newloc] = self.columns.parameter[index]
        self.columns.parameter = []
        for pos in range(len(self.columns.name)):
            if pos in save_sweep_params:
                self.columns.parameter.append(save_sweep_params[pos])
            else:
                self.columns.parameter.append([])
        self.columns.filenames = self.ui.widgets.system_list.systems

    def add2grid(
        self, widgets: LabelWidgets | ColumnWidgets, row: int = 0, column: int = 0
    ) -> None:
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
        self.ui.grid.addWidget(widgets.column, row, column)
        self.ui.grid.addWidget(widgets.nameunit, row + 1, column)
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
        self.ui.grid.addLayout(quart, row + 2, column)
        modifiers = QHBoxLayout()
        modifiers.setSpacing(5)
        if not isinstance(widgets.updown, QLabel):
            modifiers.addWidget(widgets.repeat, stretch=1)
        else:
            modifiers.addWidget(widgets.repeat)
        modifiers.addWidget(widgets.doublearrow)
        modifiers.addWidget(widgets.updown)
        self.ui.grid.addLayout(modifiers, row + 3, column)
        combobox = QVBoxLayout()
        combobox.addWidget(widgets.loopover)
        combobox.addWidget(QLabel(" "))
        self.ui.grid.addLayout(combobox, row + 4, column)

    def populate_layout(self) -> None:
        """Populate sweep control and data fields."""
        self.grid_widgets = []
        self.add2grid(ColumnGenerator.label_widgets())

        for column in range(len(self.columns.name)):
            column_generator = ColumnGenerator(self.columns, column)
            column_generator.widget_modified.connect(self.window_title_dirty.emit)
            column_generator.select_grid_column.connect(self.populate_sweep_grid)
            column_generator.append.connect(self.append_sweep_col)
            column_generator.up_down_changed.connect(self.on_up_down_changed)
            column_generator.repeat_changed.connect(self.on_repeat_changed)
            column_generator.loop_over_changed.connect(self.on_loop_over_changed)
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
        max_width = max_column_width + self.ui.grid.horizontalSpacing()
        left, _, right, _ = self.ui.grid.getContentsMargins()  # ty: ignore[not-iterable]
        screen_width = self.screen().availableGeometry().width() - left - right
        column_fit = screen_width // max_width - 1

        self.on_up_down_changed()
        self.on_loop_over_changed()
        self.on_repeat_changed()

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
        """Display a popup with the sweep given in the column."""
        sweep = self.columns.calculate_sweep()
        if isinstance(sweep, Error):
            QMessageBox.warning(self, "Cannot preview sweep:", f"{sweep.error}")
            return
        SweepPreviewPopup(self, self.preview_column, self.columns)

    def generate_datafile(self) -> Result[DataFile, str]:
        """
        Print the complete set of sweeps to self.sweep_preview.

        Returns
        -------
        bool
            True if the sweep was printed successfully, False otherwise.
        """
        result = self.columns.generate_file()
        if isinstance(result, Error):
            QMessageBox.warning(self, "Cannot generate sweep:", f"{result.error}")
            return result
        self.ui.widgets.sweep_preview.setRowCount(len(result.value.lines))
        for i, line in enumerate(result.value.lines):
            value = QTableWidgetItem(line[:1000])
            self.ui.widgets.sweep_preview.setItem(i, 0, value)
        return result

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
        result = self.generate_datafile()
        if isinstance(result, Error):
            self.ui.widgets.notifier.show_message(
                NotifierMessage("No data generated, no file saved.")
            )
            return False
        if filename.suffix != self.extension:
            filename = filename.with_suffix(self.extension)
        try:
            mode = "a" if append else "w"
            with filename.open(mode) as outputFile:
                if not append:
                    outputFile.write(result.value.header)
                for line in result.value.lines:
                    # replace excess spaces from file and print, could be removed
                    outputFile.write(line.replace("   ", " ") + "\n")
        except OSError as e:
            QMessageBox.warning(self, "Error!", f"File can not be written: {e}")
            return False
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
        Add defined sweep parameters to self.columns.parameter and populate sweep table.

        Parameters
        ----------
        column : int
            The column index (0-based).
        """
        cw = self.grid_widgets[column]
        self.columns.parameter[column].append([cw.start.text(), cw.end.text(), cw.points.text()])
        cw.start.setText("")
        cw.end.setText("")
        cw.points.setText("")
        self.sweep_available(True)
        self.populate_sweep_grid(column)

    def sweep_available(self, available: bool) -> None:
        """Change actions based on sweep availability."""
        self.ui.actions.sweep.setEnabled(available)
        self.ui.actions.save.setEnabled(available)
        self.ui.actions.save_as.setEnabled(available)
        self.ui.actions.append.setEnabled(available)
        self.ui.actions.append_to.setEnabled(available)

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
        self.ui.widgets.sweep_table.setRowCount(len(self.columns.parameter[actual_column]))

        for row, param_set in enumerate(self.columns.parameter[actual_column]):
            for i in range(3):
                line_edit = QLineEdit(self)
                line_edit.setText(str(param_set[i]))
                if i == 2:
                    line_edit.setValidator(validator[numpy.uint])
                else:
                    line_edit.setValidator(validator[float])
                line_edit.editingFinished.connect(
                    lambda line_edit=line_edit, actual_column=actual_column, row=row, i=i: (
                        self.columns.parameter[actual_column][row].__setitem__(i, line_edit.text())
                    )
                )
                line_edit.textChanged.connect(lambda: self.window_title_dirty.emit())
                line_edit.setAlignment(Qt.AlignmentFlag.AlignRight)
                self.ui.widgets.sweep_table.setCellWidget(row, i, line_edit)
            delete_button = QPushButton("-")
            delete_button.clicked.connect(
                lambda _, actual_column=actual_column, row=row: self.remove_sweep_parameter(
                    actual_column, row
                )
            )
            delete_button.clicked.connect(lambda: self.window_title_dirty.emit())
            wrapper = QWidget()
            layout = QHBoxLayout(wrapper)
            layout.addWidget(delete_button)
            layout.setContentsMargins(5, 5, 5, 5)
            layout.setAlignment(delete_button, Qt.AlignmentFlag.AlignCenter)
            self.ui.widgets.sweep_table.setCellWidget(row, 3, wrapper)

        if self.columns.parameter[actual_column]:
            self.ui.actions.preview.setEnabled(True)
        else:
            self.ui.actions.preview.setEnabled(False)

    def remove_sweep_parameter(self, col: int, row: int) -> None:
        """
        Remove a set of linspace parameters from columns.parameter at the correct position.

        Parameters
        ----------
        col : int
            The currently selected matrix column (0-based index).
        row : int
            The row of the table to be deleted.
        """
        del self.columns.parameter[col][row]
        if not any(self.columns.parameter):
            self.sweep_available(False)
        self.populate_sweep_grid(col)

    def load_file(self) -> None:
        """Open a QFileDialog to open an existing sweep file."""
        if self.dirty and not self.in_pytest:
            if not save_messagebox(self, self.save_file):
                return
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
            "# up_down : ": [],
            "# repeat : ": [],
        }
        try:
            with Path(filename).open() as infile:
                self.ui.widgets.system_list.clear()
                for line in infile:
                    regex = r"^# [Ss]ystem filename : (.+)"
                    if match := re.match(regex, line.strip()):
                        self.ui.widgets.system_list.add_systems(match.group(1).split(","))
                        if not self.update_systems():
                            return
                    for key in params.keys():
                        if key in line:
                            # read the parameters from the corresponding line
                            line = line.strip().replace(key, "")
                            params[key] = literal_eval(line)
        except PermissionError:
            QMessageBox.warning(self, "Permission error.", "No permission to open the sweep file.")
            return
        (parameter, loop_over, up_down, repeat) = params.values()
        self.columns.parameter = parameter
        # initialize layout with values specified in file
        for col in range(len(self.columns.name)):
            self.grid_widgets[col].loopover.setCurrentIndex(loop_over[col] + 1)
            self.grid_widgets[col].updown.setCheckState(Qt.CheckState(up_down[col]))
            self.grid_widgets[col].repeat.setValue(repeat[col])
        self.last_filename = Path(filename)
        self.update_window_title()
        self.generate_datafile()

    def new_file(self, reset_systems: bool = False) -> None:
        """
        Prepare a completely new sweep.

        Delete all existing sweep parameters, update the sweep grid
        accordingly and empty the sweep preview. Also reset all input
        fields to their original states.

        Parameters
        ----------
        reset_systems : bool, optional
            If True, also clear loaded systems and related state.
        """
        if self.dirty and not self.in_pytest:
            if not save_messagebox(self, self.save_file):
                return
        self._reset_state(reset_systems)

    def _reset_state(self, reset_systems: bool) -> None:
        """
        Reset UI and state to a clean baseline.

        Parameters
        ----------
        reset_systems : bool
            If True, also clear loaded systems and related state.
        """
        if reset_systems:
            self.reset_layout()
            self.ui.widgets.system_list.clear()
            self.columns.clear()
            self.last_filename = None
            self.ui.widgets.sweep_preview.setRowCount(0)
            self.update_window_title(dirty=False)
            return

        self.columns.parameter = []
        for col in range(len(self.columns.name)):
            self.columns.parameter.append([])
            self.grid_widgets[col].start.setText("")
            self.grid_widgets[col].end.setText("")
            self.grid_widgets[col].points.setText("")
            self.grid_widgets[col].repeat.setValue(1)
            self.grid_widgets[col].updown.setChecked(False)
            self.grid_widgets[col].loopover.setCurrentIndex(0)
            self.populate_sweep_grid(col)
        if self.columns.name:
            self.generate_datafile()
            self.grid_widgets[0].start.setFocus()
        else:
            self.ui.widgets.sweep_preview.setRowCount(0)
        self.last_filename = None
        self.update_window_title(dirty=False)


def main():
    """Set the basic GUI parameters and run."""
    install_error_handler()
    app = MApplication(sys.argv)
    app.setDesktopFileName("sweep-generator")
    main_window = MainWindow() if len(sys.argv) < 2 else MainWindow(filename=Path(sys.argv[1]))
    main_window.show()
    app.connect_file_handler(main_window.open_file)  # MacOS specific FileOpenEvent
    main_window.restore_window_state()
    ret = app.exec()
    sys.exit(ret)
