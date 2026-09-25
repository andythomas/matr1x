# This file is part of a software collection for data aquisition (matr1x).
# Copyright (C) 2006-2026 matr1x developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3.0, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Test the CodeEditor API surface without instantiating the widget."""

from matr1x.gui.editor import CodeEditor

REQUIRED_ATTRIBUTES = (
    "setPlainText",
    "toPlainText",
    "toggleLineComment",
    "find",
    "zoomIn",
    "zoomOut",
    "undo",
    "redo",
    "cut",
    "copy",
    "paste",
    "formatCode",
    "isModified",
    "setModified",
    "setReadOnly",
    "highlight",
    "removeHighlight",
    "setTheme",
    "supportedThemes",
    "enableTabCompletion",
    "setSystemInfo",
    "insertText",
    "returnIssues",
)


def test_CodeEditor_API():
    """
    Confirm the existence of all required CodeEditor methods.

    The checks run on the class, so no QApplication or widget instance is
    required.
    """
    missing = [name for name in REQUIRED_ATTRIBUTES if not hasattr(CodeEditor, name)]
    assert not missing, f"CodeEditor is missing: {', '.join(missing)}"
