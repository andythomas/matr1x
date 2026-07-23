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
# CustomDateAxis class in this file adapted from
# https://pyqtgraph.readthedocs.io/en/latest/_modules/pyqtgraph/graphicsItems/AxisItem.html#AxisItem.tickValues
# licensed under MIT-license
"""
Contains GUI related functions and class definitions.

These are used by sweep-generator, matrix-gui, matrix-preview, matrix-
script and control-guis.
"""

from __future__ import annotations

import contextlib
import datetime
import inspect
import logging
import os
import platform
import re
import signal
import subprocess
import sys
import tempfile
import threading
import types
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    ParamSpec,
    Protocol,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

if sys.version_info >= (3, 12):
    from typing import TypeAliasType
else:
    TypeAliasType = None

from importlib.metadata import PackageNotFoundError, version

import numpy as np
import pygit2
import pyqtgraph
import PySide6
import shiboken6
from pydantic import BaseModel, ValidationError
from pyqtgraph.exporters import ImageExporter
from PySide6.QtCore import (
    QAbstractItemModel,
    QByteArray,
    QEvent,
    QLibraryInfo,
    QLocale,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    QPoint,
    Qt,
    QTimer,
    Signal,
    Slot,
    qVersion,
)
from PySide6.QtGui import (
    QAction,
    QBrush,
    QCloseEvent,
    QColor,
    QDoubleValidator,
    QDragEnterEvent,
    QDropEvent,
    QFileOpenEvent,
    QFontDatabase,
    QHideEvent,
    QIcon,
    QImage,
    QIntValidator,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPalette,
    QPixmap,
    QPolygon,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

import matr1x
from matr1x.error_handling import Error, InternalInvariantError, Result, Success
from matr1x.models import MainConfig, SystemInfo, validate_visa_resource

from . import merge_dicts, reload_config, write_config
from .eval import delta
from .util import resolve_config_path

if TYPE_CHECKING:
    from matr1x.scripts.shared_classes import SaferQSettings


P = ParamSpec("P")
R = TypeVar("R")


logger = logging.getLogger(__name__)

# dictionary of commonly used validators
validator: dict[type, QDoubleValidator | QIntValidator] = {
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
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
            dialog.setOption(QFileDialog.Option.DontConfirmOverwrite)
        else:
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
            dialog.setFileMode(QFileDialog.FileMode.Directory)
            dialog.setOption(QFileDialog.Option.ShowDirsOnly)

        if dialog.exec():
            # pass value to callback
            if len(dialog.selectedFiles()) > 0:
                self.callback(dialog.selectedFiles()[0])


class MetaViewerWidget(QDockWidget):
    """
    Viewer and editor for meta data stored in matrix data files.

    Extensive meta data are only include in datafiles of version 7 or
    higher.
    """

    _visa_resource_cache: list[str] | None = None
    _visa_resource_query_running = False

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

        def __init__(self, editable: bool = False, parent: QObject | None = None):
            super().__init__(parent=parent)
            self.editable: bool = editable

        def createEditor(
            self,
            parent: QWidget,
            option: QStyleOptionViewItem,
            index: QModelIndex | QPersistentModelIndex,
        ) -> QWidget:
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
            """
            if isinstance(index, QPersistentModelIndex):
                raise TypeError("Index is a QPersistentModelIndex, but must be a QModelIndex.")
            model = cast(MetaViewerWidget.TreeModel, index.model())
            schema = model.type(index)
            item = index.internalPointer()
            item.setData(index, "", Qt.ItemDataRole.DisplayRole)

            json_type = cast(str, schema.get("type"))
            ui_type = cast(str | None, schema.get("ui_type"))
            decimals = cast(int | None, schema.get("decimals"))

            if "enum" in schema:
                # strict, use combobox
                editor = QComboBox(parent)
                editor.insertItems(0, [str(i) for i in schema["enum"]])
                editor.setStyleSheet("QComboBox { border: none; padding: 0px; }")
            elif json_type == "string" and ui_type == "visa_resource":
                editor = QComboBox(parent)
                editor.setEditable(True)
                editor.insertItems(0, MetaViewerWidget.visa_resource_names())
                editor.setStyleSheet("QComboBox { border: none; padding: 0px; }")
                editor.editTextChanged.connect(
                    lambda value, tree_model=model, model_index=index: (
                        MetaViewerWidget._update_visa_editor_validation(
                            cast(QComboBox, editor),
                            value,
                            tree_model,
                            model_index,
                            refresh_view=False,
                        )
                    )
                )
            elif json_type == "boolean":
                editor = QCheckBox(parent)
                editor.setStyleSheet("QCheckBox { border: none; padding: 0px; }")
            elif json_type == "integer":
                editor = QSpinBox(parent)
                editor.setRange(schema.get("minimum", MIN_INT64), schema.get("maximum", MAX_INT64))
                if "multipleOf" in schema:
                    editor.setSingleStep(schema["multipleOf"])
                editor.setStyleSheet("QSpinBox { border: none; padding: 0px; }")
                editor.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            elif json_type == "number":
                if ui_type == "scifloat":
                    editor = QLineEdit(parent)
                    scifloat_validator = cast(QDoubleValidator, validator[float])
                    if decimals:
                        scifloat_validator.setDecimals(decimals)
                    scifloat_validator.setRange(
                        schema.get("minimum", -sys.float_info.max),
                        schema.get("maximum", sys.float_info.max),
                    )
                    editor.setValidator(scifloat_validator)
                else:
                    editor = QDoubleSpinBox(parent)
                    if decimals:
                        editor.setDecimals(decimals)
                    editor.setRange(
                        schema.get("minimum", -sys.float_info.max),
                        schema.get("maximum", sys.float_info.max),
                    )
                    if "multipleOf" in schema:
                        editor.setSingleStep(schema["multipleOf"])
                    editor.setStyleSheet("QDoubleSpinBox { border: none; padding: 0px; }")
                    editor.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
            elif json_type == "string" and ui_type in ("file", "folder"):

                def cb(value):
                    index.model().setData(index, value, Qt.ItemDataRole.EditRole)
                    index.model().dataChanged.emit(index, index)

                editor = FileLineEdit(cb, parent, ui_type)
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

        def setEditorData(
            self, editor: QWidget, index: QModelIndex | QPersistentModelIndex
        ) -> None:
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
                editor.setText(str(value))
                editor.resize(editor.sizeHint())
            elif isinstance(editor, QCheckBox):
                editor.setChecked(bool(value))
            elif isinstance(editor, FileLineEdit):
                editor.setText(str(value))
            elif isinstance(editor, QComboBox):
                editor.setCurrentText(str(value))
            elif isinstance(editor, QSpinBox):
                try:
                    editor.setValue(int(value))
                except (ValueError, TypeError):
                    editor.setValue(0)
            elif isinstance(editor, QDoubleSpinBox):
                try:
                    editor.setValue(float(value))
                except (ValueError, TypeError):
                    editor.setValue(0.0)
            elif isinstance(editor, QLineEdit):
                editor.setText(str(value))

        def setModelData(
            self,
            editor: QWidget,
            model: QAbstractItemModel,
            index: QModelIndex | QPersistentModelIndex,
        ) -> None:
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
                value = editor.isChecked()
            elif isinstance(editor, FileLineEdit):
                value = editor.text()
            elif isinstance(editor, QComboBox):
                value = editor.currentText()
            elif isinstance(editor, (QSpinBox, QDoubleSpinBox)):
                value = editor.value()
            elif isinstance(editor, QLineEdit):
                try:
                    value = float(editor.text())
                except ValueError:
                    value = editor.text()

            schema = cast(MetaViewerWidget.TreeModel, model).type(cast(QModelIndex, index))
            if schema.get("ui_type") == "visa_resource":
                try:
                    value = validate_visa_resource(str(value))
                except ValueError as exc:
                    tree_model = cast(MetaViewerWidget.TreeModel, model)
                    tree_model.setData(index, value, Qt.ItemDataRole.EditRole)
                    tree_model.set_validation_error(index, str(exc))
                    MetaViewerWidget._update_visa_editor_validation(
                        cast(QComboBox, editor), str(value)
                    )
                    return
            tree_model = cast(MetaViewerWidget.TreeModel, model)
            tree_model.setData(index, value, Qt.ItemDataRole.EditRole)
            tree_model.set_validation_error(index, None)

    @staticmethod
    def _update_visa_editor_validation(
        editor: QComboBox,
        value: str,
        model: TreeModel | None = None,
        index: QModelIndex | QPersistentModelIndex | None = None,
        *,
        refresh_view: bool = True,
    ) -> None:
        """Show VISA validation feedback on an editable resource combo box."""
        validation_error = None
        try:
            validate_visa_resource(value)
        except ValueError as exc:
            validation_error = str(exc)
            editor.setStyleSheet(
                "QComboBox { border: 1px solid #b3261e; padding: 0px; background: #ffd9d9; }"
            )
            editor.setToolTip(validation_error)
            if line_edit := editor.lineEdit():
                line_edit.setToolTip(validation_error)
        else:
            editor.setStyleSheet("QComboBox { border: none; padding: 0px; }")
            editor.setToolTip("")
            if line_edit := editor.lineEdit():
                line_edit.setToolTip("")

        if model is not None and index is not None:
            model.set_validation_error(index, validation_error, refresh_view=refresh_view)

    @staticmethod
    def visa_resource_names() -> list[str]:
        """Return cached VISA resource suggestions without starting discovery."""
        return (MetaViewerWidget._visa_resource_cache or []).copy()

    @staticmethod
    def _query_visa_resource_names() -> list[str] | None:
        """Query VISA resource suggestions from PyVISA."""
        try:
            import pyvisa

            return [str(resource) for resource in pyvisa.ResourceManager().list_resources()]
        except Exception as exc:
            logger.info("Could not query PyVISA resources for config editor suggestions: %s", exc)
            logger.debug("PyVISA resource discovery traceback", exc_info=True)
            return None

    @staticmethod
    def prefetch_visa_resource_names(*, force: bool = False) -> None:
        """Start VISA resource discovery in the background if it is not already running."""
        if not force and MetaViewerWidget._visa_resource_cache is not None:
            return
        if MetaViewerWidget._visa_resource_query_running:
            return

        def query_resources() -> None:
            try:
                resources = MetaViewerWidget._query_visa_resource_names()
                if resources is not None:
                    MetaViewerWidget._visa_resource_cache = resources
            finally:
                MetaViewerWidget._visa_resource_query_running = False

        MetaViewerWidget._visa_resource_query_running = True
        threading.Thread(
            target=query_resources,
            name="matr1x-visa-resource-query",
            daemon=True,
        ).start()

    @staticmethod
    def schema_contains_visa_resource(schema: Any) -> bool:
        """Return True when a nested schema tree contains a VISA resource editor hint."""
        if isinstance(schema, dict):
            if schema.get("ui_type") == "visa_resource":
                return True
            return any(
                MetaViewerWidget.schema_contains_visa_resource(value) for value in schema.values()
            )
        if isinstance(schema, list):
            return any(MetaViewerWidget.schema_contains_visa_resource(value) for value in schema)
        return False

    @staticmethod
    def resolve_schema(schema: dict, root_schema: dict | None = None) -> dict:
        """
        Resolve a Pydantic JSON schema to a flat dictionary of properties.

        Handles $ref, anyOf, allOf by merging or picking the first non-null type.
        """
        if not isinstance(schema, dict):
            return {}

        # Handle custom _schema wrapper used in ConfigEditWidget
        if "_schema" in schema:
            return MetaViewerWidget.resolve_schema(schema["_schema"], root_schema)

        # Handle $ref
        if "$ref" in schema and root_schema:
            ref_path = schema["$ref"].split("/")
            # Assuming refs are always like #/$defs/MyModel
            ref_schema = root_schema
            for part in ref_path[1:]:
                ref_schema = ref_schema.get(part, {})
            return MetaViewerWidget.resolve_schema(ref_schema, root_schema)

        # Handle anyOf (often used for Optional[T] -> [T, null])
        if "anyOf" in schema:
            for sub_schema in schema["anyOf"]:
                resolved = MetaViewerWidget.resolve_schema(sub_schema, root_schema)
                if resolved.get("type") != "null":
                    # Merge the anyOf schema with the outer schema (for description, etc.)
                    merged = {**schema, **resolved}
                    merged.pop("anyOf", None)
                    return merged

        # Handle allOf (merging multiple schemas)
        if "allOf" in schema:
            merged = {**schema}
            for sub_schema in schema["allOf"]:
                merged.update(MetaViewerWidget.resolve_schema(sub_schema, root_schema))
            merged.pop("allOf", None)
            return merged

        return schema

    class TreeItem:
        """
        An item in the TreeModel.

        Parameters
        ----------
        key : str
            The key or identifier for this item.
        value : Any
            The value associated with this item.
        types : Any, optional
            The type/schema information for this item.
        parent : TreeItem, optional
            The parent item of this item, if any.
        root_schema : dict, optional
            The root JSON schema for resolving $refs.
        """

        def __init__(
            self,
            key: str,
            value: Any,
            types: Any | None = None,
            parent: MetaViewerWidget.TreeItem | None = None,
            root_schema: dict | None = None,
        ):
            """Initialize a TreeItem."""
            self.parent_item = parent
            self.child_items: list[MetaViewerWidget.TreeItem] = []

            self.key: str = key
            self.value: Any = value
            self.root_schema: dict | None = root_schema or (parent.root_schema if parent else None)

            # Resolve schema if it's a dict
            if isinstance(types, dict):
                self._type = MetaViewerWidget.resolve_schema(types, self.root_schema)
            else:
                self._type = types

            self.description: str | None = None
            if isinstance(self._type, dict):
                self.description = self._type.get("description")
            self.hidden: bool = False
            self.validation_error: str | None = None

            # If value is a dict or Pydantic model, convert its items to TreeItem children
            if isinstance(self.value, (dict, BaseModel)):
                schema = self._type if isinstance(self._type, dict) else {}
                # Update root_schema if this is a new Pydantic model
                if isinstance(self.value, BaseModel):
                    self.root_schema = self.value.__class__.model_json_schema()
                    schema = self.root_schema

                if isinstance(self.value, BaseModel):
                    # Get all field names and extra fields
                    all_keys = list(self.value.__class__.model_fields.keys())
                    if self.value.model_extra:
                        all_keys.extend(self.value.model_extra.keys())
                    items = [(k, getattr(self.value, k)) for k in all_keys]
                else:
                    items = self.value.items()

                for child_key, child_value in items:
                    if child_key == "_schema":
                        continue

                    # Determine type from Pydantic schema or nested types dict
                    cast_type = {}
                    if isinstance(schema, dict):
                        cast_type = schema.get("properties", {}).get(child_key)
                        if cast_type is None:
                            cast_type = schema.get(child_key, {})

                    self.child_items.append(
                        MetaViewerWidget.TreeItem(
                            child_key, child_value, cast_type, self, self.root_schema
                        )
                    )
            elif isinstance(self.value, (tuple, list, np.ndarray)):
                # for lists with finite length also use nest view
                # key is list index
                cast_type = self._type.get("items", {}) if isinstance(self._type, dict) else {}

                if len(self.value) > 1:
                    for i, child_value in enumerate(self.value):
                        self.child_items.append(
                            MetaViewerWidget.TreeItem(
                                f"{i}", child_value, cast_type, self, self.root_schema
                            )
                        )
                elif len(self.value) == 1:
                    # only list with length one, use that element only
                    self.value = self.value[0]
                else:
                    # length 0 list, replace with string representation
                    self.value = str(self.value)

        def child(self, row: int) -> MetaViewerWidget.TreeItem:
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

        def child_count(self) -> int:
            """
            Get the number of child items.

            Returns
            -------
            int
                The number of child items.
            """
            return len(self.child_items)

        def column_count(self) -> Literal[2]:
            """
            Get the number of columns in the item.

            Returns
            -------
            int
                The number of columns (always 2 for Key and Value).
            """
            return 2  # Key and Value columns

        def type(self, column: int) -> dict[str, str] | None:
            """
            Get the type information for the specified column.

            Parameters
            ----------
            column : int
                The column index (0 for Key, 1 for Value).

            Returns
            -------
            dict
                A Pydantic-compatible JSON schema dictionary representing the type.
            """
            if column == 0:
                return {"type": "string"}
            elif column == 1:
                if isinstance(self.value, (tuple, list, dict, np.ndarray)):
                    return {"type": "string"}
                return self._type if isinstance(self._type, dict) else {"type": "string"}
            return None

        def data(self, column: int, role) -> str | None:
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

        def setData(self, index: QModelIndex, value: Any, role=Qt.ItemDataRole.EditRole) -> None:
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

        def parent(self) -> MetaViewerWidget.TreeItem | None:
            """
            Get the parent item.

            Returns
            -------
            TreeItem
                The parent item.
            """
            return self.parent_item

        def row(self) -> int:
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
        Custom tree model for displaying hierarchical data from dicts or Pydantic models.

        Parameters
        ----------
        data : dict or BaseModel
            The hierarchical data to be displayed in the tree.
        parent : QObject, optional
            The parent object for this model.
        """

        validationChanged = Signal()

        def __init__(self, data: dict | BaseModel, parent=None):
            super().__init__(parent)
            self.root_item = MetaViewerWidget.TreeItem("Root", data)

        def data(
            self,
            index: QModelIndex | QPersistentModelIndex,
            role: int = Qt.ItemDataRole.DisplayRole,
        ) -> Any:
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

            if role == Qt.ItemDataRole.ToolTipRole:
                if index.column() == 1 and item.validation_error:
                    return (
                        f"{item.description or ''}\n\nValidation error: {item.validation_error}"
                    ).strip()
                return item.description

            if (
                role == Qt.ItemDataRole.BackgroundRole
                and index.column() == 1
                and item.validation_error
            ):
                return QBrush(QColor("#ffd9d9"))

            if role == Qt.ItemDataRole.TextAlignmentRole:
                return Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft

            return None

        def type(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
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

        def setData(
            self,
            index: QModelIndex | QPersistentModelIndex,
            value: Any,
            role: int = Qt.ItemDataRole.EditRole,
        ) -> bool:
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

        def set_validation_error(
            self,
            index: QModelIndex | QPersistentModelIndex,
            error: str | None,
            *,
            refresh_view: bool = True,
        ) -> None:
            """Mark an item invalid and refresh its validation feedback."""
            item = index.internalPointer()
            if item.validation_error == error:
                return
            item.validation_error = error
            self.validationChanged.emit()
            if refresh_view:
                self.dataChanged.emit(index, index)

        def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
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
            if not index.isValid():
                return Qt.ItemFlag.NoItemFlags
            if index.column() == 1:
                return (
                    Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsEditable
                )
            return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

        def headerData(
            self,
            section: int,
            orientation: Qt.Orientation,
            role: int = Qt.ItemDataRole.DisplayRole,
        ) -> Any:
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

        def index(self, row: int, column: int, parent=QModelIndex()) -> QModelIndex:
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

        def parent(self, index) -> QModelIndex:  # type: ignore our issue #1600
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

        def resetData(self, data: dict | BaseModel, types: dict | None = None) -> None:
            """
            Reset the model with new data.

            Parameters
            ----------
            data : dict or BaseModel
                The new hierarchical data to be displayed in the tree.
            types : dict or dict-like
                Type/schema information for the displayed data.
            """
            self.beginResetModel()
            del self.root_item
            self.root_item = MetaViewerWidget.TreeItem("Root", data, types)
            self.endResetModel()

        def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:
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

        def columnCount(
            self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()
        ) -> Literal[2]:
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
        self,
        metadata,
        heading: str = "Metadata Viewer",
        editable: bool = False,
        parent: QWidget | None = None,
    ):
        """
        Initialize the MetaViewerWidget.

        Parameters
        ----------
        metadata : dict or BaseModel
            Metadata/Configuration to be displayed in the viewer.
        heading : str, optional
            The heading text for the dock widget.
        editable : bool, optional
            Whether the items should be editable.
        parent : QWidget, optional
            The parent widget.
        """
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

    def update_data(self, meta, types: dict = {}) -> None:
        """
        Update data stored in the model and resize table to fit contents.

        Parameters
        ----------
        meta : dict
            New metadata to be displayed.
        types : dict, optional
            Type definition for editable meta data
        """
        # get position of scroll bar before resetting the data
        if self.schema_contains_visa_resource(types):
            self.prefetch_visa_resource_names()
        current_pos = self.tree_view.verticalScrollBar().value()
        self.model.resetData(self.parse_header(meta), self.parse_header(types))
        # resize and expand all entries
        # (the latter might be disabled in the future, or configurable?)
        for i in range(2):
            self.tree_view.resizeColumnToContents(i)
        self.tree_view.expandAll()
        # restore scroll bar position
        self.tree_view.verticalScrollBar().setValue(current_pos)

    def get_validation_errors(self) -> list[str]:
        """Return validation errors currently marked in the tree."""
        errors = []

        def collect(item, parent_path: str = "") -> None:
            path = f"{parent_path}.{item.key}" if parent_path else item.key
            if item.validation_error:
                errors.append(f"{path}: {item.validation_error}")
            for child in item.child_items:
                collect(child, path)

        for item in self.model.root_item.child_items:
            collect(item)
        return errors

    def parse_header(self, hdr: dict) -> dict:
        """
        Shallow copy a matrix header to prepare for display.

        Parameters
        ----------
        hdr : dict
            Header dictionary to be copied.

        Returns
        -------
        dict
            Copied header data.
        """
        # TODO: Implement sorting?
        return hdr.copy()


@contextlib.contextmanager
def blocked_signals(*objects: QObject) -> Iterator[None]:
    """Temporarily block signals for Qt objects."""
    blocked_objects = [(obj, obj.blockSignals(True)) for obj in objects]
    try:
        yield
    finally:
        for obj, previous_state in blocked_objects:
            obj.blockSignals(previous_state)


class ConfigEditWidget(MetaViewerWidget):
    """
    Editor for config files based on the MetaViewerWidget.

    Allows editing and saving the config file.
    """

    def __init__(self, popup: bool = False):
        super().__init__({}, heading="Device config", editable=True)
        if popup:
            self.setTitleBarWidget(QWidget())
        self.setObjectName("config_editor")
        self.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.systemfile = None
        self.system_info: SystemInfo | None = None
        self.full_system_list = []
        self._unmapped_system_config_validation_errors: list[str] = []
        widget = QWidget()
        layout = QVBoxLayout()
        button_layout = QHBoxLayout()

        # Dublin Core Elements
        self.w_update_config: QPushButton = QPushButton("Reload config")
        self.w_update_config.setEnabled(False)
        self.w_update_config.clicked.connect(self.reload_and_update_data)
        button_layout.addWidget(self.w_update_config)
        layout.addLayout(button_layout)
        layout.addWidget(self.tree_view)
        widget.setLayout(layout)
        self.setWidget(widget)
        self.action: QAction = QAction(get_matrix_icon("CHAR_≡"), "Device config", self)
        self.action.setToolTip("Show the devices preferences/ configuration.")
        self.action.setShortcut(QKeySequence("Ctrl+3"))
        self.action.setCheckable(True)
        self.action.toggled.connect(self.toggle_visibility)
        self.visibilityChanged.connect(self._sync_metadata_view)

    def toggle_visibility(self, checked: bool) -> None:
        """Toggle the visibility of this dock widget."""
        if checked:
            self.show()
            self.raise_()
            self.activateWindow()
        else:
            self.hide()

    def _sync_metadata_view(self) -> None:
        """Match view action state to the restored widget visibility."""
        with blocked_signals(self.action):
            self.action.setChecked(not self.isHidden())

    def parse_header(self, hdr: dict) -> dict:
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
        """
        # TODO: Implement sorting?
        return {key: val for key, val in hdr.items() if key not in {"columns", "units"}}

    def set_systemfile(self, systemfile: list) -> None:
        """
        Set systemfile for config editor, must be called before update_data.

        Parameters
        ----------
        systemfile : list
            List of system names to update.
        """
        self.systemfile = systemfile

    def set_system_info(self, system_info: SystemInfo | None) -> None:
        """
        Set system information from subprocess for config editor.

        Parameters
        ----------
        system_info : dict
            Dictionary containing system information including config.
        """
        self.system_info = system_info

    def set_full_system_list(self, full_system_list: list) -> None:
        """
        Set the full system list for reloading system information.

        Parameters
        ----------
        full_system_list : list
            List of all system names (both configurable and non-configurable).
        """
        self.full_system_list = full_system_list

    def reload_and_update_data(self) -> None:
        """Reload system information and update data - wrapper for button action."""
        # Reload system information if full system list is available
        if hasattr(self, "full_system_list") and self.full_system_list:
            system_info = get_system_info(self.full_system_list)
            if isinstance(system_info, Error):
                print(system_info.error)  # noqa: T201
                self.system_info = None
            else:
                self.system_info = system_info.value
        self.update_data()  # Call the original update_data method

    def update_data(self, meta: Any = None, types: dict[Any, Any] | None = None) -> None:
        """Update the configuration data in the widget."""
        syst_dict = {}
        reload_config()

        # Check if we have a merged system by looking for comma-separated system names
        is_merged_system = self.system_info is not None and any(
            "," in system_name for system_name in self.system_info.config.keys()
        )

        # parse config of systems specified in self.systemfile
        # Skip individual system configs if we have a merged system to avoid duplicates
        if self.systemfile is not None and not is_merged_system:
            for syst in self.systemfile:
                syst_dict[syst.strip()] = resolve_config_path(matr1x.config, syst.strip())

        # parse config from system info (from subprocess)
        if self.system_info is not None:
            for system_name, config_info in self.system_info.config.items():
                if system_name not in syst_dict:
                    syst_dict[system_name] = {}

                # Check for Pydantic-based config (contains 'value' and 'schema' keys)
                if (
                    isinstance(config_info, dict)
                    and "value" in config_info
                    and "schema" in config_info
                ):
                    syst_dict[system_name] = config_info["value"]
                    syst_dict[system_name]["_schema"] = config_info["schema"]
                    continue

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
            for system_name, config_info in self.system_info.config.items():
                if system_name in syst_dict:
                    try:
                        system_config = resolve_config_path(matr1x.config, system_name)
                        if "_schema" not in syst_dict[system_name] and hasattr(
                            system_config, "model_json_schema"
                        ):
                            syst_dict[system_name]["_schema"] = system_config.model_json_schema()
                    except Exception:
                        # If we can't get type info, continue without it
                        pass

        def parse_dict_and_types(d, dv, dt):
            for key, item in d.items():
                if key == "_schema":
                    dt["_schema"] = d[key]
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
        self._apply_system_config_validation_errors()
        self.w_update_config.setEnabled(True)

    def _iter_system_config_validation_errors(self) -> Iterator[str]:
        """Yield individual system config validation error lines."""
        if self.system_info is None:
            return
        for error in self.system_info.config_validation_errors:
            for line in error.splitlines():
                stripped = line.strip()
                if stripped:
                    yield stripped

    def _index_for_config_path(self, path: str) -> QModelIndex:
        """Return the value-column model index for a dotted config path."""
        for system_row, system_item in enumerate(self.model.root_item.child_items):
            if path == system_item.key:
                return self.model.index(system_row, 1, QModelIndex())
            if not path.startswith(f"{system_item.key}."):
                continue

            parent_index = self.model.index(system_row, 0, QModelIndex())
            item = system_item
            value_index = self.model.index(system_row, 1, QModelIndex())
            for part in path[len(system_item.key) + 1 :].split("."):
                for child_row, child_item in enumerate(item.child_items):
                    if child_item.key == part:
                        value_index = self.model.index(child_row, 1, parent_index)
                        parent_index = self.model.index(child_row, 0, parent_index)
                        item = child_item
                        break
                else:
                    return QModelIndex()
            return value_index
        return QModelIndex()

    def _apply_system_config_validation_errors(self) -> None:
        """Map system config validation errors to fields where possible."""
        self._unmapped_system_config_validation_errors = []
        for error in self._iter_system_config_validation_errors():
            path, separator, message = error.partition(":")
            if not separator:
                self._unmapped_system_config_validation_errors.append(error)
                continue

            index = self._index_for_config_path(path)
            if not index.isValid():
                self._unmapped_system_config_validation_errors.append(error)
                continue

            self.model.set_validation_error(index, message.strip())

    def get_system_config_validation_errors(self) -> list[str]:
        """Return system config validation errors that could not be mapped to a field."""
        return self._unmapped_system_config_validation_errors.copy()

    def flatten_dict(self, nested: dict, parent_key: str = "", sep: str = ".") -> dict:
        """Flatten a nested dictionary into dotted-key notation."""
        items = {}
        for key, value in nested.items():
            new_key = f"{parent_key}{sep}{key}" if parent_key else key
            if isinstance(value, dict):
                # If all nested values are non-dicts, stop flattening here
                if all(not isinstance(v, dict) for v in value.values()):
                    items[new_key] = value
                else:
                    items.update(self.flatten_dict(value, new_key, sep))
            else:
                items[new_key] = value
        return items

    def apply_config_dict(self, config: dict) -> None:
        """Apply values from a nested config dict to the tree items."""

        def _merge(base: dict, update: dict) -> None:
            """Deep-merge update into base."""
            for key, val in update.items():
                if key in base and isinstance(base[key], dict) and isinstance(val, dict):
                    _merge(base[key], val)
                else:
                    base[key] = val

        _merge(self.value_dict, self.flatten_dict(config))
        super().update_data(self.value_dict, self.types_dict)

    def parse_item(self, item) -> Any:
        """
        Parse a TreeItem and its children into a configuration dictionary.

        Parameters
        ----------
        item : TreeItem
            The TreeItem to parse.

        Returns
        -------
        dict or str or Any
            A dictionary representing the parsed configuration, or a value
            if the item has no children.
        """
        if item.child_count() > 0:
            config = {}
            for child_item in item.child_items:
                config[child_item.data(0, Qt.ItemDataRole.EditRole)] = self.parse_item(child_item)

            # If the item itself represents a Pydantic model, validate the config
            if isinstance(item.value, BaseModel):
                try:
                    # Validate and convert back to a plain dict for the writing process
                    # Use model_validate to check types and apply default values
                    validated = item.value.__class__.model_validate(config)
                    return validated.model_dump(mode="json", by_alias=True, exclude_none=True)
                except ValidationError as e:
                    logger.warning(
                        "Validation error during config extraction for %s: %s", item.key, e
                    )
                    return config  # Fallback to raw config on error
            return config

        # Handle leaf nodes
        schema = item.type(1)
        if schema:
            json_type = schema.get("type")
            raw_value = item.data(1, Qt.ItemDataRole.EditRole)
            if json_type == "boolean":
                return str(raw_value).lower() == "true"
            elif json_type == "integer":
                try:
                    return int(raw_value)
                except (ValueError, TypeError):
                    return raw_value
            elif json_type == "number":
                try:
                    return float(raw_value)
                except (ValueError, TypeError):
                    return raw_value
        return item.data(1, Qt.ItemDataRole.EditRole)

    def get_config_dict(self) -> dict:
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

        config_dict = {}
        for item in self.model.root_item.child_items:
            if item.child_count() == 0:
                # system has no configurable options
                continue
            sys_key = item.key
            key_parts = sys_key.split(".")
            merge_dicts(config_dict, create_nested_dict(key_parts, item))

        return config_dict

    def write_config(self) -> Path:
        """Write the configuration to a temporary file."""
        return self.write_config_dict(self.get_config_dict())

    @staticmethod
    def write_config_dict(config_dict: dict[str, Any]) -> Path:
        """
        Write a configuration dictionary to a temporary file.

        The configuration data is normalized and written to a named temporary
        file. This file persists after the function returns and can be used
        as an optional configuration file.
        """
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
            elif self.math_mode == "custom":
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
                    yscale = (y1 - y0) / self.z.shape[1]  # type: ignore
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
        state = cast(dict, source_plot.vb.state)  # pyqtgraph is not strongly typed
        x_auto = bool(state["autoRange"][0])
        # pyqtgraph keeps (xAuto, yAuto)

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

    def mouseClickEvent(self, ev: QMouseEvent):
        """
        Handle mouse click events.

        Parameters
        ----------
        ev : QMouseEvent
            The mouse event.
        """
        if ev.button() == Qt.MouseButton.RightButton:
            self.autoRange()
            self.enableAutoRange()

    def mouseDragEvent(self, ev: QMouseEvent, axis=None):
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


class LoggerMixin:
    """Add a logger for fine grained information of the origin."""

    def __init_subclass__(cls, **kwargs):
        """Generate the logger."""
        super().__init_subclass__(**kwargs)
        cls.logger = logging.getLogger(f"{cls.__module__}.{cls.__qualname__}")


def get_package_version(module: ModuleType) -> str:
    """Return the version of the given module."""
    if hasattr(module, "__version__"):
        return module.__version__
    try:
        return version(module.__name__)
    except PackageNotFoundError:
        return "unknown"


def get_install_info(
    imported_package: ModuleType,
) -> tuple[str, str, str, Literal["not available"] | int]:
    """
    Receive git infos about the installed version.

    Parameters
    ----------
    imported_package: ModuleType
        Any module (package) that was already imported.

    Returns
    -------
    installed_version: str,
    commit_branch: str,
    commit_short_sha: str,
    commit_time: str or int
        The version and commit info(s) of the package.
    """
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
    installed_version = get_package_version(imported_package)
    return (installed_version, commit_branch, commit_short_sha, commit_time)


class AboutBox(QMessageBox):
    """Provide an about box with install debug info."""

    def __init__(
        self,
        title: str,
        icon: QIcon,
        package: ModuleType,
        date_format: str,
        parent: QWidget | None = None,
    ):
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
        icon_size = style.pixelMetric(QStyle.PixelMetric.PM_MessageBoxIconSize)
        pixmap = icon.pixmap(icon_size)
        self.setIconPixmap(pixmap)
        self.setWindowTitle(title)
        # Get package and git information
        (version, branch, sha, time) = get_install_info(package)
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

                    <p>(C) 2006-2026 Matr1x Developers. All rights reserved.</p>
                </div>
                """

        self.setText(f"<b>{title} {version}</b>")
        self.setInformativeText(text)
        self.setStandardButtons(QMessageBox.StandardButton.Ok)
        self.action = QAction("About")
        self.action.setMenuRole(QAction.MenuRole.AboutRole)
        self.action.triggered.connect(self.exec)

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


def save_messagebox(instance, save_cb: Callable[[], bool]) -> bool:
    """
    Show a messagebox to query file save.

    Ask the user to write unsaved changes to a file
    and return choice.

    Returns
    -------
    return : bool
        The file was saved (True) or not (False).
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
    discard.setText("Don't Save")
    msg.setDefaultButton(QMessageBox.StandardButton.Save)
    ret = msg.exec()
    if ret == QMessageBox.StandardButton.Cancel:
        return False
    if ret == QMessageBox.StandardButton.Save:
        if not save_cb():
            return False
    return True


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
    openfile = Signal(str)

    @property
    def isDark(self) -> bool:
        """
        Return whether the current theme is dark.

        Returns
        -------
        bool
            True if dark theme is active, False otherwise.
        """
        return self._theme_detector.isDark()

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
        if not self.applicationName():
            self.setApplicationName("matr1x")
        if not self.organizationName():
            self.setOrganizationName("matr1x")
        if os.name == "nt":
            self.setStyle("fusion")  # Enable modern mode on Windows which allows for dark mode
        self._theme_detector = ThemeDetector()
        self._theme_detector.isDarkSignal.connect(self.isDarkSignal.emit)
        self._pending_files: list[str] = []
        self._handler_connected = False
        self._signal_timer = QTimer()
        self._signal_timer.timeout.connect(lambda: None)
        signal.signal(signal.SIGINT, self._exit_gracefully)
        signal.signal(signal.SIGTERM, self._exit_gracefully)

    def _exit_gracefully(self, signum: int, frame: object) -> None:
        """
        Handle SIGINT/SIGTERM by quitting the application.

        This enables the safety precautions such as "do you want to
        save" and similar things.

        Parameters
        ----------
        signum : int
            The signal number received.
        frame : object
            The current stack frame (unused).
        """
        logger.debug("Kill signal received (%s)", signum)
        MApplication.quit()

    def exec(self) -> int:
        """
        Run the event loop with a keepalive timer for signal handling.

        Starts a periodic no-op timer so Python can process OS signals
        (e.g. SIGINT from Ctrl+C) while Qt owns the event loop.  The
        timer is stopped automatically when exec returns.

        Returns
        -------
        int
            The exit code returned by the Qt event loop.
        """
        self._signal_timer.start(100)
        try:
            return super().exec()
        finally:
            self._signal_timer.stop()

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

    @classmethod
    def instance(cls) -> MApplication:
        """
        Return the MApplication instance.

        Narrows the return type from QCoreApplication | None to
        MApplication and raises if no instance exists yet.

        Returns
        -------
        MApplication
            The running application instance.

        Raises
        ------
        InternalInvariantError
            If no MApplication instance has been created.
        """
        app = super().instance()
        if not isinstance(app, MApplication):
            raise InternalInvariantError("The application instance is None!")
        return app


# Common system information functions for matrix scripts
def get_system_info(systems: list[str]) -> Result[SystemInfo, str]:
    """Get system information using subprocess."""
    script = (
        "import json\n"
        "import sys\n"
        "from matr1x import validation_errors\n"
        "from matr1x.error_handling import Error\n"
        "from matr1x.system import MergedSystem\n"
        "validation_error_count = len(validation_errors)\n"
        f"result = MergedSystem.from_files({systems!r})\n"
        "if isinstance(result, Error):\n"
        "    print(result.error, file=sys.stderr)\n"
        "    raise SystemExit(1)\n"
        "info = result.value.grab_information()\n"
        "info['config_validation_errors'] = validation_errors[validation_error_count:]\n"
        "print(json.dumps(info))\n"
    )
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
            ],
            capture_output=True,
            timeout=30,
        )
    except Exception as e:
        return Error(f"Could not run system info subprocess: {e}")

    if result.returncode == 0:
        output_str = result.stdout.decode()
        # Find the last line that looks like JSON to avoid warnings/garbage
        json_str = ""
        for line in reversed(output_str.splitlines()):
            if line.strip().startswith("{") and line.strip().endswith("}"):
                json_str = line.strip()
                break

        if not json_str:
            return Error(f"Warning: No JSON found in subprocess output:\n{output_str}")

        try:
            validated_data = SystemInfo.model_validate_json(json_str)
            return Success(validated_data)
        except ValidationError as e:
            return Error(f"Warning: Could not parse JSON from subprocess output:\n{e}")

    stderr_output = result.stderr.decode()
    return Error(stderr_output)


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


def check_config(config: BaseModel) -> None:
    """
    Validate the configuration tomls.

    Parameters
    ----------
    config: BaseModel
        The configuration model to validate.
    """
    from . import validation_errors

    html = "".join(validation_errors).replace("\n", "<br>")
    try:
        MainConfig.model_validate(config)
    except (ValidationError, TypeError, ValueError) as e:
        html += _format_validation_error(e)
    if html != "":
        html = (
            f"Please check your configuration file ({Path.home() / '.matr1x.toml'})! "
            "Some settings will not work as intended. "
            "The following error(s) occured:<br><br>"
        ) + html
        QMessageBox.critical(None, "Validation error!", html)


def create_matrix_settings_action() -> QAction:
    """Create the common matr1x.toml action."""
    action = QAction("Open matr1x.toml")
    action.setMenuRole(QAction.MenuRole.PreferencesRole)
    action.setShortcut(QKeySequence.StandardKey.Preferences)
    return action


def create_matr1x_quit_action() -> QAction:
    """Create the common matr1x quit action."""
    action = QAction("Quit")
    if os.name == "nt":
        action.setShortcut(QKeySequence.StandardKey.Close)
    else:
        action.setShortcut(QKeySequence.StandardKey.Quit)
    return action


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
                self.file_dropped.emit(urls[0].toLocalFile())
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
        return


class LoggingWindow(QMainWindow):
    """Detached window to display logging messages."""

    LOG_FIELDS = ["asctime", "name", "levelname", "message"]
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


class hasLogActions(Protocol):
    """The actions needed by the LogWindowMixin."""

    show_log: QAction
    post_install: QAction
    remove_desktop_integration: QAction


class LogWindowMixin:
    """Shared log-window action handling for GUI scripts."""

    log_window: LoggingWindow

    @staticmethod
    def create_show_log_action() -> QAction:
        """Create the common log-window action."""
        show_log = QAction("Show Log Window")
        show_log.setCheckable(True)
        return show_log

    @staticmethod
    def create_about_action() -> QAction:
        """Create the common about action."""
        about = QAction("About")
        about.setMenuRole(QAction.MenuRole.AboutRole)
        return about

    @staticmethod
    def create_post_install_action() -> QAction:
        """Create the common desktop integration installation action."""
        return QAction("Install Desktop Integration")

    @staticmethod
    def create_remove_desktop_integration_action() -> QAction:
        """Create the common desktop integration removal action."""
        return QAction("Remove Desktop Integration")

    @classmethod
    def add_common_help_actions(cls, menu: QMenu, actions: hasLogActions) -> None:
        """
        Add common help menu actions.

        Parameters
        ----------
        menu : QMenu
            The help menu to populate.
        actions : hasLogActions
            Object exposing about, show_log, post_install and
            remove_desktop_integration actions.
        """
        menu.addAction(actions.show_log)
        menu.addSeparator()
        menu.addAction(actions.post_install)
        menu.addAction(actions.remove_desktop_integration)
        menu.addSeparator()

    def save_log_window_state(self, settings: SaferQSettings, *, enabled: bool = True) -> None:
        """
        Save the log window geometry.

        Parameters
        ----------
        settings : SaferQSettings
            The application settings object.
        enabled : bool
            Whether this window owns the log window state.
        """
        if not enabled:
            return
        if not shiboken6.isValid(self.log_window):
            return
        settings.setValue("log_window/geometry", self.log_window.saveGeometry())

    def restore_log_window_state(self, settings: SaferQSettings, *, enabled: bool = True) -> None:
        """
        Restore the log window geometry.

        Parameters
        ----------
        settings : SaferQSettings
            The application settings object.
        enabled : bool
            Whether this window owns the log window state.
        """
        if not enabled:
            return
        if not shiboken6.isValid(self.log_window):
            return
        self.log_window.restoreGeometry(
            settings.safer_value("log_window/geometry", QByteArray(), type=QByteArray)
        )

    def cleanup_log_window(self, *, enabled: bool = True) -> None:
        """
        Remove the log handler and delete the log window.

        Parameters
        ----------
        enabled : bool
            Whether this window owns the log window.
        """
        if not enabled:
            return
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.log_window.log_handler)
        self.log_window.deleteLater()

    def toggle_log_window(self) -> None:
        """Toggle the visibility of the logging window."""
        if self.log_window.isVisible():
            self.log_window.hide()
        else:
            self.log_window.show()
            self.log_window.raise_()
            self.log_window.activateWindow()

    def _on_log_window_visibility_changed(self, visible: bool, actions: hasLogActions) -> None:
        """Keep the 'Show Log Window' action state in sync."""
        action = actions.show_log
        action.setChecked(visible)
        action.setText("Hide Log Window" if visible else "Show Log Window")


def AutoSlot(function: Callable[P, R]) -> Callable[P, R]:
    """
    Provide a Qt slot for a typed python function or method.

    To have only one source of truth, the type hints generate the
    appropriate slot automatically and automatically generates Qt Slot
    overloads.
    """
    function = inspect.unwrap(function)
    hints = get_type_hints(function)
    signature = inspect.signature(function)
    params = _collect_parameters(signature, hints)
    overloads = _build_overloads(params)
    result_type = _normalize_result_type(hints.get("return"))
    for args in reversed(overloads):
        if result_type is not None:
            function = Slot(*args, result=result_type)(function)
        else:
            function = Slot(*args)(function)
    return function


def _collect_parameters(
    signature: inspect.Signature, hints: dict[str, Any]
) -> list[dict[str, Any]]:
    """Extract parameter metadata (types + default info)."""
    params: list[dict[str, Any]] = []
    for name, param in signature.parameters.items():
        if name == "self":
            continue
        if name not in hints:
            raise TypeError(f"Missing type hint for parameter '{name}'")
        params.append(
            {
                "types": _expand_type(hints[name]),
                "has_default": param.default is not inspect._empty,
            }
        )
    return params


def _expand_type(t: Any) -> list[type]:
    """Expand a Python type hint into Qt-compatible types."""
    # Special handling for Python 3.12+ TypeAliasType (e.g., numpy.typing.ArrayLike)
    if TypeAliasType is not None and isinstance(t, TypeAliasType):
        return _expand_type(t.__value__)
    origin = get_origin(t)
    if origin is type:
        return [type]
    if origin in (Union, types.UnionType):
        result = []
        for arg in get_args(t):
            result.extend(_expand_type(arg))
        return result
    if origin is not None:
        return [origin]
    return [t]


def _build_overloads(params: list[dict]) -> list[list[type]]:
    """Create all Qt slot overload combinations."""
    overloads = [[]]
    for param in params:
        new_overloads = [base + [t] for base in overloads for t in param["types"]]
        if param["has_default"]:
            overloads = overloads + new_overloads
        else:
            overloads = new_overloads
    seen = []
    for o in overloads:
        if o not in seen:
            seen.append(o)
    return seen


def _normalize_result_type(t: Any) -> Any:
    """Convert Python return annotation to Qt-compatible type."""
    if t is type(None):
        return None
    if t is None:
        return None
    # Special handling for Python 3.12+ TypeAliasType
    if TypeAliasType is not None and isinstance(t, TypeAliasType):
        return _normalize_result_type(t.__value__)
    origin = get_origin(t)
    if origin is type:
        return type
    if origin is not None:
        return origin
    return t


def clear_layout(layout: QLayout) -> None:
    """Clear all child widgets from layout."""
    while layout.count():
        item = layout.takeAt(0)
        if item is not None:
            if widget := item.widget():
                widget.deleteLater()
            elif child_layout := item.layout():
                clear_layout(child_layout)
