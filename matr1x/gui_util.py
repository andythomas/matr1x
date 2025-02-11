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
#
# CustomDateAxis class in this file adapted from
# https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/graphicsItems/AxisItem.html#AxisItem.tickValues
# licensed under MIT-license
"""
Contains GUI related functions and class definitions.

These are used by sweep-generator, matrix-gui, matrix-preview, matrix-script and
control-guis.
"""

import datetime
import os
import sys
import time
from importlib.metadata import version as package_version
from os.path import dirname, expanduser, join, normpath
from types import TracebackType
from typing import Any, Dict, Optional, Sequence, TextIO, Type

import numpy as np
import pygit2
import pyqtgraph
from PyQt6.QtCore import (
    QAbstractItemModel,
    QEvent,
    QLibraryInfo,
    QLocale,
    QModelIndex,
    QObject,
    QPoint,
    Qt,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QColor,
    QDoubleValidator,
    QDropEvent,
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
from PyQt6.QtWidgets import (
    QAbstractItemView,
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
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    QTextEdit,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from . import (
    datetimefmt,
    get_config_dict,
    load_config,
    logfolder,
    merge_dicts,
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


class QRangeWidget(QGroupBox):
    """
    Widget that displays a range slider with decrement/increment sliders.

    This widget consists of a range slider with a decrement/increment slider
    on either side and a label on the left.
    """

    value_changed = pyqtSignal(int)

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
        self.label.setText(
            f"{self.base_title} - {self.value()} ({self.maximum()+1})")

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

    This widget consists of a QLineEdit and a FileDialog. Upon return the
    selected filename is passed to the callback function provided as argument
    """

    def __init__(self, callback, parent=None, spec="file"):
        super().__init__(parent)

        self.callback = callback
        self.spec = spec
        # Create the QLineEdit and QPushBottn
        self.dialog_button = QToolButton(self)
        self.dialog_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        )
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
        dialog = QFileDialog(self.parent())
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
        orderChanged (pyqtSignal): Signal emitted when the order of items changes.
    """

    orderChanged = pyqtSignal()  # Custom signal for order changes

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
        """Add item but avoid duplicates.

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

    Extensive meta data are only include in datafiles of version 7 or higher.
    """

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
                if not cast_spec:
                    # unbounded
                    editor.setRange(-int(1e9), int(1e9))
                elif len(cast_spec) == 1:
                    # lower bound
                    editor.setRange(cast_spec[0], int(1e9))
                elif len(cast_spec) == 2:
                    # lower and upper bound
                    editor.setRange(cast_spec[0], cast_spec[1])
                elif len(cast_spec) == 3:
                    # lower and upper bound and step
                    editor.setRange(cast_spec[0], cast_spec[1])
                    editor.setSingleStep(cast_spec[2])
                else:
                    # unbounded and something is wrong with config
                    # raise error?
                    editor.setRange(-int(1e9), int(1e9))
                editor.setStyleSheet("QSpinBox { border: none; padding: 0px; }")
            elif cast_type[0] is float:
                editor = QDoubleSpinBox(parent)
                if cast_type[1]:
                    editor.setDecimals(cast_type[1])
                if not cast_spec:
                    # unbounded
                    editor.setRange(-1e9, 1e9)
                elif len(cast_spec) == 1:
                    # lower bound
                    editor.setRange(cast_spec[0], 1e9)
                elif len(cast_spec) == 2:
                    # lower and upper bound
                    editor.setRange(cast_spec[0], cast_spec[1])
                elif len(cast_spec) == 3:
                    # lower and upper bound and step
                    editor.setRange(cast_spec[0], cast_spec[1])
                    editor.setSingleStep(cast_spec[2])
                else:
                    # unbounded and something is wrong with config
                    # raise error?
                    editor.setRange(-1e9, 1e9)
                editor.setStyleSheet("QDoubleSpinBox { border: none; padding: 0px; }")
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
                cast_type = (globals()["__builtins__"][cast_split[0]], None)
            except AttributeError:
                raise AttributeError("Wrong type specified in config")
            if len(cast_split) == 1:
                # only type is specified
                return (cast_type, None)
            if cast_type[0] is float:
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
            if cast_type[0] is str and (
                cast_split[1] == "folder" or cast_split[1] == "file"
            ):
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
                        MetaViewerWidget.TreeItem(
                            child_key, child_value, cast_type, self
                        )
                    )
            elif isinstance(self.value, (tuple, list, np.ndarray)):
                # for lists with finite length also use nest view
                # key is list index
                cast_type = "str"
                if isinstance(self._type, dict):
                    if self._type[child_key]:
                        cast_type = self._type[child_key]
                else:
                    if self._type:
                        cast_type = self._type
                if len(self.value) > 1:
                    for i, child_value in enumerate(self.value):
                        self.child_items.append(
                            MetaViewerWidget.TreeItem(
                                f"{i}", child_value, cast_type, parent=self
                            )
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
                    return str("")
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

    def __init__(
        self, metadata, heading="Metadata Viewer", editable=False, parent=None
    ):
        super().__init__(heading, parent)

        self.editable = editable

        self.tree_view = QTreeView()

        self.model = self.TreeModel(self.parse_header(metadata))
        self.tree_view.setModel(self.model)
        for i in range(2):
            self.tree_view.resizeColumnToContents(i)
        self.tree_view.expandAll()

        # make widget expanding
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tree_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.tree_view.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
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
        super().__init__({}, heading="Preferences", editable=True)

        widget = QWidget()
        # Create a QVBoxLayout instance
        layout = QVBoxLayout()

        # Dublin Core Elements
        self.w_write_config = QPushButton("Write config")
        self.w_write_config.setEnabled(False)
        self.w_write_config.clicked.connect(self.write_config)

        # Add the form layout to the main layout
        layout.addWidget(self.w_write_config)
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

    def update_data(self, systemfile):
        """
        Update data stored in the model with system configuration.

        Parameters
        ----------
        systemfile : list
            List of system names to update.
        """
        syst_dict = {}
        for syst in systemfile:
            syst_dict[syst.strip()] = get_config_dict(syst.strip())

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
        self.w_write_config.setEnabled(True)

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
                config[child_item.data(0)] = self.parse_item(child_item)
        else:
            if item.type(1)[0][0] is bool:
                return item.data(1).lower() == "true"
            return item.type(1)[0][0](item.data(1))
        return config

    def write_config(self):
        """Write the current configuration to file."""

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
                    value = normpath(expanduser(value))

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

        config = {}
        for item in self.tree_view.model().root_item.child_items:
            if item.child_count() == 0:
                # system has no configurable options
                continue
            sys_key = item.data(0)
            key_parts = sys_key.split(".")
            merge_dicts(config, create_nested_dict(key_parts, item))
        # load full config and replace modified entries
        full_config = normalize_dict(load_config())
        full_config = merge_dicts(full_config, normalize_dict(config))
        write_config(full_config)


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

    class PlotObject():
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
        exposed_functions = {"np": np, "sqrt": np.sqrt, "e": np.e,
                             "pi": np.pi, "power": np.power, "log10": np.log10,
                             "cos": np.cos, "sin": np.sin, "tan": np.tan,
                             "arccos": np.arccos, "arcsin": np.arcsin,
                             "arctan": np.arctan, "log": np.log, "exp": np.exp,
                             }

        # default math operations can be added here if required
        # the key should correspond to the value of math_mode for this to
        # be selected, has to provide a pair of fucntions for the x and y
        # value, respectively
        default_math = {
            "no math": [lambda xf: xf, lambda yf: yf],
            "delta-": [lambda xf: delta(xf)[0],
                       lambda yf: delta(yf)[1]],
            "delta+": [lambda xf: delta(xf)[0],
                       lambda yf: delta(yf)[0]]}

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
                        datetime.datetime.fromtimestamp(value).strftime(fmt)
                        for value in values
                    ]
                return [
                    datetime.datetime.fromtimestamp(value).strftime(fmt).rstrip("0")
                    for value in values
                ]

        class CategoricalAxis(pyqtgraph.AxisItem):
            """Custom axis item for displaying categorical data.

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
                super().__init__(orientation=orientation, *args, **kwargs)
                self.mapping = mapping or {}
                self.unique_ticks = set()

            def tickStrings(self, values, scale, spacing):
                """Return the strings that should be placed next to ticks.

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
                """Return the values and spacing of ticks to draw.

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

        def __init__(self, l_plot, error, l_slider, plot2d, index, desig, pen=None):
            self.index = index
            self.desig = desig
            self.l_plot = l_plot
            self.l_slider = l_slider
            self.plot2d = plot2d
            self.error = error

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
                self.pw = self.l_plot.addPlot(row=self.index, col=0,
                                              viewBox=self.vb,
                                              title=f"p{index}")
            else:
                self.pw = self.l_plot.addPlot(row=self.index, col=0,
                                              viewBox=self.vb,
                                              title=f"p{index}")
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

            self.ordinary_axis = {"bottom": self.pw.getAxis("bottom"),
                                  "left": self.pw.getAxis("left")}

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
                    [
                        list(mapping.keys())[list(mapping.values()).index(str(x))]
                        for x in data
                    ]
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
                        return eval(self.math_texts[1],
                                    ({"x": xf, "y": yf} |
                                     self.exposed_functions))
                    xc = fx(x, y)
                except Exception as e:
                    self._raise_error(
                        "error in math function (x): " + str(e))

                try:
                    # define function based on the string stored in
                    # math_texts[0]
                    def fy(yf, xf):
                        return eval(self.math_texts[0],
                                    ({"y": yf, "x": xf} |
                                     self.exposed_functions))
                    yc = fy(y, x)
                except Exception as e:
                    self._raise_error(
                        "error in math function (y): " + str(e))

                if yc is not None and xc is not None:
                    if len(yc) != len(xc):
                        self._raise_error(
                            "error in math: arrays have different length")
                    elif len(yc.shape) > 1 and all(np.array(yc.shape) > 1):
                        self._raise_error(
                            "error in math: y array has too high dimension")
                    elif len(xc.shape) > 1 and all(np.array(xc.shape) > 1):
                        self._raise_error(
                            "error in math: y array has too high dimension")
                    else:
                        y, x = yc, xc
            return y, x

        def _handle_multidim_and_sliders(self):
            """Handle slider visibility according to data dimensions."""
            self.md = False
            for slider, dshape in zip([self.w_zslider, self.w_xslider],
                                      [self.zdata.shape, self.xdata.shape]):
                slider.setVisible(False)
                if len(dshape) > 2:
                    # data is 3D, so show sliders
                    self.md = True
                    slider.setVisible(True)
                    slider.set_range(0, dshape[0]-1)
                elif ((len(dshape) > 1 and dshape[1] > 1) and
                      self.plot2d is False):
                    # array is 2d and second dimension is longer than 1
                    self.md = True
                    slider.setVisible(True)
                    slider.set_range(0, dshape[1]-1)
                elif ((len(dshape) > 1 and dshape[1] == 1) and
                      self.plot2d is False):
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

            This method adjusts the data dimensions and selects appropriate data
            based on the current slider positions for multi-dimensional data sets.
            It updates the x, y, and z data attributes of the object accordingly.
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
                self.plt.setCurrentIndex(val)
                self.pw.setTitle(f"p{self.index} at {self.labels[1]} "
                                 f"= {self.x[val]} {self.units[1]}")
            else:
                # for curve, handle the data and replot
                self._handle_multidim_data()
                self.plot(symbol="o")

        def remove_plot(self):
            """
            Remove the plot and the widgets that belong to the PlotObject.

            This method removes the plot from the provided layouts, including
            the horizontal line, x-slider, and z-slider widgets associated
            with this PlotObject.
            """
            self.l_plot.removeItem(self.l_plot.getItem(row=self.index, col=0))
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
                Variable length argument list passed to the plot function if curve plotting is enabled.
            **kwargs
                Arbitrary keyword arguments passed to the plot function if curve plotting is enabled.
            """
            if self.plot2d is True:
                if len(self.zdata.shape) > 2:
                    # 3d plotting
                    self.plt.setImage(self.z, pos=[0, 0], scale=[1, 1],
                                      xvals=self.x,
                                      axes={"t": 0, "x": 1, "y": 2})
                    # make sure top and right axis are hidden
                    for i, ax in zip(range(2), ["right", "top"]):
                        self.pw.hideAxis(ax)
                    # set labels to array index, same as on the y-axis
                    self.pw.setLabel("bottom", self.labels[2], self.units[2])
                    self.vb.setAspectLocked(False)
                    self.vb.invertY(False)
                else:
                    # 2d data follows different dimensioning scheme
                    x0, x1 = self.x[0], self.x[-1]
                    xscale = (x1-x0)/self.z.shape[0]
                    y0, y1 = self.y[0], self.y[-1]
                    yscale = (y1-y0)/self.z.shape[1]
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

                try:
                    self.plt.setData(x=x, y=z, *args, **kwargs)
                except ValueError as e:
                    # Handle shape mismatch errors
                    self._raise_error(f"Plot error: {str(e)}")


    def __init__(self, cb_error, cb_index, parent=None):
        super().__init__("", parent)

        self.cb_error = cb_error
        self.cb_index = cb_index
        self.plot2d = False

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
        self.w_calc.addItems(list(self.PlotObject.default_math.keys()) +
                             ["custom"])
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
                "operation and have to remain in a single dimension.")

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
        self.gl.setSizePolicy(QSizePolicy.Policy.Expanding,
                              QSizePolicy.Policy.Expanding)

        # have proxy that connects the position of the mouse on the
        # GraphicsLayout to display the x/y position on the current
        # plot, additionally introduce proxy to select active plot by
        # just clicking into the plot
        self.proxy = pyqtgraph.SignalProxy(
            self.gl.scene().sigMouseMoved, rateLimit=30, slot=self._mouse_moved
        )
        self.proxy2 = pyqtgraph.SignalProxy(
            self.gl.scene().sigMouseClicked, rateLimit=2, slot=self._mouse_clicked
        )

        # add the first empty plot with
        self.plots = [self.PlotObject(self.gl, self.cb_error, self.l_slider,
                                      False, 0, [0, 0, 0]), ]

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
        self.plots.append(self.PlotObject(self.gl, self.cb_error, self.l_slider,
                                          False, index, [0, 0, 0],
                                          pen=self.w_line.isChecked()))
        self.w_plots.setItemText(len(self.plots)-1, f"p{index} -  vs ")
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
            self.w_plots.setCurrentIndex(index-1)
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
        if index == cnt-1 and cnt > 1:
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
            self.plots[current_plot].x_is_categorical
            or self.plots[current_plot].z_is_categorical
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
                name = (f"p{plot.index} - {plot.labels[0]} vs {plot.labels[1]} "
                        f"and {plot.labels[2]}")
            else:
                name = (
                    f"p{plot.index} - {plot.labels[0]} vs {plot.labels[1]}")
            self.w_plots.setItemText(i, name)
        # reset error
        self.cb_error("")

        self.plots[current_plot].set_math_mode(
            math_mode, [math.text() for math in self.w_math])
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
            if vb.boundingRect().contains(ev[0]+pos):
                vb_mouse = vb
                # stop once we have found the correct viewbox
                continue
        if vb_mouse is not None:
            mousePoint = vb_mouse.mapSceneToView(ev[0])
            self.w_pos.setText(
                "x: {:.5e}\ny: {:.5e}".format(mousePoint.x(),
                                              mousePoint.y()))

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
                    plot.plt.setPen((0, 0, 153), width=3)
        if state is False:
            for plot in self.plots:
                if plot.plot2d is False:
                    plot.plt.setPen(None)

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
        self.plots.insert(index, self.PlotObject(self.gl, self.cb_error,
                                                 self.l_slider, new_state,
                                                 plotindex, [0, 0, 0],
                                                 pen=self.w_line.isChecked()))
        # reset global plot2d flag
        if any([plot.plot2d for plot in self.plots]) is True:
            self._toggle_plot2d(True)
        else:
            self._toggle_plot2d(False)

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
        exporter = pyqtgraph.exporters.ImageExporter(self.gl.scene())
        exporter.export(filename)

    def get_columns(self) -> tuple[str, str]:
        """Return the plotted columns."""
        index = self.w_plots.currentIndex()
        y = self.plots[index].labels[0]
        x = self.plots[index].labels[1]
        return (y, x)

    def save_data(self, filename) -> None:
        """Export the currently displayed plot into a text file.

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
        with open(filename, "w") as f:
            f.write(
                f"{self.plots[index].labels[1]}{delimiter}{self.plots[index].labels[0]}{newline}"
            )
            f.write(
                f"{self.plots[index].units[1]}{delimiter}{self.plots[index].units[0]}{newline}"
            )
        with open(filename, "a") as f:
            np.savetxt(f, data, delimiter=delimiter, newline=newline)

    def reset(self):
        """Reset the full SimplePlotWidget to its default state."""
        self.w_plots.blockSignals(True)
        for plot in self.plots:
            plot.remove_plot()
        del self.plots
        self.plots = [self.PlotObject(self.gl, self.cb_error, self.l_slider,
                                      False, 0, [0, 0, 0]), ]
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
    text_written : pyqtSignal
        Signal emitted when text is written to the stream.
    """

    name = "GUIStream"
    text_written = pyqtSignal(str)

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

        This method is required for file-like objects but does nothing in this implementation.
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
        self, stream: Optional[TextIO], prefix: str = "control", fallbackname: str = ""
    ) -> None:
        """
        Initialize an object for output duplication into a file.

        Parameters
        ----------
        stream : Optional[TextIO]
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
        self.log = open(join(logfolder, f"{prefix}-{name}.log"), "a")
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
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
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

    def __init__(self, initial_values: Optional[Dict[str, Any]] = None) -> None:
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

    def load_initial_values(self, values: Dict[str, Any]) -> None:
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

    def get_metadata(self) -> Dict[str, str]:
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


class TextInputDialog(QDialog):
    """Modal dialog for text input for matrix-script."""

    def __init__(self, query: str, parent=None):
        """
        Initialize the text input dialog with a its GUI elements.

        Parameters
        ----------
        query : str
            The text to display on the label above the input field.
        parent : QWidget, optional
            The parent widget of the dialog.
        """
        super().__init__(parent)
        self.setWindowTitle("Matrix-script input")

        self.label = QLabel(query, self)
        self.input = QLineEdit(self)
        self.input.setPlaceholderText("input to send to script")

        self.ok_button = QPushButton("Send input", self)
        self.abort_button = QPushButton("Abort script", self)

        self.ok_button.clicked.connect(self.accept)
        self.abort_button.clicked.connect(self.reject)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.abort_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.label)
        main_layout.addWidget(self.input)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

        # Ensure the dialog stays on top of the main window
        self.setWindowModality(Qt.WindowModality.ApplicationModal)


class YesNoAbortDialog(QMessageBox):
    """Modal dialog for boolean input for matrix-script."""

    def __init__(self, question: str, parent=None):
        """
        Initialize the yes/no dialog with a question and buttons.

        Parameters
        ----------
        question : str
            The question to display on the label.
        parent : QWidget, optional
            The parent widget of the dialog.
        """
        super().__init__(parent)
        self.setWindowTitle("Question")
        self.setText(question)
        self.setIcon(QMessageBox.Icon.Question)

        # Add custom buttons
        self.yes_button = self.addButton("Yes", QMessageBox.ButtonRole.AcceptRole)
        self.no_button = self.addButton("No", QMessageBox.ButtonRole.RejectRole)
        self.abort_button = self.addButton("Abort script", QMessageBox.ButtonRole.DestructiveRole)

    def exec_and_get_response(self):
        """
        Show the dialog and return the button clicked by the user.

        Returns
        -------
        str
            The response based on the button clicked ("Yes", "No", or "Abort").
        """
        self.exec()

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
        self.finish_button = self.addButton(
            "Finished", QMessageBox.ButtonRole.AcceptRole
        )

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
        """Initialize an about box dialog with installation information.

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
        icon_size = QApplication.style().pixelMetric(
            QStyle.PixelMetric.PM_MessageBoxIconSize
        )
        pixmap = icon.pixmap(icon_size)
        self.setIconPixmap(pixmap)
        self.setWindowTitle(title)
        self.setText(title)
        (version, branch, sha, time) = self.get_install_info(package)
        if time != "not available":
            date = datetime.datetime.fromtimestamp(time).strftime(date_format)
        else:
            date = time
        text = f"""
                <div style="text-align: left;">
                    <p><b>Version:</b> {version}<br>
                    <b>Git branch:</b> {branch}<br>
                    <b>Git commit:</b> {sha}<br>
                    <b>Git date:</b> {date}<br>
                    <br>
                    (C) 2006-2025 Matr1x Developers. All rights reserved.
                </div>
                """
        self.setInformativeText(text)
        self.setStandardButtons(QMessageBox.StandardButton.Ok)

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
            commit_time = last_commit.commit_time
        except pygit2.GitError:
            pass
        installed_version = package_version(imported_package.__name__)
        return (installed_version, commit_branch, commit_short_sha, commit_time)


