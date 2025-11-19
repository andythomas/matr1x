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
#
# CustomDateAxis class in this file adapted from
# https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/graphicsItems/AxisItem.html#AxisItem.tickValues
# licensed under MIT-license
"""
Contains GUI related functions and class definitions.

These are used by sweep-generator, matrix-gui, matrix-preview, matrix-
script and control-guis.
"""

import datetime
import json
import logging
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from importlib.metadata import version as package_version
from pathlib import Path
from types import TracebackType
from typing import Any, TextIO, cast, overload

import numpy as np
import pygit2
import pyqtgraph
import PySide6
from pydantic import ValidationError
from pyqtgraph.exporters import ImageExporter
from PySide6.QtCore import (
    QAbstractItemModel,
    QByteArray,
    QEvent,
    QLibraryInfo,
    QLocale,
    QModelIndex,
    QObject,
    QPoint,
    QSettings,
    QSize,
    Qt,
    QTimer,
    Signal,
    qVersion,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDoubleValidator,
    QDragEnterEvent,
    QDropEvent,
    QFileOpenEvent,
    QFontDatabase,
    QIcon,
    QImage,
    QIntValidator,
    QKeySequence,
    QPainter,
    QPalette,
    QPixmap,
    QPolygon,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from matr1x.error_handling import InternalInvariantError
from matr1x.models import MainConfig, UserlibConfig

from . import (
    datetimefmt,
    get_config_dict,
    logfolder,
    merge_dicts,
    reload_config,
    write_config,
)
from .eval import delta

# dictionary of commonly used validators
validator = {
    float: QDoubleValidator(),
    int: QIntValidator(),
    np.uint: QIntValidator(),
}
# for a double validator that disallows comma
_lo = QLocale("C")
_lo.setNumberOptions(QLocale.NumberOption.RejectGroupSeparator)
validator[float].setLocale(_lo)
validator[np.uint].setBottom(0)

MIN_INT64 = -(2**63)
MAX_INT64 = 2**63 - 1


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
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            dialog.setOption(QFileDialog.Option.DontConfirmOverwrite)
        else:
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
            dialog.setFileMode(QFileDialog.FileMode.Directory)
            dialog.setOption(QFileDialog.Option.ShowDirsOnly)

        if dialog.exec():
            # pass value to callback
            if len(dialog.selectedFiles()) > 0:
                self.callback(dialog.selectedFiles()[0])


class SystemListWidget(QListWidget):
    """
    A custom QListWidget that allows drag-and-drop reordering of items.

    This widget emits a signal when the order of items changes due to drag-and-drop operations.

    Attributes
    ----------
        orderChanged (Signal): Signal emitted when the order of items changes.
    """

    orderChanged = Signal()  # Custom signal for order changes

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialize the SystemListWidget.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(*args, **kwargs)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        # Enable drag-and-drop sorting
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)

    def dropEvent(self, event: QDropEvent) -> None:
        """
        Handle the drop event for drag-and-drop operations.

        This method is called when an item is dropped after being dragged. It updates
        the order of items and emits the orderChanged signal.

        Args:
            event (QDropEvent): The drop event object.
        """
        # Call the base class drop event to handle the reordering
        super().dropEvent(event)
        self.orderChanged.emit()  # Emit the custom signal when the order changes

    def addItem(self, item) -> None:
        """
        Add item but avoid duplicates.

        Parameters
        ----------
        item
            The item, i.e. system file to be added.
        """
        for index in range(self.count()):
            existing = self.item(index).text()
            if item == existing:
                print(f"{item} is already added and was omitted.")
                return
        super().addItem(item)


class MetaViewerWidget(QDockWidget):
    """
    Viewer and editor for meta data stored in matrix data files.

    Extensive meta data are only include in datafiles of version 7 or
    higher.
    """

    class scifloat(float):
        """Allow to edit scientific notation via this helper class."""

        def __new__(cls, value):
            """Behave like float with a different name."""
            instance = super().__new__(cls, value)
            return instance

    class EditableDelegate(QStyledItemDelegate):
        """
        Custom delegate for editable items in a view.

        This delegate provides custom editing and display functionality
        for items in a view, allowing for more advanced text selection
        and read-only behavior.

        Parameters
        ----------
        editable : bool, optional
            Whether the item should be editable. Default is False.
        parent : QWidget, optional
            The parent widget. Default is None.
        """

        def __init__(self, editable=False, parent=None):
            super().__init__(parent=parent)
            self.editable = editable

        def createEditor(self, parent, option, index):
            """
            Create and return a custom editor widget for editing item data.

            Parameters
            ----------
            parent : QWidget
                The parent widget for the editor.
            option : QStyleOptionViewItem
                The style options for the editor.
            index : QModelIndex
                The index of the item being edited.

            Returns
            -------
            Widget according to variable type
                A widget configured for editing, widget type depends on
                variable type (str - QTextEdit, str/path - FileLineEdit,
                int - QSpinBox, float - QDoubleSpinBox, any/strict - QComboBox).
            """
            cast_type, cast_spec = index.model().type(index)
            item = index.internalPointer()
            item.setData(index, "", Qt.ItemDataRole.DisplayRole)
            # Create a QTextEdit for more advanced text selection
            if isinstance(cast_spec, map):
                # strict, use combobox
                editor = QComboBox(parent)
                editor.insertItems(0, [i for i in map(str, cast_spec)])
                editor.setStyleSheet("QComboBox { border: none; padding: 0px; }")
            elif cast_type[0] is bool:
                editor = QCheckBox(parent)
                editor.setStyleSheet("QCheckBox { border: none; padding: 0px; }")
            elif cast_type[0] is int:
                editor = QSpinBox(parent)
                min_val = cast_spec[0] if (cast_spec and len(cast_spec) >= 1) else MIN_INT64
                max_val = cast_spec[1] if (cast_spec and len(cast_spec) >= 2) else MAX_INT64
                editor.setRange(min_val, max_val)
                editor.setStyleSheet("QSpinBox { border: none; padding: 0px; }")
                editor.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            elif cast_type[0] is float:
                editor = QDoubleSpinBox(parent)
                if cast_type[1]:
                    editor.setDecimals(cast_type[1])
                min_val = (
                    cast_spec[0] if (cast_spec and len(cast_spec) >= 1) else -sys.float_info.max
                )
                max_val = (
                    cast_spec[1] if (cast_spec and len(cast_spec) >= 2) else sys.float_info.max
                )
                editor.setRange(min_val, max_val)
                editor.setStyleSheet("QDoubleSpinBox { border: none; padding: 0px; }")
                editor.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            elif cast_type[0] is MetaViewerWidget.scifloat:
                editor = QLineEdit(parent)
                scifloat_validator = cast(QDoubleValidator, validator[float])
                if cast_type[1]:
                    scifloat_validator.setDecimals(cast_type[1])
                min_val = (
                    cast_spec[0] if (cast_spec and len(cast_spec) >= 1) else -sys.float_info.max
                )
                max_val = (
                    cast_spec[1] if (cast_spec and len(cast_spec) >= 2) else sys.float_info.max
                )
                scifloat_validator.setRange(min_val, max_val)
                editor.setValidator(scifloat_validator)
            elif cast_type[0] is str and cast_spec in ["file", "folder"]:

                def cb(value):
                    # I do not like this callback function.
                    # Can this be done with signals?
                    index.model().setData(index, value, Qt.ItemDataRole.EditRole)
                    index.model().dataChanged.emit(index, index)

                editor = FileLineEdit(cb, parent, cast_spec)
                editor.setStyleSheet("QLineEdit { border: none; padding: 0px; }")
            else:
                editor = QTextEdit(parent)
                editor.setStyleSheet("QTextBox { border: none; padding: 0px; }")
                # disable frame remove margins and scroll bar
                editor.setFrameStyle(0)
                editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            # Make it read-only, but still allow text selection
            if not isinstance(editor, (QComboBox, QCheckBox)):
                editor.setReadOnly(not self.editable)
            editor.setContentsMargins(0, 0, 0, 0)
            return editor

        def setEditorData(self, editor, index):
            """
            Set the editor data based on the current index.

            Parameters
            ----------
            editor : QWidget
                The editor widget to be updated.
            index : QModelIndex
                The index of the item being edited.
            """
            value = index.model().data(index, Qt.ItemDataRole.EditRole)
            if isinstance(editor, QTextEdit):
                editor.setText(value)
            elif isinstance(editor, QCheckBox):
                try:
                    editor.setChecked(value.lower() == "true")
                except ValueError:
                    # should only happen when previous value is present
                    # in editor (edited in the file)
                    editor.setValue(False)
            elif isinstance(editor, FileLineEdit):
                editor.setText(value)
            elif isinstance(editor, QComboBox):
                editor.setCurrentText(value)
            elif isinstance(editor, QSpinBox):
                try:
                    editor.setValue(int(value))
                except ValueError:
                    # should only happen when previous value is present
                    # in editor (edited in the file)
                    editor.setValue(0)
            elif isinstance(editor, QDoubleSpinBox):
                try:
                    editor.setValue(float(value))
                except ValueError:
                    # should only happen when previous value is present
                    # in editor (edited in the file)
                    editor.setValue(0)

        def setModelData(self, editor, model, index):
            """
            Set the model data based on the editor's content.

            Parameters
            ----------
            editor : QWidget
                The editor widget containing the data.
            model : QAbstractItemModel
                The model to be updated.
            index : QModelIndex
                The index of the item being edited.
            """
            if isinstance(editor, QTextEdit):
                value = editor.toPlainText()
            elif isinstance(editor, QCheckBox):
                value = bool(editor.isChecked())
            elif isinstance(editor, FileLineEdit):
                value = editor.text()
            elif isinstance(editor, QComboBox):
                value = editor.currentText()
            elif isinstance(editor, (QSpinBox, QDoubleSpinBox)):
                value = editor.value()
            elif isinstance(editor, QLineEdit):
                value = float(editor.text())
            index.model().setData(index, value, Qt.ItemDataRole.EditRole)

        def sizeHint(self, option, index):
            """Return size hint of editor widget."""
            sizeHint = super().sizeHint(option, index)
            # sizeHint.setHeight(50)
            return sizeHint

    class TreeItem:
        """
        A class representing a tree item in a hierarchical structure.

        Parameters
        ----------
        key : str
            The key or identifier for this item.
        value : Any
            The value associated with this item.
        parent : TreeItem, optional
            The parent item of this item, if any.

        Attributes
        ----------
        parent_item : TreeItem
            The parent item of this item.
        child_items : list
            List of child TreeItem objects.
        key : str
            The key or identifier for this item.
        value : Any
            The value associated with this item.
        types : Any
            The type associated with this item.
        """

        def parse_config_type(self, cast_type_spec):
            """
            Parse type info from type string provided in matr1x config.

            Arguments
            ---------
            cast_type_spec : string
                string according to the matr1x config type format

            Returns
            -------
            cast_type : tuple of type + additional parameter (used only for float)
                first entry contains type of config variable (str, int, float)
                second entry contains number of decimals for float display
            cast_spec : tuple, map, str or None
                provides the specifications for the type. Can be either
                range limits ([low, high, step], value map for strict variable,
                or "folder"/"file" for path variables
            """
            if not cast_type_spec:
                return ((str, None), None)
            # alternative way of parsing using regex:
            # regex =  r"(\w+)(?:;;(\d+))?(?:;;(folder|file|strict|range))?(?:;;(\S+))?"
            cast_split = cast_type_spec.split(";;")
            try:
                # make sure type is interpreted correctly
                if cast_split[0] == "scifloat":
                    cast_type = (MetaViewerWidget.scifloat, None)
                else:
                    cast_type = (globals()["__builtins__"][cast_split[0]], None)
            except AttributeError:
                raise AttributeError("Wrong type specified in config")
            if len(cast_split) == 1:
                # only type is specified
                return (cast_type, None)
            if cast_type[0] in (float, MetaViewerWidget.scifloat):
                # on float, second parameter can be number of digits
                try:
                    cast_type = (cast_type[0], int(cast_split[1]))
                    cast_split.pop(1)  # remove entry
                    if len(cast_split) == 1:
                        # only type and decimals are specified
                        return (cast_type, None)
                except ValueError:
                    pass  # variable not a digit, keep parsing
            if cast_split[1] == "strict":
                # strict type, following values are list, make sure they
                # are interepreted as the correct type
                try:
                    return (cast_type, map(cast_type[0], cast_split[2:]))
                except TypeError:
                    raise TypeError("Wrong value specified for strict config setting")
            if cast_split[1] == "range":
                # range type, create range spec
                if len(cast_split) < 3:
                    raise IndexError("Range value missing in config")
                try:
                    return (cast_type, [i for i in map(cast_type[0], cast_split[2:])])
                except TypeError:
                    raise TypeError("Wrong value specified for range config setting")
            if cast_type[0] is str and (cast_split[1] == "folder" or cast_split[1] == "file"):
                # file/folder path
                return (cast_type, cast_split[1])
            # something went wrong with parsing the settings, use default
            return ((str, None), None)

        def __init__(self, key, value, types=None, parent=None):
            self.parent_item = parent
            self.child_items = []

            self.key = key
            self.value = value
            self._type = types
            self.hidden = False

            # If value is a dict, convert its items to TreeItem children
            if isinstance(self.value, dict):
                for child_key, child_value in value.items():
                    cast_type = "str"
                    if isinstance(self._type, dict):
                        if child_key in self._type.keys():
                            if self._type[child_key]:
                                cast_type = self._type[child_key]
                    else:
                        if self._type:
                            cast_type = self._type
                    self.child_items.append(
                        MetaViewerWidget.TreeItem(child_key, child_value, cast_type, self)
                    )
            elif isinstance(self.value, (tuple, list, np.ndarray)):
                # for lists with finite length also use nest view
                # key is list index
                cast_type = "str"
                if isinstance(self._type, dict):
                    if self._type[child_key]:  # ty: ignore[unresolved-reference]
                        cast_type = self._type[child_key]  # ty: ignore[unresolved-reference], fixed via IFW_software #1430
                else:
                    if self._type:
                        cast_type = self._type
                if len(self.value) > 1:
                    for i, child_value in enumerate(self.value):
                        self.child_items.append(
                            MetaViewerWidget.TreeItem(f"{i}", child_value, cast_type, parent=self)
                        )
                elif len(self.value) == 1:
                    # only list with length one, use that element only
                    self.value = self.value[0]
                else:
                    # length 0 list, replace with string representation
                    self.value = str(self.value)

        def child(self, row):
            """
            Get the child item at the specified row.

            Parameters
            ----------
            row : int
                The index of the child item to retrieve.

            Returns
            -------
            TreeItem
                The child item at the specified row.
            """
            return self.child_items[row]

        def child_count(self):
            """
            Get the number of child items.

            Returns
            -------
            int
                The number of child items.
            """
            return len(self.child_items)

        def column_count(self):
            """
            Get the number of columns in the item.

            Returns
            -------
            int
                The number of columns (always 2 for Key and Value).
            """
            return 2  # Key and Value columns

        def type(self, column):
            """
            Get the data for the specified column.

            Parameters
            ----------
            column : int
                The column index (0 for Key, 1 for Value).

            Returns
            -------
            str
                The data for the specified column.
            """
            if column == 0:
                return "str", None
            elif column == 1:
                if isinstance(self.value, (tuple, list, dict, np.ndarray)):
                    # empty widgets are of type str
                    return "str", None
                return self.parse_config_type(self._type)
            return None

        def data(self, column, role):
            """
            Get the data for the specified column.

            Parameters
            ----------
            column : int
                The column index (0 for Key, 1 for Value).
            read_hidden : bool
                If true, yield the hidden value, else show nothing if hidden

            Returns
            -------
            str
                The data for the specified column.
            """
            if column == 0:
                return self.key
            elif column == 1:
                if isinstance(self.value, (tuple, list, dict, np.ndarray)):
                    # Display an empty value if it's a nested iterable
                    return ""
                if self.hidden and role == Qt.ItemDataRole.DisplayRole:
                    # editor is active, act like there is no value
                    return ""
                return str(self.value)  # Convert non-dict values to string
            return None

        def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
            """
            Set the data for the item.

            Parameters
            ----------
            index : QModelIndex
                The index of the item to set.
            value : Any
                The value to set.
            role : Qt.ItemDataRole, optional
                The role of the data being set (default is EditRole).
            """
            if not index.isValid():
                return None
            if index.column() == 1:
                if self.child_count() > 0:
                    # prevent writing into the header lines
                    return None
                if role == Qt.ItemDataRole.EditRole:
                    self.value = value
                    self.hidden = False
                else:
                    self.hidden = True

        def parent(self):
            """
            Get the parent item.

            Returns
            -------
            TreeItem
                The parent item.
            """
            return self.parent_item

        def row(self):
            """
            Get the row number of this item in its parent's list of children.

            Returns
            -------
            int
                The row number of this item.
            """
            if self.parent_item:
                return self.parent_item.child_items.index(self)
            return 0

    class TreeModel(QAbstractItemModel):
        """
        Custom tree model for displaying hierarchical data.

        Parameters
        ----------
        data : dict
            The hierarchical data to be displayed in the tree.
        parent : QObject, optional
            The parent object for this model.
        """

        def __init__(self, data, parent=None):
            super().__init__(parent)
            self.root_item = MetaViewerWidget.TreeItem("Root", data)

        def data(self, index, role=Qt.ItemDataRole.DisplayRole):
            """
            Return data for the given index and role.

            Parameters
            ----------
            index : QModelIndex
                The index of the item.
            role : Qt.ItemDataRole, optional
                The role of the data being requested.

            Returns
            -------
            Any
                The data for the given index and role.
            """
            if not index.isValid():
                return None

            item = index.internalPointer()

            if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
                return item.data(index.column(), role)

            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft

            return None

        def type(self, index, role=Qt.ItemDataRole.DisplayRole):
            """
            Return data for the given index and role.

            Parameters
            ----------
            index : QModelIndex
                The index of the item.
            role : Qt.ItemDataRole, optional
                The role of the data being requested.

            Returns
            -------
            Any
                The type for the given index and role.
            """
            if not index.isValid():
                return None

            item = index.internalPointer()

            if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
                return item.type(index.column())

            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft

            return None

        def setData(self, index, value, role):
            """
            Update the data for the given index and role.

            Parameters
            ----------
            index : QModelIndex
                The index of the item to update.
            value : Any
                The new value to set.
            role : Qt.ItemDataRole
                The role of the data being set.

            Returns
            -------
            bool
                True if the data was successfully set, False otherwise.
            """
            if role == Qt.ItemDataRole.EditRole:
                item = index.internalPointer()
                item.setData(index, value, role)
                return True
            return False

        def flags(self, index):
            """
            Return the item flags for the given index.

            Parameters
            ----------
            index : QModelIndex
                The index of the item.

            Returns
            -------
            Qt.ItemFlags
                The item flags for the given index.
            """
            if index.isValid():
                if index.column() == 1:
                    return (
                        Qt.ItemFlag.ItemIsSelectable
                        | Qt.ItemFlag.ItemIsEnabled
                        | Qt.ItemFlag.ItemIsEditable
                    )
                return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

        def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
            """
            Return the header data for the given section, orientation, and role.

            Parameters
            ----------
            section : int
                The section number.
            orientation : Qt.Orientation
                The orientation of the header.
            role : Qt.ItemDataRole, optional
                The role of the data being requested.

            Returns
            -------
            str or None
                The header data for the given section, orientation, and role.
            """
            if role == Qt.ItemDataRole.DisplayRole:
                if section == 0:
                    return "Key"
                elif section == 1:
                    return "Value"
            return None

        def index(self, row, column, parent=QModelIndex()):
            """
            Create and return a model index for the given row, column, and parent.

            Parameters
            ----------
            row : int
                The row number.
            column : int
                The column number.
            parent : QModelIndex, optional
                The parent index.

            Returns
            -------
            QModelIndex
                The model index for the given row, column, and parent.
            """
            if not self.hasIndex(row, column, parent):
                return QModelIndex()

            if parent.isValid():
                parent_item = parent.internalPointer()
            else:
                parent_item = self.root_item

            child_item = parent_item.child(row)
            if child_item:
                return self.createIndex(row, column, child_item)
            return QModelIndex()

        def parent(self, index):
            """
            Return the parent index for the given index.

            Parameters
            ----------
            index : QModelIndex
                The index of the item.

            Returns
            -------
            QModelIndex
                The parent index of the given index.
            """
            if not index.isValid():
                return QModelIndex()

            child_item = index.internalPointer()
            parent_item = child_item.parent()

            if parent_item == self.root_item:
                return QModelIndex()

            return self.createIndex(parent_item.row(), 0, parent_item)

        def resetData(self, data, types=None):
            """
            Reset the model with new data.

            Parameters
            ----------
            data : dict
                The new hierarchical data to be displayed in the tree.
            types : dict
                Types of the displayed data
            """
            self.beginResetModel()
            del self.root_item
            self.root_item = MetaViewerWidget.TreeItem("Root", data, types)
            self.endResetModel()

        def rowCount(self, parent=QModelIndex()):
            """
            Return the number of rows under the given parent.

            Parameters
            ----------
            parent : QModelIndex, optional
                The parent index.

            Returns
            -------
            int
                The number of rows under the given parent.
            """
            if not parent.isValid():
                return self.root_item.child_count()
            parent_item = parent.internalPointer()
            return parent_item.child_count()

        def columnCount(self, index):
            """
            Return the number of columns for the children of the given parent.

            Parameters
            ----------
            index : QModelIndex
                The parent index.

            Returns
            -------
            int
                The number of columns for the children of the given parent.
            """
            return 2

    def __init__(self, metadata, heading="Metadata Viewer", editable=False, parent=None):
        super().__init__(heading, parent)

        self.editable = editable

        self.tree_view: QTreeView = QTreeView()

        self.model: self.TreeModel = self.TreeModel(self.parse_header(metadata))
        self.tree_view.setModel(self.model)
        for i in range(2):
            self.tree_view.resizeColumnToContents(i)
        self.tree_view.expandAll()

        # make widget expanding
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tree_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tree_view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setWidget(self.tree_view)

        # Set the custom editable delegate
        delegate = self.EditableDelegate(editable=self.editable, parent=self.tree_view)
        self.tree_view.setItemDelegate(delegate)

        # Allow editing/selecting text in both columns
        self.tree_view.setEditTriggers(QTreeView.EditTrigger.AllEditTriggers)
        # stop auto scrolling of tree view
        self.tree_view.setAutoScroll(False)
        # add visual separation between key items
        # self.tree_view.setStyleSheet("""
        #     QTreeView::item {
        #         border-bottom: 1px solid #d3d3d3;  /* Light gray bottom border */
        #         padding: 2px;  /* Add some padding for better spacing */
        #     }
        # """)

    def update_data(self, meta, types={}):
        """
        Update data stored in the model and resize table to fit contents.

        Parameters
        ----------
        meta : dict
            New metadata to be displayed.
        types : dict
            Type definition for editable meta data
        """
        # get position of scroll bar before resetting the data
        current_pos = self.tree_view.verticalScrollBar().value()
        self.model.resetData(self.parse_header(meta), self.parse_header(types))
        # resize and expand all entries
        # (the latter might be disabled in the future, or configurable?)
        for i in range(2):
            self.tree_view.resizeColumnToContents(i)
        self.tree_view.expandAll()
        # restore scroll bar position
        self.tree_view.verticalScrollBar().setValue(current_pos)

    def parse_header(self, hdr):
        """
        Parse a matrix header and prepare for display in the table view.

        Parameters
        ----------
        hdr : dict
            Header dictionary to be parsed.

        Returns
        -------
        dict
            Parsed header data.

        TODO: Implement sorting?
        """
        data = {}
        for key, val in hdr.items():
            data[key] = val
        return data


