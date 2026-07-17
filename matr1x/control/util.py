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
Contains utility functions for generating control GUIs or devices.

This module provides functionality for creating control graphical user
interfaces or devices based on the scpi_tcp_server.
"""

import copy
import inspect
import itertools
import logging
import mimetypes
import numbers
import os
import re
import smtplib
import ssl
import sys
import threading
import time
from collections import UserDict
from collections.abc import Callable, Sequence
from email import encoders
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import IntEnum
from operator import attrgetter
from pathlib import Path
from subprocess import PIPE, Popen
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, TypeVar, cast, overload

import numpy
import psutil
from decorator import FunctionMaker
from numpy.typing import ArrayLike
from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator
from pydantic_core import PydanticCustomError
from PySide6.QtCore import (
    QObject,
    QPoint,
    QSize,
    QStandardPaths,
    Qt,
    QThread,
    QTimer,
    Signal,
)
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from matr1x.gui_util import AutoSlot
from matr1x.scripts.shared_classes import SaferQSettings

if TYPE_CHECKING:
    from matr1x.control.controlwindow import ControlWindow


from matr1x.system import System

from .. import config
from ..error_handling import InternalInvariantError
from ..gui_util import MApplication, validator
from ..util import Command, normalize_cmds

__all__ = [
    "GuiDict",
    "MethodBundle",
    "MyQDockWidget",
    "catchEmitError",
    "control_main",
    "guiObject",
    "linear_trend",
    "sendNotificationEmail",
    "var",
]

logger = logging.getLogger(__name__)


_F = TypeVar("_F", bound=Callable[..., Any])


class variable(Protocol):
    def __call__(self, *, variable: "var") -> None: ...


class widget(Protocol):
    def __call__(self, *, widget: Any) -> None: ...


class value(Protocol):
    def __call__(self, *, value: Any) -> None: ...


class variableWidget(Protocol):
    def __call__(self, *, variable: "var", widget: Any) -> None: ...


class variableValue(Protocol):
    def __call__(self, *, variable: "var", value: Any) -> None: ...


class widgetValue(Protocol):
    def __call__(self, *, widget: Any, value: Any) -> None: ...


class variableWidgetValue(Protocol):
    def __call__(self, *, variable: "var", widget: Any, value: Any) -> None: ...


ChangeHandler: TypeAlias = (
    variable | widget | value | variableWidget | variableValue | widgetValue | variableWidgetValue
)


def catchEmitError(method: _F) -> _F:
    """
    Define error handling decorator.

    This decorator works only with ControlWindow which defines a sig_error signal.

    Parameters
    ----------
    method : callable
        The method to be decorated.

    Returns
    -------
    callable
        The decorated method.
    """

    def call(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception:
            # report error to the main thread if relevant part can't be disabled
            exc_type, exc_value, exc_traceback = sys.exc_info()
            pointer = getattr(method, "__name__")
            logger.exception("Handling error in %s", pointer)
            # if the GuiDict which raised the error allows disabling lets just
            # disable it and swallow the error
            guidict = getattr(self, "guidict", None)
            if guidict is None and hasattr(self, "_dispatcher"):
                guidict = self

            if guidict is not None and hasattr(guidict, "_dispatcher"):
                logger.error("Error occurred inside '%s'", guidict.__class__.__name__)
                if getattr(guidict, "allow_disabling", False):
                    guidict._dispatcher.disable_requested.emit()
                    logger.info("Ignoring last Exception since device can be deactivated.")
                    return
            if hasattr(self, "sig_error"):
                self.sig_error.emit(exc_type, exc_value, pointer)
            elif hasattr(self, "parent") and self.parent:
                self.parent.sig_error.emit(exc_type, exc_value, pointer)

    return cast(
        _F,
        FunctionMaker.create(
            method,
            "return call(%(shortsignature)s)",
            dict(call=call, _method=method),
            __wrapped__=method,
        ),
    )


class ToggleButton(QPushButton):
    """
    Custom QPushButton to emulate a proper toggle button.

    Including the change of the button's label upon pushing.

    Parameters
    ----------
    *args : str | list[str] | tuple[str, str]]
        Positional arguments. The first argument should be either a
        string (single label) or a list/tuple of two strings (labels
        for unchecked/checked states).
    **kwargs : dict
        Keyword arguments to be passed to the QPushButton constructor.
    """

    def __init__(self, *args: str | list[str] | tuple[str, str], **kwargs):
        if isinstance(args[0], (list, tuple)):
            label = args[0][0]
        else:
            label = args[0]
        super().__init__(label, **kwargs)
        self._labels = args[0]
        self.setCheckable(True)

    def setChecked(self, state: bool) -> None:
        """
        Change label of toggle button.

        Parameters
        ----------
        state : bool
            The new checked state of the button.
        """
        super().setChecked(state)
        # if it is checked
        if isinstance(self._labels, (list, tuple)):
            if state:
                self.setText(self._labels[1])
            # if it is unchecked
            else:
                self.setText(self._labels[0])


class MethodBundle:
    """Allow a thread-safe modification of a guiObject."""

    def __init__(self):
        self.calls: list[Callable[[Any], None]] = []
        self.change_calls: list[ChangeHandler] = []

    def add_setup_method(self, function: Callable[[Any], None]):
        """
        Add a widget setup callable to the bundle.

        Parameters
        ----------
        function : callable
            A callable (method or function) to be invoked. There is only
            one allowed parameter (the widget).
        """
        sig = inspect.signature(function)
        params = list(sig.parameters.values())
        if len(params) != 1:
            name = getattr(function, "__name__", "function")
            raise TypeError(f"{name} must accept exactly one parameter (the widget)")
        self.calls.append(function)
        return self

    def add_change_handler(self, function: ChangeHandler):
        """
        Add a handler to be called on every value change.

        Parameters
        ----------
        function : callable
            A callable (method or function) to be invoked.

        Notes
        -----
        Handlers must declare any used context explicitly by name. The
        allowed parameter names are ``variable``, ``widget``, and
        ``value``.
        """
        self.change_calls.append(function)
        return self

    def apply(self, obj: QWidget):
        """Apply all methods in the bundle on the given object."""
        for function in self.calls:
            function(obj)

    def connect_value_changed(self, obj: "var", widget: QWidget):
        """Register the change handlers with the variable dispatcher."""
        for callback in self.change_calls:
            obj._register_change_handler(callback, widget)

    @staticmethod
    def _invoke_change_callback(
        callback: Callable[..., Any], obj: "var", widget: QWidget, value: Any
    ) -> None:
        """Invoke a callback using only the declared named context."""
        signature = inspect.signature(callback)
        context = {"variable": obj, "widget": widget, "value": value}

        kwargs: dict[str, Any] = {}
        for parameter in signature.parameters.values():
            if parameter.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                raise TypeError(
                    f"Unsupported MethodBundle change handler signature for {callback!r}. "
                    "Handlers must use only named parameters from (variable, widget, value)."
                )
            if parameter.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            ):
                if parameter.name in context:
                    kwargs[parameter.name] = context[parameter.name]
                    continue
                raise TypeError(
                    f"Unsupported MethodBundle change handler parameter '{parameter.name}' "
                    f"for {callback!r}. Allowed names are (variable, widget, value)."
                )

        callback(**kwargs)


class guiObject(IntEnum):
    """
    Enum object for GUI elements identification.

    This enum makes it easier to write readable code and identify GUI
    elements by their name instead of only by a number.
    """

    button = 0
    lineedit = 1
    checkbox = 2
    progressbar = 3
    combobox = 4
    togglebutton = 5
    spinbox = 6
    doublespinbox = 7
    labeltext = 8
    hline = 9

    @classmethod
    def getWidget(
        cls,
        label: str,
        wType: "guiObject | str | None",
        init: object | None = None,
        *,
        modify: MethodBundle | None = None,
    ) -> QWidget | None:
        """
        Return the widget of the correct type.

        Parameters
        ----------
        label : str
            Label of widget (used as a fallback string on the button if no init
            value is given).
        wType : int or guiObject or str
            Can be one of:
            * str : QLabel: string used as label text.
            * 0 : QPushButton
            * 1 : QLineEdit
            * 2 : QCheckBox
            * 3 : QProgressBar
            * 4 : QComboBox
            * 5 : QPushButton(checkable=True)
            * 6 : QSpinBox
            * 7 : QDoubleSpinBox
            * 8 : QLabel: used as Value indicator
            * 9 : QFrame: used to generate a horizontal separator line
        init : tuple, object, optional
            Provides the initialization values (button label, valid ranges,
            combobox entries).

        Returns
        -------
        QWidget or None
            Widget of requested type or None.

        Examples
        --------
        Generate a toggle button which changes its label upon being set:
        >>> getWidget("Property", guiObject.togglebutton, init=("Slow", "Fast"))

        Generate a QComboBox with prefilled options:
        >>> getWidget("Property", guiObject.combobox, init=("opt 1", "opt 2"))

        Generate a SpinBox (similar for DoubleSpinBox):
        >>> getWidget("Property", guiObject.spinbox, init=(0, 200))

        Generate a PushBotton with text "Set":
        >>> getWidget("Property", guiObject.button, init="Set")

        Generate a label with text "Example":
        >>> getWidget("Property", "Example")
        """
        widget_creation_methods: dict[Any, Callable[[Any], QWidget]] = {
            str: lambda wType: cls._create_label_widget(wType),
            guiObject.labeltext: lambda init: cls._create_labeltext_widget(init),
            guiObject.button: lambda init: QPushButton(init if init else label),
            guiObject.lineedit: lambda init: QLineEdit(init if init else None),
            guiObject.checkbox: lambda init=None: QCheckBox(),
            guiObject.progressbar: lambda init: cls._create_progressbar_widget(init),
            guiObject.combobox: lambda init: cls._create_combobox_widget(init),
            guiObject.togglebutton: lambda init: ToggleButton(init if init else label),
            guiObject.spinbox: lambda init: cls._create_spinbox_widget(init),
            guiObject.doublespinbox: lambda init: cls._create_doublespinbox_widget(init),
            guiObject.hline: lambda init: cls._create_hline_widget(init),
        }
        if isinstance(wType, str):
            widget_type = str
        else:
            widget_type = wType if not isinstance(wType, int) else guiObject(wType)
        creation_method = widget_creation_methods.get(widget_type)
        if creation_method:
            if widget_type is str and init is None:
                return_widget = creation_method(wType)
            else:
                return_widget = creation_method(init)
            if modify:
                modify.apply(return_widget)
            return return_widget

        return None

    @classmethod
    def _create_label_widget(cls, wType: str) -> QLabel:
        qlab = QLabel(wType)
        qlab.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return qlab

    @classmethod
    def _create_labeltext_widget(cls, init) -> QLabel:
        label = QLabel(init if init else None)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    @classmethod
    def _create_progressbar_widget(cls, init) -> QProgressBar:
        pbar = QProgressBar()
        if init:
            pbar.setValue(init)
        return pbar

    @classmethod
    def _create_combobox_widget(cls, init) -> QComboBox:
        qcombo = QComboBox()
        if init is not None:
            qcombo.insertItems(0, init)
        return qcombo

    @classmethod
    def _create_spinbox_widget(cls, init) -> QSpinBox:
        sb = QSpinBox()
        if init is not None and len(init) == 2:
            sb.setRange(*init)
        return sb

    @classmethod
    def _create_doublespinbox_widget(cls, init) -> QDoubleSpinBox:
        sb = QDoubleSpinBox()
        if init is not None and len(init) == 2:
            sb.setRange(*init)
        return sb

    @classmethod
    def _create_hline_widget(cls, init) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if init is not None:
            line.setFixedWidth(init)
        line.setMinimumHeight(2)
        return line


class varData(BaseModel):
    """
    Provide a data model for the var class.

    This used to store, validate and normalize the data for subsequent
    use in the var class.
    """

    model_config = {"arbitrary_types_allowed": True}

    dtype: type | None
    columns: list[str | guiObject | None] = [None, None]
    unit: str = ""
    log_default: bool = Field(alias="log", default=False)
    init: list = [None, None]
    hide: bool = False
    modify: list[MethodBundle | None] = [None, None]

    def __init__(self, *args, **kwargs):
        """Map positional arguments to field names."""
        field_names = list(type(self).model_fields.keys())
        for name, value in zip(field_names, args):
            if name in kwargs:
                raise TypeError(f"Multiple values for argument '{name}'")
            kwargs[name] = value
        super().__init__(**kwargs)

    @field_validator("columns", mode="before")
    @classmethod
    def normalize_columns(cls, columns):
        """Normalize columns to a list."""
        if type(columns) is int or (
            isinstance(columns, list) and any(type(x) is int for x in columns)
        ):
            raise TypeError("Only use guiObjects and no integers.")
        if not isinstance(columns, list):
            return [columns, None]
        if len(columns) == 1:
            return [columns[0], None]
        if len(columns) != 2:
            raise ValueError("columns requires one or two entries.")
        return columns

    @field_validator("init", "modify", mode="before")
    @classmethod
    def normalize_pair(cls, value, info: ValidationInfo):
        """Normalize init and modify into a list."""
        if not isinstance(value, list):
            return [value, value]
        if len(value) == 1:
            return [value[0], None]
        if len(value) != 2:
            raise ValueError(f"{info.field_name} requires one or two entries.")
        return value

    @model_validator(mode="after")
    def check_log_requires_dtype(self):
        """Validate that log=True is only allowed if dtype is not None."""
        if self.log_default and self.dtype is None:
            raise PydanticCustomError(
                "Invalid_configuration",
                "Cannot enable logging without a defined parameter type.",
            )
        return self


class var(QObject):
    """
    Variable storage for implementing with qt GUI.

    Emits valueChanged signal if the value has changed so it can
    be connected to a display.

    Parameters
    ----------
    dType : type or None
        Type of the variable (float, int, str, ...).
    columns : list[guiObject] | guiObject, optional
        Reqired GUI elements, typically two entries: View the current
        value and alter it. The values are enumerations from guiObject.
    unit : str, optional
        Unit string used in the label and data logging.
    log_default : bool, optional, default = False
        Boolean flag to set the default behavior in the logging config.
    init : list[object1, object2] or object
        Initialization values for column1 and column2. A single object
        is assumed to apply to both columns.
    hide : bool, optional, default = False
        Flag to mark extendable entries that are initially hidden.
    modify : MethodBundle
        Modify the standard widget with stored methods.
    """

    valueChanged: Signal = Signal(object)
    unitChanged: Signal = Signal(str)
    tooltipChanged: Signal = Signal(str)
    copyValueRequested: Signal = Signal()

    @overload
    def __init__(
        self,
        dtype: type | None,
        *,
        columns: list[guiObject | str | None] | str | guiObject | None = None,
        unit: str = "",
        log: bool | None = False,
        init: object | None = None,
        hide: bool = False,
        modify: MethodBundle | list[MethodBundle | None] | None = None,
    ) -> None: ...

    @overload
    def __init__(self, __dtype: type | None, /) -> None: ...

    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        self._data: varData = varData(*args, **kwargs)
        self.log = None if self._data.dtype is None else self._data.log_default
        self.hide = self._data.hide
        self._value = None
        self.widgets: list[Any] = []
        self._tooltip: str = ""
        self._change_handlers: list[tuple[Callable[..., Any], QWidget]] = []
        self._gui_cache: dict[int, Any] = {}
        self._gui_cache_lock = threading.Lock()
        self.valueChanged.connect(self._update_readout_slot)
        self.valueChanged.connect(self._update_toggle_slot)
        self.valueChanged.connect(self._dispatch_change_handlers)
        self.unitChanged.connect(self._update_label_slot)
        self.tooltipChanged.connect(self._update_tooltip_slot)
        self.copyValueRequested.connect(self._copy_value_slot)

    def _register_change_handler(self, callback: Callable[..., Any], widget: QWidget) -> None:
        """Register a change handler for GUI-thread dispatch."""
        self._change_handlers.append((callback, widget))

    def setValue(self, newValue: Any) -> None:
        """
        Set the value of the variable.

        Parameters
        ----------
        newValue : Any
            The new value to set.
        """
        self.value = newValue

    @property
    def value(self) -> Any:
        """
        Get the current value of the variable.

        Returns
        -------
        Any
            The current value of the variable.
        """
        return self._value

    @value.setter
    def value(self, new_value: Any) -> None:
        """
        Set the value of the variable and emit a signal if it has changed.

        Parameters
        ----------
        newValue : Any
            The new value to set.
        """
        if self._data.dtype is None:
            return
        if new_value is None:
            self._value = None
            return
        new_value = self._data.dtype(new_value)
        if new_value != self._value:
            self._value = new_value
            self.valueChanged.emit(self._value)

    @property
    def unit(self) -> str:
        """
        Get the unit of the variable.

        Returns
        -------
        str
            The unit of the variable.
        """
        return self._data.unit

    @unit.setter
    def unit(self, newunit: str) -> None:
        """
        Set the unit of the variable and emit a signal.

        Parameters
        ----------
        newunit : str
            The new unit to set.
        """
        self._data.unit = newunit
        self.unitChanged.emit(self._data.unit)

    @property
    def tooltip(self) -> str:
        """
        Get the tooltip of the variable.

        Returns
        -------
        str
            The tooltip of the variable.
        """
        return self._tooltip

    @tooltip.setter
    def tooltip(self, newtooltip: str) -> None:
        """
        Set the tooltip of the variable and emit a signal.

        Parameters
        ----------
        newtooltip : str
            The new tooltip to set.
        """
        self._tooltip = newtooltip
        self.tooltipChanged.emit(self._tooltip)

    def _generate_widgets(self, label: str = "") -> None:
        """
        Generate a list of Qt widgets corresponding to the label and columns.

        These widgets can be used to build a graphical user interface. The
        widgets property is filled with the corresponding items after this
        function was executed. Variable values will be automatically linked to
        these widgets with the connect_signal method.

        Parameters
        ----------
        label : str, optional
            The label for the widgets.

        Examples
        --------
        >>> var(int, columns=[guiObject.lineedit, guiObject.checkbox])
        # will result in a (visible) layout as follows:
        # QLabel(label) - QLineEdit - QCheckBox

        >>> var(int,
        ...     columns=[guiObject.combobox, guiObject.combobox],
        ...     init=("a", "b"))
        # results in:
        # QLabel(label) - QComboBox("a", "b") - QComboBox("a", "b")

        Note
        ----
        In all cases above the label and first GUI element will be
        declared read only since they are assumed to serve to show a value
        read-out from an instrument.

        In addition to the visible items a by default hidden checkbox will be
        added which shows and changes the logging preferences.
        """
        self._change_handlers = []
        self._gui_cache = {}
        fulllabel = f"{label} ({self.unit})" if self.unit != "" else label
        self.widgets = [QLabel(fulllabel)]

        for i, widget in enumerate(self._data.columns):
            widgetinit = self._data.init[i]
            if self._data.modify[i]:
                self.widgets.append(
                    guiObject.getWidget(label, widget, widgetinit, modify=self._data.modify[i])
                )
            else:
                self.widgets.append(guiObject.getWidget(label, widget, widgetinit))

        # set sensible default values and disable readout column
        if isinstance(self.widgets[1], QLineEdit):
            self.widgets[1].setReadOnly(True)
        elif isinstance(self.widgets[1], (QComboBox, QCheckBox)):
            self.widgets[1].setEnabled(False)
        # apply a validator
        if isinstance(self.widgets[2], QLineEdit) and self._data.dtype is not None:
            val = validator.get(self._data.dtype, None)
            if val:
                self.widgets[2].setValidator(val)
        # add config checkbox
        if self.log is not None:
            checkbox = QCheckBox()
            checkbox.setChecked(self.log)
            checkbox.setVisible(False)
            self.widgets.append(checkbox)
        # connect variable value with the widgets
        self._connect_signal()
        if self.hide:
            for w in self.widgets:
                if w:
                    w.hide()

    def _update_label(self, newunit: str) -> None:
        """
        Update the label of the widget with a new unit.

        Parameters
        ----------
        newunit : str
            The new unit to display in the label.
        """
        widget = self.widgets[0]
        if not isinstance(widget, QLabel):
            raise InternalInvariantError("updateLabel should work on a QLabel!")
        label = widget.text()
        if re.search(r"\([^)]*\)", label):
            newlabel = re.sub(r"\([^)]*\)", f"({newunit})", label)
        else:
            newlabel = f"{label} ({newunit})"
        widget.setText(newlabel)

    def _write_value_to_widget(
        self,
        widget: QWidget,
        value: object,
        *,
        cache_column: int | None = None,
    ) -> None:
        """Write a value into a widget and optionally update the GUI cache."""
        if isinstance(widget, (QLineEdit, QLabel)):
            widget.setText(str(value))
            if cache_column is not None and isinstance(widget, QLabel):
                self._set_cached_gui_value(cache_column, value)
        elif isinstance(widget, (QSpinBox, QProgressBar)):
            widget.setValue(int(cast(Any, value)))
        elif isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(cast(Any, value)))
        elif isinstance(widget, QComboBox):
            if isinstance(value, int):
                widget.setCurrentIndex(value)
            elif isinstance(value, str):
                widget.setCurrentText(value)
        elif isinstance(widget, (QCheckBox, QPushButton)):
            if widget.isCheckable():
                widget.setChecked(bool(value))
        else:
            raise TypeError(f"Unsupported widget type {type(widget)}")

    @AutoSlot
    def _update_readout_slot(self, value: object) -> None:
        """Update the readout widget on the variable thread."""
        if self._data.dtype is None or len(self.widgets) <= 1:
            return
        try:
            self._write_value_to_widget(self.widgets[1], value, cache_column=1)
        except (TypeError, ValueError):
            pass

    @AutoSlot
    def _update_toggle_slot(self, value: object) -> None:
        """Keep toggle buttons synchronized with checkbox readouts."""
        if len(self.widgets) <= 2:
            return
        if isinstance(self.widgets[1], QCheckBox) and isinstance(self.widgets[2], ToggleButton):
            if self.widgets[2].isCheckable():
                self.widgets[2].setChecked(bool(value))

    @AutoSlot
    def _update_label_slot(self, newunit: str) -> None:
        """Update the label on the variable thread."""
        if self.widgets and isinstance(self.widgets[0], QLabel):
            self._update_label(newunit)

    @AutoSlot
    def _update_tooltip_slot(self, newtooltip: str) -> None:
        """Update the readout tooltip on the variable thread."""
        if len(self.widgets) > 1 and isinstance(self.widgets[1], QWidget):
            self.widgets[1].setToolTip(newtooltip)

    def getGUIvalue(self, column: int = 2) -> Any:
        """
        Return the value of the GUI element in the respective column.

        On the widget-owning thread the widget is read directly. Otherwise
        a cached GUI value is returned when available.

        Parameters
        ----------
        column : int, optional
            Column index in the widget list to read the value from.

        Returns
        -------
        Any
            The value from the GUI element, cast to variableType.

        Raises
        ------
        RuntimeError
            If the method is called off the widget-owning thread and no
            thread-safe value source is available.
        """
        element = self.widgets[column]
        if self._is_widget_threadsafe_here(element):
            value = self._read_widget_value(column)
            self._set_cached_gui_value(column, value)
            return value

        cached = self._get_cached_gui_value(column)
        if cached is not None:
            return cached

        raise RuntimeError(
            f"Thread-unsafe GUI read from column {column} of {type(element).__name__} "
            "without cached value available."
        )

    def _is_widget_threadsafe_here(self, widget: QWidget) -> bool:
        """Return whether direct widget access is safe in the current thread."""
        return QThread.currentThread() == widget.thread()

    def _read_widget_value(self, column: int) -> Any:
        """Read and cast a widget value from the given column."""
        if self._data.dtype is None:
            raise InternalInvariantError("variableType should not be None at this point!")
        element = self.widgets[column]
        if isinstance(element, (QLineEdit, QLabel)):
            value = element.text()
        elif isinstance(element, (QSpinBox, QDoubleSpinBox, QProgressBar)):
            value = element.value()
        elif isinstance(element, QComboBox):
            if self._data.dtype in [int, float]:
                value = element.currentIndex()
            else:
                value = element.currentText()
        elif isinstance(element, (QCheckBox, QPushButton)):
            value = element.isChecked()
        else:
            raise TypeError(f"Unknown type of GUI element {type(element)}")
        return self._data.dtype(value)

    def _set_cached_gui_value(self, column: int, value: Any) -> None:
        """Store a cached GUI value for thread-safe non-GUI access."""
        with self._gui_cache_lock:
            self._gui_cache[column] = value

    def _get_cached_gui_value(self, column: int) -> Any | None:
        """Return a cached GUI value if available."""
        with self._gui_cache_lock:
            return self._gui_cache.get(column)

    def _connect_signal(self) -> None:
        """Register widget-specific handlers and GUI caches."""
        if self._data.dtype is not None and len(self.widgets) > 1:
            for column, modify in enumerate(self._data.modify, start=1):
                if modify is None:
                    continue
                if not isinstance(self.widgets[column], QWidget):
                    raise RuntimeError(
                        f"MethodBundle change handlers require a widget in column {column}."
                    )
                modify.connect_value_changed(self, self.widgets[column])

        cache_stop = 3 if self.log is not None else 2
        for _col_idx in range(1, cache_stop):
            self._init_widget_cache(_col_idx, self.widgets[_col_idx])

    @AutoSlot
    def _dispatch_change_handlers(self, value: object) -> None:
        """Dispatch MethodBundle change handlers on the variable thread."""
        for callback, widget in self._change_handlers:
            MethodBundle._invoke_change_callback(callback, self, widget, value)

    def _init_widget_cache(self, col_idx: int, widget: Any) -> None:
        """
        Connect a widget's change signal to the GUI value cache.

        Establishes a signal connection so that every change of
        widget updates _gui_cache on the GUI thread, making the cached
        value safe to read from any thread via getGUIvalue.

        Parameters
        ----------
        col_idx : int
            Index of the column.
        widget : Any
            The Qt widget to monitor.
        """
        variable_type = self._data.dtype
        if variable_type is None:
            return

        def _cache(value: Any) -> None:
            try:
                self._set_cached_gui_value(col_idx, variable_type(value))
            except (ValueError, TypeError):
                pass

        initial: Any
        if isinstance(widget, QLineEdit):
            initial = widget.text()
            widget.textChanged.connect(_cache)
        elif isinstance(widget, QLabel):
            if self._value is not None:
                self._set_cached_gui_value(col_idx, variable_type(self._value))
            return
        elif isinstance(widget, (QSpinBox, QProgressBar, QDoubleSpinBox)):
            initial = widget.value()
            widget.valueChanged.connect(_cache)
        elif isinstance(widget, QComboBox):
            if self._data.dtype in (int, float):
                initial = widget.currentIndex()
                widget.currentIndexChanged.connect(_cache)
            else:
                initial = widget.currentText()
                widget.currentTextChanged.connect(_cache)
        elif isinstance(widget, (QCheckBox, QPushButton)):
            initial = widget.isChecked()
            widget.toggled.connect(_cache)
        else:
            return

        _cache(initial)

    def copy_value(self) -> None:
        """
        Copy the read values into the set field.

        Thread-safe: emits copyValueRequested, which Qt dispatches
        to the GUI thread via a queued connection when called from a
        worker thread, and as a direct call when already on the GUI
        thread.
        """
        self.copyValueRequested.emit()

    @AutoSlot
    def _copy_value_slot(self) -> None:
        """Perform the widget update on the GUI thread."""
        # check that a set-field exists, otherwise pass
        if len(self.widgets) > 2 and self.widgets[2] is not None and self._data.dtype is not None:
            try:
                self._write_value_to_widget(self.widgets[2], self.value, cache_column=2)
            except (TypeError, ValueError):
                # allow a type mismatch in case a variable is not set
                if self.value is not None:
                    raise


class MyQDockWidget(QDockWidget):
    """Modify QDockWidget to be able to track its closing."""

    dockClosed: Signal = Signal()

    def __init__(self, title: str, appname: str) -> None:
        super().__init__(title)
        self.application_name: str = appname
        self.setObjectName(f"{appname}-{title}")
        self.settings: SaferQSettings = SaferQSettings("matr1x", appname)
        self.disabled: bool = False
        self.extended: bool = False

    @AutoSlot
    def saveCurrentState(self) -> None:
        """Save current dock geometry and enable state."""
        self.settings.beginGroup(self.windowTitle())
        self.settings.setValue("size", self.size())
        self.settings.setValue("pos", self.pos())
        self.settings.setValue("disabled", self.disabled)
        self.settings.setValue("extended", self.extended)
        self.settings.endGroup()

    def restoreState(self) -> None:
        """Load stored dock geometry and disable state."""
        self.settings.beginGroup(self.windowTitle())
        self.resize(self.settings.safer_value("size", self.size(), type=QSize))
        self.move(self.settings.safer_value("pos", self.pos(), type=QPoint))
        self.disabled = self.settings.safer_value("disabled", False, type=bool)
        self.extended = self.settings.safer_value("extended", False, type=bool)
        self.settings.endGroup()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Emit dockClosed signal when the dock is closed."""
        super().closeEvent(event)
        self.dockClosed.emit()