class MIcon(QIcon):
    """Generate either Qt built-in icons, letters or Matrix specific QIcons."""

    def __new__(cls, name, color="default") -> QIcon:
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

        Returns
        -------
        QIcon
        """
        # Get the included Qt icon
        if name.startswith("SP_"):
            icon = QApplication.style().standardIcon(
                getattr(QStyle.StandardPixmap, name)
            )
            return icon
        # Use the original matrix icons
        elif name.startswith("matr1x-"):
            icondir = join(dirname(__file__), "scripts", "icons")
            pixmap = QPixmap(join(icondir, name))
            # Change the color of the white icon if requested
            # and remove the rest for better visibility in a GUI
            if color != "default":
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
        if color == "default":
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
            painter.setPen(QColor("white"))
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, letter)
        elif name.startswith("CUSTOM_"):
            custom_name = name[7:]
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor("white"))
            painter.setPen(QColor("white"))
            if custom_name == "Play":
                triangle = QPolygon(
                    [
                        QPoint(int(size // 15 + size * 0.3), int(size * 0.2)),
                        QPoint(int(size // 15 + size * 0.3), int(size * 0.8)),
                        QPoint(int(size // 15 + size * 0.7), int(size * 0.5)),
                    ]
                )
                painter.drawPolygon(triangle)
            elif custom_name == "Stop":
                painter.drawRect(
                    int(size * 0.3), int(size * 0.3), int(size * 0.4), int(size * 0.4)
                )
            elif custom_name == "Pause":
                bar_width = size * 0.15
                bar_height = size * 0.4
                spacing = size * 0.1
                x_offset = (size - 2 * bar_width - spacing) / 2
                y_offset = (size - bar_height) / 2
                painter.drawRect(
                    int(x_offset), int(y_offset), int(bar_width), int(bar_height)
                )
                painter.drawRect(
                    int(x_offset + bar_width + spacing),
                    int(y_offset),
                    int(bar_width),
                    int(bar_height),
                )
            else:
                raise ValueError(f"MIcon: Unknown icon type {name}.")
        else:
            raise ValueError(f"MIcon: Unknown icon type {name}.")
        painter.end()
        return QIcon(pixmap)


def _set_palette(instance):
    """Set the base and text color according to the enabled state."""
    palette = instance.palette()
    # use QTextEdit as an example to determine the palette
    text_edit = QTextEdit()
    unchanged_palette = text_edit.palette()
    text_edit.setEnabled(False)
    changed_palette = text_edit.palette()
    if instance.isEnabled():
        palette.setColor(
            QPalette.ColorRole.Text,
            QColor(unchanged_palette.color(QPalette.ColorRole.Text)),
        )
    else:
        palette.setColor(
            QPalette.ColorRole.Text,
            QColor(changed_palette.color(QPalette.ColorRole.Text)),
        )
    if not instance.isEnabled() or instance.isReadOnly():
        palette.setColor(
            QPalette.ColorRole.Base,
            QColor(changed_palette.color(QPalette.ColorRole.Base)),
        )
    else:
        palette.setColor(
            QPalette.ColorRole.Base,
            QColor(unchanged_palette.color(QPalette.ColorRole.Base)),
        )

    instance.setPalette(palette)

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
        keys = QKeySequence(shortcut)[0]
    elif isinstance(shortcut, QKeySequence):
        keys = shortcut[0]
    else:
        raise ValueError("Shortcut has to be of type(str) or type(QKeySequence).")
    if key == keys.key() and modifiers == keys.keyboardModifiers():
        return True
    else:
        return False

class MLineEdit(QLineEdit):
    """Provide QLineEdit with visual cues for non-editable."""

    def __init__(self):
        """Call init of QLineEdit()."""
        super().__init__()

    def changeEvent(self, event: QEvent):
        """
        Detect palette and read-only changes.

        This method implements visual cues that work when the palette changes,
        for example if the desktop changes from dark to bright mode.

        Parameters
        ----------
        event : QEvent
            The event that triggered the change.
        """
        if (
            event.type() == QEvent.Type.PaletteChange
            or event.type() == QEvent.Type.ReadOnlyChange
        ):
            _set_palette(self)
            super().changeEvent(event)


class MTextEdit(QTextEdit):
    """Provide QRTextEdit with visual cues for non-editable."""

    def __init__(self):
        """Call init of QTextEdit()."""
        super().__init__()

    def changeEvent(self, event: QEvent):
        """Detect palette and read-only changes.

        Implement visual cues that work also when the palette changes, for example if the desktop changes
        from dark to bright mode.
        """
        if (
            event.type() == QEvent.Type.PaletteChange
            or event.type() == QEvent.Type.ReadOnlyChange
        ):
            _set_palette(self)
            super().changeEvent(event)


class MApplication(QApplication):
    """Fix GUI related issues for all applications."""

    def _list_platform_plugins(self) -> Sequence[str]:
        """
        List available platforms by inspecting the platforms directory.

        Returns
        -------
        list of str
            A list consisting of all possible platforms
        """
        plugin_path = QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath)
        platforms_path = os.path.join(plugin_path, "platforms")

        if os.path.exists(platforms_path):
            plugins = [
                f
                for f in os.listdir(platforms_path)
                if os.path.isfile(os.path.join(platforms_path, f))
            ]
            platforms = [
                os.path.splitext(plugin)[0].replace("libq", "") for plugin in plugins
            ]
            return platforms
        else:
            return []

    def _repair_palette(self) -> None:
        """
        Repair the palette if disabled and enabled state are indistinguishable.

        This fixes a bug prevalent in, e.g., Linux machines using Qt6.5 under some circumstances.
        """
        palette = QPalette()
        if self._palette_bug:
            if palette.color(QPalette.ColorRole.Text).value() < 128:  # bright mode
                white = QColor("#FFFFFF")
                off_white = QColor("#F5F5F5")
                grayish = QColor("#ECECEC")
                palette.setColor(
                    QPalette.ColorGroup.Active, QPalette.ColorRole.Window, grayish
                )
                palette.setColor(
                    QPalette.ColorGroup.Inactive, QPalette.ColorRole.Window, grayish
                )
                palette.setColor(
                    QPalette.ColorGroup.Disabled, QPalette.ColorRole.Window, grayish
                )
                palette.setColor(
                    QPalette.ColorGroup.Active, QPalette.ColorRole.Base, white
                )
                palette.setColor(
                    QPalette.ColorGroup.Inactive, QPalette.ColorRole.Base, white
                )
                palette.setColor(
                    QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, grayish
                )
                palette.setColor(
                    QPalette.ColorGroup.Active,
                    QPalette.ColorRole.AlternateBase,
                    off_white,
                )
                palette.setColor(
                    QPalette.ColorGroup.Inactive,
                    QPalette.ColorRole.AlternateBase,
                    off_white,
                )
                palette.setColor(
                    QPalette.ColorGroup.Disabled,
                    QPalette.ColorRole.AlternateBase,
                    off_white,
                )
            else:  # dark mode
                black = QColor("#171717")
                dark = QColor("#323232")
                gray = QColor("#989898")
                palette.setColor(
                    QPalette.ColorGroup.Active, QPalette.ColorRole.Window, dark
                )
                palette.setColor(
                    QPalette.ColorGroup.Inactive, QPalette.ColorRole.Window, dark
                )
                palette.setColor(
                    QPalette.ColorGroup.Disabled, QPalette.ColorRole.Window, dark
                )
                palette.setColor(
                    QPalette.ColorGroup.Active, QPalette.ColorRole.Base, black
                )
                palette.setColor(
                    QPalette.ColorGroup.Inactive, QPalette.ColorRole.Base, black
                )
                palette.setColor(
                    QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base, dark
                )
                palette.setColor(
                    QPalette.ColorGroup.Active, QPalette.ColorRole.AlternateBase, gray
                )
                palette.setColor(
                    QPalette.ColorGroup.Inactive, QPalette.ColorRole.AlternateBase, gray
                )
                palette.setColor(
                    QPalette.ColorGroup.Disabled, QPalette.ColorRole.AlternateBase, gray
                )
            self.setPalette(palette)

    def __init__(self, args: Sequence[str]) -> None:
        """
        Call init of QApplication, automatically select the xcb client and fix palette if need be.

        (1) If, for example, wayland is used as the default window manager, the lack of client side decorations
        would lead to missing visual cues such as window shadows. To regain the visual aids, the client-side is
        switched to xcb. (2) Linux machines using Qt6.5 experience a broken palette under some circumstances. This
        bug is detected and fixed here.

        args : list of str
            Arguments for QApplication
        """
        if sys.platform == "linux":
            if "xcb" in self._list_platform_plugins():
                os.environ["QT_QPA_PLATFORM"] = "xcb"
        active_base = QPalette().color(
            QPalette.ColorGroup.Active, QPalette.ColorRole.Base
        )
        disabled_base = QPalette().color(
            QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base
        )
        if active_base == disabled_base:
            self._palette_bug = True
        else:
            self._palette_bug = False
        super().__init__(args)
        MApplication.instance().paletteChanged.connect(self._repair_palette)
        self._repair_palette()

    def toolbar_icon_size(self) -> int:
        """
        Return the toolbar icon size for all GUIs.

        Returns
        -------
        int
            size of the icon
        """
        small = MApplication.style().pixelMetric(QStyle.PixelMetric.PM_SmallIconSize)
        standard = MApplication.style().pixelMetric(
            QStyle.PixelMetric.PM_ToolBarIconSize
        )
        intermediate = int((small + standard) / 2)
        return intermediate