class ConfigEditWidget(MetaViewerWidget):
    """
    Editor for config files based on the MetaViewerWidget.

    Allows editing and saving the config file.
    """

    def __init__(self):
        super().__init__({}, heading="Device config", editable=True)
        self.system_file = None
        self.system_info = {}
        self.full_system_list = []

        widget = QWidget()
        # Create a QVBoxLayout instance
        layout = QVBoxLayout()
        button_layout = QHBoxLayout()

        # Dublin Core Elements
        self.w_update_config = QPushButton("Reload config")
        self.w_update_config.setEnabled(False)
        self.w_update_config.clicked.connect(self.reload_and_update_data)

        # Add the form layout to the main layout
        button_layout.addWidget(self.w_update_config)
        layout.addLayout(button_layout)
        layout.addWidget(self.tree_view)

        # Set the main layout for the dialog
        widget.setLayout(layout)
        self.setWidget(widget)

    def parse_header(self, hdr):
        """
        Parse a matrix header and prepare for display in the table view.

        Parameters
        ----------
        hdr : dict
            Header dictionary to be parsed.

        Returns
        -------
        dict
            Parsed header data.

        TODO: Implement sorting?
        """
        data = {}
        for key, val in hdr.items():
            if key in ["columns", "units"]:
                # omit columns and units since these belong directly to the
                # data
                continue
            data[key] = val
        return data

    def set_systemfile(self, systemfile):
        """
        Set systemfile for config editor, must be called before update_data.

        Parameters
        ----------
        systemfile : list
            List of system names to update.
        """
        self.systemfile = systemfile

    def set_system_info(self, system_info):
        """
        Set system information from subprocess for config editor.

        Parameters
        ----------
        system_info : dict
            Dictionary containing system information including config.
        """
        self.system_info = system_info or {}

    def set_full_system_list(self, full_system_list):
        """
        Set the full system list for reloading system information.

        Parameters
        ----------
        full_system_list : list
            List of all system names (both configurable and non-configurable).
        """
        self.full_system_list = full_system_list

    def reload_and_update_data(self):
        """Reload system information and update data - wrapper for button action."""
        # Reload system information if full system list is available
        if hasattr(self, "full_system_list") and self.full_system_list:
            try:
                self.system_info = get_system_info(self.full_system_list)
                if not self.system_info:
                    print("Warning: Could not reload system info")
                    self.system_info = {}
            except Exception as e:
                print(f"Warning: Could not reload system info: {e}")
                self.system_info = {}

        # Call the original update_data method
        self.update_data()

    def update_data(self):
        """Update the configuration data in the widget."""
        syst_dict = {}
        reload_config()

        # Check if we have a merged system by looking for comma-separated system names
        is_merged_system = (
            self.system_info
            and "config" in self.system_info
            and any("," in system_name for system_name in self.system_info["config"].keys())
        )

        # parse config of systems specified in self.systemfile
        # Skip individual system configs if we have a merged system to avoid duplicates
        if self.systemfile is not None and not is_merged_system:
            for syst in self.systemfile:
                syst_dict[syst.strip()] = get_config_dict(syst.strip())

        # parse config from system info (from subprocess)
        if self.system_info and "config" in self.system_info:
            for system_name, config_info in self.system_info["config"].items():
                if system_name not in syst_dict:
                    syst_dict[system_name] = {}
                # Add runtime config from system info
                for key, value_info in config_info.items():
                    if isinstance(value_info, dict):
                        if "value" in value_info:
                            # Extract just the value from the nested structure
                            syst_dict[system_name][key] = value_info["value"]
                        else:
                            # If it's a dict but doesn't have 'value' key,
                            # it might be the nested structure itself, skip it
                            continue
                    else:
                        syst_dict[system_name][key] = value_info

        # Try to get type information from config system for all systems with config
        if self.system_info and "config" in self.system_info:
            for system_name, config_info in self.system_info["config"].items():
                if system_name in syst_dict:
                    try:
                        system_config_with_types = get_config_dict(system_name)
                        if "_types" in system_config_with_types:
                            if "_types" not in syst_dict[system_name]:
                                syst_dict[system_name]["_types"] = {}
                            syst_dict[system_name]["_types"].update(
                                system_config_with_types["_types"]
                            )
                    except Exception:
                        # If we can't get type info, continue without it
                        pass

        def parse_dict_and_types(d, dv, dt):
            for key, item in d.items():
                if "_types" == key:
                    dt.update(d[key])
                    continue
                elif isinstance(item, dict):
                    dv[key] = {}
                    dt[key] = {}
                    parse_dict_and_types(item, dv[key], dt[key])
                else:
                    dv[key] = d[key]

        self.value_dict = {}
        self.types_dict = {}

        parse_dict_and_types(syst_dict, self.value_dict, self.types_dict)

        super().update_data(self.value_dict, self.types_dict)
        self.w_update_config.setEnabled(True)

    def parse_item(self, item):
        """
        Parse a TreeItem and its children into a configuration dictionary.

        Parameters
        ----------
        item : TreeItem
            The TreeItem to parse.

        Returns
        -------
        dict or str
            A dictionary representing the parsed configuration, or a string
            if the item has no children.
        """
        config = {}
        if item.child_count() > 0:
            for child_item in item.child_items:
                config[child_item.data(0, Qt.ItemDataRole.EditRole)] = self.parse_item(child_item)
        else:
            if item.type(1)[0][0] is bool:
                return item.data(1, Qt.ItemDataRole.EditRole).lower() == "true"
            try:
                return item.type(1)[0][0](item.data(1, Qt.ItemDataRole.EditRole))
            except ValueError:
                return item.data(
                    1, Qt.ItemDataRole.EditRole
                )  # Return original data if conversion fails
        return config

    def get_config_dict(self):
        """
        Extract and normalize configuration data from the tree view.

        Returns
        -------
        dict
            The normalized configuration dictionary.
        """

        def create_nested_dict(keys, item):
            """Create a nested dictioinary from QItemView."""
            if len(keys) == 1:
                return {keys[0]: self.parse_item(item)}
            return {keys[0]: create_nested_dict(keys[1:], item)}

        def normalize_value(value):
            """
            Attempt to convert the input value to the appropriate type.

            Parameters
            ----------
            value : str
                The value to normalize.

            Returns
            -------
            int, float, bool, or str
                The normalized value.
            """
            if isinstance(value, str):
                # Try to convert to an integer
                if value.isdigit():
                    return int(value)
                # Try to convert to a float
                try:
                    return float(value)
                except ValueError:
                    pass
                # Convert 'true'/'false' to booleans
                if value.lower() == "true":
                    return True
                if value.lower() == "false":
                    return False

                if "~" in value:
                    value = str(Path(value).expanduser().resolve())

                # Return the value as-is if no conversion was possible
                return value
            # otherwise just return the value
            return value

        def normalize_dict(input_dict):
            """
            Apply value normalization to input_dict.

            Parameters
            ----------
            input_dict : dict
                The dictionary to normalize.

            Returns
            -------
            dict
                The normalized dictionary.
            """
            for key, value in input_dict.items():
                # If the value is a dictionary, recursively normalize dict
                if isinstance(value, dict):
                    input_dict[key] = normalize_dict(value)
                else:
                    input_dict[key] = normalize_value(value)
            return input_dict

        config_dict = {}
        for item in self.model.root_item.child_items:
            if item.child_count() == 0:
                # system has no configurable options
                continue
            sys_key = item.key
            key_parts = sys_key.split(".")
            merge_dicts(config_dict, create_nested_dict(key_parts, item))

        return normalize_dict(config_dict)

    def write_config(self, config_dict: dict[str, Any] | None = None) -> Path:
        """
        Write config data to a temporary file using matr1x.write_config.

        The configuration data is normalized and written to a named temporary
        file. This file persists after the function returns and can be used
        as an optional configuration file.

        Parameters
        ----------
        config_dict : dict, optional
            Configuration dictionary to write. If None, extracts configuration
            from the tree view using get_config_dict().

        Returns
        -------
        Path
            Path to the temporary file containing the written configuration.
        """
        if config_dict is None:
            config_dict = self.get_config_dict()

        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".toml") as tmpfile:
            temp_file = Path(tmpfile.name)
            write_config(config_dict, temp_file)  # Use matr1x's write_config

        return temp_file