class _GuiDispatcher(QObject):
    """Small QObject living on the GUI thread to run widget updates safely."""

    copy_requested: Signal = Signal()
    disable_requested: Signal = Signal()

    def __init__(self, guidict: "GuiDict") -> None:
        super().__init__()
        self._guidict: GuiDict = guidict
        self.copy_requested.connect(self.copy_values_slot)
        self.disable_requested.connect(self.disable_guidict)

    @AutoSlot
    def copy_values_slot(self) -> None:
        """Trigger a safe copy-values operation on the GUI thread."""
        self._guidict.copy_values()

    @AutoSlot
    def disable_guidict(self) -> None:
        """Disable the GuiDict safely on the GUI thread."""
        self._guidict.enable_switch.setChecked(False)


class _Worker(QObject):
    """
    Worker object for the refresh thread.

    This is needed for the QTimer to work inside the QThread.

    Attributes
    ----------
    activity : Signal
        Signal to indicate an iteration of the refresh timer.
    panic : Signal
        Signal to indicate a panic state.
    sig_error : Signal
        Signal to report errors.
    """

    # activity signal to indicate an iteration of the refresh timer
    activity = Signal(str)
    panic = Signal(bool, str)
    sig_error = Signal(type, Exception, str)

    def __init__(self, target: Callable[[int], None], interval: int, parent: "GuiDict") -> None:
        super().__init__()
        self.target: Callable[[int], None] = target  # target function for the refresh loop
        self.interval: int = interval  # in milliseconds
        self.guidict: GuiDict = parent
        self._timer: QTimer = QTimer()  # fake definition

    @catchEmitError
    @AutoSlot
    def run(self) -> None:
        """Start the worker's refresh loop and copy readout to set fields."""
        self._timer = QTimer()
        self._timer.setInterval(self.interval)
        counter = itertools.count(1)
        self._timer.timeout.connect(lambda: self._target(next(counter)))
        # start refresh immediately and then again after the timer timeout
        self.target(0)
        # copy values from readout to set fields upon first run
        self.guidict._dispatcher.copy_requested.emit()
        self._timer.start()

    @AutoSlot
    def stop(self) -> None:
        """Stop the worker's refresh loop."""
        self._timer.stop()
        self.activity.emit("lightgray")

    @catchEmitError
    def _target(self, count: int) -> None:
        """
        Encapsulate target function to emit the activity signal.

        Parameters
        ----------
        count : int
            The current iteration count.
        """
        if count % 2:
            self.activity.emit("green")
        else:
            self.activity.emit("lightgreen")
        self.target(count)


