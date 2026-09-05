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
"""The meta data viewer and the configuration editor widget."""

from __future__ import annotations

import contextlib
import copy
import logging
import math
import re
import sys
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import (
    Any,
    Literal,
    cast,
)

import numpy as np
from pydantic import BaseModel, ValidationError
from PySide6.QtCore import (
    QAbstractItemModel,
    QLocale,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QDoubleValidator,
    QIntValidator,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTextEdit,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

import matr1x.core.config as core_config
from matr1x.core.config import merge_dicts, reload_config, write_config
from matr1x.core.error_handling import Error, Result, Success
from matr1x.core.models import (
    SystemInfo,
)
from matr1x.core.util import resolve_config_path
from matr1x.core.visa_helpers import (
    VisaResourceRequirements,
    get_visa_resource_manager,
    validate_visa_resource,
)

from .helpers import get_matrix_icon, get_system_info
from .widgets import FileLineEdit

logger = logging.getLogger(__name__)


_DEFAULT_PARENT_INDEX = QModelIndex()


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
            visa_requirements = cast(
                VisaResourceRequirements | None,
                schema.get("visa_resource_requirements"),
            )

            if "enum" in schema:
                # strict, use combobox
                editor = QComboBox(parent)
                editor.insertItems(0, [str(i) for i in schema["enum"]])
                editor.setStyleSheet("QComboBox { border: none; padding: 0px; }")
            elif json_type == "string" and ui_type == "visa_resource":
                editor = QComboBox(parent)
                editor.setEditable(True)
                editor.insertItems(0, MetaViewerWidget.visa_resource_names(visa_requirements))
                editor.setStyleSheet("QComboBox { border: none; padding: 0px; }")
                editor.currentTextChanged.connect(
                    lambda value, tree_model=model, model_index=index: (
                        MetaViewerWidget._update_visa_editor_validation(
                            cast(QComboBox, editor),
                            value,
                            tree_model,
                            model_index,
                            visa_requirements,
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

        def destroyEditor(
            self,
            editor: QWidget,
            index: QModelIndex | QPersistentModelIndex,
        ) -> None:
            """Restore the cell display after committing or cancelling an edit."""
            if index.isValid():
                item = index.internalPointer()
                item.hidden = False
                index.model().dataChanged.emit(index, index)
            super().destroyEditor(editor, index)

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
                if isinstance(value, str):
                    editor.setChecked(value.strip().casefold() == "true")
                else:
                    editor.setChecked(bool(value))
            elif isinstance(editor, FileLineEdit):
                editor.setText(str(value))
            elif isinstance(editor, QComboBox):
                was_blocked = editor.blockSignals(True)
                editor.setCurrentText(str(value))
                editor.blockSignals(was_blocked)
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
                    value = validate_visa_resource(
                        str(value),
                        cast(
                            VisaResourceRequirements | None,
                            schema.get("visa_resource_requirements"),
                        ),
                    )
                except ValueError as exc:
                    tree_model = cast(MetaViewerWidget.TreeModel, model)
                    tree_model.setData(index, value, Qt.ItemDataRole.EditRole)
                    tree_model.set_validation_error(index, str(exc))
                    MetaViewerWidget._update_visa_editor_validation(
                        cast(QComboBox, editor),
                        str(value),
                        requirements=cast(
                            VisaResourceRequirements | None,
                            schema.get("visa_resource_requirements"),
                        ),
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
        requirements: VisaResourceRequirements | None = None,
        *,
        refresh_view: bool = True,
    ) -> None:
        """Show VISA validation feedback on an editable resource combo box."""
        validation_error = None
        try:
            validate_visa_resource(value, requirements)
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
            model.setData(index, value, Qt.ItemDataRole.EditRole)
            model.set_validation_error(index, validation_error, refresh_view=refresh_view)

    @staticmethod
    def visa_resource_names(
        requirements: VisaResourceRequirements | None = None,
    ) -> list[str]:
        """Return cached VISA resource suggestions matching field requirements."""
        resources = MetaViewerWidget._visa_resource_cache or []
        if requirements is None:
            return resources.copy()

        matching_resources = []
        for resource in resources:
            try:
                validate_visa_resource(resource, requirements)
            except ValueError:
                continue
            matching_resources.append(resource)
        return matching_resources

    @staticmethod
    def _query_visa_resource_names() -> list[str] | None:
        """Query VISA resource suggestions from PyVISA."""
        try:
            return [str(resource) for resource in get_visa_resource_manager().list_resources()]
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

    @staticmethod
    def default_value_from_schema(schema: dict, root_schema: dict | None = None) -> Any:
        """Create an editable placeholder for a missing JSON-schema value."""
        schema = MetaViewerWidget.resolve_schema(schema, root_schema)
        if "default" in schema:
            return schema["default"]

        json_type = schema.get("type")
        if json_type == "object":
            return {}
        if json_type == "array":
            return []
        if json_type == "boolean":
            return False
        if json_type == "integer":
            return int(schema.get("minimum", 0))
        if json_type == "number":
            return float(schema.get("minimum", 0.0))
        return ""

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
            *,
            missing: bool = False,
        ):
            """Initialize a TreeItem."""
            self.parent_item = parent
            self.child_items: list[MetaViewerWidget.TreeItem] = []

            self.key: str = key
            self.value: Any = value
            self.missing = missing
            self.root_schema: dict | None = root_schema or (parent.root_schema if parent else None)
            if isinstance(types, dict) and isinstance(types.get("_schema"), dict):
                self.root_schema = types["_schema"]

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
                    items = []
                    for child_key in all_keys:
                        try:
                            child_value = getattr(self.value, child_key)
                        except AttributeError:
                            child_schema = schema.get("properties", {}).get(child_key, {})
                            items.append(
                                (
                                    child_key,
                                    MetaViewerWidget.default_value_from_schema(
                                        child_schema, self.root_schema
                                    ),
                                    True,
                                )
                            )
                        else:
                            items.append((child_key, child_value, False))
                else:
                    items = [(k, v, False) for k, v in self.value.items()]
                    present_keys = self.value.keys()
                    properties = schema.get("properties", {})
                    for child_key in schema.get("required", []):
                        if child_key in present_keys or child_key not in properties:
                            continue
                        items.append(
                            (
                                child_key,
                                MetaViewerWidget.default_value_from_schema(
                                    properties[child_key], self.root_schema
                                ),
                                True,
                            )
                        )

                for child_key, child_value, child_missing in items:
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
                            child_key,
                            child_value,
                            cast_type,
                            self,
                            self.root_schema,
                            missing=child_missing,
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
            role
                If editor is active, act like there is no value.

            Returns
            -------
            str
                The data for the specified column.
            """
            if column == 0:
                return self.key
            elif column == 1:
                if self.missing:
                    return ""
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
                return
            if index.column() == 1:
                if self.child_count() > 0:
                    # prevent writing into the header lines
                    return
                if role == Qt.ItemDataRole.EditRole:
                    self.value = value
                    self.hidden = False
                    item: MetaViewerWidget.TreeItem | None = self
                    while item is not None:
                        item.missing = False
                        item = item.parent()
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
            item = index.internalPointer()
            is_container = item.child_count() > 0 or isinstance(item.value, (dict, BaseModel))
            if index.column() == 1 and not is_container:
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

        def index(
            self,
            row: int,
            column: int,
            parent: QModelIndex | QPersistentModelIndex = _DEFAULT_PARENT_INDEX,
        ) -> QModelIndex:
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

        def rowCount(
            self, parent: QModelIndex | QPersistentModelIndex = _DEFAULT_PARENT_INDEX
        ) -> int:
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
            self, parent: QModelIndex | QPersistentModelIndex = _DEFAULT_PARENT_INDEX
        ) -> Literal[2]:
            """
            Return the number of columns for the children of the given parent.

            Parameters
            ----------
            parent : QModelIndex
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

    def update_data(self, meta, types: dict | None = None) -> None:
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
        if types is None:
            types = {}
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
        # TODO: Implement sorting?  # noqa: FIX002
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
        self.w_update_config: QPushButton = QPushButton("Reload all")
        self.w_update_config.setIcon(get_matrix_icon("SP_BrowserReload"))
        self.w_update_config.setToolTip("Reload all system configurations from disk.")
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

    def show_for_validation_errors(self) -> None:
        """Open the configuration editor once after validation fails."""
        if self.isVisible():
            return
        with blocked_signals(self.action):
            self.action.setChecked(True)
        self.show()
        self.raise_()
        self.activateWindow()

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
        # TODO: Implement sorting?  # noqa: FIX002
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
        """Reload all system configuration information and rebuild the editor."""
        expansion_state = self._config_expansion_state()
        if self.full_system_list:
            system_info = get_system_info(self.full_system_list)
            if isinstance(system_info, Error):
                print(system_info.error)  # noqa: T201
                self.system_info = None
            else:
                self.system_info = system_info.value
        self.update_data()
        self._restore_config_expansion_state(expansion_state)

    def reload_system_config(self, system_name: str) -> None:
        """Reload one system while preserving unsaved values in all other systems."""
        retained_config: dict[str, Any] = {
            item.key: self.parse_item(item)
            for item in self.model.root_item.child_items
            if item.key != system_name and item.child_count() > 0
        }
        self.reload_and_update_data()
        self.apply_config_dict(retained_config)

    def _install_system_reload_buttons(self) -> None:
        """Place a reload button in the value cell of every system header."""
        for row, item in enumerate(self.model.root_item.child_items):
            index = self.model.index(row, 1, QModelIndex())
            container = QWidget(self.tree_view)
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 2, 0)
            layout.addStretch()
            button = QToolButton(container)
            button.setIcon(get_matrix_icon("SP_BrowserReload"))
            button.setAutoRaise(True)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            button.setToolTip(f"Reload the configuration for {item.key} from disk.")
            button.clicked.connect(
                lambda checked=False, system_name=item.key: self.reload_system_config(system_name)
            )
            layout.addWidget(button)
            self.tree_view.setIndexWidget(index, container)

    def _config_expansion_state(self) -> dict[tuple[str, ...], bool]:
        """Return the expanded state of every existing configuration section."""
        state: dict[tuple[str, ...], bool] = {}

        def collect(parent: QModelIndex, path: tuple[str, ...] = ()) -> None:
            for row in range(self.model.rowCount(parent)):
                index = self.model.index(row, 0, parent)
                item_path = (*path, str(index.data(Qt.ItemDataRole.EditRole)))
                if self.model.rowCount(index) > 0:
                    state[item_path] = self.tree_view.isExpanded(index)
                    collect(index, item_path)

        collect(QModelIndex())
        return state

    def _restore_config_expansion_state(
        self, expansion_state: dict[tuple[str, ...], bool]
    ) -> None:
        """Restore expansion states for sections that still exist after a reload."""

        def restore(parent: QModelIndex, path: tuple[str, ...] = ()) -> None:
            for row in range(self.model.rowCount(parent)):
                index = self.model.index(row, 0, parent)
                item_path = (*path, str(index.data(Qt.ItemDataRole.EditRole)))
                if item_path in expansion_state:
                    self.tree_view.setExpanded(index, expansion_state[item_path])
                if self.model.rowCount(index) > 0:
                    restore(index, item_path)

        restore(QModelIndex())

    def _has_merged_system_config(self) -> bool:
        """Return whether runtime configuration represents a merged system."""
        return self.system_info is not None and any(
            "," in system_name for system_name in self.system_info.config
        )

    def _config_from_systemfile(self) -> dict[str, Any]:
        """Load file-backed configuration unless runtime data is already merged."""
        if self.systemfile is None or self._has_merged_system_config():
            return {}
        return {
            system.strip(): resolve_config_path(core_config.config, system.strip())
            for system in self.systemfile
        }

    @staticmethod
    def _pydantic_config_value(config_info: dict[str, Any]) -> dict[str, Any]:
        """Copy a Pydantic config value and retain its schema."""
        config = copy.deepcopy(config_info["value"])
        schema = config_info["schema"]
        # The tree model adds absent required fields as editable, explicitly
        # missing items using this schema.
        config["_schema"] = schema
        return config

    def _add_system_config(
        self, syst_dict: dict[str, Any], system_name: str, config_info: Any
    ) -> None:
        """Add one runtime system configuration to the editor data."""
        if isinstance(config_info, dict) and {"value", "schema"} <= config_info.keys():
            syst_dict[system_name] = self._pydantic_config_value(config_info)
            return

        system_config = syst_dict.setdefault(system_name, {})
        for key, value_info in config_info.items():
            if isinstance(value_info, dict):
                if "value" in value_info:
                    system_config[key] = value_info["value"]
                continue
            system_config[key] = value_info

    def _add_missing_system_schemas(self, syst_dict: dict[str, Any]) -> None:
        """Supplement runtime configuration with locally available JSON schemas."""
        if self.system_info is None:
            return
        for system_name in self.system_info.config:
            if system_name not in syst_dict or "_schema" in syst_dict[system_name]:
                continue
            try:
                system_config = resolve_config_path(core_config.config, system_name)
                if hasattr(system_config, "model_json_schema"):
                    syst_dict[system_name]["_schema"] = system_config.model_json_schema()
            except Exception:
                # If type information is unavailable, retain the values alone.
                logger.debug(
                    "Could not load the local schema for runtime system %s",
                    system_name,
                    exc_info=True,
                )

    @staticmethod
    def _split_config_values_and_types(
        source: dict[str, Any], values: dict[str, Any], types: dict[str, Any]
    ) -> None:
        """Separate configuration values from the schema tree used by the model."""
        for key, item in source.items():
            if key == "_schema":
                types[key] = item
            elif isinstance(item, dict):
                values[key] = {}
                types[key] = {}
                ConfigEditWidget._split_config_values_and_types(item, values[key], types[key])
            else:
                values[key] = item

    def update_data(self, meta: Any = None, types: dict[Any, Any] | None = None) -> None:
        """Update the configuration data in the widget."""
        reload_config()
        syst_dict = self._config_from_systemfile()

        # parse config from system info (from subprocess)
        if self.system_info is not None:
            for system_name, config_info in self.system_info.config.items():
                self._add_system_config(syst_dict, system_name, config_info)
            self._add_missing_system_schemas(syst_dict)

        self.value_dict = {}
        self.types_dict = {}
        self._split_config_values_and_types(syst_dict, self.value_dict, self.types_dict)

        super().update_data(self.value_dict, self.types_dict)
        self._install_system_reload_buttons()
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

    def validate_config(self) -> Result[None, str]:
        """Return all validation errors currently known to the config editor."""
        errors = self.get_system_config_validation_errors()
        errors.extend(self.get_validation_errors())
        for item in self.model.root_item.child_items:
            errors.extend(self._validate_schema_item(item))
        if errors:
            return Error("\n".join(dict.fromkeys(errors)))
        return Success(None)

    @staticmethod
    def _coerce_schema_value(value: Any, schema: dict[str, Any]) -> Any:
        """Convert an editor value to the primitive type declared by JSON schema."""
        json_type = schema.get("type")
        if json_type == "integer":
            return int(value)
        if json_type == "number":
            return float(value)
        if json_type == "string":
            return str(value)
        return value

    @classmethod
    def _validate_enum_or_const(cls, value: Any, schema: dict[str, Any]) -> str | None:
        """Validate enum choices and const values."""
        if "enum" in schema:
            try:
                enum = [
                    cls._coerce_schema_value(candidate, schema) for candidate in schema["enum"]
                ]
            except (TypeError, ValueError):
                enum = schema["enum"]
            if value not in enum:
                choices = ", ".join(repr(candidate) for candidate in enum)
                return f"Input should be one of: {choices}"

        if "const" in schema and value != schema["const"]:
            return f"Input should be {schema['const']!r}"

        return None

    @classmethod
    def _validate_numeric_constraints(cls, value: Any, schema: dict[str, Any]) -> str | None:
        """Validate numeric range and multipleOf constraints."""
        if "minimum" in schema and value < schema["minimum"]:
            return f"Input should be greater than or equal to {schema['minimum']}"
        if "maximum" in schema and value > schema["maximum"]:
            return f"Input should be less than or equal to {schema['maximum']}"
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            return f"Input should be greater than {schema['exclusiveMinimum']}"
        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            return f"Input should be less than {schema['exclusiveMaximum']}"
        if multiple_of := schema.get("multipleOf"):
            quotient = value / multiple_of
            if not math.isclose(quotient, round(quotient), abs_tol=1e-12):
                return f"Input should be a multiple of {multiple_of}"
        return None

    @classmethod
    def _validate_string_constraints(cls, value: Any, schema: dict[str, Any]) -> str | None:
        """Validate string length, regex patterns, and specialized UI types like visa_resource."""
        if "minLength" in schema and len(value) < schema["minLength"]:
            return f"Input should have at least {schema['minLength']} characters"
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            return f"Input should have at most {schema['maxLength']} characters"
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            return f"Input should match pattern {schema['pattern']!r}"
        if schema.get("ui_type") == "visa_resource":
            try:
                validate_visa_resource(
                    value,
                    cast(
                        VisaResourceRequirements | None,
                        schema.get("visa_resource_requirements"),
                    ),
                )
            except ValueError as exc:
                return str(exc)
        return None

    @classmethod
    def _schema_validation_error(cls, item) -> str | None:
        """Validate one leaf value against constraints represented in JSON schema."""
        if item.missing:
            return "Field required"

        schema = item.type(1)
        if not isinstance(schema, dict):
            return None

        try:
            value = cls._coerce_schema_value(item.value, schema)
        except (TypeError, ValueError):
            return f"Input should be a valid {schema.get('type', 'value')}"

        if err := cls._validate_enum_or_const(value, schema):
            return err

        json_type = schema.get("type")
        if json_type in {"integer", "number"}:
            return cls._validate_numeric_constraints(value, schema)
        if json_type == "string":
            return cls._validate_string_constraints(value, schema)

        return None

    @classmethod
    def _validate_schema_item(cls, item, parent_path: str = "") -> list[str]:
        """Return schema-validation errors for one config tree and its children."""
        path = f"{parent_path}.{item.key}" if parent_path else item.key
        if item.validation_error:
            return []
        if item.missing:
            return [f"{path}: Field required"]
        if item.child_count() > 0:
            errors = []
            for child_item in item.child_items:
                errors.extend(cls._validate_schema_item(child_item, path))
            return errors
        if error := cls._schema_validation_error(item):
            return [f"{path}: {error}"]
        return []

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

    def apply_config_dict(self, config: dict[str, Any]) -> None:
        """Apply values for configuration sections present in the current tree."""
        self._apply_config_value(config)

    def _apply_config_value(self, value: Any, path: str = "") -> None:
        """Apply a configuration value or recursively apply its child values."""
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else key
                self._apply_config_value(child, child_path)
            return

        # Do not turn a missing required field into a literal null value.
        if value is None:
            return
        index = self._index_for_config_path(path)
        if not index.isValid():
            return

        validation_error = None
        if self.model.type(index).get("ui_type") == "visa_resource":
            try:
                value = validate_visa_resource(
                    str(value),
                    cast(
                        VisaResourceRequirements | None,
                        self.model.type(index).get("visa_resource_requirements"),
                    ),
                )
            except ValueError as exc:
                validation_error = str(exc)
        self.model.setData(index, value, Qt.ItemDataRole.EditRole)
        self.model.set_validation_error(index, validation_error)
        self.model.dataChanged.emit(index, index)

    @classmethod
    def _parse_leaf_item(cls, item: MetaViewerWidget.TreeItem) -> Any:
        """Parse and type-coerce a leaf TreeItem value."""
        raw_value = item.data(1, Qt.ItemDataRole.EditRole)
        if raw_value is None:
            return None

        schema = item.type(1)
        if not isinstance(schema, dict):
            return raw_value

        json_type = schema.get("type")
        if json_type == "boolean":
            return raw_value.lower() == "true"

        if json_type == "integer":
            try:
                return int(raw_value)
            except (ValueError, TypeError):
                return raw_value

        if json_type == "number":
            try:
                return float(raw_value)
            except (ValueError, TypeError):
                return raw_value

        return raw_value

    def _parse_container_item(self, item: MetaViewerWidget.TreeItem) -> dict | Any:
        """Parse child TreeItems into a dictionary and validate Pydantic models."""
        config = {
            child_item.data(0, Qt.ItemDataRole.EditRole): self.parse_item(child_item)
            for child_item in item.child_items
            if not child_item.missing
        }

        if isinstance(item.value, BaseModel):
            try:
                validated = item.value.__class__.model_validate(config)
                return validated.model_dump(mode="json", by_alias=True, exclude_none=True)
            except ValidationError as e:
                logger.warning("Validation error during config extraction for %s: %s", item.key, e)
                return config

        return config

    def parse_item(self, item: MetaViewerWidget.TreeItem) -> Any:
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
            return self._parse_container_item(item)
        return self._parse_leaf_item(item)

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