class SimplePlotWidget(QGroupBox):
    """
    Plot widget for multiple vertically stacked curve or 2d plots.

    Parameters
    ----------
    cb_error : callable
        Callback function that takes a single string as parameter.
        The string will describe the present error.
        If called with an empty string, it should clear the error.
    cb_index : callable
        Callback function that takes a PlotObject as parameter.
        The function is called with the currently selected PlotObject if the
        latter changes.
    """

    class PlotObject:
        """
        Object that contains the plot, data corresponding identifiers and widgets.

        Relies on external layouts to insert the widgets/plots.

        Parameters
        ----------
        l_plot : pyqtgraph.GraphicsLayoutWidget
            Layout into which the plot is to be inserted.
        error : callable
            Callback function that takes a single string as parameter.
            The string will describe the present error.
        l_slider : QVBoxLayout
            Layout into which the sliders are added using l_slider.addWidget.
        plot2d : bool
            Flag that defines whether plot is curve or 2d plot.
        index : int
            Index of the plot in the pyqtgraph.GraphicsLayoutWidget.
        desig : list of int
            Designator that stores integers that connect the plotted values
            to some external gui elements. Essentially a simple storage.
        pen : bool or None, optional
            If True, lines will be displayed.
        """

        # exposed functions that can be used by the custom math eval
        # expression stored in math_texts.
        exposed_functions = {
            "np": np,
            "sqrt": np.sqrt,
            "e": np.e,
            "pi": np.pi,
            "power": np.power,
            "log10": np.log10,
            "cos": np.cos,
            "sin": np.sin,
            "tan": np.tan,
            "arccos": np.arccos,
            "arcsin": np.arcsin,
            "arctan": np.arctan,
            "log": np.log,
            "exp": np.exp,
        }

        # default math operations can be added here if required
        # the key should correspond to the value of math_mode for this to
        # be selected, has to provide a pair of fucntions for the x and y
        # value, respectively
        default_math = {
            "no math": [lambda xf: xf, lambda yf: yf],
            "delta-": [lambda xf: delta(xf)[0], lambda yf: delta(yf)[1]],
            "delta+": [lambda xf: delta(xf)[0], lambda yf: delta(yf)[0]],
        }

        class CustomDateAxisItem(pyqtgraph.DateAxisItem):
            # This text is included pursuant to the obligations of this upstream licence
            # and must be retained in any derivatives of this class.
            # This specific class may be used under the terms of the MIT-license:
            # Permission is hereby granted, free of charge, to any person obtaining a
            # copy of this software and associated documentation files (the "Software"),
            # to deal in the Software without restriction, including without limitation
            # the rights to use, copy, modify, merge, publish, distribute, sublicense,
            # and/or sell copies of the Software, and to permit persons to whom the
            # Software is furnished to do so, subject to the following conditions:
            #
            # The above copyright notice and this permission notice shall be included in
            # all copies or substantial portions of the Software.
            #
            # THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
            # IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
            # FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
            # THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
            # LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
            # FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
            # DEALINGS IN THE SOFTWARE.
            """
            Custom date axis item for displaying dates with customizable formatting.

            This class extends the pyqtgraph DateAxisItem to provide more flexible
            date formatting options based on the scale of the axis.

            Parameters
            ----------
            *args
                Variable length argument list passed to the parent class.
            **kwargs
                Arbitrary keyword arguments passed to the parent class.
            """

            def tickValues(self, minVal, maxVal, size):
                """
                Return the values and spacing of ticks to draw.

                Parameters
                ----------
                minVal : float
                    Minimum value of the axis range.
                maxVal : float
                    Maximum value of the axis range.
                size : int
                    Size of the axis in pixels.

                Returns
                -------
                list of tuples
                    Each tuple contains (spacing, [ticks]), where:
                    - spacing is the distance between ticks
                    - [ticks] is a list of tick values

                Notes
                -----
                The returned list has the format:
                [
                    (spacing, [major ticks]),
                    (spacing, [minor ticks]),
                    ...
                ]

                This method calls tickSpacing to determine the correct tick locations.
                """
                minVal, maxVal = sorted((minVal, maxVal))

                minVal *= self.scale
                maxVal *= self.scale

                ticks = []
                tickLevels = self.tickSpacing(minVal, maxVal, size)
                allValues = np.array([])
                for i in range(len(tickLevels)):
                    spacing, offset = tickLevels[i]

                    # determine starting tick
                    start = (np.ceil((minVal - offset) / spacing) * spacing) + offset

                    # determine number of ticks
                    num = int((maxVal - start) / spacing) + 1
                    values = (np.arange(num) * spacing + start) / self.scale
                    # remove any ticks that were present in higher levels
                    # we assume here that if the difference between a tick value and
                    # a previously seen tick value
                    # is less than spacing/100, then they are 'equal' and we can
                    # ignore the new tick.
                    close = np.any(
                        np.isclose(
                            allValues,
                            values[:, np.newaxis],
                            rtol=0,
                            atol=spacing / self.scale * 0.01,
                        ),
                        axis=-1,
                    )
                    values = values[~close]
                    allValues = np.concatenate([allValues, values])
                    ticks.append((spacing / self.scale, values.tolist()))

                if self.logMode:
                    # not tested
                    return self.logTickValues(minVal, maxVal, size, ticks)

                return ticks

            def tickStrings(self, values, scale, spacing):
                """
                Return the labels corresponding to the tick values depending on the spacing.

                Parameters
                ----------
                values : array-like
                    The tick values.
                scale : float
                    The scale factor for the values.
                spacing : float
                    The spacing between tick values.

                Returns
                -------
                list of str
                    The tick labels corresponding to the values.
                """
                # Choose the date format based on the scale
                if spacing < 0.5:  # less than 0.5 seconds
                    fmt = "%S.%f"
                elif spacing < 5:  # less than 5 seconds
                    fmt = "%M:%S.%f"
                elif spacing < 100:  # less than a minute
                    fmt = "%H:%M:%S"
                elif spacing < 4000:  # less than an hour
                    fmt = "%H:%M"
                elif spacing < 80000:  # less than a day
                    fmt = "%m-%d %H:%M"
                elif spacing < 6e5:  # less than a week
                    fmt = "%m-%d %Hh"
                elif spacing < 2.5e6:  # less than a month
                    fmt = "%y-%m-%d"
                else:
                    fmt = "%Y-%m-%d"

                # Convert timestamps to formatted date strings
                if spacing >= 5:
                    return [
                        datetime.datetime.fromtimestamp(value).strftime(fmt) for value in values
                    ]
                return [
                    datetime.datetime.fromtimestamp(value).strftime(fmt).rstrip("0")
                    for value in values
                ]

        class CategoricalAxis(pyqtgraph.AxisItem):
            """
            Custom axis item for displaying categorical data.

            This class extends pyqtgraph's AxisItem to properly display categorical
            data by mapping numeric indices to category labels.

            Parameters
            ----------
            orientation : str
                The orientation of the axis ('left', 'right', 'top', or 'bottom').
            mapping : dict, optional
                Dictionary mapping numeric indices to category labels.
            *args
                Variable length argument list passed to parent class.
            **kwargs
                Arbitrary keyword arguments passed to parent class.

            Attributes
            ----------
            mapping : dict
                Dictionary storing the mapping between numeric indices and category labels.
            unique_ticks : set
                Set storing unique tick values.
            """

            def __init__(self, orientation, mapping=None, *args, **kwargs):
                super().__init__(orientation, *args, **kwargs)
                self.mapping = mapping or {}
                self.unique_ticks = set()

            def tickStrings(self, values, scale, spacing):
                """
                Return the strings that should be placed next to ticks.

                For categorical data, shows all tick labels regardless of plot size.

                Parameters
                ----------
                values : list
                    List of values to create tick strings for.
                scale : float
                    Scale factor for values.
                spacing : float
                    Space between ticks.

                Returns
                -------
                list of str
                    List of strings to display at tick marks.
                """
                # For categorical data, show all ticks regardless of plot size
                strings = []
                for v in range(len(self.mapping)):
                    if v in self.mapping:
                        strings.append(str(self.mapping[v]))
                    else:
                        strings.append("")
                return strings

            def tickValues(self, minVal, maxVal, size):
                """
                Return the values and spacing of ticks to draw.

                Parameters
                ----------
                minVal : float
                    Minimum value visible on axis.
                maxVal : float
                    Maximum value visible on axis.
                size : int
                    Width or height of axis in pixels.

                Returns
                -------
                list of tuple
                    List containing (spacing, [tick positions]) pairs.
                """
                # Override to return fixed ticks for categorical data
                ticks = []
                if not self.mapping:
                    return [(1, [])]
                values = list(range(len(self.mapping)))
                ticks.append((1, values))
                return ticks

        def __init__(
            self,
            l_plot: pyqtgraph.GraphicsLayoutWidget,
            error,
            l_slider,
            plot2d: bool,
            index,
            desig,
            pen=None,
        ):
            self.index = index
            self.desig = desig
            self.l_plot: pyqtgraph.GraphicsLayoutWidget = l_plot
            self.l_slider = l_slider
            self.plot2d: bool = plot2d
            self.error = error

            self.pw: pyqtgraph.PlotItem
            self.plt: pyqtgraph.PlotDataItem | pyqtgraph.ImageView
            self.vb: CustomViewBox

            # Store mappings for categorical data
            self.x_mapping = {}
            self.z_mapping = {}
            self.x_is_categorical = False
            self.z_is_categorical = False

            # Cache for unique values
            self.x_unique_values = None
            self.z_unique_values = None

            # initialize the pyqtgraph display widgets
            self.vb = CustomViewBox()
            if self.plot2d is True:
                self.plt = pyqtgraph.ImageView(view=self.vb)
                # please note https://github.com/pyqtgraph/pyqtgraph/issues/3023
                self.pw = self.l_plot.ci.addPlot(
                    row=self.index, col=0, viewBox=self.vb, title=f"p{index}"
                )
            else:
                self.pw = self.l_plot.ci.addPlot(
                    row=self.index, col=0, viewBox=self.vb, title=f"p{index}"
                )
                self.plt = self.pw.plot([])
                if pen is True:
                    self.plt.setPen((0, 0, 153), width=3)
                else:
                    self.plt.setPen(None)

            self.date_axis = {
                "bottom": self.CustomDateAxisItem(orientation="bottom"),
                "top": self.CustomDateAxisItem(orientation="top"),
                "left": self.CustomDateAxisItem(orientation="left"),
                "right": self.CustomDateAxisItem(orientation="right"),
            }

            self.categorical_axis = {
                "bottom": self.CategoricalAxis(orientation="bottom"),
                "left": self.CategoricalAxis(orientation="left"),
            }

            self.ordinary_axis = {
                "bottom": self.pw.getAxis("bottom"),
                "left": self.pw.getAxis("left"),
            }

            # initialize storage variables
            self.labels = ["", "", ""]
            self.units = ["", "", ""]
            self.math_mode = "no math"
            self.math_texts = ["y", "x"]
            self.z = np.zeros(0)
            self.x = np.zeros(0)
            self.y = np.zeros(0)
            self.fx = None
            self.fy = None

            # initialize slider widget and horizontal spacer line
            # and add to l_slider
            self.w_hline = QFrame()
            self.w_hline.setFrameShape(QFrame.Shape.HLine)
            self.w_hline.setFixedHeight(2)
            self.w_hline.setVisible(False)
            if plot2d is True:
                self.w_zslider = QRangeWidget(f"p{index} - z")
            else:
                self.w_zslider = QRangeWidget(f"p{index} - y")
            self.w_zslider.set_range(0, 19)
            self.w_zslider.value_changed.connect(self._slider_event)
            self.w_zslider.setVisible(False)
            self.w_xslider = QRangeWidget(f"p{index} - x")
            self.w_xslider.set_range(0, 0)
            self.w_xslider.value_changed.connect(self._slider_event)
            self.w_xslider.setVisible(False)
            self.l_slider.addWidget(self.w_hline)
            self.l_slider.addWidget(self.w_zslider)
            self.l_slider.addWidget(self.w_xslider)

        def _convert_categorical(self, data, is_x=True):
            """Convert categorical data to numeric values with mapping."""
            if data.dtype == np.dtype("O"):
                # For categorical data, convert to numeric indices
                unique_values = np.unique([str(x) for x in data])
                if is_x:
                    self.x_unique_values = unique_values
                    self.x_is_categorical = True
                else:
                    self.z_unique_values = unique_values
                    self.z_is_categorical = True

                # Create mapping
                mapping = {idx: val for idx, val in enumerate(unique_values)}
                numeric_data = np.array(
                    [list(mapping.keys())[list(mapping.values()).index(str(x))] for x in data]
                )

                # Store mapping for axis
                if is_x:
                    self.categorical_axis["bottom"].mapping = mapping
                else:
                    self.categorical_axis["left"].mapping = mapping

                return numeric_data

            if is_x:
                self.x_is_categorical = False
            else:
                self.z_is_categorical = False
            return data

        def _raise_error(self, error):
            """
            Handle errors.

            Parameters
            ----------
            error : str
                Description of the error.
            """
            self.error(error)

        def _get_math(self, y, x):
            """
            Apply the math operation to the two data arrays.

            Applies the math operation depending on the value stored in
            self.math_mode. See default_math for the default functions that
            are implemented.

            Currently can be one of the following:
                any key of self.default_math - applies the
                  functions defined there.
                "custom" - custom math that can be specified via a
                  string stored in self.math_texts that is passed to
                  evaluated by eval(string). Available parameters are defined
                  in self.exposed_functions
                neither of the two above - no math is applied

            Parameters
            ----------
            y: numpy array
                Data to be processed.
            x: numpy array
                Data to be processed.

            Returns
            -------
            y: numpy array
                Processed data.
            x: numpy array
                Processed data.
            """
            # Don't apply math to categorical data
            if self.x_is_categorical or self.z_is_categorical:
                return y, x

            if self.math_mode in self.default_math.keys():
                # some of our default math is supposed to be used
                x = self.default_math[self.math_mode][0](x)
                y = self.default_math[self.math_mode][1](y)
            elif "custom" == self.math_mode:
                # none of the above, so we are in custom mode
                xc = None
                yc = None
                try:
                    # define function based on the string stored in
                    # math_texts[1]
                    def fx(xf, yf):
                        return eval(
                            self.math_texts[1],
                            ({"x": xf, "y": yf} | self.exposed_functions),
                        )

                    xc = fx(x, y)
                except Exception as e:
                    self._raise_error("error in math function (x): " + str(e))

                try:
                    # define function based on the string stored in
                    # math_texts[0]
                    def fy(yf, xf):
                        return eval(
                            self.math_texts[0],
                            ({"y": yf, "x": xf} | self.exposed_functions),
                        )

                    yc = fy(y, x)
                except Exception as e:
                    self._raise_error("error in math function (y): " + str(e))

                if yc is not None and xc is not None:
                    if len(yc) != len(xc):
                        self._raise_error("error in math: arrays have different length")
                    elif len(yc.shape) > 1 and all(np.array(yc.shape) > 1):
                        self._raise_error("error in math: y array has too high dimension")
                    elif len(xc.shape) > 1 and all(np.array(xc.shape) > 1):
                        self._raise_error("error in math: y array has too high dimension")
                    else:
                        y, x = yc, xc
            return y, x

        def _handle_multidim_and_sliders(self):
            """Handle slider visibility according to data dimensions."""
            self.md = False
            for slider, dshape in zip(
                [self.w_zslider, self.w_xslider], [self.zdata.shape, self.xdata.shape]
            ):
                slider.setVisible(False)
                if len(dshape) > 2:
                    # data is 3D, so show sliders
                    self.md = True
                    slider.setVisible(True)
                    slider.set_range(0, dshape[0] - 1)
                elif (len(dshape) > 1 and dshape[1] > 1) and self.plot2d is False:
                    # array is 2d and second dimension is longer than 1
                    self.md = True
                    slider.setVisible(True)
                    slider.set_range(0, dshape[1] - 1)
                elif (len(dshape) > 1 and dshape[1] == 1) and self.plot2d is False:
                    # array is 2d and second dimension is exactly 1
                    # do not show sliders in this case (only one element)
                    self.md = True
                else:
                    # reset hidden slider to zero to avoid intereference
                    # with new data
                    slider.set_value(0)

            # hide or show the horizontal spacers
            if self.md is True:
                self.w_hline.setVisible(True)
            else:
                self.w_hline.setVisible(False)
            # sliders are handled, now worry about data
            self._handle_multidim_data()

        def _handle_multidim_data(self):
            """
            Handle data redimensioning and selection according to slider position.

            This method adjusts the data dimensions and selects
            appropriate data based on the current slider positions for
            multi-dimensional data sets. It updates the x, y, and z data
            attributes of the object accordingly.
            """
            if self.md is True and self.plot2d is False:
                self.x = self.xdata[:, self.w_xslider.value()]
                self.z = self.zdata[:, self.w_zslider.value()]
            elif self.md is False and self.plot2d is False:
                self.x = self.xdata
                self.z = self.zdata
            elif self.plot2d is True:
                self.x = self.xdata
                self.y = self.ydata
                self.z = self.zdata

        def _slider_event(self, val):
            """
            Handle slider events and update the displayed data accordingly.

            Parameters
            ----------
            val: int
                Current value of the slider that is to be applied.
            """
            if self.plot2d is True:
                # for 2d plot, select index of current data element
                self._handle_multidim_data()
                if not isinstance(self.plt, pyqtgraph.ImageView):
                    raise InternalInvariantError("Plotting 3D data requires an ImageView widget!")
                self.plt.setCurrentIndex(val)
                self.pw.setTitle(
                    f"p{self.index} at {self.labels[1]} = {self.x[val]} {self.units[1]}"
                )
            else:
                # for curve, handle the data and replot
                self._handle_multidim_data()
                self.plot(symbol="o")

        def remove_plot(self):
            """
            Remove the plot and the widgets that belong to the PlotObject.

            This method removes the plot from the provided layouts,
            including the horizontal line, x-slider, and z-slider
            widgets associated with this PlotObject.
            """
            self.l_plot.removeItem(self.l_plot.ci.getItem(row=self.index, col=0))
            self.l_slider.removeWidget(self.w_hline)
            self.l_slider.removeWidget(self.w_xslider)
            self.l_slider.removeWidget(self.w_zslider)

        def parse_data(self, z, x, y):
            """
            Parse the data dictionaries into the corresponding class variables.

            Parameters
            ----------
            z : dict
                Dictionary containing z data with keys "data", "label", "desig", and "unit".
            x : dict
                Dictionary containing x data with keys "data", "label", "desig", and "unit".
            y : dict or None
                Dictionary containing y data with keys "data", "label", "desig", and "unit",
                or None if not applicable.
            """
            # Handle categorical data conversions
            self.zdata = self._convert_categorical(z["data"], is_x=False)
            self.xdata = self._convert_categorical(x["data"], is_x=True)

            # Update axis types based on data
            self.z_is_categorical = z["data"].dtype == np.dtype("O")
            self.x_is_categorical = x["data"].dtype == np.dtype("O")

            # Update axis items based on data type
            if self.z_is_categorical:
                self.pw.setAxisItems({"left": self.categorical_axis["left"]})
            else:
                # Reset to ordinary axis for numerical data
                self.pw.setAxisItems({"left": self.ordinary_axis["left"]})

            if self.x_is_categorical:
                self.pw.setAxisItems({"bottom": self.categorical_axis["bottom"]})
            else:
                # Reset to ordinary axis for numerical data
                self.pw.setAxisItems({"bottom": self.ordinary_axis["bottom"]})

            if y is not None:
                self.ydata = y["data"]
                data_sets = [z, x, y]
                self.labels = [dat["label"] for dat in data_sets]
                self.desig = [dat["desig"] for dat in data_sets]
                self.units = [dat["unit"] for dat in data_sets]
            else:
                data_sets = [z, x]
                self.labels[:2] = [dat["label"] for dat in data_sets]
                self.desig[:2] = [dat["desig"] for dat in data_sets]
                self.units[:2] = [dat["unit"] for dat in data_sets]

        def set_math_mode(self, index, math_texts):
            """
            Set the math mode and texts.

            Parameters
            ----------
            index: int
                Selects the math operation to be applied, see self.default_math.
            math_texts: [str, str]
                Contains two strings that are evaluated by eval(string). Are
                only allowed to contain functions/variables that are defined
                in self.exposed_functions.
            """
            self.math_mode = index
            self.math_texts = math_texts

        def set_data(self, z, x, y=None):
            """
            Update the data that is stored in the present plot.

            Used keys are "data", "label", "desig" and "unit".

            Parameters
            ----------
            z: dict
                z data dictionary.
            x: dict
                x data dictionary.
            y: dict or None
                y data dictionary.
            """
            self.parse_data(z, x, y)
            self._handle_multidim_and_sliders()

        def plot(self, *args, **kwargs):
            """
            Handle the actual plotting of the data and update the labels.

            Parameters
            ----------
            *args
                Variable length argument list passed to the plot
                function if curve plotting is enabled.
            **kwargs
                Arbitrary keyword arguments passed to the plot function
                if curve plotting is enabled.
            """
            if self.plot2d is True:
                if len(self.zdata.shape) > 2:
                    # 3d plotting
                    if not isinstance(self.plt, pyqtgraph.ImageView):
                        raise InternalInvariantError(
                            "Plotting 3D data requires an ImageView widget!"
                        )
                    self.plt.setImage(
                        self.z,
                        pos=[0, 0],
                        scale=[1, 1],
                        xvals=self.x,
                        axes={"t": 0, "x": 1, "y": 2},
                    )
                    # make sure top and right axis are hidden
                    for i, ax in zip(range(2), ["right", "top"]):
                        self.pw.hideAxis(ax)
                    # set labels to array index, same as on the y-axis
                    self.pw.setLabel("bottom", self.labels[2], self.units[2])
                    self.vb.setAspectLocked(False)
                    self.vb.invertY(False)
                else:
                    if not isinstance(self.plt, pyqtgraph.ImageView):
                        raise InternalInvariantError(
                            "Plotting 3D data requires an ImageView widget!"
                        )
                    # 2d data follows different dimensioning scheme
                    x0, x1 = self.x[0], self.x[-1]
                    xscale = (x1 - x0) / self.z.shape[0]
                    y0, y1 = self.y[0], self.y[-1]
                    yscale = (y1 - y0) / self.z.shape[1]
                    pos = [x0, y0]
                    scale = [xscale, yscale]
                    self.plt.setImage(self.z, pos=pos, scale=scale)
                    for i, ax in zip(range(1, 3), ["top", "right"]):
                        if self.labels[i] == "timeUTC":
                            self.pw.setAxisItems({ax: self.date_axis[ax]})
                        elif self.pw.getAxis(ax).isVisible():
                            self.pw.hideAxis(ax)
                    for i, ax in zip(range(1, 3), ["bottom", "left"]):
                        self.pw.setLabel(ax, self.labels[i], self.units[i])
                self.pw.getAxis("left").textWidth = 0
                # remove aspect lock for free zooming and do not invert y axis
                self.vb.setAspectLocked(False)
                self.vb.invertY(False)
            else:
                # for curves apply math, set labels and data
                z, x = self._get_math(self.z, self.x)
                self.pw.getAxis("left").textWidth = 0

                for i, ax in zip(range(2), ["right", "top"]):
                    if self.labels[i] == "timeUTC":
                        self.pw.setAxisItems({ax: self.date_axis[ax]})
                    elif self.pw.getAxis(ax).isVisible():
                        self.pw.hideAxis(ax)

                # Already set up in parse_data() for categorical axes
                # Set labels for axes
                for i, ax in zip(range(2), ["left", "bottom"]):
                    self.pw.setLabel(ax, self.labels[i], self.units[i])
                if not isinstance(self.plt, pyqtgraph.PlotDataItem):
                    raise InternalInvariantError("Plotting requires an PlotDataItem widget!")
                try:
                    self.plt.setData(x=x, y=z, *args, **kwargs)
                except ValueError as e:
                    # Handle shape mismatch errors
                    self._raise_error(f"Plot error: {str(e)}")

            # After plotting, if autorange is enabled on any axis, recompute now.
            auto_range = self.vb.state["autoRange"]
            if auto_range is None or isinstance(auto_range, (int, float)):
                raise InternalInvariantError("Invalid auto_range value!")
            x_auto, y_auto = auto_range
            if x_auto or y_auto:
                # updateAutoRange respects which axes are enabled for auto
                self.vb.updateAutoRange()

    def __init__(self, cb_error, cb_index, parent=None):
        super().__init__("", parent)

        self.cb_error = cb_error
        self.cb_index = cb_index
        self.plot2d = False
        self._is_refreshing = False

        grid = QGridLayout()

        self.w_pos = QLabel("x: 0.00000e-0\ny: 0.00000e-0")
        self.w_pos.setMinimumWidth(140)

        self.w_delete = QPushButton("delete")
        self.w_delete.clicked.connect(self._remove_plot)
        self.w_delete.setVisible(False)

        self.l_slider = QVBoxLayout()
        self.l_slider.setSpacing(0)

        # initialize w_calc combo box with the default math items defined
        # in the PlotObject, add "custom" for custom math.
        self.w_calc = QComboBox()
        self.w_calc.setToolTip("math operation")
        self.w_calc.addItems(list(self.PlotObject.default_math.keys()) + ["custom"])
        self.w_calc.currentIndexChanged.connect(self._calc_or_data_changed)

        self.w_math = [QLineEdit("y"), QLineEdit("x")]
        self.w_lmath = [QLabel("lambda y : "), QLabel("lambda x : ")]

        for i in range(2):
            self.w_math[i].editingFinished.connect(self._calc_or_data_changed)
            self.w_math[i].setToolTip(
                "You can use power, sqrt, exp, log, log10, cos, sin, tan and "
                "their inverse functions, pi and e.\n"
                "For more complex math, numpy is additionally defined as np.\n"
                "The dimensions on y and x need to be equal after any "
                "operation and have to remain in a single dimension."
            )

        # hide custom math layouts by default
        for widget in self.w_math + self.w_lmath:
            widget.setVisible(False)

        # put custom math in separate layout to make them scale independetly
        l_math = QHBoxLayout()
        for i in range(2):
            l_math.addWidget(self.w_lmath[i])
            l_math.addWidget(self.w_math[i], stretch=1)

        # Add GraphicsLayout and make most prominent widget
        self.gl = pyqtgraph.GraphicsLayoutWidget()
        self.gl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # have proxy that connects the position of the mouse on the
        # GraphicsLayout to display the x/y position on the current
        # plot, additionally introduce proxy to select active plot by
        # just clicking into the plot
        scene = cast(pyqtgraph.GraphicsScene, self.gl.scene())
        self.proxy = pyqtgraph.SignalProxy(
            scene.sigMouseMoved, rateLimit=30, slot=self._mouse_moved
        )
        self.proxy2 = pyqtgraph.SignalProxy(
            scene.sigMouseClicked, rateLimit=2, slot=self._mouse_clicked
        )

        # add the first empty plot with
        initial_plot = self.PlotObject(self.gl, self.cb_error, self.l_slider, False, 0, [0, 0, 0])
        self.plots: list[self.PlotObject] = [initial_plot]

        # Connect X-axis linking signal for automatic linking
        if hasattr(initial_plot, "vb") and initial_plot.vb is not None:
            initial_plot.vb.sigRangeChanged.connect(self._on_range_changed)

        self.w_plots = QComboBox()
        self.w_plots.addItem("p0 -  vs")
        self.w_plots.addItem("add plot")
        self.w_plots.currentIndexChanged.connect(self._update_wplots)

        # line_init controls default value of line visibility on startup
        line_init = False
        self.w_line = QCheckBox("lines")
        self.w_line.setChecked(line_init)
        self._update_linesetting(line_init)
        self.w_line.toggled.connect(self._update_linesetting)

        grid.addWidget(self.w_plots, 0, 0, 1, 2)
        grid.addWidget(self.w_delete, 0, 2, 1, 1)
        grid.addWidget(self.w_line, 0, 3)
        grid.addWidget(self.w_calc, 0, 4, 1, 1)
        grid.addWidget(self.w_pos, 0, 5)
        grid.addLayout(l_math, 1, 0, 1, -1)
        grid.addLayout(self.l_slider, 4, 0, 1, -1)
        grid.addWidget(self.gl, 3, 0, 1, -1)

        grid.setColumnStretch(0, 1)
        grid.setRowStretch(3, 1)
        grid.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        grid.setContentsMargins(0, 0, 0, 0)

        self.setLayout(grid)

    def _add_plot(self):
        """
        Add a plot (via PlotObject) to the current display.

        Ensures that the new plot is always appended to the end.
        """
        index = max([plot.index for plot in self.plots]) + 1
        new_plot = self.PlotObject(
            self.gl,
            self.cb_error,
            self.l_slider,
            False,
            index,
            [0, 0, 0],
            pen=self.w_line.isChecked(),
        )
        self.plots.append(new_plot)

        # Connect X-axis linking signal for automatic linking
        if hasattr(new_plot, "vb") and new_plot.vb is not None:
            new_plot.vb.sigRangeChanged.connect(self._on_range_changed)

        self.w_plots.setItemText(len(self.plots) - 1, f"p{index} -  vs ")
        self.w_plots.addItem("add plot")

    def _remove_plot(self):
        """Remove plot that is currently selected in self.w_plots."""
        if len(self.plots) == 1:
            # only single plot present
            return
        index = self.w_plots.currentIndex()
        # pop plot container from list, remove widget and delete object
        # for garbage collection
        plot = self.plots.pop(index)
        plot.remove_plot()
        del plot
        # change index to previous plot and remove the deleted one
        if index != 0:
            self.w_plots.setCurrentIndex(index - 1)
        self.w_plots.removeItem(index)
        if self.w_plots.count() == 2:
            # nothing else to be deleted, hide button
            self.w_delete.setVisible(False)

    def _update_wplots(self, index):
        """
        Update the currently selected plot upon a change of self.w_plots.

        Parameters
        ----------
        index : int
            Index of the newly selected plot in self.w_plots.
        """
        cnt = self.w_plots.count()
        if index == cnt - 1 and cnt > 1:
            # selecting last index (add plot) leads to plot being added
            self._add_plot()
            cnt += 1
        if cnt > 2 and self.w_delete.isVisible() is False:
            # something can be deleted, make button visible
            self.w_delete.setVisible(True)

        current_plot = self.plots[index]

        # Check if any axes are categorical
        has_categorical = current_plot.x_is_categorical or current_plot.z_is_categorical

        # Keep math box visible but enable/disable based on plot type and data
        self.w_calc.setVisible(not current_plot.plot2d)
        self.w_calc.setEnabled(not current_plot.plot2d and not has_categorical)

        # If categorical, reset to "no math" but keep box visible
        if has_categorical:
            self.w_calc.setCurrentIndex(0)  # "no math" index
            current_plot.math_mode = "no math"

        # update widgets according to specifications in currently selected plot
        for i in range(2):
            self.w_math[i].setText(current_plot.math_texts[i])

        # load math_mode from PlotObject and set index
        index_math = self.w_calc.findText(current_plot.math_mode)
        if index_math != -1:
            # for -1, item not found in combo box texts
            self.w_calc.setCurrentIndex(index_math)

        # pass current PlotObject to callback function to be handled externally
        self.cb_index(current_plot)

    def _toggle_plot2d(self, flag):
        """
        Toggle the plot2d flag and handle visibility of math widgets.

        Parameters
        ----------
        flag: bool
            Flag that controls whether plot2d is False or True.
        """
        self.plot2d = flag
        for widget in self.w_math + self.w_lmath:
            widget.setVisible(not flag)
        self.w_calc.setVisible(not flag)

    def _calc_or_data_changed(self):
        """Apply new data, math and labels and update the plot."""
        math_mode = self.w_calc.currentText()
        current_plot = self.w_plots.currentIndex()

        # Check if current plot has categorical data
        has_categorical = (
            self.plots[current_plot].x_is_categorical or self.plots[current_plot].z_is_categorical
        )

        # Enable/disable math combo box based on categorical data
        self.w_calc.setEnabled(not has_categorical)

        if math_mode == "custom" and self.w_math[0].isVisible() is False:
            for widget in self.w_math + self.w_lmath:
                widget.setVisible(True)
        elif math_mode != "custom" and self.w_math[0].isVisible() is True:
            for widget in self.w_math + self.w_lmath:
                widget.setVisible(False)
        # update the labels of the plot combo box
        for i, plot in enumerate(self.plots):
            if plot.plot2d is True:
                name = f"p{plot.index} - {plot.labels[0]} vs {plot.labels[1]} and {plot.labels[2]}"
            else:
                name = f"p{plot.index} - {plot.labels[0]} vs {plot.labels[1]}"
            self.w_plots.setItemText(i, name)
        # reset error
        self.cb_error("")

        self.plots[current_plot].set_math_mode(math_mode, [math.text() for math in self.w_math])
        self.plots[current_plot].plot(symbol="o")

    def _mouse_moved(self, ev):
        """
        Handle mouse interaction and display x and y values at mouse position.

        If the mouse is in one of the viewboxes, display the x and y value
        at the mouse position.

        Parameters
        ----------
        ev : tuple
            Contains the coordinates of the mouse in coordinates of self.gl.
        """
        boxes = [plot.vb for plot in self.plots]
        vb_mouse = None
        for vb in boxes:
            # get coordinate transform for top left of viewbox to identify
            # in which of the viewboxes the mouse currently resides
            pos = vb.mapRectFromView(vb.borderRect.rect()).topLeft()
            if vb.boundingRect().contains(ev[0] + pos):
                vb_mouse = vb
                # stop once we have found the correct viewbox
                continue
        if vb_mouse is not None:
            mousePoint = vb_mouse.mapSceneToView(ev[0])
            self.w_pos.setText(f"x: {mousePoint.x():.5e}\ny: {mousePoint.y():.5e}")

    def _mouse_clicked(self, ev):
        """
        Handle mouse interaction and set active plot in w_plots ComboBox.

        If the mouse is in one of the viewboxes, change the currently active
        plot on click, currently works for all types of click (left/right/middle)

        Parameters
        ----------
        ev : MouseClickEvent
            Contains the click event of the mouse in coordinates of self.gl.
        """
        boxes = [plot.vb for plot in self.plots]
        vb_mouse = None
        for vb in boxes:
            # get coordinate transform for top left of viewbox to identify
            # in which of the viewboxes the mouse currently resides
            pos = vb.mapRectFromView(vb.borderRect.rect()).topLeft()
            if vb.boundingRect().contains(ev[0].scenePos() + pos):
                vb_mouse = vb
                # stop once we have found the correct viewbox
                continue
        if vb_mouse is not None:
            index = boxes.index(vb_mouse)
            self.w_plots.setCurrentIndex(index)

    def _update_linesetting(self, state):
        """
        Update the line visibility in all plot objects that are not 2d plots.

        Parameters
        ----------
        state : bool
            If True, show lines. If False, hide lines.
        """
        if state is True:
            for plot in self.plots:
                if plot.plot2d is False:
                    if not isinstance(plot.plt, pyqtgraph.PlotDataItem):
                        raise InternalInvariantError("Plotting requires an PlotDataItem widget!")
                    plot.plt.setPen((0, 0, 153), width=3)
        if state is False:
            for plot in self.plots:
                if plot.plot2d is False:
                    if not isinstance(plot.plt, pyqtgraph.PlotDataItem):
                        raise InternalInvariantError("Plotting requires an PlotDataItem widget!")
                    plot.plt.setPen(None)

    def _on_range_changed(self, view_box, ranges: tuple[tuple[float, float], tuple[float, float]]):
        """Handle range change event to synchronize X-axis across plots with same X-column.

        Parameters
        ----------
        view_box : CustomViewBox
            The `CustomViewBox` instance that emitted the `sigRangeChanged` signal.
        ranges : tuple[tuple[float, float], tuple[float, float]]
            A tuple containing two tuples, representing the new X and Y ranges
            of the `view_box`. Each inner tuple is `(min_value, max_value)`.
        """
        # identify source
        source_plot = next((p for p in self.plots if p.vb is view_box), None)
        if source_plot is None or not source_plot.labels:
            return

        source_x_label = source_plot.labels[1]
        x_auto = bool(source_plot.vb.state["autoRange"][0])  # pyqtgraph keeps (xAuto, yAuto)

        x_range = ranges[0]

        for plot in self.plots:
            if plot is source_plot or not plot.labels:
                continue
            if plot.labels[1] != source_x_label:
                continue

            plot.vb.sigRangeChanged.disconnect(self._on_range_changed)
            if x_auto:
                plot.vb.enableAutoRange(axis=pyqtgraph.ViewBox.XAxis, enable=True)
                plot.vb.updateAutoRange()
            else:
                plot.vb.enableAutoRange(axis=pyqtgraph.ViewBox.XAxis, enable=False)
                plot.vb.setXRange(*x_range, padding=0)
            plot.vb.sigRangeChanged.connect(self._on_range_changed)

    def _plot2d_changed(self, index, new_state):
        """
        Handle a change of the plot type by replacing the PlotObject in place.

        Parameters
        ----------
        index: int
          index of the plot to be replaced (refers to w_plots)
        new_state: bool
          flag that determines whether the plot is supposed to be 2d or not
        """
        # store index of plot in self.gl
        plotindex = self.plots[index].index
        # remove plot and replace with new one
        plt = self.plots.pop(index)
        plt.remove_plot()
        del plt
        new_plot = self.PlotObject(
            self.gl,
            self.cb_error,
            self.l_slider,
            new_state,
            plotindex,
            [0, 0, 0],
            pen=self.w_line.isChecked(),
        )
        self.plots.insert(index, new_plot)

        # Connect X-axis linking signal for automatic linking
        if hasattr(new_plot, "vb") and new_plot.vb is not None:
            new_plot.vb.sigRangeChanged.connect(self._on_range_changed)
        # reset global plot2d flag
        if any([plot.plot2d for plot in self.plots]) is True:
            self._toggle_plot2d(True)
        else:
            self._toggle_plot2d(False)

    def refresh_all_plots(self):
        """
        Refresh every existing plot by briefly activating each tab once.

        Emit currentIndexChanged because that is how plots rebuild.
        """
        if self._is_refreshing:
            return
        self._is_refreshing = True
        try:
            combo = self.w_plots
            current = combo.currentIndex()
            # skip the 'add plot' entry if you keep it as the last tab
            last_real = combo.count() - 1
            if last_real <= 0:
                return
            for i in range(last_real):
                if i == current:
                    continue
                combo.setCurrentIndex(i)
            combo.setCurrentIndex(current)
        finally:
            self._is_refreshing = False

    def save_plot(self, filename):
        """
        Export the currently displayed plots into a PNG file.

        This method exports all plots currently visible in the graphics layout
        (self.gl) to a single PNG image file.

        Parameters
        ----------
        filename : str
            The path and name of the file where the PNG image will be saved.
        """
        exporter = ImageExporter(self.gl.scene())
        exporter.export(filename)

    def get_columns(self) -> tuple[str, str]:
        """Return the plotted columns."""
        index = self.w_plots.currentIndex()
        y = self.plots[index].labels[0]
        x = self.plots[index].labels[1]
        return (y, x)

    def save_data(self, filename) -> None:
        """
        Export the currently displayed plot into a text file.

        Parameters
        ----------
        filename : str
            The path and name of the file where the text file will be saved.
        """
        index = self.w_plots.currentIndex()
        z, x = self.plots[index]._get_math(self.plots[index].z, self.plots[index].x)
        data = np.column_stack((x, z))
        delimiter = "\t"
        newline = "\n"
        with Path(filename).open("w") as f:
            f.write(
                f"{self.plots[index].labels[1]}{delimiter}{self.plots[index].labels[0]}{newline}"
            )
            f.write(
                f"{self.plots[index].units[1]}{delimiter}{self.plots[index].units[0]}{newline}"
            )
        with Path(filename).open("a") as f:
            np.savetxt(f, data, delimiter=delimiter, newline=newline)

    def reset(self):
        """Reset the full SimplePlotWidget to its default state."""
        self.w_plots.blockSignals(True)
        for plot in self.plots:
            plot.remove_plot()
        del self.plots
        initial_plot = self.PlotObject(self.gl, self.cb_error, self.l_slider, False, 0, [0, 0, 0])
        self.plots = [initial_plot]

        # Connect X-axis linking signal for automatic linking
        if hasattr(initial_plot, "vb") and initial_plot.vb is not None:
            initial_plot.vb.sigRangeChanged.connect(self._on_range_changed)

        self.w_plots.setCurrentIndex(0)
        self.w_plots.clear()
        self.w_plots.addItem("p0 -  vs")
        self.w_plots.addItem("add plot")
        self.w_plots.blockSignals(False)
        self.w_calc.setCurrentIndex(0)
        self.w_math[0].setText("y")
        self.w_math[1].setText("x")
        self.w_delete.setVisible(False)
        # self.w_line.setChecked(False)

    def plot(self, z, x, y=None, plot2d=False):
        """
        Plot a new set of data.

        TODO: Document possible combinations once fully settled

        Parameters
        ----------
        z : dict
            Dictionary containing the z-axis data. Key "data" contains
            np.array of dimension 1, 2, or 3.
        x : dict
            Dictionary containing the x-axis data. Key "data" contains
            np.array of dimension 1 or 2.
        y : dict or None, optional
            Dictionary containing the y-axis data. Key "data" contains
            np.array of dimension 1 or 2. Default is None.
        plot2d : bool, optional
            Determines whether the plot is 2D or a curve. Default is False.
        """
        index = self.w_plots.currentIndex()
        if self.plots[index].plot2d != plot2d:
            self._plot2d_changed(index, plot2d)
        self.plots[index].set_data(z, x, y)
        self._calc_or_data_changed()