class GuiDict(UserDict[str, var]):
    """
    Custom dictionary representing elements and commands of the control GUI.

    Additionally a System object with related devices can be stored in this
    class as object variable.

    Important class variables which shall be overwritten are:

    Attributes
    ----------
    cmds : dict
        List of commands for this device.
        e.g.: cmds = {":v1": Command(int, "setV1", "V1"),
                      "*idn": Get(str, "id-string")}
    data : dict
        GUI dictionary elements.
        e.g.
        data = {"Example": var(None, columns=["Readout", "Setpoint"]),
                "V1": var(int, columns=[go.combobox, go.combobox],
                          log=True, init=("i1", "i2")),
                "V2": var(float, columns=[go.lineedit, go.lineedit], unit="mT"),
                "Set": var(None, columns=[go.button, go.button],
                           init=["Set", "Copy"]),
               }
    refresh_period : float
        Period (in seconds) in which the timer attempts to run the refresh method
        once. If the refresh method takes more execution time than this
        period it's called without further delay. It will never be called more
        often than once per this period. (default: 1 sec)
    allow_disabling : bool
        Flag to decide if the GuiDict can be disabled. If this is set to True the
        underlying devices should all provide a `close` method or be a pymeasure
        Instrument. Otherwise likely reenabling will fail.
    """

    data: dict[str, var] = {}
    cmds: dict[str, Command] = {}
    refresh_period: float = 1.0
    allow_disabling: bool = False

    def __init__(self) -> None:
        super().__init__(self.data)
        if not hasattr(self, "S"):
            self.S = System()
        self._refresh_thread: QThread = QThread()
        self._panic: bool = False
        self._extended_visible = threading.Event()
        self.refresh_worker: _Worker = _Worker(
            target=self.refresh,
            interval=self.refresh_period_ms,
            parent=self,
        )
        self.refresh_worker.moveToThread(self._refresh_thread)
        self._refresh_thread.started.connect(self.refresh_worker.run)
        self._refresh_thread.finished.connect(self.refresh_worker.stop)
        # reference to parent object which it will save in after its assigned
        # this reference is used to raise an error on the parent if needed
        self.parent = None
        self.running: bool = False
        self.showlog: bool = False
        # buffer original commands
        normalize_cmds(self.cmds)
        self._orig_cmds: dict[str, Command] = copy.deepcopy(self.cmds)
        # empty custom menu
        self.menu_actions = []
        # initialize all with None
        self._reset()
        self._dispatcher = _GuiDispatcher(self)
        self.name: str = next(iter(self.keys()), self.__class__.__name__)

    def create_GUI(self) -> MyQDockWidget:
        """
        Create a QDockWidget to be attached to the main control GUI.

        Also link all buttons to respective methods.

        Returns
        -------
        QDockWidget
            The created dock widget.
        """
        if self.parent is not None:
            self.dock: MyQDockWidget = MyQDockWidget(self.name, self.parent.windowTitle())
        else:
            self.dock = MyQDockWidget(self.name, "")
        self.dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.dock.setAllowedAreas(Qt.DockWidgetArea.TopDockWidgetArea)
        dockcontainer = QWidget()
        column = QVBoxLayout(dockcontainer)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        self.dock.setWidget(dockcontainer)
        self.container: QWidget = QWidget()
        self.container.setContentsMargins(10, 0, 10, 10)

        # add top controls (hiding/enable) to the content widget
        self.control_layout: QHBoxLayout = QHBoxLayout()
        self.toolbar: QToolBar = QToolBar()
        style = MApplication.style()
        icon_size = style.pixelMetric(QStyle.PixelMetric.PM_SmallIconSize)
        self.toolbar.setIconSize(QSize(icon_size, icon_size))
        self.control_layout.addWidget(self.toolbar)
        self.extend_switch: QCheckBox = QCheckBox()
        self.enable_switch: QCheckBox = QCheckBox()
        self.extend_switch.toggled.connect(self._set_extended_visible)
        self._set_extended_visible(self.extend_switch.isChecked())

        has_hiding = any(variable.hide for variable in self.values())
        if has_hiding:
            self.extend_switch.stateChanged.connect(self.toggle_hidden)
            self.extend_switch.setChecked(False)
        if self.allow_disabling:
            self.enable_switch.stateChanged.connect(self.makeEnabled)
        column.addLayout(self.control_layout)
        column.addWidget(self.container)
        column.addStretch()

        # create content
        self.create_content()

        return self.dock

    def create_content(self) -> None:
        """
        Create the real content of the GuiDict.

        This function takes the variables from the GuiDict and generates
        the respective GUI widgets. If a user overwrites this function
        it will need to attach its output to self.container!
        """
        grid = QGridLayout(self.container)
        # create items of dictionary inside content
        for row, (key, variable) in enumerate(self.items()):
            variable._generate_widgets(key)
            for col, widget in enumerate(variable.widgets):
                # add widgets to the grid layout at the correct position
                # but skip hidden checkbox
                if col == 0 and row == 0:
                    continue
                if widget:
                    grid.addWidget(widget, row, col, 1, 1)

    def toggle_hidden(self, state: bool) -> None:
        """
        Toggle the visibility of hidden widgets.

        Parameters
        ----------
        state : bool
            If True, show hidden widgets; if False, hide them.
        """
        if state:
            self.dock.extended = True
            for variable in self.values():
                if isinstance(variable, var) and variable.hide:
                    for i, w in enumerate(variable.widgets):
                        if (
                            variable.log is not None
                            and i == len(variable.widgets) - 1
                            and not self.showlog
                        ):
                            continue
                        if w:
                            w.show()
        else:
            self.dock.extended = False
            for variable in self.values():
                if isinstance(variable, var) and variable.hide:
                    for w in variable.widgets:
                        if w:
                            w.hide()

    @property
    def extended_visible(self) -> bool:
        """bool: Whether hidden controls are currently shown."""
        return self._extended_visible.is_set()

    @AutoSlot
    def _set_extended_visible(self, state: bool) -> None:
        """Store extend-switch state in a thread-safe mirror."""
        if state:
            self._extended_visible.set()
        else:
            self._extended_visible.clear()

    def copy_values(self) -> None:
        """Copy the values from the first to the second column."""
        for variable in self.values():
            variable.copy_value()

    @property
    def refresh_period_ms(self) -> int:
        """
        Get the refresh period in milliseconds.

        Returns
        -------
        int
            The refresh period in milliseconds.
        """
        return int(self.refresh_period * 1000)

    def makeEnabled(self, state: int) -> None:
        """
        Enable or disable the GUI based on the given state.

        Parameters
        ----------
        state : int
            0 to disable, any other value to enable.
        """
        if state == 0:
            self.stop()
        else:
            self.start()
        self.dock.disabled = not self.enable_switch.isChecked()

    def restoreFeatures(self) -> None:
        """Restore features based on the enable switch setting."""
        if self.enable_switch.isChecked():
            self.container.setEnabled(True)
            if self.allow_disabling:
                self.dock.setFeatures(
                    self.dock.features() & ~QDockWidget.DockWidgetFeature.DockWidgetClosable
                )
        else:
            self.container.setEnabled(False)
            if self.allow_disabling:
                self.dock.setFeatures(
                    self.dock.features() | QDockWidget.DockWidgetFeature.DockWidgetClosable
                )

    def stop(self, wait: bool = True) -> None:
        """
        Disable GUI fields and the update loop.

        Parameters
        ----------
        wait : bool, optional
            Flag to make this function block up to twice the refresh period or
            until the refresh thread ended (default is True).

        Returns
        -------
        None
        """
        if self.running:
            self.running = False
            self._refresh_thread.quit()
            if wait:
                finished = self._refresh_thread.wait(2 * self.refresh_period_ms)
                if not finished and self._refresh_thread.isRunning():
                    logger.warning(
                        "GuiDict %s refresh thread did not terminate within %.2f s",
                        self.__class__.__name__,
                        2 * self.refresh_period_ms / 1000,
                    )

        # Ensure UI reflects stopped state if it was still checked.
        # This covers cases where stop() is called due to a crash or panic.
        if self.allow_disabling and self.enable_switch.isChecked():
            # Signal unchecking back to the GUI thread. Using the dispatcher
            # ensures this works even when called from a worker thread.
            self._dispatcher.disable_requested.emit()

        # Ensure cleanup even if start() failed halfway or stop was called
        # multiple times.
        if hasattr(self, "S"):
            try:
                self.S.reset()
                self.S.close()
            except Exception:
                logger.exception("Error during System cleanup in GuiDict.stop()")

        self.restoreFeatures()
        # reset variables and commands
        self._reset()

    def _reset(self) -> None:
        """
        Reset all values and cmd functions to None.

        This is done to avoid logging or reporting something not
        updated.
        """
        for variable in self.data.values():
            variable.value = None
        for cmd in self.cmds.values():
            cmd.reset_to_None()

    @catchEmitError
    def start(self) -> None:
        """Start the refresh loop in a dedicated thread."""
        if not self.running and self.enable_switch.isChecked():
            # initialize the system
            self.S.set()
            # convert command function names to executables
            self.set_cmd_funcs(window_obj=self.parent, system=self.S)
            self.restoreFeatures()
            self.running = True
            self._refresh_thread.start()

    def set_cmd_funcs(
        self, window_obj: "ControlWindow | None" = None, system: System | None = None
    ) -> dict[str, Command]:
        """
        Replace setter and getter functions by an instance of Command.

        Depending on the setter and getter functions type either the
        respective class methods, variables or device functions from the
        system are used.
        """
        # replace entries with executable functions
        for name, cmd in self._orig_cmds.items():
            setfunc, setargs = self._create_setfunc(name, cmd, window_obj, system)
            getfunc, getargs = self._create_getfunc(name, cmd, window_obj, system)

            # set new Command properties in existing list
            self.cmds[name].setfunc = setfunc
            self.cmds[name].getfunc = getfunc
            self.cmds[name].setargs = setargs
            self.cmds[name].getargs = getargs
        return self.cmds

    def _create_setfunc(
        self,
        name: str,
        cmd: Command,
        window_obj: "ControlWindow | None" = None,
        system: System | None = None,
    ) -> tuple[Callable | None, tuple]:
        """
        Create the setter function from the command definition.

        The function determines what the user intended by the specified
        cmd and generates an appropriate function.
        """
        if cmd.setfunc is None:
            return None, ()
        elif isinstance(cmd.setfunc, str):
            return self._handle_string_setfunc(name, cmd, window_obj)
        elif isinstance(cmd.setfunc, (tuple, list)):
            if system is None:
                raise ValueError("System must be specified as 'system' keyword argument")
            return self._handle_tuple_setfunc(name, cmd, system)
        elif callable(cmd.setfunc):
            return cmd.setfunc, cmd.setargs
        raise ValueError(f"could not identify '{cmd.setfunc}' of '{name}'")

    def _handle_string_setfunc(
        self, name: str, cmd: Command, window_obj: "ControlWindow | None"
    ) -> tuple[Callable | None, tuple]:
        """Handle the case where setfunc is a string."""
        cmd.setfunc = cast(str, cmd.setfunc)
        if hasattr(self, cmd.setfunc):  # if GuiDict method or property
            attr = attrgetter(cmd.setfunc)(self)
            if callable(attr):
                return attr, cmd.setargs
            else:

                def setfunc(value, c=self, a=cmd.setfunc):
                    setattr(c, a, value)

                return setfunc, ()
        elif cmd.setfunc in self:  # if GuiDict.data entry

            def setfunc(value, c=self.data[cmd.setfunc]):
                setattr(c, "value", value)

            return setfunc, ()
        elif hasattr(window_obj, cmd.setfunc):  # if ControlWindow method
            attr = attrgetter(cmd.setfunc)(window_obj)
            if callable(attr):
                return attr, ()
            else:

                def setfunc(value, c=window_obj, a=cmd.setfunc):
                    setattr(c, a, value)

                return setfunc, ()
        raise ValueError(f"could not identify '{cmd.setfunc}' of '{name}'")

    def _handle_tuple_setfunc(
        self, name: str, cmd: Command, system: System
    ) -> tuple[Callable | None, tuple]:
        """Handle the case where setfunc is a tuple or list (system device)."""
        cmd.setfunc = cast(tuple, cmd.setfunc)
        devname, funcname = cmd.setfunc
        attr = attrgetter(funcname)(system.devs[devname])
        if callable(attr):
            return attr, cmd.setargs
        else:

            def setfunc(value, c=system.devs[devname], a=funcname):
                setattr(c, a, value)

            return setfunc, ()

    def _create_getfunc(
        self,
        name: str,
        cmd: Command,
        window_obj: "ControlWindow | None" = None,
        system: System | None = None,
    ) -> tuple[Callable | None, tuple]:
        """
        Create the getter function from the command definition.

        The function determines what the user intended by the specified
        cmd and generates an appropriate function.
        """
        if cmd.getfunc is None:
            return None, ()
        elif isinstance(cmd.getfunc, str):
            return self._handle_string_getfunc(name, cmd, window_obj)
        elif isinstance(cmd.getfunc, (tuple, list)):
            if system is None:
                raise ValueError("System must be specified as 'system' keyword argument")
            return self._handle_tuple_getfunc(name, cmd, system)
        elif callable(cmd.getfunc):
            return cmd.getfunc, cmd.getargs
        raise ValueError(f"could not identify '{cmd.getfunc}' of '{name}'")

    def _handle_string_getfunc(
        self, name: str, cmd: Command, window_obj: "ControlWindow | None"
    ) -> tuple[Callable | None, tuple]:
        """Handle the case where getfunc is a string."""
        cmd.getfunc = cast(str, cmd.getfunc)
        if hasattr(self, cmd.getfunc):  # if GuiDict method or property
            attr = attrgetter(cmd.getfunc)(self)
            if callable(attr):
                return attr, cmd.getargs
            else:

                def getfunc(c=self, a=cmd.getfunc):
                    return getattr(c, a)

                return getfunc, ()
        elif cmd.getfunc in self:  # if GuiDict.data entry

            def getfunc(c=self.data[cmd.getfunc]):
                return getattr(c, "value")

            return getfunc, ()
        elif hasattr(window_obj, cmd.getfunc):  # if ControlWindow method
            attr = attrgetter(cmd.getfunc)(window_obj)
            if callable(attr):
                return attr, ()
            else:

                def getfunc(c=window_obj, a=cmd.getfunc):
                    return getattr(c, a)

                return getfunc, ()
        elif cmd.dtype == str and not cmd.getargs:

            def getfunc(v=cmd.getfunc):
                return str(v)

            return getfunc, ()
        raise ValueError(f"could not identify '{cmd.getfunc}' of '{name}'")

    def _handle_tuple_getfunc(
        self, name: str, cmd: Command, system: System
    ) -> tuple[Callable | None, tuple]:
        """Handle the case where getfunc is a tuple or list (system device)."""
        cmd.getfunc = cast(tuple, cmd.getfunc)
        devname, funcname = cmd.getfunc
        attr = attrgetter(funcname)(system.devs[devname])
        if callable(attr):
            return attr, cmd.getargs
        else:

            def getfunc(c=system.devs[devname], a=funcname):
                return getattr(c, a)

            return getfunc, ()

    def panic(self) -> None:
        """
        Enable panic mode and put everyting to a save state.

        Should be overloaded by derived functions if needed.
        """
        self._panic = True
        self.enable_switch.setEnabled(False)

    def unpanic(self) -> None:
        """Make device operational again."""
        self.enable_switch.setEnabled(True)
        self._panic = False

    def refresh(self, count: int) -> None:
        """
        Update values from the device and show them in the GUI.

        This method has to be implementated by every derived class.

        It should contain code to refresh the GUI values a single time
        (no endless loop). If some items should be updated infrequently
        it can be done by performing a modulo operation on the 'count'
        argument. Also it should never access the GUI elements directly
        but use the variable value properties which trigger an update to
        the GUI correctly by emitting a signal.
        """
        # an example implementation
        # self["V2"].value = self.S["dev"].get_value_from_hardware_somehow()
        # if count % 10 == 0:
        #     self["V1"].value = self.S["dev"].get_another_value()


def linear_trend(
    timestamps: ArrayLike, data: ArrayLike, interval: float = 60
) -> tuple[float | None, float | None]:
    """
    Calculate the linear trend of the data in the last 'interval' seconds.

    Parameters
    ----------
    timestamps : array-like
      time stamps of data in Unix-time in seconds (e.g. from `time.time()`)
    data : array-like
      past data points (most recent data point has index 0!).
      shape is assumed to be same for the two arguments
    interval : float, optional
      time interval of the data points which should be considered. Older data
      points are ignored.

    Note: best use collections.deque and appendleft to generate the needed data

    Returns
    -------
    slope, stdev
      slope and standard deviation of past `interval` seconds. If there are
      insufficient data points to calculate the statistics each value will be
      `None`.
    """
    ret = (None, None)
    mask = (time.time() - numpy.asarray(timestamps)) < interval
    t, y = numpy.asarray(timestamps)[mask], numpy.asarray(data)[mask]
    if len(t) >= 2:
        if numpy.all([isinstance(el, numbers.Number) for el in y]):
            slope = numpy.mean(numpy.gradient(y, t))
            std = numpy.std(y)
            ret = (slope, std)
    return ret


def sendNotificationEmail(
    address: str, subject: str, msgtext: str, attachments: list[str | Path] = []
) -> None:
    """
    Send messages to a list of email addresses.

    Utility function that uses the sendmail command line function which has to
    be configured to work as intended.

    Parameters
    ----------
    address : str
     email adress(es) in a comma seperated list
    subject : str
     email subject
    msgtext : str
     email message, can contain HTML code including img-tags
     (-> attach the image file)
    attachments: list
     list of file names of things to attach to the email.
    """
    # a check for valid email adresses should be added here!
    if address == "":
        return
    msg = MIMEMultipart()
    msg["To"] = address
    msg["Subject"] = subject
    mimetxt = MIMEText(msgtext, "html")
    msg.attach(mimetxt)
    # add attachments (code adapted from
    # https://docs.python.org/3.4/library/email-examples.html)
    for fname in attachments:
        fpath = Path(fname)
        if not fpath.is_file():
            continue
        # Guess the content type based on the file's extension.  Encoding
        # will be ignored, although we should check for simple things like
        # gzip'd or compressed files.
        ctype, encoding = mimetypes.guess_type(fpath)
        if ctype is None or encoding is not None:
            # No guess could be made, or the file is encoded (compressed),
            # so use a generic bag-of-bits type.
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        if maintype == "text":
            with fpath.open() as fp:
                # Note: we should handle calculating the charset
                att = MIMEText(fp.read(), _subtype=subtype)
        elif maintype == "image":
            with fpath.open("rb") as fp:
                att = MIMEImage(fp.read(), _subtype=subtype)
            att.add_header("Content-ID", f"<{fpath.name}>")
        elif maintype == "audio":
            with fpath.open("rb") as fp:
                att = MIMEAudio(fp.read(), _subtype=subtype)
        else:
            with fpath.open("rb") as fp:
                att = MIMEBase(maintype, subtype)
                att.set_payload(fp.read())
            # Encode the payload using Base64
            encoders.encode_base64(att)
        # Set the filename parameter
        att.add_header("Content-Disposition", "attachment", filename=fpath.name)
        msg.attach(att)

    # read email config
    conf = config.matr1x.email
    context = ssl.create_default_context()

    try:
        if (
            conf.smtp_server is not None
            and conf.smtp_user is not None
            and conf.fromemail is not None
            and conf.password is not None
        ):
            with smtplib.SMTP_SSL(conf.smtp_server, conf.smtp_port, context=context) as server:
                server.login(conf.smtp_user, conf.password)
                server.send_message(msg, from_addr=conf.fromemail, to_addrs=address)
        elif os.name == "posix":
            p = Popen(["sendmail", "-t"], stdin=PIPE)
            p.communicate(msg.as_bytes())
            p.wait()
            logger.info("notification email %s sent to %s", msgtext, address)
        else:
            logger.error("no email configuration found; see documentation on how to set it up")
    except Exception:
        logger.exception("Ignoring error during sending email")