class CustomViewBox(pyqtgraph.ViewBox):
    """
    Reimplements the pyqthgraph ViewBox and improves its usability with the mouse.

    Behavior is as follows:

    - Right click autoscales graph
    - Mouse inside plot:
        - Left drag zooms to rectangle
        - Right drag allows panning plot
        - Mouse wheel zooms in/out with cursor position defining center
    - Mouse on x or y axis:
        - Left button drags corresponding axis
        - Right button allows panning individual axis
        - Mouse wheel zooms in/out with cursor position defining center
    """

    def __init__(self, *args, **kwds):
        """
        Initialize the CustomViewBox.

        Parameters
        ----------
        *args
            Variable length argument list.
        **kwds
            Arbitrary keyword arguments.
        """
        pyqtgraph.ViewBox.__init__(self, *args, **kwds)
        self.setMouseMode(self.RectMode)

    def mouseClickEvent(self, ev):
        """
        Handle mouse click events.

        Parameters
        ----------
        ev : QMouseEvent
            The mouse event.
        """
        if ev.button() == Qt.MouseButton.RightButton:
            self.autoRange()
            # set autorange upon change of data
            self.enableAutoRange()
        # elif ev.button() == Qt.MidButton:
        #     self.raiseContextMenu(ev)

    def mouseDragEvent(self, ev, axis=None):
        """
        Handle mouse drag events.

        Parameters
        ----------
        ev : QMouseEvent
            The mouse event.
        axis : str, optional
            The axis being dragged, if any.
        """
        if ev.button() in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
            # enable pan mode
            self.setMouseMode(self.PanMode)
            pyqtgraph.ViewBox.mouseDragEvent(self, ev, axis)
            self.setMouseMode(self.RectMode)
        elif ev.button() == Qt.MouseButton.LeftButton and axis is not None:
            # enable pan mode on individual axis
            self.setMouseMode(self.PanMode)
            pyqtgraph.ViewBox.mouseDragEvent(self, ev, axis)
            self.setMouseMode(self.RectMode)
        else:
            pyqtgraph.ViewBox.mouseDragEvent(self, ev, axis)


class EmittingStream(QObject):
    """
    Stream to communicate between threads.

    Attributes
    ----------
    name : str
        Name of the stream.
    text_written : Signal
        Signal emitted when text is written to the stream.
    """

    name = "GUIStream"
    text_written = Signal(str)

    def write(self, text):
        """
        Write text to the stream and emit a signal.

        Parameters
        ----------
        text : str
            The text to be written to the stream.
        """
        self.text_written.emit(str(text))

    def flush(self):
        """
        Flush the stream.

        This method is required for file-like objects but does nothing
        in this implementation.
        """
        pass


class OutputDuplication:
    """
    A class for duplicating print output to both the original stream and a log file.

    This class is used to duplicate output from a given stream (like stdout or stderr)
    to both the original destination and a log file. It's particularly useful for
    preserving output in GUI applications that might crash.

    Attributes
    ----------
    terminal : Optional[TextIO]
        The original stream being duplicated. If None, only log is used.
    log : TextIO
        The file object for the log file where output is additionally written.
    """

    def __init__(
        self, stream: TextIO | None, prefix: str = "control", fallbackname: str = ""
    ) -> None:
        """
        Initialize an object for output duplication into a file.

        Parameters
        ----------
        stream : TextIO | None
            The stream to duplicate output from. If None, only writes to the log file.
        prefix : str, optional
            Prefix for the log file name, by default 'control'.
        fallbackname : str, optional
            Fallback name for the log file if stream has no name, by default "".
        """
        self.terminal = stream
        if stream is not None:
            name = stream.name.strip("<>")
        else:
            name = fallbackname
        self.log = (Path(logfolder) / f"{prefix}-{name}.log").open("a")
        print(f"opening log: {self.log.name}")

    def write(self, message: str) -> None:
        """
        Write the message to both the terminal and the log file.

        Parameters
        ----------
        message : str
            The message to be written.
        """
        if self.terminal is not None:
            self.terminal.write(message)
        if message and message != "\n":
            self.log.write(f"{time.strftime(datetimefmt)}: ")
        self.log.write(message.lstrip("\r"))
        self.flush()

    def flush(self) -> None:
        """Flush both the terminal and log file streams."""
        if self.terminal is not None:
            self.terminal.flush()
        self.log.flush()

    def close(self) -> None:
        """Close the log file."""
        self.log.close()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Exit the context manager and close the log file.

        Parameters
        ----------
        exc_type : Optional[Type[BaseException]]
            The type of the exception that caused the context to be exited.
            None if no exception occurred.
        exc_value : Optional[BaseException]
            The instance of the exception that caused the context to be exited.
            None if no exception occurred.
        traceback : Optional[TracebackType]
            A traceback object encoding the stack trace.
            None if no exception occurred.
        """
        self.close()


class MetaDataDialog(QDialog):
    """Create a dialog able to handle meta data input for file headers."""

    def __init__(self, initial_values: dict[str, Any] | None = None) -> None:
        """
        Initialize the meta data dialog with optional initial values.

        Parameters
        ----------
        initial_values : Optional[Dict[str, Any]]
            Optional dictionary with initial values for the fields.
        """
        super().__init__()

        self.setWindowTitle("Dublin Core Metadata Input")

        # Create a QVBoxLayout instance
        layout = QVBoxLayout()
        # Create a QFormLayout for organized input fields
        form_layout = QFormLayout()

        # Dublin Core Elements
        self.creator = QLineEdit()
        self.identifier = QLineEdit()
        self.relation = QLineEdit()
        self.description = QTextEdit()

        # Load initial values if provided
        if initial_values:
            self.load_initial_values(initial_values)

        # Add form elements to layout
        form_layout.addRow("Creator/User:", self.creator)
        form_layout.addRow("Identifier/Sample:", self.identifier)
        form_layout.addRow("Relation:", self.relation)

        # Add the form layout to the main layout
        layout.addLayout(form_layout)
        layout.addWidget(QLabel("Description:"))
        layout.addWidget(self.description)

        # Set the main layout for the dialog
        self.setLayout(layout)

    def load_initial_values(self, values: dict[str, Any]) -> None:
        """
        Load initial values into the dialog fields.

        Parameters
        ----------
        values : Dict[str, Any]
            Dictionary with initial values for the fields.
        """
        self.creator.setText(values.get("creator", ""))
        self.identifier.setText(values.get("identifier", ""))
        self.relation.setText(values.get("relation", ""))
        self.description.setPlainText(values.get("description", ""))

    def get_metadata(self) -> dict[str, str]:
        """
        Get the metadata entered in the dialog.

        Returns
        -------
        Dict[str, str]
            Dictionary with metadata values.
        """
        return {
            "creator": self.creator.text(),
            "identifier": self.identifier.text(),
            "relation": self.relation.text(),
            "description": self.description.toPlainText(),
        }

    def setEnabled(self, state: bool) -> None:
        """
        Accept or prohibit user inputs.

        Parameters
        ----------
        state : bool
            Accept (True) or block (False) input.
        """
        self.creator.setEnabled(state)
        self.identifier.setEnabled(state)
        self.relation.setEnabled(state)
        self.description.setEnabled(state)
        QDialog.setEnabled(self, state)


class TimeoutDialogBase(QDialog):
    """Base class for dialogs with timeout functionality."""

    def __init__(
        self,
        query: str,
        parent: QWidget | None = None,
        timeout: float = float("inf"),
        default_value: Any = "",
    ):
        """
        Initialize the base dialog with timeout functionality.

        Parameters
        ----------
        query : str
            The text to display on the label above the input field.
        parent : QWidget, optional
            The parent widget of the dialog.
        timeout : float, optional
            Timeout in seconds before dialog automatically closes. Default is infinity (no timeout).
            0 is interpreted as infinity.
        default_value : Any, optional
            Default value to show in input field.
        """
        super().__init__(parent)
        self.setWindowTitle("Matrix-script input")

        self.default_value = default_value
        self.user_responded = False  # Track if user clicked a button
        self.timeout = timeout if timeout else float("inf")

        self.label = QLabel(query, self)

        # This will be created by subclasses
        self.input_widget = None

        self.timer_label = QLabel("", self)
        self.timer_label.setVisible(self.timeout != float("inf"))

        self.ok_button = QPushButton("Send input", self)
        self.abort_button = QPushButton("Abort script", self)

        self.ok_button.clicked.connect(self._button_clicked)
        self.ok_button.clicked.connect(self.accept)
        self.abort_button.clicked.connect(self._button_clicked)
        self.abort_button.clicked.connect(self.reject)

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

    def setup_layout(self):
        """Set up the dialog layout."""
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.abort_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.label)
        if self.input_widget:
            main_layout.addWidget(self.input_widget)
        main_layout.addWidget(self.timer_label)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

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
        parent: QWidget | None = None,
        timeout: float = float("inf"),
        default_value: str = "",
    ):
        """
        Initialize the text input dialog with a its GUI elements.

        Parameters
        ----------
        query : str
            The text to display on the label above the input field.
        parent : QWidget, optional
            The parent widget of the dialog.
        timeout : float, optional
            Timeout in seconds before dialog automatically closes. Default is infinity (no timeout).
            0 is interpreted as infinity.
        default_value : str, optional
            Default value to show in input field.
        """
        super().__init__(query, parent, timeout, default_value)

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
        parent: QWidget | None = None,
        timeout: float = float("inf"),
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
        parent : QWidget, optional
            The parent widget of the dialog.
        timeout : float, optional
            Timeout in seconds before dialog automatically closes. Default is infinity (no timeout).
            0 is interpreted as infinity.
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
        super().__init__(query, parent, timeout, default_value)

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


class YesNoAbortDialog(QMessageBox):
    """Modal dialog for boolean input for matrix-script."""

    def __init__(
        self,
        question: str,
        parent: QWidget | None = None,
        timeout: float = float("inf"),
        default_value: str = "yes",
    ):
        """
        Initialize the yes/no dialog with a question and buttons.

        Parameters
        ----------
        question : str
            The question to display on the label.
        parent : QWidget, optional
            The parent widget of the dialog.
        timeout : float, optional
            Timeout in seconds before dialog automatically returns default_value.
            Default is infinity (no timeout). 0 is interpreted as infinity.
        default_value : str, optional
            Default value to return if timeout occurs. Should be "Yes", "No", or empty.
            Default is True.
        """
        super().__init__(parent)
        self.setWindowTitle("Question")
        self.setText(question)
        self.setIcon(QMessageBox.Icon.Question)

        self.logger = logging.getLogger("YesNoAbortDialog")

        # Normalize default value and ensure it's either "yes" or "no"
        self.default_value = (
            default_value.lower() if default_value.lower() in ["yes", "no"] else "yes"
        )
        self.timeout_occurred = False  # Required for YesNoAbortDialog functionality
        self.user_responded = False  # Track if user clicked a button
        self.timeout = timeout if timeout else float("inf")

        # Add custom buttons with default button indication when timeout is set
        button_text_yes = "Yes"
        button_text_no = "No"

        # If timeout is set, add visual indications to the default button
        if self.timeout != float("inf"):
            if self.default_value == "yes":
                button_text_yes = "Yes (Default)"
            else:
                button_text_no = "No (Default)"

        # Create buttons
        self.yes_button = self.addButton(button_text_yes, QMessageBox.ButtonRole.AcceptRole)
        self.no_button = self.addButton(button_text_no, QMessageBox.ButtonRole.RejectRole)
        self.abort_button = self.addButton("Abort script", QMessageBox.ButtonRole.DestructiveRole)

        # Connect button signals to track user response
        self.yes_button.clicked.connect(self._button_clicked)
        self.no_button.clicked.connect(self._button_clicked)
        self.abort_button.clicked.connect(self._button_clicked)

        # Simple styling for default button if timeout is set
        if self.timeout != float("inf"):
            # Set bold font for the default button
            default_button = self.yes_button if self.default_value == "yes" else self.no_button
            font = default_button.font()
            font.setBold(True)
            default_button.setFont(font)

            # Make this the default button (responds to Enter key)
            self.setDefaultButton(default_button)

            # Set up timer and label - use milliseconds for better precision
            self.timer_label = QLabel(f"Time remaining: {int(self.timeout)} seconds", self)
            layout = self.layout()
            if isinstance(layout, QGridLayout):
                layout.addWidget(self.timer_label, 1, 1, 1, 3)
            else:
                raise InternalInvariantError("No grid-layout was returned!")
            self.remaining_time = self.timeout * 1000  # Convert to milliseconds
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.update_timer)
            self.timer.start(100)  # Update every 100ms for better precision

    def _button_clicked(self):
        """Mark that user has responded to prevent timeout override."""
        self.user_responded = True
        if hasattr(self, "timer"):
            self.timer.stop()

    def update_timer(self):
        """Update the timer display and handle timeout."""
        # Don't process timeout if user already responded
        if self.user_responded:
            return

        self.remaining_time -= 100  # Decrement by 100ms

        if self.remaining_time <= 0:
            # Give a small grace period for button clicks
            if not self.user_responded:
                self.timeout_occurred = True
                self.timer.stop()
                self.close()
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

    def exec_and_get_response(self):
        """
        Show the dialog and return the button clicked by the user.

        Returns
        -------
        str
            The response based on the button clicked ("yes", "no", or "abort").
            If timeout occurred, returns the default_value.
        """
        self.exec()

        # Check timeout first, but only if user didn't respond
        if self.timeout_occurred and not self.user_responded:
            self.logger.info(
                "Dialog timeout occurred - automatically selected: %s", self.default_value
            )
            if self.default_value in ["yes", "no"]:
                return self.default_value
            # If default_value is not valid, return "yes" as a default
            return "yes"

        # User responded - return their choice
        if self.clickedButton() == self.yes_button:
            return "yes"
        elif self.clickedButton() == self.no_button:
            return "no"
        elif self.clickedButton() == self.abort_button:
            return "abort"
        return "Unknown"


class TerminationDialog(QMessageBox):
    """
    Dialog to determine how a terminated datafile should be marked.

    This dialog presents two options to the user:
    1. Mark the datafile as "Aborted"
    2. Mark the datafile as "Finished"

    The user's selection determines how the termination status of the datafile
    will be recorded.

    Returns
    -------
    str
        The selected termination status: either "aborted" or "finished".
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Termination Status")
        self.setText("How should the terminated datafile be marked?")
        self.setIcon(QMessageBox.Icon.Question)

        # Add buttons
        self.abort_button = self.addButton("Aborted", QMessageBox.ButtonRole.RejectRole)
        self.finish_button = self.addButton("Finished", QMessageBox.ButtonRole.AcceptRole)

    def get_selection(self):
        """
        Display the dialog and return the user's selection.

        Returns
        -------
        str
            The selected termination status: either "finished" or "aborted".
        """
        self.exec()

        if self.clickedButton() == self.finish_button:
            return "finished"
        else:
            return "aborted"