def control_main(
    name: str,
    window_class: "type[ControlWindow]",
    guidicts: GuiDict | type[GuiDict] | Sequence[type[GuiDict] | GuiDict] | None = None,
    extra_cmds: dict | None = None,
    lockfile: bool = True,
    package: str = "matr1x",
    **kwargs: Any,
) -> None:
    """
    Run main function of control GUI.

    This function exists to avoid duplication in all control GUIs.

    Parameters
    ----------
    name : str
        Identifier string used as Window title and for the lock file.
    window_class : ControlWindow
        Class derived from QMainWindow to be used to construct the GUI.
    guidicts : GuiDict, list or tuple of GuiDicts, optional
        GuiDict class(es) with the definition of the GUI.
    extra_cmds : dict, optional
        Dictionary with commands for the measurement interface. While
        most commands will be connected with the GuiDicts, those which
        do not fit there can be supplied here.
    lockfile : bool, optional
        Boolean flag to specify if a lockfile shall be created/checked
        to avoid multiple instances of the control GUI. Default is True.
    package : str, optional
        Package name to identify the desktop file. Default is "matr1x".
    **kwargs : dict
        Keyword arguments which are forwarded to the window_class
        constructor.
    """
    if sys.platform == "win32":
        try:
            from ctypes import windll

            myappid = f"python.{package}.{name}.version"
            windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except ImportError:
            pass

    app = MApplication(sys.argv)
    app.setDesktopFileName(f"python.{package}.{Path(sys.argv[0]).name}")

    if lockfile:
        # lock files are stored in a user specific cache directory
        # to ensure they are available even if no log folder exists
        lockdir = Path(
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
        )
        lockdir.mkdir(parents=True, exist_ok=True)
        lockfilename = lockdir / f"{package}_gui_{name}.lock"
        if lockfilename.exists():
            # check if process still running
            with lockfilename.open(encoding="utf-8") as lockf:
                otherpid = int(lockf.read())
            try:
                psutil.Process(otherpid)
                QMessageBox.critical(
                    QWidget(),
                    "Other instance running",
                    f"""Another instance of '{name}' was found running.
The control GUI can not start.
Kill the other process ({otherpid}) before restarting.""",
                )
                sys.exit()
            except psutil.NoSuchProcess:
                # this is the normal behavior in this case -> move on.
                pass
        # generate lockfile and write in the process ID
        with lockfilename.open("w", encoding="utf-8") as lockf:
            lockf.write(f"{os.getpid()}\n")

    kwargs["package"] = package
    logger.info("Starting GUI")
    with window_class(name, guidicts=guidicts, extra_cmds=extra_cmds, **kwargs):
        ret = app.exec()
    logger.info("Exiting GUI")
    if lockfile:
        # clean exit, remove lockfile
        if lockfilename.exists():
            lockfilename.unlink()
    sys.exit(ret)