class AboutBox(QMessageBox):
    """Provide an about box with install debug info."""

    def __init__(self, title, icon, package, date_format, parent=None):
        """
        Initialize an about box dialog with installation information.

        Parameters
        ----------
        title : str
            Title string to show in the window title and header.
        icon : QIcon
            Icon to display in the about box.
        package : module
            Python package/module to get version and git info from.
        date_format : str
            Format string for displaying git commit date.
        parent : QWidget, optional
            Parent widget for this dialog, by default None.
        """
        super().__init__(parent)
        # The rich text (html) messes with the sizes
        style = QApplication.style()
        assert style is not None
        icon_size = style.pixelMetric(QStyle.PixelMetric.PM_MessageBoxIconSize)
        pixmap = icon.pixmap(icon_size)
        self.setIconPixmap(pixmap)
        self.setWindowTitle(title)

        # Get package and git information
        (version, branch, sha, time) = self.get_install_info(package)
        if time != "not available":
            date = datetime.datetime.fromtimestamp(time).strftime(date_format)
        else:
            date = time

        # Get Python interpreter information
        python_info = self.get_python_interpreter_info()

        # Get system and Qt information
        system_type = platform.system().lower()
        result = subprocess.run(
            "qmake6 --version | grep -oE '6[.][0-9]+[.][0-9]+'",
            shell=True,
            text=True,
            capture_output=True,
        )
        if result.returncode == 0:
            qmake_qt6_version = result.stdout.strip()
        else:
            qmake_qt6_version = "unavailable"

        text = f"""
                <div style="text-align: left;">
                    <p><b>Git information:</b><br>
                    Branch:</b> {branch}<br>
                    Commit:</b> {sha}<br>
                    Date:</b> {date}</p>

                    <p><b>Python Environment</b><br>
                    Python:</b> {python_info["implementation"]} {python_info["full_version"]}<br>
                    Executable:</b> {python_info["executable"]}<br>
                    Environment:</b> {python_info["env_description"]}<br>
                    PySide6 version:</b> {PySide6.__version__}<br>
                    PySide6 build against:</b> {qVersion()}<br>
                    Location:</b> {python_info["env_location"]}</p>

                    <p><b>System Information</b><br>
                    Platform:</b> {system_type}<br>
                    System Qt (qmake):</b> {qmake_qt6_version}</p>

                    <p>(C) 2006-2025 Matr1x Developers. All rights reserved.</p>
                </div>
                """

        self.setText(f"<b>{title} {version}</b>")
        self.setInformativeText(text)
        self.setStandardButtons(QMessageBox.StandardButton.Ok)

    def _shorten_path(self, path: str) -> str:
        """
        Shorten a file system path for display by using ~ for home directory.

        Parameters
        ----------
        path : str
            Full file system path to shorten.

        Returns
        -------
        str
            Shortened path with ~ substitution if under home directory.
        """
        try:
            path_obj = Path(path).resolve()
            home = Path.home()
            if path_obj.is_relative_to(home):
                return "~/" + str(path_obj.relative_to(home))
            return str(path_obj)
        except (ValueError, AttributeError, OSError):
            return path

    def get_python_interpreter_info(self) -> dict[str, str]:
        """
        Get Python interpreter information formatted for the about dialog.

        Returns
        -------
        dict[str, str]
            Dictionary containing interpreter version, implementation, and environment info.
        """
        # Full version string (includes build info)
        full_version = sys.version.split()[0]

        # Implementation (CPython, PyPy, etc.)
        implementation = sys.implementation.name.title()

        # Interpreter executable path (shortened)
        executable = self._shorten_path(sys.executable)

        # Virtual environment detection
        venv_info = self.get_virtual_env_info()

        return {
            "full_version": full_version,
            "implementation": implementation,
            "executable": executable,
            "env_description": venv_info["description"],
            "env_location": venv_info["location"],
        }

    def get_virtual_env_info(self) -> dict[str, str]:
        """
        Detect and return virtual environment information.

        Returns
        -------
        dict[str, str]
            Dictionary containing environment description and location.
        """
        # Determine environment type (only modern venv, not old virtualenv)
        if hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix:
            env_type = "venv"
            env_location = sys.prefix
        else:
            env_type = "system"
            env_location = sys.prefix

        # Check for conda
        conda_env = os.environ.get("CONDA_DEFAULT_ENV")
        if conda_env:
            if env_type == "system":
                env_type = "conda"
            env_description = "Conda"
        elif env_type == "system":
            env_description = "System Python"
        else:
            env_description = env_type.title()

        # Shorten location path for display
        location = self._shorten_path(env_location)

        return {"description": env_description, "location": location}

    def get_install_info(self, imported_package):
        """Receive git infos about the installed version."""
        commit_branch = "not available"
        commit_time = "not available"
        commit_short_sha = "not available"
        try:
            repo = pygit2.Repository(imported_package.__file__)
            commit_branch = repo.head.shorthand
            last_commit = repo[repo.head.target]
            commit_short_sha = str(last_commit.id)[:7]
            commit_time = last_commit.author.time
            if commit_branch == "HEAD":
                # Attempt to find the remote branch
                for ref_name in repo.references:
                    ref = repo.lookup_reference(ref_name)
                    if ref.target == repo.head.target and ref_name.startswith("refs/remotes/"):
                        commit_branch = ref.shorthand
                        break
        except pygit2.GitError:
            pass
        installed_version = package_version(imported_package.__name__)
        return (installed_version, commit_branch, commit_short_sha, commit_time)


def get_matrix_icon(
    name: str, color: QColor | None = None, pencolor: QColor = QColor("white")
) -> QIcon:
    """
    Look up 'name' and get corresponding QIcon back.

    Icons from a theme such as QIcon.fromTheme("media-playback-start") are not available on all
    platforms. Consequently, we fallback to the Qt icons, which are also repecting platform and
    theme, at least to some extent. Additionally, icons can be generated or the Matrix
    applications icons can be used.

    Parameters
    ----------
    name : str
        The name of the icon. If it starts 'SP_' it signifies to use the Qt build-in icon,
        'CHAR_' will generate a circle with the letter in it, 'CUSTOM_' provides several
        painted icons and 'matr1x-' will use the matrix application icons.
    color : QColor or str
        The color of the icon if applicable.
    pencolor: QColor
        The color of the painted items.

    Returns
    -------
    QIcon
    """
    # Get the included Qt icon
    if name.startswith("SP_"):
        style = QApplication.style()
        assert style is not None
        icon = style.standardIcon(getattr(QStyle.StandardPixmap, name))
        return icon
    # Use the original matrix icons
    elif name.startswith("matr1x-"):
        icondir = Path(__file__).parent / "scripts" / "icons"
        pixmap = QPixmap(str(icondir / name))
        # Change the color of the white icon if requested
        # and remove the rest for better visibility in a GUI
        if color is not None:
            image = pixmap.toImage()
            image = image.convertToFormat(QImage.Format.Format_ARGB32)
            for x in range(image.width()):
                for y in range(image.height()):
                    pixel_color = QColor(image.pixel(x, y))
                    if pixel_color != QColor("white"):
                        image.setPixelColor(x, y, QColor(0, 0, 0, 0))
                    else:
                        image.setPixelColor(x, y, color)
            pixmap = QPixmap.fromImage(image)
        pixmap = pixmap.copy(15, 15, 226, 226)
        return QIcon(pixmap)
    # Draw to shared circle part
    if color is None:
        color = QColor("RoyalBlue")
    size = 256
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(5, 5, size - 10, size - 10)
    if name.startswith("CHAR_"):  # Draw an icon with a letter in the center
        letter = name[5]
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSizeF(size * 0.8)
        painter.setFont(font)
        painter.setPen(pencolor)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, letter)
    elif name.startswith("CUSTOM_"):
        custom_name = name[7:]
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(pencolor)
        painter.setPen(pencolor)
        if custom_name == "Play":
            triangle = QPolygon(
                [
                    QPoint(int(size // 15 + size * 0.3), int(size * 0.2)),
                    QPoint(int(size // 15 + size * 0.3), int(size * 0.8)),
                    QPoint(int(size // 15 + size * 0.7), int(size * 0.5)),
                ]
            )
            painter.drawPolygon(triangle)
        elif custom_name == "Updown":
            up_arrow = QPolygon(
                [
                    QPoint(int(size * 0.25), int(size * 0.2)),
                    QPoint(int(size * 0.05), int(size * 0.8)),
                    QPoint(int(size * 0.45), int(size * 0.8)),
                ]
            )
            down_arrow = QPolygon(
                [
                    QPoint(int(size * 0.55), int(size * 0.2)),
                    QPoint(int(size * 0.75), int(size * 0.8)),
                    QPoint(int(size * 0.95), int(size * 0.2)),
                ]
            )
            painter.drawPolygon(up_arrow)
            painter.drawPolygon(down_arrow)
        elif custom_name == "Power":
            width = size // 8
            height = size // 2
            painter.drawRect(size // 2 - width // 2, size // 4, width, height)
        elif custom_name == "Stop":
            painter.drawRect(int(size * 0.3), int(size * 0.3), int(size * 0.4), int(size * 0.4))
        elif custom_name == "Pause":
            bar_width = size * 0.15
            bar_height = size * 0.4
            spacing = size * 0.1
            x_offset = (size - 2 * bar_width - spacing) / 2
            y_offset = (size - bar_height) / 2
            painter.drawRect(int(x_offset), int(y_offset), int(bar_width), int(bar_height))
            painter.drawRect(
                int(x_offset + bar_width + spacing),
                int(y_offset),
                int(bar_width),
                int(bar_height),
            )
        else:
            raise ValueError(f"Unknown icon type {name}.")
    else:
        raise ValueError(f"Unknown icon type {name}.")
    painter.end()
    return QIcon(pixmap)


def detect_shortcut(event, shortcut):
    """
    Compare a combination of keys in a string to a keypress event.

    Parameters
    ----------
    event : QEvent
        The event that was detected
    shortcut : str or QKeySequence
        The keyboard shortcut as used in QKeySequence(string) or directly

    Returns
    -------
    bool
        Indicates if there is a match
    """
    key = event.key()
    modifiers = event.modifiers()
    # A QKeySequence could be a sequence of several keys. Only the first
    # combination makes sense as a shortcut
    if isinstance(shortcut, str):
        # There seems to be bug bug, but this code is unreachable.
        # Will look at it later (at).
        keys = QKeySequence(shortcut)[0]  # type: ignore
    elif isinstance(shortcut, QKeySequence):
        keys = shortcut[0]
    else:
        raise ValueError("Shortcut has to be of type(str) or type(QKeySequence).")
    if key == keys.key() and modifiers == keys.keyboardModifiers():
        return True
    else:
        return False


def save_messagebox(instance) -> int:
    """
    Show a messagebox to query file save.

    Ask the user to write unsaved changes to a file
    and return choice.

    Returns
    -------
    return : int
        The choice as a QMessageBox.StandardButton enum.
    """
    msg = QMessageBox(parent=instance)
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setText("Unsaved modifications!")
    msg.setInformativeText("Do you want to save your changes?")
    msg.setStandardButtons(
        QMessageBox.StandardButton.Save
        | QMessageBox.StandardButton.Discard
        | QMessageBox.StandardButton.Cancel
    )
    discard = msg.button(QMessageBox.StandardButton.Discard)
    assert discard is not None
    discard.setText("Don't Save")
    # Is this the best default button?
    msg.setDefaultButton(QMessageBox.StandardButton.Save)
    return msg.exec()


def create_tray_notification(title: str, message: str, instance) -> None:
    """
    Show a platform independent desktop notification.

    Parameters
    ----------
    title : str
        The title of the notification.
    message : str
        The message of the notification.
    """
    instance._tray_icon = QSystemTrayIcon()
    main_window = instance.window()
    if isinstance(main_window, QMainWindow):
        icon = main_window.windowIcon()
    else:
        icon = QIcon()
    instance._tray_icon.setIcon(icon)
    instance._tray_icon.show()
    instance._tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Warning)


class ThemeDetector(QWidget):
    """
    Hidden widget that detects theme changes.

    This is required because a QWidget receives different signals than
    the QApplication.
    """

    isDarkSignal = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hide()
        self._is_dark = QTextEdit().palette().color(QPalette.ColorRole.Text).value() > 128

    def isDark(self) -> bool:
        """
        Return the desktop theme (Light or Dark).

        Returns
        -------
        bool
            Desktop dark (True) or Light (False).
        """
        return self._is_dark

    def changeEvent(self, event) -> None:
        """Detect theme change event."""
        if event.type() == QEvent.Type.PaletteChange:
            self._is_dark = QTextEdit().palette().color(QPalette.ColorRole.Text).value() > 128
            self.isDarkSignal.emit(self._is_dark)
        super().changeEvent(event)


class MApplication(QApplication):
    """Fix GUI related issues for all applications."""

    isDarkSignal = Signal(bool)
    isDark = property(lambda self: self._theme_detector.isDark())
    openfile = Signal(str)

    def __init__(self, args: Sequence[str]) -> None:
        """
        Improve theme change handling, linux and mac behavior.

        Use a helper widget for better theme handling. Automatically
        select the xcb client on a Linux machine.  Allow double-click
        file opening on a Mac.

        args : list of str
            Arguments for QApplication
        """
        if sys.platform == "linux":
            if "QT_QPA_PLATFORM" not in os.environ and "xcb" in self._list_platform_plugins():
                os.environ["QT_QPA_PLATFORM"] = "xcb"
        super().__init__(args)
        if os.name == "nt":
            self.setStyle("fusion")  # Enable modern mode on Windows which allows for dark mode
        self._theme_detector = ThemeDetector()
        self._theme_detector.isDarkSignal.connect(self.isDarkSignal.emit)
        self._pending_files = []
        self._handler_connected = False

    def _list_platform_plugins(self) -> Sequence[str]:
        """
        List available platforms by inspecting the platforms directory.

        Returns
        -------
        Sequence[str]
            A list consisting of all possible platforms
        """
        plugin_path = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
        platforms_path = plugin_path / "platforms"
        if platforms_path.exists():
            plugins = [f.name for f in platforms_path.iterdir() if f.is_file()]
            platforms = [Path(plugin).stem.replace("libq", "") for plugin in plugins]
            return platforms
        else:
            return []

    def toolbar_icon_size(self) -> int:
        """
        Return the toolbar icon size for all GUIs.

        Returns
        -------
        int
            size of the icon
        """
        small = MApplication.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize)
        standard = MApplication.style().pixelMetric(QStyle.PixelMetric.PM_ToolBarIconSize)
        intermediate = int((small + standard) / 2)
        return intermediate

    def event(self, event: QEvent) -> bool:
        """Handle application events including file open events."""
        if event.type() == QEvent.Type.FileOpen and isinstance(event, QFileOpenEvent):
            filename = event.file()
            if self._handler_connected:
                self.openfile.emit(filename)
            else:
                self._pending_files.append(filename)
        return QApplication.event(self, event)

    def connect_file_handler(self, handler: Callable[[str], None]) -> None:
        """
        Connect file open handler and process any buffered events.

        Parameters
        ----------
        handler: Callable[[str], None]
            A function to connect that takes a filename as a parameter.
        """
        self.openfile.connect(handler)
        self._handler_connected = True
        for filename in self._pending_files:
            self.openfile.emit(filename)
        self._pending_files.clear()

    def setDesktopFileName(self, name: str, /) -> None:
        """
        Set desktop filename with platform-specific optimizations.

        Parameters
        ----------
        name : str
            The desktop filename (e.g., "matrix-script")
        """
        if sys.platform == "darwin":
            from AppKit import NSApplication  # type: ignore
            from Foundation import NSBundle  # type: ignore

            bundle = NSBundle.mainBundle()
            if bundle:
                info_dict = bundle.localizedInfoDictionary() or bundle.infoDictionary()
                info_dict["CFBundleName"] = name
            # Correct the menu
            app = NSApplication.sharedApplication()
            main_menu = app.mainMenu()
            if main_menu:
                # Get left-most menu with app-specific items
                app_menu = main_menu.itemAtIndex_(0).submenu()
                for i in range(app_menu.numberOfItems()):
                    item = app_menu.itemAtIndex_(i)
                    item.setTitle_(item.title().replace("Python", name))

        super().setDesktopFileName(name)


def get_application_instance() -> MApplication:
    """
    Return the MApplication instance.

    This simplifies pyright static type checking.

    Returns
    -------
    MApplication
        The instance that cannot be None.
    """
    app = MApplication.instance()
    if not isinstance(app, MApplication):
        raise InternalInvariantError("The application instance is None!")
    return app


# Common system information functions for matrix scripts
def get_system_info(systems):
    """Get system information using subprocess."""
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import json; from matr1x.system import MergedSystem;"
                f"print(json.dumps(MergedSystem.from_files({systems})."
                "grab_information()))",
            ],
            capture_output=True,
            timeout=30,
        )

        if result.returncode == 0:
            output_str = result.stdout.decode()
            json_data = extract_json_from_output(output_str)
            if json_data is not None:
                return json_data
            else:
                print("Warning: Could not parse JSON from subprocess output")
                return {}
        else:
            stderr_output = result.stderr.decode()
            print(f"Error getting system info: {stderr_output}")
            # If subprocess failed due to missing dependencies, return empty dict
            if "ModuleNotFoundError" in stderr_output:
                print("Note: System config will not be available due to missing dependencies")
            return {}
    except (subprocess.TimeoutExpired, Exception) as e:
        print(f"Error getting system info: {e}")
        return {}


def _format_validation_error(e: ValidationError | TypeError | ValueError, base: str = "") -> str:
    """
    Format the error output of the toml validation in html.

    Parameters
    ----------
    e: ValidationError or TypeError or ValueError
        The errors with all information.
    base: str
        The prefix of the error location, e.g., 'ifwlib'.

    Returns
    -------
    str
        The html with the human readable errors.
    """
    html = ""
    if isinstance(e, ValidationError):
        for err in e.errors():
            location = base + ".".join(str(i) for i in err["loc"])
            msg = err["msg"].replace(">", "&gt;").replace("<", "&lt;")
            html += f"{location}: {msg}"
            if "url" in err:
                url = err["url"]
                html += f' (<a href="{url}">More info</a>)'
            html += "<br><br>"
    else:
        # Handle TypeError and ValueError which don't have errors() method
        msg = str(e).replace(">", "&gt;").replace("<", "&lt;")
        html += f"{base}: {msg}<br><br>"
    return html


def check_config(config: dict) -> None:
    """
    Validate the configuration tomls.

    Parameters
    ----------
    config: dict
        The configuration dictionary to validate.
    """
    html = ""
    data = dict(config)
    for key in list(data.keys()):  # validate everything but matr1x
        if key != "matr1x":
            try:
                UserlibConfig(**data.pop(key))
            except (ValidationError, TypeError, ValueError) as e:
                html += _format_validation_error(e, key + ".")
    try:
        MainConfig(**config)
    except (ValidationError, TypeError, ValueError) as e:
        html += _format_validation_error(e)
    if html != "":
        html = (
            f"Please check your configuration file ({Path.home() / '.matr1x.toml'})! "
            "Some settings will not work as intended. "
            "The following error(s) occured:<br><br>"
        ) + html
        QMessageBox.critical(None, "Validation error!", html)


def extract_json_from_output(output_str):
    """Extract JSON from subprocess output."""
    try:
        # Try to parse the entire output as JSON first
        return json.loads(output_str.strip())
    except json.JSONDecodeError:
        # If that fails, try to find JSON in the output
        lines = output_str.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    return json.loads(line)
                except json.JSONDecodeError:
                    continue
        return None


def show_json_parse_error(output_str):
    """Show JSON parse error with output details."""
    error_msg = "Failed to parse system information from subprocess output."
    if output_str:
        error_msg += f"\nOutput received: {output_str[:200]}..."
    print(error_msg)


def open_matrix_toml() -> None:
    """Open a file browser with the matrix toml selected."""
    toml_home = Path.home() / ".matr1x.toml"
    if not toml_home.exists():
        QMessageBox.warning(
            None,
            "Toml file does not exist!",
            f"Please create a '.matr1x.toml' file at {Path.home()}.",
        )
        return
    if os.name == "nt":
        subprocess.run(["explorer", f"/select,{toml_home.resolve(strict=False)}"])
    elif sys.platform == "darwin":
        subprocess.run(["open", "-R", toml_home])
    else:
        subprocess.run(["xdg-open", toml_home])


class FileDropMixin:
    """Enable drag and drop of a file for QWidgets."""

    file_dropped = Signal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.valid_extensions: list = []

    def setValidExtensions(self, valid_extensions: list[str | re.Pattern]) -> None:
        """
        Set the valid extensions.

        Parameters
        ----------
        valid_extensions: list[str | re.Pattern]
            A list where each element is either a string or a compiled!
            RegEx pattern.
        """
        self.valid_extensions = valid_extensions

    def dragEnterEvent(self, a0: QDragEnterEvent) -> None:
        """Enable drag and drop (1)."""
        if a0.mimeData().hasUrls():
            a0.acceptProposedAction()
        else:
            a0.ignore()

    def dropEvent(self, a0: QDropEvent) -> None:
        """Enable drag and drop (2)."""
        urls = a0.mimeData().urls()
        if len(urls) != 1:
            QMessageBox.warning(None, "Too many Files", "Please only drop a single file.")
            return
        suffix = Path(urls[0].toLocalFile()).suffix
        for extension in self.valid_extensions:
            if (isinstance(extension, re.Pattern) and extension.match(suffix)) or (
                isinstance(extension, str) and suffix == extension
            ):
                self.file_dropped.emit(urls[0].toLocalFile())  # type: ignore
                a0.acceptProposedAction()
                return
        QMessageBox.warning(
            None,
            "Invalid File",
            "Unsupported file dropped.",
        )


def find_parent_of_type(widget: QWidget, cls: type[QWidget]) -> QWidget | None:
    """
    Return first ancestor of `widget` that is an instance of `cls`.

    Parameters
    ----------
    widget: QWidget
        The widget to start the search from.
    cls: type[QWidget]
        The class to search for.

    Returns
    -------
    QWidget or None
        The first ancestor of 'widget' that is an instance of 'cls'.
    """
    w = widget
    while w is not None:
        if isinstance(w, cls):
            return w
        w = w.parentWidget()
    return None


def protected_restore(restore_settings: Callable[[], None]):
    """
    Allow settings-reload to savely fail.

    Parameters
    ----------
    restore_settings: Callable() -> None
        The method used for the restore.
    """
    try:
        restore_settings()
    except Exception as e:
        print(
            f"\n{e}\nRestoring the settings resulted in an unexpected issue. "
            f"This caused all settings to be reset."
        )


class SaferQSettings(QSettings):
    """Require default value and type hint for settings restore."""

    def __init__(self, organization: str, application: str) -> None:
        super().__init__(organization, application)

    @overload
    def safer_value(self, key: str, defaultValue: QPoint, type: type[QPoint]) -> QPoint: ...
    @overload
    def safer_value(self, key: str, defaultValue: QSize, type: type[QSize]) -> QSize: ...
    @overload
    def safer_value(
        self, key: str, defaultValue: QByteArray, type: type[QByteArray]
    ) -> QByteArray: ...
    @overload
    def safer_value(self, key: str, defaultValue: bool, type: type[bool]) -> bool: ...
    @overload
    def safer_value(self, key: str, defaultValue: int, type: type[int]) -> int: ...
    @overload
    def safer_value(self, key: str, defaultValue: list, type: type[list]) -> list: ...
    @overload
    def safer_value(self, key: str, defaultValue: float, type: type[float]) -> float: ...
    @overload
    def safer_value(self, key: str, defaultValue: str, *, type: type[str]) -> str: ...

    def safer_value(self, key, defaultValue, type):  # noqa: A002
        """Call the original QSaver value method."""
        return super().value(key, defaultValue, type)


class _LogSignalHelper(QObject):
    """Provide signals for QTableLogger without conflicts."""

    log_record_received = Signal(list)


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
        row_position = self.widget.rowCount()
        self.widget.insertRow(row_position)
        for column, part in enumerate(parts):
            item = QTableWidgetItem(str(part))
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

    LOG_FIELDS = ["asctime", "name", "levelname", "message"]
    LOG_SEPARATOR = "\x1f"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log Messages")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        self.log_table = QTableWidget()
        self.log_table.setColumnCount(len(LoggingWindow.LOG_FIELDS))
        self.log_table.setHorizontalHeaderLabels(
            [field.title() for field in LoggingWindow.LOG_FIELDS]
        )
        self.log_table.setAlternatingRowColors(True)
        self.log_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
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

    def _on_level_changed(self):
        """Handle logging level change from combobox."""
        selected_level = self.level_combo.currentData()
        root_logger = logging.getLogger()
        root_logger.setLevel(selected_level)

    def _clear(self):
        """Clear the table."""
        self.log_table.clearContents()
        self.log_table.setRowCount(0)
