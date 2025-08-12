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
"""Allow to write measurement scripts in Python."""

import ast
import logging
import os
import re
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
from os.path import basename, dirname
from typing import List, Optional, Tuple, Union

import autopep8
import pyflakes.checker
import pyflakes.messages
import pyflakes.reporter
from PyQt6.Qsci import QsciAPIs, QsciLexerPython, QsciScintilla
from PyQt6.QtCore import (
    QByteArray,
    QEvent,
    QObject,
    QRegularExpression,
    QSettings,
    QSize,
    Qt,
    QThread,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QFontDatabase,
    QKeyEvent,
    QKeySequence,
    QPalette,
    QTextCharFormat,
    QTextCursor,
)
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import matr1x
from matr1x.control.util import QtGracefulKiller
from matr1x.gui_util import (
    AboutBox,
    ConfigEditWidget,
    EmittingStream,
    MApplication,
    MetaDataDialog,
    MIcon,
    NumericalInputDialog,
    OutputDuplication,
    SystemListWidget,
    TerminationDialog,
    TextInputDialog,
    YesNoAbortDialog,
    check_config,
    detect_shortcut,
    get_application_instance,
    get_system_info,
    open_matrix_toml,
    save_messagebox,
)
from matr1x.scripts import matrix_preview
from matr1x.util import (
    create_temp_dir_with_symlinks,
    generate_script,
    generate_script_prefix_suffix,
    get_importable_module_name,
    set_correct_mac_appname,
)

logger = logging.getLogger(os.path.split(__file__)[-1])
logger.info("matrix-script starting")
config = matr1x.get_config_dict("matr1x.scripts.matrix-script")

# pyflakes warnings that trigger an error
LINTER_ERRORS = [
    "UndefinedName",
    "UndefinedExport",
    "UndefinedLocal",
    "DuplicateArgument",
    "ReturnOutsideFunction",
    "YieldOutsideFunction",
    "ContinueOutsideLoop",
    "BreakOutsideLoop",
    "IfTuple",
    "AssertTuple",
    "IsLiteral",
    "StringDotFormatExtraNamedArguments",
    "StringDotFormatMissingArgument",
    "StringDotFormatInvalidFormat",
    "StringDotFormatInvalidFormat",
    "PercentFormatInvalidFormat",
    "PercentFormatPositionalCountMismatch",
    "PercentFormatExtraNamedArguments",
    "PercentFormatMissingArgument",
]

# +1 here is needed since otherwise the last newline is not counted.
SCRIPT_OFFSET = len(generate_script_prefix_suffix("")[0].splitlines()) + 1

MAX_LINES_STATUS = 10000
# to test what a good limiting value is, use the following:
# ```
# for i in range(1000):
#   print(f"{i}" + 10*"snsnsnsnsn\n" + f"{i}")
#   wait(0.1)
# ```
# By setting the appropriate wait and multiplier, the highest expected
# number of lines/s can be set (here 110 lines/s). With this in place
# run matrix-script until it reaches the limit and see whether the
# display perforamnce of the GUI drops.


class Matr1xFunctionChecker(ast.NodeVisitor):
    """Implements ast-based function checker for matr1x functions."""

    def __init__(self, parent, indexes, settables, columns):
        self.parent = parent
        self.indexes = indexes
        self.settables = settables
        self.columns = columns
        self.errors = 0

    def visit_Call(self, node):
        """Reimplemented function to perform custom function checking."""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            lineno = node.func.lineno

            if func_name in ("set_value", "read_value", "trigger_value"):
                args = node.args

                num_required = 2 if func_name == "set_value" else 1

                scriptname = "sc"
                error_title = "value error"

                # make sure number of parameters is correct
                if len(args) < num_required:
                    if len(args) == 1 and num_required == 2:
                        # check for starred expression and report that
                        # these cannot be checked
                        if isinstance(args[0], ast.Starred):
                            error_text = (
                                "Cannot statically check starred expression"
                                f" <*{args[0].value.id}> in set_value call in"
                                f" line {args[0].lineno}"
                            )
                            self.parent.reporter.syntaxError(
                                scriptname,
                                "warning",
                                lineno,
                                0,
                                error_text,
                                0,
                            )
                            return
                        else:
                            self.errors += 1
                            error_text = "too few parameters."
                            self.parent.reporter.syntaxError(
                                scriptname,
                                error_title,
                                lineno,
                                0,
                                error_text,
                            )
                            return
                    else:
                        self.errors += 1
                        error_text = "too few parameters."
                        self.parent.reporter.syntaxError(
                            scriptname,
                            error_title,
                            lineno,
                            0,
                            error_text,
                        )
                        return
                elif len(args) > num_required:
                    self.errors += 1
                    error_text = "too many parameterz."
                    self.parent.reporter.syntaxError(
                        scriptname,
                        error_title,
                        lineno,
                        0,
                        error_text,
                    )
                    return
                col_name = args[0]
                if isinstance(col_name, ast.Constant):
                    value = col_name.value
                    if isinstance(value, int):
                        if value >= len(self.indexes) or value < 0:
                            # make sure column index is in valid range
                            self.errors += 1
                            error_text = f"index <{value}> beyond valid range."
                            self.parent.reporter.syntaxError(
                                scriptname,
                                error_title,
                                lineno,
                                0,
                                error_text,
                            )
                        elif not self.settables[value] and func_name == "set_value":
                            # make sure column is settable in set_value
                            self.errors += 1
                            error_text = f"index <{value}> not settable."
                            self.parent.reporter.syntaxError(
                                scriptname,
                                error_title,
                                lineno,
                                0,
                                error_text,
                            )
                    elif value not in self.columns:
                        # check validity of string based columns
                        self.errors += 1
                        error_text = f"<{value}> not a valid column name."
                        self.parent.reporter.syntaxError(
                            scriptname,
                            error_title,
                            lineno,
                            0,
                            error_text,
                        )
                    elif (
                        not self.settables[self.columns.index(value)] and func_name == "set_value"
                    ):
                        # make sure column is settable in set_value function
                        self.errors += 1
                        error_text = f"column <{value}> not settable."
                        self.parent.reporter.syntaxError(
                            scriptname,
                            error_title,
                            lineno,
                            0,
                            error_text,
                        )
                # could add check for defined variables at an earlier point
                # however, requires more sophisticated checking of variable
                # definitions
                # for now, remain with a printed warning to the user
                # could also be made into a warning
                # elif isinstance(col_name, ast.Name):...
                else:
                    error_text = (
                        f"Cannot statically check arg in {func_name} in line {col_name.lineno}"
                    )
                    self.parent.reporter.syntaxError(
                        scriptname, "warning", SCRIPT_OFFSET + lineno, 0, error_text, 0
                    )


class Matr1xApplication(MApplication):
    """Enable double-click open on a Mac."""

    openfile = pyqtSignal(str)

    def event(self, event):
        """Evaluate the event and open the file."""
        if event.type() == QEvent.Type.FileOpen:
            filename = event.file()
            self.openfile.emit(filename)
        return MApplication.event(self, event)


class DroppableWidget(QWidget):
    """Allow drag and drop of files."""

    fileDropped = pyqtSignal(str)  # Custom signal to emit file path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)  # Enable drag and drop for this widget

    def is_valid_extension(self, file_path):
        """Check is extension is valid."""
        return file_path.endswith(MainWindow.extension)

    def dragEnterEvent(self, event):
        """Enable drag and drop (1)."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Enable drag and drop (2)."""
        urls = event.mimeData().urls()
        if len(urls) == 1:
            file_path = urls[0].toLocalFile()
            if self.is_valid_extension(file_path):
                self.fileDropped.emit(file_path)
            else:
                QMessageBox.warning(
                    self,
                    "Invalid Action",
                    f"Only files with {MainWindow.extension} extension can be dropped.",
                )
        else:
            QMessageBox.warning(self, "Multiple Files", "Please drop only a single file.")


class TerminalOutput(QTextEdit):
    """Custom class for terminal-like text output."""

    def __init__(self) -> None:
        """Init the class with a mono-spaced font and respect theme."""
        super().__init__()
        self.setReadOnly(True)
        mono_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono_font.setPointSizeF(self.font().pointSize())
        self.setFont(mono_font)
        self.updateColors()

    def updateColors(self) -> None:
        """Update terminal colors based on system theme."""
        palette = self.palette()
        text_edit = QTextEdit()
        text_edit.setEnabled(False)
        changed_palette = text_edit.palette()
        palette.setColor(
            QPalette.ColorRole.Base,
            QColor(changed_palette.color(QPalette.ColorRole.Base)),
        )
        self.setPalette(palette)

    def changeEvent(self, event) -> None:
        """Detect theme change event."""
        if event.type() == event.Type.PaletteChange:
            self.updateColors()
        super().changeEvent(event)


class CustomReporter(pyflakes.reporter.Reporter):
    """Create custom reporter class based on pyflakes."""

    def __init__(self, stream, hook):
        """
        Init the custom reporter.

        Only use a single stream from errors and warnings and
        provide a hook to handle the linter errors.

        Parameters
        ----------
            hook : function
                callback to call on script errors. Should accept the line,
                column (cursor position), a message, its arguments, and
                a number which styles the response
        """
        super().__init__(stream, stream)
        self.linter_hook = hook

    def flake(self, message):
        """
        Reimplement the flaker function.

        Called if formatting or similar error is found (naming etc.).
        """
        style = 0
        if message.__class__.__name__ in LINTER_ERRORS:
            style = 1
        self.linter_hook(
            message.lineno - SCRIPT_OFFSET,
            message.col - 4,
            message.message % message.message_args,
            message.message_args,
            style,
        )

    def syntaxError(self, filename, msg, lineno, offset, text, style=1):
        """
        Reimplement the syntax error function.

        Handles the messages and properly initializes the linter hook.
        """
        if text is None:
            line = None
        else:
            line = text.splitlines()[-1]

        m = re.search(r"line (\d+)", msg)
        if m is not None:
            lineno = int(m.groups(0)[0])
            line = None
        else:
            # lineno might be None if the error was during tokenization
            # lineno might be 0 if the error came from stdin
            lineno = max(lineno or 0, 1)

        lineno -= SCRIPT_OFFSET

        msg = re.sub(r"line (\d+)", f"line {lineno + 1}", msg)

        if offset is not None:
            if offset >= 4:
                offset -= 5
        else:
            offset = 0
        if line is not None:
            ret = (f"{msg} : {line.lstrip()}", (f"{line.lstrip()[offset:]}",))
        else:
            ret = (f"{msg}", ("",))
        self.linter_hook(lineno, offset, *ret, style)


# code of the rxIndex function, CompleterPython and QScintillaCustom classes
# unless otherwise noted adapted from the eric7 editor
# https://eric-ide.python-projects.org/index.html
# -*- coding: utf-8 -*-
# Copyright (c) 2007 - 2023 Detlev Offenbach <detlev@die-offenbachs.de>
# licensed under GPLv3
#
def rxIndex(rx, txt):
    """
    Get the index (start position) of a regular expression match within some text.

    Parameters
    ----------
    rx : re.Pattern
        regular expression object as created by re.compile()
    txt : str
        text to be scanned

    Returns
    -------
    return : int
        start position of the match or -1 indicating no match was found
    """
    match = rx.search(txt)
    if match is None:
        return -1
    else:
        return match.start()


class CompleterPython(QObject):
    # adapted from
    # https://hg.die-offenbachs.homelinux.org/eric/file/eric7/src/eric7/QScintilla/TypingCompleters/CompleterPython.py
    """Class implementing a python completer."""

    def __init__(self, editor, parent=None):
        """
        Init the Python completer.

        Parameters
        ----------
        editor : QScintilla.Editor
            Editor reference to the editor object
        parent : QObject
            Reference to the parent object. If parent is None, we set the editor as the parent.
        """
        if parent is None:
            parent = editor

        super().__init__(parent)

        self.editor = editor
        self.enabled = False

        self.__defRX = re.compile(r"^[ \t]*(async[ \t]+)?(def|cdef|cpdef) \w+\(")
        self.__defSelfRX = re.compile(
            r"^[ \t]*(async[ \t]+)?(def|cdef|cpdef) \w+\([ \t]*self[ \t]*[,)]"
        )
        self.__defClsRX = re.compile(
            r"^[ \t]*(async[ \t]+)?(def|cdef|cpdef) \w+\([ \t]*cls[ \t]*[,)]"
        )
        self.__classRX = re.compile(r"^[ \t]*(cdef[ \t]+)?class \w+[(:]")
        self.__importRX = re.compile(r"^[ \t]*from [\w.]+ ")
        self.__classmethodRX = re.compile(r"^[ \t]*@classmethod")
        self.__staticmethodRX = re.compile(r"^[ \t]*@staticmethod")

        self.__defOnlyRX = re.compile(r"^[ \t]*def ")

        self.__ifRX = re.compile(r"^[ \t]*if ")
        self.__elifRX = re.compile(r"^[ \t]*elif ")
        self.__elseRX = re.compile(r"^[ \t]*else:")

        self.__tryRX = re.compile(r"^[ \t]*try:")
        self.__finallyRX = re.compile(r"^[ \t]*finally:")
        self.__exceptRX = re.compile(r"^[ \t]*except ")
        self.__exceptcRX = re.compile(r"^[ \t]*except:")

        self.__whileRX = re.compile(r"^[ \t]*while ")
        self.__forRX = re.compile(r"^[ \t]*(async[ \t]+)?for ")

        self.__trailingBlankRe = re.compile(r"(?:,)(\s*)\r?\n")

        self.__openBrackets = ("(", "[", "{")
        self.__closeBrackets = (")", "]", "}")

        # configure completer, see eric7 documentation for behavior
        self.__insertClosingBrace = False
        self.__indentBrace = True
        self.__skipBrace = True
        self.__insertQuote = False
        self.__dedentElse = True
        self.__dedentExcept = True
        self.__py24StyleTry = True
        self.__insertImport = True
        self.__insertSelf = True
        self.__insertBlank = False
        self.__colonDetection = True
        self.__dedentDef = True

    def setEnabled(self, enable):
        """
        Public slot to set the enabled state.

        Parameters
        ----------
        enable : bool
            flag indicating the new enabled state
        """
        if enable:
            if not self.enabled:
                self.editor.SCN_CHARADDED.connect(self.charAdded)
        else:
            if self.enabled:
                self.editor.SCN_CHARADDED.disconnect(self.charAdded)
        self.enabled = enable

    def isEnabled(self):
        """
        Public method to get the enabled state.

        Returns
        -------
        state : bool
            enabled state
        """
        return self.enabled

    def charAdded(self, charNumber):
        """
        Public slot called to handle the user entering a character.

        Parameters
        ----------
        charNumber : int
            value of the character entered
        """
        char = chr(charNumber)
        if char not in ["(", ")", "{", "}", "[", "]", " ", ",", "'", '"', "\n", ":"]:
            return  # take the short route

        line, col = self.editor.getCursorPosition()

        if (
            self.__inComment(line, col)
            or (char != '"' and self.__inDoubleQuotedString())
            or (char != '"' and self.__inTripleDoubleQuotedString())
            or (char != "'" and self.__inSingleQuotedString())
            or (char != "'" and self.__inTripleSingleQuotedString())
        ):
            return

        # open parenthesis
        # insert closing parenthesis and self
        if char == "(":
            txt = self.editor.text(line)[:col]
            self.editor.beginUndoAction()
            if self.__insertSelf and self.__defRX.fullmatch(txt) is not None:
                if self.__isClassMethodDef():
                    self.editor.insert("cls")
                    self.editor.setCursorPosition(line, col + 3)
                elif self.__isStaticMethodDef():
                    # nothing to insert
                    pass
                elif self.__isClassMethod():
                    self.editor.insert("self")
                    self.editor.setCursorPosition(line, col + 4)
            if self.__insertClosingBrace:
                if self.__defRX.fullmatch(txt) is not None or (
                    self.__classRX.fullmatch(txt) is not None and txt.endswith("(")
                ):
                    self.editor.insert("):")
                else:
                    self.editor.insert(")")
            self.editor.endUndoAction()

        # closing parenthesis
        # skip matching closing parenthesis
        elif char in [")", "}", "]"]:
            txt = self.editor.text(line)
            if col < len(txt) and char == txt[col] and self.__skipBrace:
                self.editor.setSelection(line, col, line, col + 1)
                self.editor.removeSelectedText()

        # space
        # insert import, dedent to if for elif, dedent to try for except,
        # dedent def
        elif char == " ":
            txt = self.editor.text(line)[:col]
            if self.__insertImport and self.__importRX.fullmatch(txt):
                self.editor.beginUndoAction()
                if self.__importBraceType:
                    self.editor.insert("import ()")
                    self.editor.setCursorPosition(line, col + 8)
                else:
                    self.editor.insert("import ")
                    self.editor.setCursorPosition(line, col + 7)
                self.editor.endUndoAction()
            elif self.__dedentElse and self.__elifRX.fullmatch(txt):
                self.__dedentToIf()
            elif self.__dedentExcept and self.__exceptRX.fullmatch(txt):
                self.__dedentExceptToTry()
            elif self.__dedentDef and self.__defOnlyRX.fullmatch(txt):
                self.__dedentDefStatement()

        # comma
        # insert blank
        elif char == "," and self.__insertBlank:
            self.editor.insert(" ")
            self.editor.setCursorPosition(line, col + 1)

        # open curly brace
        # insert closing brace
        elif char == "{" and self.__insertClosingBrace:
            self.editor.insert("}")

        # open bracket
        # insert closing bracket
        elif char == "[" and self.__insertClosingBrace:
            self.editor.insert("]")

        # double quote
        # insert double quote
        elif char == '"' and self.__insertQuote:
            self.editor.insert('"')

        # quote
        # insert quote
        elif char == "'" and self.__insertQuote:
            self.editor.insert("'")

        # colon
        # skip colon, dedent to if for else:
        elif char == ":":
            text = self.editor.text(line)
            if col < len(text) and char == text[col]:
                if self.__colonDetection:
                    self.editor.setSelection(line, col, line, col + 1)
                    self.editor.removeSelectedText()
            else:
                txt = text[:col]
                if self.__dedentElse and self.__elseRX.fullmatch(txt):
                    self.__dedentElseToIfWhileForTry()
                elif self.__dedentExcept and self.__exceptcRX.fullmatch(txt):
                    self.__dedentExceptToTry()
                elif self.__dedentExcept and self.__finallyRX.fullmatch(txt):
                    self.__dedentFinallyToTry()

        # new line
        # indent to opening brace
        elif char == "\n" and self.__indentBrace:
            txt = self.editor.text(line - 1)
            if self.__insertBlank and self.__trailingBlankRe.search(txt):
                match = self.__trailingBlankRe.search(txt)
                if match is not None:
                    startBlanks = match.start(1)
                    endBlanks = match.end(1)
                    if startBlanks != -1 and startBlanks != endBlanks:
                        # previous line ends with whitespace, e.g. caused by
                        # blank insertion above
                        self.editor.setSelection(line - 1, startBlanks, line - 1, endBlanks)
                        self.editor.removeSelectedText()
                        # get the line again for next check
                        txt = self.editor.text(line - 1)

                    self.editor.setCursorPosition(line, 0)
                    self.editor.editorCommand(QsciScintilla.SCI_VCHOME)

            if re.search(":\r?\n", txt) is None:
                self.editor.beginUndoAction()
                stxt = txt.strip()
                if stxt and stxt[-1] in self.__openBrackets:
                    # indent one more level
                    self.editor.indent(line)
                    self.editor.editorCommand(QsciScintilla.SCI_VCHOME)
                else:
                    # indent to the level of the opening brace
                    openCount = len(re.findall("[({[]", txt))
                    closeCount = len(re.findall(r"[)}\]]", txt))
                    if openCount > closeCount:
                        openCount = 0
                        closeCount = 0
                        openList = list(re.finditer("[({[]", txt))
                        index = len(openList) - 1
                        while index > -1 and openCount == closeCount:
                            lastOpenIndex = openList[index].start()
                            txt2 = txt[lastOpenIndex:]
                            openCount = len(re.findall("[({[]", txt2))
                            closeCount = len(re.findall(r"[)}\]]", txt2))
                            index -= 1
                        if openCount > closeCount and lastOpenIndex > col:
                            self.editor.insert(" " * (lastOpenIndex - col + 1))
                            self.editor.setCursorPosition(line, lastOpenIndex + 1)
                self.editor.endUndoAction()

    def __dedentToIf(self):
        """
        Dedent the last line to match that of the last if statement, private.

        Goes back to the last if statement with less (or equal)
        indentation.
        """
        line, col = self.editor.getCursorPosition()
        indentation = self.editor.indentation(line)
        ifLine = line - 1
        while ifLine >= 0:
            txt = self.editor.text(ifLine)
            edInd = self.editor.indentation(ifLine)
            if rxIndex(self.__elseRX, txt) == 0 and edInd <= indentation:
                indentation = edInd - 1
            elif (
                rxIndex(self.__ifRX, txt) == 0 or rxIndex(self.__elifRX, txt) == 0
            ) and edInd <= indentation:
                self.editor.cancelList()
                self.editor.setIndentation(line, edInd)
                break
            ifLine -= 1

    def __dedentElseToIfWhileForTry(self):
        """
        Dedent the line of the else statement, private.

        Matches the indent of the last if, while, for or try statement
        with less (or equal) indentation.
        """
        line, col = self.editor.getCursorPosition()
        indentation = self.editor.indentation(line)
        if line > 0:
            prevInd = self.editor.indentation(line - 1)
        ifLine = line - 1
        while ifLine >= 0:
            txt = self.editor.text(ifLine)
            edInd = self.editor.indentation(ifLine)
            if (rxIndex(self.__elseRX, txt) == 0 and edInd <= indentation) or (
                rxIndex(self.__elifRX, txt) == 0 and edInd == indentation and edInd == prevInd
            ):
                indentation = edInd - 1
            elif (
                rxIndex(self.__ifRX, txt) == 0
                or rxIndex(self.__whileRX, txt) == 0
                or rxIndex(self.__forRX, txt) == 0
                or rxIndex(self.__tryRX, txt) == 0
            ) and edInd <= indentation:
                self.editor.cancelList()
                self.editor.setIndentation(line, edInd)
                break
            ifLine -= 1

    def __dedentExceptToTry(self):
        """
        Dedents the line of an except statement, private.

        Matches the indent of the last try statement with less (or
        equal) indentation.
        """
        line, col = self.editor.getCursorPosition()
        indentation = self.editor.indentation(line)
        tryLine = line - 1
        while tryLine >= 0:
            txt = self.editor.text(tryLine)
            edInd = self.editor.indentation(tryLine)
            if (
                rxIndex(self.__exceptcRX, txt) == 0 or rxIndex(self.__finallyRX, txt) == 0
            ) and edInd <= indentation:
                indentation = edInd - 1
            elif (
                rxIndex(self.__exceptRX, txt) == 0 or rxIndex(self.__tryRX, txt) == 0
            ) and edInd <= indentation:
                self.editor.cancelList()
                self.editor.setIndentation(line, edInd)
                break
            tryLine -= 1

    def __dedentFinallyToTry(self):
        """
        Dedents the line of an finally statement, private.

        Matches the indent of the last try statement with less (or
        equal) indentation.
        """
        line, col = self.editor.getCursorPosition()
        indentation = self.editor.indentation(line)
        tryLine = line - 1
        while tryLine >= 0:
            txt = self.editor.text(tryLine)
            edInd = self.editor.indentation(tryLine)
            if rxIndex(self.__finallyRX, txt) == 0 and edInd <= indentation:
                indentation = edInd - 1
            elif (
                rxIndex(self.__tryRX, txt) == 0
                or rxIndex(self.__exceptcRX, txt) == 0
                or rxIndex(self.__exceptRX, txt) == 0
            ) and edInd <= indentation:
                self.editor.cancelList()
                self.editor.setIndentation(line, edInd)
                break
            tryLine -= 1

    def __dedentDefStatement(self):
        """
        Dedents the line of the def statement, private.

        Matches the indent of a previous def statement or class
        statement.
        """
        line, col = self.editor.getCursorPosition()
        indentation = self.editor.indentation(line)
        tryLine = line - 1
        inMultiLineString = False
        while tryLine >= 0:
            txt = self.editor.text(tryLine)
            if txt.count('"""') % 2 != 0 or txt.count("'''") % 2 != 0:
                inMultiLineString = not inMultiLineString
            if not inMultiLineString:
                edInd = self.editor.indentation(tryLine)
                newInd = -1
                if rxIndex(self.__defRX, txt) == 0 and edInd < indentation:
                    newInd = edInd
                elif rxIndex(self.__classRX, txt) == 0 and edInd < indentation:
                    newInd = edInd + (self.editor.indentationWidth() or self.editor.tabWidth())
                if newInd >= 0:
                    self.editor.cancelList()
                    self.editor.setIndentation(line, newInd)
                    break
            tryLine -= 1

    def __isClassMethod(self):
        """
        Private method to check, if the user is defining a class method.

        Returns
        -------
        flag : bool
            Indicates the definition of a class method
        """
        line, col = self.editor.getCursorPosition()
        indentation = self.editor.indentation(line)
        curLine = line - 1
        inMultiLineString = False
        while curLine >= 0:
            txt = self.editor.text(curLine)
            if txt.count('"""') % 2 != 0 or txt.count("'''") % 2 != 0:
                inMultiLineString = not inMultiLineString
            if not inMultiLineString:
                if (
                    (rxIndex(self.__defSelfRX, txt) == 0 or rxIndex(self.__defClsRX, txt) == 0)
                    and self.editor.indentation(curLine) == indentation
                ) or (
                    rxIndex(self.__classRX, txt) == 0
                    and self.editor.indentation(curLine) < indentation
                ):
                    return True
                elif (
                    rxIndex(self.__defRX, txt) == 0
                    and self.editor.indentation(curLine) <= indentation
                ):
                    return False
            curLine -= 1
        return False

    def __isClassMethodDef(self):
        """
        Check if the user is defing a class method (@classmethod), private.

        Returns
        -------
        flag : bool
            flag indicating the definition of a class metho
        """
        line, col = self.editor.getCursorPosition()
        indentation = self.editor.indentation(line)
        curLine = line - 1
        if (
            rxIndex(self.__classmethodRX, self.editor.text(curLine)) == 0
            and self.editor.indentation(curLine) == indentation
        ):
            return True
        return False

    def __isStaticMethodDef(self):
        """
        Check if the user is defing a static method (@staticmethod), private.

        Parameters
        ----------
        flag : bool
            flag indicating the definition of a static method
        """
        line, col = self.editor.getCursorPosition()
        indentation = self.editor.indentation(line)
        curLine = line - 1
        if (
            rxIndex(self.__staticmethodRX, self.editor.text(curLine)) == 0
            and self.editor.indentation(curLine) == indentation
        ):
            return True
        return False

    def __inComment(self, line, col):
        """
        Check if the cursor is inside a comment, private.

        Parameters
        ----------
        line : int
            current line
        col : in
            current position within line

        Returns
        -------
        flag : bool
            indicates if the cursor is inside a comment
        """
        txt = self.editor.text(line)
        if col == len(txt):
            col -= 1
        while col >= 0:
            if txt[col] == "#":
                return True
            col -= 1
        return False

    def __inDoubleQuotedString(self):
        """
        Check if the cursor is within a double quoted string, private.

        Returns
        -------
        flag : bool
            indicates if the cursor is inside a double quoted string
        """
        return self.editor.currentStyle() == QsciLexerPython.DoubleQuotedString

    def __inTripleDoubleQuotedString(self):
        """
        Check if the cursor is within a triple double quoted string, private.

        Returns
        -------
        flag : bool
            indicates if the cursor is inside a triple double quoted string
        """
        return self.editor.currentStyle() == QsciLexerPython.TripleDoubleQuotedString

    def __inSingleQuotedString(self):
        """
        Check if the cursor is within a single quoted string, private.

        Returns
        -------
        flag : bool
            indicating, if the cursor is inside a single quoted string (boolean)
        """
        return self.editor.currentStyle() == QsciLexerPython.SingleQuotedString

    def __inTripleSingleQuotedString(self):
        """
        Check if the cursor is within a triple single quoted string.

        Returns
        -------
        flag : bool
            indicates, if the cursor is inside a triple single quoted
            string (boolean)
        """
        return self.editor.currentStyle() == QsciLexerPython.TripleSingleQuotedString


class QScintillaCustom(QsciScintilla, DroppableWidget):
    # adapted from https://hg.die-offenbachs.homelinux.org/eric/file/eric7/src/eric7/QScintilla/QsciScintillaCompat.py
    # with commenting functionality from https://github.com/matkuki/qscintilla_docs/blob/master/examples/commenting.py
    # both licensed under GPLv3
    """Custom QSciScintilla editor with basic commenting functionality."""

    comment_string = "# "
    line_ending = "\n"
    fileDropped = pyqtSignal(str)

    def __init__(self, stream, parent):
        super().__init__(parent=parent)
        self.parent = parent
        self.output_stream = stream
        self.reporter = CustomReporter(self.output_stream, self.handle_linter)
        self.parent = parent

    def keyPressEvent(self, event):
        """Check for shortcuts such as linting."""
        key = event.key()
        if detect_shortcut(event, "Ctrl+/"):
            self.toggle_commenting()
            return
        if detect_shortcut(event, "Ctrl+Shift+7"):
            self.toggle_commenting()
            return
        if key == Qt.Key.Key_QuoteDbl:
            if bool(self.SendScintilla(self.SCI_GETSELECTIONEMPTY)) is False:
                self.add_quotes('"')
                return
        if key == Qt.Key.Key_Apostrophe:
            if bool(self.SendScintilla(self.SCI_GETSELECTIONEMPTY)) is False:
                self.add_quotes("'")
                return
        super().keyPressEvent(event)

    def run_autopep8(self):
        """Run the formatter autopep8."""
        self.setText(autopep8.fix_code(self.text(), options=None))
        return

    def run_linter(self):
        """
        Call the linter for the editor view.

        Convenience function to call the linter, generates the script
        according to what matrix-script would do when one presses the
        run button. Custom definitions for parameters that are passed by
        the process are made here.

        Returns -1 if a syntax error was found
        """
        # the second check is required to no crash the len_last
        if self.text().strip() == "" or len(self.text().strip().splitlines()) <= 0:
            print("Nothing to lint")
            return 0
        # remove potential annotations from previous linting run
        self.clearAnnotations()
        ret_err = 0
        last_line = len(self.text().splitlines()) - 1
        len_last = len(self.text().splitlines()[-1])
        # remove potential indicators from previous linting run
        for i in range(2):
            self.clearIndicatorRange(0, 0, last_line, len_last, i)
        # add initial definitions that are passed to the script
        # externally to avoid linter errors, make sure not to add an
        # additional line here
        script = "_interrupt=lambda x, s:x;_print=lambda x:x;"
        script += "_input=lambda x:x;_report_line=lambda x:x;"
        script += "_report_path=lambda x:x; _status='';"
        script += "_meta_data='';_scriptname='';_script='';"
        script += generate_script("", self.text())
        # reimplement the pyflakes.api.check function
        scriptname = "sc"
        try:
            tree = ast.parse(script, filename=scriptname)
        except SyntaxError as e:
            self.reporter.syntaxError(scriptname, e.args[0], e.lineno, e.offset, e.text)
            print("Linter found a syntax error.")
            return -1
        except Exception as e:
            self.reporter.syntaxError(
                scriptname,
                "Problem decoding source",
                SCRIPT_OFFSET,
                0,
                "Error during linting.",
            )
            print(f"Linter found the following error:\n{e}.")
            return -1
        checker = Matr1xFunctionChecker(self, *self.parent.get_settables())
        checker.visit(tree)
        if checker.errors > 0:
            print_str = f"Linter found {checker.errors} value error(s) "
            ret_err = -1
        else:
            print_str = "Linter found no value error "
        w = pyflakes.checker.Checker(tree, filename=scriptname)
        w.messages.sort(key=lambda m: m.lineno)
        n_err = 0
        for warning in w.messages:
            self.reporter.flake(warning)
            if warning.__class__.__name__ in LINTER_ERRORS:
                ret_err = -1
                n_err += 1
        n_msg = len(w.messages)
        n_warn = n_msg - n_err
        print_str += "and "
        if n_msg == 0:
            print_str += "no syntax errors."
            print(print_str)
            return ret_err
        if n_err > 0:
            print_str += f"{n_err} error{'s' if n_err > 1 else ''}"
            print_str += " and " if n_warn > 0 else "."
        if n_warn > 0:
            print_str += f"{n_warn} warning{'s' if n_warn > 1 else ''}."
        print(print_str)
        return ret_err

    def handle_linter(self, line, col, message, message_args, style):
        """Call back function that is passed to the reporter of the linter."""
        if line < 0 or line >= len(self.text().splitlines()):
            error_message = "error outside script: " + message
            self.parent.print_colored(error_message)
            return
        # remove comment to add verbose output of linter to status_preview
        # print(f"Error in line {line+1} at position {col+1} : \n  {message}")
        self.indicatorDefine(QsciScintilla.IndicatorStyle.FullBoxIndicator, style)
        offset = 0
        if len(message_args) > 0:
            # TODO: Look at all message_args and see which make sense to
            # include here
            if isinstance(message_args[0], (str, tuple, list)):
                offset = len(message_args[0])
        self.fillIndicatorRange(line, col, line, col + offset, style)
        self.annotate(line, message, style)
        # move the cursor to the position of the last error
        self.setCursorPosition(line, col)

    def add_quotes(self, char):
        """Handle adding single or double quotes."""
        selections = self.get_selections()
        if selections is None:
            return
        while self.merge_test(selections) is True:
            selections = self.merge_selections(selections)
        self.beginUndoAction()
        for i, sel in enumerate(selections):
            self.setSelection(sel[0], sel[2], sel[1], sel[3])
            # Add the commenting char to the beginning and end of the
            # selected text
            self.replaceSelectedText(char + self.selectedText() + char)
        self.SendScintilla(self.SCI_CLEARSELECTIONS)
        for i, sel in enumerate(selections):
            start_index = self.positionFromLineIndex(sel[0], sel[2])
            # if beginning and end of selection are in the same line, two
            # symbols are added
            increment = 1 if sel[0] != sel[1] else 2
            end_index = self.positionFromLineIndex(sel[1], sel[3] + increment)
            if i == 0:
                self.SendScintilla(self.SCI_SETSELECTION, start_index, end_index)
            else:
                self.SendScintilla(self.SCI_ADDSELECTION, start_index, end_index)
        # Set the end of the undo action
        self.endUndoAction()

    def toggle_commenting(self):
        """
        Handle the comment toggling using # comments.

        If one of the lines is not commented, adds a # to one line,
        otherwise removes one from all lines.
        """
        # Check if the selections are valid
        selections = self.get_selections()
        if selections is None:
            return
        # Merge overlapping selections
        while self.merge_test(selections) is True:
            selections = self.merge_selections(selections)
        # Start the undo action that can undo all commenting at once
        self.beginUndoAction()
        # Loop over selections and comment them
        for i, sel in enumerate(selections):
            all_commented = True
            # check if any of the lines is not commented, if so comment all
            # but empty selected lines
            if sel[0] != sel[1] and sel[3] == 0:
                # check if cursor is at the very beginning of the line and
                # more than one line is selected
                lmax = sel[1]
            else:
                lmax = sel[1] + 1
            for line in range(sel[0], lmax):
                line_text = self.text(line).lstrip()
                if line_text == "":
                    continue
                if not line_text.startswith(self.comment_string):
                    all_commented = False
            self.set_commenting(
                sel[0], lmax - 1, self._uncomment if all_commented else self._comment
            )
        # Select back the previously selected regions
        self.SendScintilla(self.SCI_CLEARSELECTIONS)
        # shift depending on the comment
        shift = -2 if all_commented else 2
        for i, sel in enumerate(selections):
            # shift the start index by the commenting string
            start_index = self.positionFromLineIndex(sel[0], sel[2] + shift)
            if sel[3] == 0:
                end_index = self.positionFromLineIndex(sel[1], sel[3])
            else:
                end_index = self.positionFromLineIndex(sel[1], sel[3] + shift)
            if i == 0:
                self.SendScintilla(self.SCI_SETSELECTION, start_index, end_index)
            else:
                self.SendScintilla(self.SCI_ADDSELECTION, start_index, end_index)
        # Set the end of the undo action
        self.endUndoAction()

    def get_selections(self):
        """Obtain the selections."""
        # Get the selection and store them in a list
        selections = []
        for i in range(self.SendScintilla(self.SCI_GETSELECTIONS)):
            selection = (
                self.SendScintilla(self.SCI_GETSELECTIONNSTART, i),
                self.SendScintilla(self.SCI_GETSELECTIONNEND, i),
            )
            # Add selection to list
            from_line, from_index = self.lineIndexFromPosition(selection[0])
            to_line, to_index = self.lineIndexFromPosition(selection[1])
            selections.append((from_line, to_line, from_index, to_index))
        selections.sort()
        # Return selection list
        return selections

    def merge_test(self, selections):
        """Test if merging of selections is needed."""
        for i in range(1, len(selections)):
            # Get the line numbers
            previous_end_line = selections[i - 1][1]
            current_start_line = selections[i][0]
            if previous_end_line == current_start_line:
                return True
        # Merging is not needed
        return False

    def merge_selections(self, selections):
        """Merge selections with overlapping lines."""
        # Test if merging is required
        if len(selections) < 2:
            return selections
        merged_selections = []
        skip_flag = False
        for i in range(1, len(selections)):
            # Get the line numbers
            previous_start_line = selections[i - 1][0]
            previous_end_line = selections[i - 1][1]
            current_start_line = selections[i][0]
            current_end_line = selections[i][1]
            # Test for merge
            if previous_end_line == current_start_line and skip_flag is False:
                merged_selections.append((previous_start_line, current_end_line))
                skip_flag = True
            else:
                if skip_flag is False:
                    merged_selections.append((previous_start_line, previous_end_line))
                skip_flag = False
                # Add the last selection only if it was not merged
                if i == (len(selections) - 1):
                    merged_selections.append((current_start_line, current_end_line))
        # Return the merged selections
        return merged_selections

    def set_block_commenting(self, from_line, to_line, from_index, to_index, char):
        """Set block commenting."""
        # Set the selection from the beginning of the cursor line
        # to the end of the last selection line
        self.setSelection(from_line, from_index, to_line, to_index)
        # Get the selected text and split it into lines
        selected_text = self.selectedText()
        replace_text = char + selected_text + char
        # Replace the whole selected text with the merged lines
        # containing the commenting characters
        self.replaceSelectedText(replace_text)

    def set_commenting(self, arg_from_line, arg_to_line, func):
        """Set commenting."""
        # Get the cursor information
        from_line = arg_from_line
        to_line = arg_to_line
        # Check if ending line is the last line in the editor
        last_line = to_line
        if last_line == self.lines() - 1:
            to_index = len(self.text(to_line))
        else:
            to_index = len(self.text(to_line)) - 1
        # Set the selection from the beginning of the cursor line
        # to the end of the last selection line
        self.setSelection(from_line, 0, to_line, to_index)
        # Get the selected text and split it into lines
        selected_text = self.selectedText()
        if selected_text == "":
            return
        selected_list = selected_text.splitlines()
        # Find the smallest indent level
        indent_levels = []
        for line in selected_list:
            indent_levels.append(len(line) - len(line.lstrip()))
        min_indent_level = min(indent_levels)
        # Add the commenting character to every line
        for i, line in enumerate(selected_list):
            selected_list[i] = func(line, min_indent_level)
        # Replace the whole selected text with the merged lines
        # containing the commenting characters
        replace_text = self.line_ending.join(selected_list)
        self.replaceSelectedText(replace_text)

    def _comment(self, line, indent_level):
        if line.strip() != "":
            return line[:indent_level] + self.comment_string + line[indent_level:]
        else:
            return line

    def _uncomment(self, line, indent_level):
        if line.strip().startswith(self.comment_string):
            return line.replace(self.comment_string, "", 1)
        else:
            return line

    def styleAt(self, pos):
        """
        Public method to get the style at a position in the text.

        Parameters
        ----------
        pos : int
            position in the text

        Returns
        -------
        style : int
            style at the requested position or 0, if the position
            is negative or past the end of the document
        """
        return self.SendScintilla(QsciScintilla.SCI_GETSTYLEAT, pos)

    def currentStyle(self):
        """
        Public method to get the style at the current position.

        Returns
        -------
        style : int
            style at the current position
        """
        return self.styleAt(self.currentPosition())

    def currentPosition(self):
        """
        Public method to get the current position.

        Returns
        -------
        position : int
            Absolute position of the cursor (integer)
        """
        return self.SendScintilla(QsciScintilla.SCI_GETCURRENTPOS)

    def editorCommand(self, cmd):
        """
        Public method to perform a simple editor command.

        Parameters
        ----------
        cmd : int
            the scintilla command to be performed (integer)
        """
        self.SendScintilla(cmd)


class CustomLexer(QsciLexerPython):
    """Create a custom lexer for the matrix-script editor."""

    def keywords(self, val):
        """Reimplement matrix_script custom commands for code highlighting."""
        if 2 != val:
            return super().keywords(val)
        return (
            "init_datafile measure_system wait set_value trigger_value "
            "read_value meta_data devs system input input_bool input_numerical end_script"
        )


class CustomQsciAPI(QsciAPIs):
    """Implement textual API information for call tips and auto-completion."""

    # Definition of custom commands that are supposed to be autocompleted
    autocompletions = [
        "system",
        "meta_data",
        "meta_data['creator']",
        "meta_data['identifier']",
        "meta_data['relation']",
        "meta_data['description']",
        "devs",
        "wait(duration: float = None, until: str | datetime = None, message: str = '', silent: float = 10)",  # noqa: E501
        "end_script(finished: bool = None)",
        "input(query: str = '', timeout: float = float('inf'), default_value: str = '')",
        "input_bool(query: str = '', timeout: float = float('inf'), default_value: str = 'yes')",
        "input_numerical(query: str = '', timeout: float = float('inf'), default_value: float = 0.0, min_value: float=-100e9, max_value: float=100e9, step: float=1.0, decimals: int=2)",  # noqa: E501
        "init_datafile(filename: str, comment: str = '', append: bool = False, print_header: bool = True, ntot: int = None)",  # noqa: E501
        "measure_system(print_setpoint: bool = True, print_data: bool = True, print_telemetry: bool = True)",  # noqa: E501
        "set_value(value_index: int, value)",
        "set_value(name: str, value)",
        "read_value(value_index: int)",
        "read_value(name: str)",
        "trigger_value(value_index: int)",
        "trigger_value(name: str)",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for ac in self.autocompletions:
            self.add(ac)


if os.name == "nt":
    try:
        from ctypes import windll  # Only exists on Windows.

        myappid = "python.matr1x.matrix-script.version"
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass


class ExecThread(QThread):
    """Control and the thread running the measurements."""

    # signal initiating user input from the GUI.
    # Signature: query (str),
    #            input_type (str),
    #            timeout (float),
    #            default_value (str),
    #            min_value (object, float or None),
    #            max_value (object, float or None),
    #            step (object, float or None),
    #            decimals (object, int or None)
    input_signal = pyqtSignal(str, str, float, str, object, object, object, object)
    # signal to report the currently executing line number to the editor.
    lineno_signal = pyqtSignal(int)
    # signal to report the filename of the file that is written by the process
    filename_signal = pyqtSignal(str)

    def __init__(self, meta_data, script, fallbackname, temp_config):
        """
        Initialize thread that handles script execution.

        Parameters
        ----------
            meta_data : dict
                dictionary containing meta data such as user and comment
            script : string
                user script that is supposed to be run by the ExecThread.
            fallbackname : str
                filename used to initialize the data file if not specified
                in the script. Its directory path will be used as execution
                directory.
            temp_config : str
                temporary configuration file path
        """
        super().__init__()
        self.proc = None
        self.conn = None
        self.meta_data = meta_data
        self.script = script
        self.datafilefallback = fallbackname
        self.temp_config = temp_config

    def pass_input(self, inp):
        """Communicate user input to the subprocess."""
        if self.proc is None or self.conn is None:
            return
        if len(inp) < 1 or inp[-1] != "\n":
            # input needs to have terminating character
            inp += "\n"
        self.conn.send(("i" + inp).encode("utf-8"))

    def pause(self):
        """Communicate pause to the subprocess."""
        if self.proc is None or self.conn is None:
            return
        self.conn.send("p".encode())

    def abort(self, char="q"):
        """
        Communicate stop to the subprocess' stdin.

        Parameters
        ----------
            char : str
                Single length string that is passed to the process.
                - "q" stops and queries user for state
                - "a" stops and sets state to `aborted`
                - "f" stops and sets state to `finished`
        """
        if self.proc is None or self.conn is None:
            return
        self.conn.send(char.encode())

    def kill(self):
        """Kill the process and make sure it is indeed stopped."""
        if self.proc is None or self.conn is None:
            return
        pid = self.proc.pid
        # terminate thread
        self.proc.terminate()
        # if thread is still alive, kill it
        try:
            os.kill(pid, 0)
            self.proc.kill()
            print("force killed thread")
            print("please verify all devices are operational before starting", "another script")
        except OSError:
            # this will likely not happen
            print("thread terminated gracefully")

    def recv_line(self, inp):
        """
        Receive a line from the input and handles it accordingly.

        From inp the current executing line or an input request are attemped
        to find, all other input is printed.

        TODO: not tolerant against split strings, i.e. if sent string
        is longer than 1024, one can expect a problematic behavior. Migrate
        to ZMQ and directly pass strings as python objects?
        """
        pattern_lineno = r"__lineno(-?\d+)__"
        pattern_filename = r"__//(.*)//__"
        # Format:
        # __input_type:message:timeout:default:min:max:step:decimals__
        # (trailing parameters are optional)
        # Regex to capture
        # type, message, timeout, default, min, max, step, decimals
        # Handles empty optional fields correctly
        # (e.g., :: means empty field)
        pattern_input = r"__input_(?P<type>[^:]+):(?P<strlabel>[^:]+)(?::(?P<timeout>[^:]*))?(?::(?P<default>[^:]*))?"  # noqa: E501
        pattern_input += r"(?::(?P<min>[^:]*))?(?::(?P<max>[^:]*))?(?::(?P<step>[^:]*))?(?::(?P<decimals>[^:]*))?__"  # noqa: E501
        lines = inp.split(os.linesep)
        for i, line in enumerate(lines[:-1]):
            # add \"\\n\" to all but the last element in split
            # (last element contains everything after last "\n")
            lines[i] += "\n"
        for line in lines:
            if match := re.search(pattern_lineno, line):
                digits = int(match.group(1))
                if digits >= 0:
                    self.lineno_signal.emit(digits)
                line = re.sub(pattern_lineno, "", line)
            if match := re.search(pattern_input, line):
                input_type = match.group("type")
                strlabel = match.group("strlabel")
                # convert back %0A to newline (URL-encoding)
                strlabel = strlabel.replace("%0A", "\n")

                default_value = ""  # Default for string/bool
                timeout = float("inf")
                min_value = None
                max_value = None
                step = None
                decimals = None

                # Parse timeout
                timeout_str = match.group("timeout")
                if timeout_str:
                    try:
                        timeout = float(timeout_str)
                    except ValueError:
                        print(f"Warning: Invalid timeout value received: {timeout_str}")
                        timeout = float("inf")  # Use default on error

                # Parse default value (depends on input_type, handle
                # as string initially)
                default_str = match.group("default")
                if (
                    default_str is not None
                ):  # match.group returns None if group wasn\'t in the match
                    default_value = default_str  # Keep as string for emitting

                # Parse numerical specific parameters if type is 'numerical'
                if input_type == "numerical":
                    min_str = match.group("min")
                    if min_str:
                        try:
                            min_value = float(min_str)
                        except ValueError:
                            print(f"Warning: Invalid min value received: {min_str}")
                            min_value = None  # Use default (None) on error

                    max_str = match.group("max")
                    if max_str:
                        try:
                            max_value = float(max_str)
                        except ValueError:
                            print(f"Warning: Invalid max value received: {max_str}")
                            max_value = None  # Use default (None) on error

                    step_str = match.group("step")
                    if step_str:
                        try:
                            step = float(step_str)
                        except ValueError:
                            print(f"Warning: Invalid step value received: {step_str}")
                            step = None  # Use default (None) on error

                    decimals_str = match.group("decimals")
                    if decimals_str:
                        try:
                            decimals = int(decimals_str)
                        except ValueError:
                            print(f"Warning: Invalid decimals value received: {decimals_str}")
                            decimals = None  # Use default (None) on error

                logger.info(
                    f"Requesting input type: {input_type}, Query: {strlabel}, "
                    f"Timeout: {timeout}, Default: {default_value}, Min: {min_value}, "
                    f"Max: {max_value}, Step: {step}"
                )

                # Emit the signal with all parameters
                self.input_signal.emit(
                    strlabel,
                    input_type,
                    timeout,
                    default_value,
                    min_value,
                    max_value,
                    step,
                    decimals,
                )

                line = re.sub(pattern_input, "", line)
            if match := re.search(pattern_filename, line):
                path = match.group(1)
                self.filename_signal.emit(path)
                line = re.sub(pattern_filename, "", line)
            if line != "":
                print(line, end="")

    def run(self):
        """
        Run the subprocess.

        first writes the user script into a temporary file to make sure
        all formating is conserved, then passes that file to the
        interpreter to run the script the purpose of using a subprocess
        is to keep the namespace clear of all system files. That allows
        changes to the system while matrix-script is running.
        """
        with tempfile.NamedTemporaryFile(mode="w+b") as tf:
            for line in self.script:
                tf.write(line.encode())
            # all information has been written to temporary file, make sure it
            # is updated
            tf.flush()
            # start socket that is used to communicate with the child process
            # that runs the script
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # only accept local connections and start listening
            s.bind(("127.0.0.1", 0))  # use dynamic port
            port = s.getsockname()[1]
            s.listen(1)
            # start subprocess, stderr is piped to stdout, and both of them are
            # piped so that we can read them
            # pass the script that we want to execute and generate correct
            # parameters to pass to matr1x/utils.py:matrix_script_process
            cmd = f"""import matr1x
import matr1x.util as mu
matr1x.reload_config({repr(self.temp_config)})
mu.matrix_script_process({repr(tf.name)}, {repr(self.meta_data)},
                         {repr(self.datafilefallback)}, {repr(port)})"""

            self.proc = subprocess.Popen(
                [sys.executable, "-c", cmd],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
            )
            # accept a connection from the subprocess
            # will block until a new client connects, might want to use select
            # here to make sure the subprocess actually connects?
            self.conn, address = s.accept()
            # wait until the subprocess terminates and pipe its stdout to the
            # user window
            while self.proc.poll() is None:
                try:
                    datachunk = self.conn.recv(8192).decode()
                    if len(datachunk) > 0:
                        while datachunk[-1] != "\0":
                            datachunk += self.conn.recv(8192).decode()
                        self.recv_line(datachunk.replace("\0", ""))
                except OSError:
                    print("OS error in thread communication")
            self.conn.close()
            # clean up temporary config
            os.remove(self.temp_config)


class MainWindow(QMainWindow):
    """Define layout, runs everything."""

    extension = ".matrix"

    def __init__(self, filename=None):
        """Initialize the GUI for scripted matrix control."""
        super().__init__()
        self.systems = []
        self.scriptname = ""
        self.measurement_file = ""
        self.systems_dirty = False
        self.last_loaded_file = None
        self.is_running = False
        self.shortcut_dir = None
        self.last_filename = ""
        self.settings = QSettings("matr1x", "script")
        self.output_stream = EmittingStream()
        self.output_stream.text_written.connect(self.output_written)

        self.color_palette = get_application_instance().palette()
        self.init_ui()
        # set outputStream as stdout (i.e. all output is written to status
        # preview
        sys.stdout = self.output_stream
        # If filename is passed when matrix-script is started, start
        # by loading the file
        if filename is not None:
            self.load_from_filename(filename)

    def print_colored(self, line: str) -> None:
        """
        Print a colored text.

        Afterwards, recover the original text color and follow theme changes.

        Parameters
        ----------
        line : str
            The line to be printed.
        """
        cursor = self.status_preview.textCursor()
        error_format = QTextCharFormat()
        # Royal Blue is one of the few colors that works in dark and light modes.
        error_format.setForeground(QColor("royalblue"))
        cursor.setCharFormat(error_format)
        cursor.insertText(line)
        default_format = QTextCharFormat()
        cursor.setCharFormat(default_format)
        cursor.insertText("\n")

    def insert_code(self, function: str) -> None:
        """
        Insert a code fragment with explanation at the current cursor position.

        Parameters
        ----------
        function : str
            The function name to be explained.
        """
        line, index = self.script_edit.getCursorPosition()
        if function == "init_datafile":
            code = (
                'init_datafile(filename, comment="", append=False, print_header=True, ntot=None)\n'
            )
            code += "# ntot is total number of points in a given measurement\n"
            code += "# and is used to calculate measurement duration\n"
        elif function == "measure_system":
            code = "measure_system(print_setpoint=True, print_data=True, print_telemetry=True)\n"
            code += "# performs a single measurement as specified in system\n"
        elif function == "wait":
            code = 'wait(duration=None, until=None, message="", silent=10)\n'
            code += "# waits for either a duration or until a timestamp\n"
            code += "# this also acts as a breakpoint to pause and abort the execution,\n"
            code += "# for wait period > silent, prints message\n"
        elif function == "end_script":
            code = "end_script(finished=None)\n"
            code += '# if finished is True, file is marked as "finished", for False\n'
            code += "# it is marked as aborted, otherwise user is querried\n"
        elif function == "input":
            code = 'input(query="", timeout=float("inf"), default_value="")\n'
            code += "# waits for user text input or timeouts with a default reply.\n"
        elif function == "input_bool":
            code = 'input_bool(question="", timeout=float("inf"), default_value="")\n'
            code += "# waits for user to answer a yes/no question"
            code += "or continues with the default reply after timeout.\n"
        elif function == "input_numerical":
            code = 'input_numerical(query="", timeout=float("inf"), default_value=0.0, '
            code += "min_value=-100e9, max_value=100e9, step=1.0, decimals=2)\n"
            code += (
                "# waits for user to input a number or continues with the default after timeout.\n"
            )
        elif function == "set_value":
            code = "set_value(column, value)\n"
            code += "# column can be the index or the name.\n"
            code += "# Please use 'help/system' for more information.\n"
        elif function == "read_value":
            code = "read_value(column)\n"
            code += "# column can be the index or the name.\n"
            code += "# Please use 'help/system' for more information.\n"
        elif function == "trigger_value":
            code = "trigger_value(column)\n"
            code += "# column can be the index or the name.\n"
            code += "# Please use 'Help/Show system help' for more information.\n"
        else:
            code = f"Unknown function <{function}> in 'insert_code', please file a bug report.\n"
        self.script_edit.insertAt(code, line, index)
        self.script_edit.setCursorPosition(line, index + len(code))

    def print_document(self) -> None:
        """Print the script."""
        # go via QTextEdit functions for better portability
        text_edit = QTextEdit()
        text_edit.setText(self.script_edit.text())
        printer = QPrinter()
        print_dialog = QPrintDialog(printer, self)
        if print_dialog.exec():
            text_edit.print(printer)
        del text_edit

    def show_layout(self, layout: QBoxLayout, visible: bool) -> None:
        """
        Show or hide all widgets in a layout.

        Parameters
        ----------
        layout : QBoxLayout
            The layout the show or hide.
        visible : bool
            Show (True) or hide (False) all the widgets.
        """
        for i in range(layout.count()):
            item = layout.itemAt(i)
            widget = item.widget()
            if widget:
                widget.setVisible(visible)

    def find(self) -> None:
        """Show the find layout and focus in the line edit."""
        self.show_layout(self.find_layout, True)
        self.find_line.setFocus()

    def find_update(self) -> None:
        """Update the number of occurances of the search term."""
        text_edit = QTextEdit()
        text_edit.setText(self.script_edit.text())
        cursor = text_edit.textCursor()
        count = 0
        cursor.setPosition(0)
        text_edit.setTextCursor(cursor)
        if self.find_line.text().strip() != "":
            if self.find_regex.isChecked():
                pattern = QRegularExpression(self.find_line.text().strip())
            else:
                pattern = self.find_line.text()
            while text_edit.find(pattern):
                found_cursor = text_edit.textCursor()
                text_edit.setTextCursor(found_cursor)
                count += 1
            self.find_count.setText(str(count))

    def find_next(self) -> None:
        """
        Find the next occurance of the search term and selected it.

        If the end of the document is reached, wrap around.
        """
        # go via QTextEdit functions for better portability
        text_edit = QTextEdit()
        text_edit.setText(self.script_edit.text())
        cursor = text_edit.textCursor()
        current_position = self.script_edit.SendScintilla(QsciScintilla.SCI_GETSELECTIONEND)
        cursor.setPosition(current_position)
        text_edit.setTextCursor(cursor)
        if self.find_regex.isChecked():
            pattern = QRegularExpression(self.find_line.text().strip())
        else:
            pattern = self.find_line.text()
        if not text_edit.find(pattern):
            cursor.setPosition(0)
            text_edit.setTextCursor(cursor)
            text_edit.find(pattern)
        found_cursor = text_edit.textCursor()
        text_edit.setTextCursor(found_cursor)
        start = text_edit.textCursor().selectionStart()
        end = text_edit.textCursor().selectionEnd()
        self.script_edit.SendScintilla(QsciScintilla.SCI_SETSELECTIONSTART, start)
        self.script_edit.SendScintilla(QsciScintilla.SCI_SETSELECTIONEND, end)
        del text_edit

    def save_window_state(self) -> None:
        """
        Save application configuration until next startup.

        For convenience, main window geometry, the toolbar placement,
        and the size and position of metadata and configuration pane are
        saved.
        """
        self.settings.setValue("created", 1)
        self.settings.beginGroup("MainWindow")
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter", self.splitter.sizes())
        self.settings.endGroup()

        self.settings.beginGroup("script_edit")
        self.settings.setValue("size", self.script_edit.size())
        self.settings.setValue(
            "zoom",
            self.script_edit.SendScintilla(QsciScintilla.SCI_GETZOOM, QsciScintilla.STYLE_DEFAULT),
        )
        self.settings.endGroup()

        self.settings.beginGroup("status_preview")
        self.settings.setValue("size", self.status_preview.size())
        self.settings.endGroup()

        self.settings.beginGroup("Toolbars")
        self.settings.setValue("buttons_visible", self.toolbar.isVisible())
        self.settings.setValue("buttons_placement", self.toolBarArea(self.toolbar))
        self.settings.setValue("buttons_geometry", self.toolbar.geometry())
        self.settings.endGroup()

        self.settings.beginGroup("dockable_metadata")
        self.settings.setValue("visible", self.dockable_metadata.isVisible())
        self.settings.setValue("placement", self.dockWidgetArea(self.dockable_metadata))
        self.settings.setValue("floating", self.dockable_metadata.isFloating())
        self.settings.setValue("position", self.dockable_metadata.pos())
        self.settings.setValue("size", self.dockable_metadata.size())
        self.settings.endGroup()

        self.settings.beginGroup("config_editor")
        self.settings.setValue("position", self.config_editor.pos())
        self.settings.setValue("size", self.config_editor.size())
        self.settings.endGroup()

        # Only save help dialog size and position if it has been shown at least once
        if hasattr(self, "_help_dialog_shown") and self._help_dialog_shown:
            self.settings.beginGroup("system_command_help")
            self.settings.setValue("size", self.system_command_help.size())
            self.settings.setValue("position", self.system_command_help.pos())
            self.settings.endGroup()

    def restore_window_state(self) -> None:
        """
        Restore application configuration to look similar to the previous use.

        Main window geometry, the toolbar placement, and the size and
        position of metadata and configuration pane are restored.
        """
        # Just in case it is the first start
        self.resize(self.sizeHint())
        self.settings.beginGroup("MainWindow")
        self.restoreGeometry(self.settings.value("geometry", QByteArray()))
        self.splitter.setSizes(
            [int(size) for size in self.settings.value("splitter", self.splitter.sizes())]
        )
        self.settings.endGroup()
        # Check if there is a settings file. This improves the robustness
        # against strange side effect, caused by the default values. The default
        # values are still required to ensure compatibilty in case the saved
        # settings are changed.
        if self.settings.contains("created"):
            self.settings.beginGroup("script_edit")
            self.script_edit.resize(self.settings.value("size", self.script_edit.size()))
            self.script_edit.SendScintilla(
                QsciScintilla.SCI_SETZOOM, self.settings.value("zoom", 1, type=int)
            )
            self.settings.endGroup()

            self.settings.beginGroup("status_preview")
            self.status_preview.resize(self.settings.value("size", self.status_preview.size()))
            self.settings.endGroup()

            self.settings.beginGroup("Toolbars")
            self.toolbar.setVisible(self.settings.value("buttons_visible", True, type=bool))
            self.toggle_toolbar_action.setChecked(
                self.settings.value("buttons_visible", True, type=bool)
            )
            self.addToolBar(
                self.settings.value("buttons_placement", Qt.ToolBarArea.TopToolBarArea),
                self.toolbar,
            )
            self.settings.endGroup()

            self.settings.beginGroup("dockable_metadata")
            self.dockable_metadata.setVisible(self.settings.value("visible", True, type=bool))
            self.toggle_metadata_action.setChecked(self.settings.value("visible", True, type=bool))
            self.addDockWidget(
                self.settings.value("placement", Qt.DockWidgetArea.RightDockWidgetArea),
                self.dockable_metadata,
            )
            self.dockable_metadata.setFloating(self.settings.value("floating", False, type=bool))
            if self.dockable_metadata.isFloating():
                self.dockable_metadata.move(
                    self.settings.value("position", self.dockable_metadata.pos())
                )
                self.dockable_metadata.resize(
                    self.settings.value("size", self.dockable_metadata.size())
                )
            else:
                self.resizeDocks(
                    [self.dockable_metadata],
                    [self.settings.value("size", self.dockable_metadata.size()).width()],
                    Qt.Orientation.Horizontal,
                )
            self.settings.endGroup()

            self.settings.beginGroup("config_editor")
            self.config_editor.move(self.settings.value("position", self.config_editor.pos()))
            self.config_editor.resize(self.settings.value("size", self.config_editor.size()))
            self.settings.endGroup()

    def keyPressEvent(self, event: QKeyEvent):
        """Allow to modify systems list with keyboard shortcuts."""
        if self.system_list.hasFocus():
            if detect_shortcut(event, QKeySequence(QKeySequence.StandardKey.Delete)):
                self.delete_selected_system()
            if detect_shortcut(event, QKeySequence(Qt.Key.Key_Backspace)):
                self.delete_selected_system()
        if self.find_line.hasFocus() or self.find_regex.hasFocus():
            if detect_shortcut(event, QKeySequence(Qt.Key.Key_Escape)):
                self.show_layout(self.find_layout, False)
        super().keyPressEvent(event)

    def changeEvent(self, event: QEvent):
        """Detect palette changes such as dark and bright mode desktops."""
        if event.type() == QEvent.Type.PaletteChange:
            self.color_palette = get_application_instance().palette()
            self.update_ui()

    def closeEvent(self, event: QEvent) -> None:
        """
        Capture close events and ask user whether script should be saved.

        If a script is running, the event is ignored and an explanation is given.
        If the script was modified without saving and not empty, a dialog asks
        how to proceed.

        Parameters
        ----------
        event : QEvent
            The received 'close event'
        """
        if self.is_running:
            QMessageBox.critical(
                QWidget(),
                "Script running!",
                """Please wait for the script to finish. Alternatively,
                stop or kill the script before exiting 'Matrix Script'!""",
            )
            event.ignore()
            return

        if self.systems_dirty and "" != self.scriptname:
            # if no file is given, nothing is saved
            self.update_systems(update_config=False)
            newscript = self.generate_save_content()
            with open(self.scriptname, "r") as f:
                saved_text = f.read()
                if saved_text == newscript:
                    self.systems_dirty = False

        if (self.script_edit.isModified() or self.systems_dirty) and self.script_edit.text() != "":
            qApp = get_application_instance()
            qApp.processEvents()
            ret = save_messagebox(self)
            if ret == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if ret == QMessageBox.StandardButton.Save:
                # save the file
                if -1 == self.save_file():
                    # if save fails, ignore message
                    event.ignore()
                    return
        self.save_window_state()
        event.accept()

    def standard_action(self, name, display_name=None) -> QAction:
        """
        Create and return a standard action such as 'Undo'.

        Also connects the action with a system agnostic shortcut and
        with the corresponding method.

        Parameters
        ----------
        name : str
            The name of the method as in QKeySequence.StandardKey.
        display_name : str, optional
            The name to be displayed in menu and toolbar.

        Returns
        -------
        QAction
            The action.
        """
        if not display_name:
            display_name = name
        action = QAction(display_name, self)
        action.setShortcut(getattr(QKeySequence.StandardKey, name))
        method_name = name[:1].lower() + name[1:]
        action.triggered.connect(lambda checked, method=method_name: self.standard_method(method))
        return action

    def standard_method(self, method_name: str) -> None:
        """
        Perform a standard method such as 'undo' on the focussed widget.

        Parameters
        ----------
        method_name : str
            The name of the method.
        """
        focus_widget = MApplication.focusWidget()
        try:
            method = getattr(focus_widget, method_name)
            if callable(method):
                method()
        except AttributeError:
            pass

    def info_box(self):
        """Display an 'about this app' widget."""
        box = AboutBox(
            "Matrix Script",
            MIcon("matr1x-matrix-script.png"),
            matr1x,
            matr1x.datetimefmt,
        )
        box.exec()
        return

    def update_ui(self):
        """Perform all the required tasks after a theme change."""
        palette = self.status_preview.palette()
        text_edit = QTextEdit()
        text_edit.setEnabled(False)
        text_color = QColor(self.color_palette.color(QPalette.ColorRole.Text))
        base_color = QColor(self.color_palette.color(QPalette.ColorRole.Base))
        highlight_color = QColor(self.color_palette.color(QPalette.ColorRole.Highlight))
        button_color = QColor(self.color_palette.color(QPalette.ColorRole.Button))
        button_text_color = QColor(self.color_palette.color(QPalette.ColorRole.ButtonText))
        unclosed_color = QColor("red")
        caret_color = QColor(self.color_palette.color(QPalette.ColorRole.AlternateBase))
        if palette.color(QPalette.ColorRole.Window).value() < 128:
            # dark_mode
            method_color = QColor(195, 195, 156)
            comment_color = QColor(106, 153, 86)
            string_color = QColor(205, 145, 120)
            class_color = QColor(85, 155, 212)
            keyword_color = QColor(197, 134, 192)
            own_identifier_color = QColor(244, 15, 255)
        else:
            # bright mode
            method_color = QColor(117, 95, 48)
            comment_color = QColor(30, 135, 23)
            string_color = QColor(176, 55, 55)
            class_color = QColor(13, 5, 255)
            keyword_color = QColor(182, 23, 223)
            own_identifier_color = QColor(245, 54, 255)
        self.executed_line_color = highlight_color
        self.lexer.setPaper(base_color)
        self.script_edit.setCaretLineBackgroundColor(caret_color)
        self.script_edit.setMarginsBackgroundColor(button_color)
        self.script_edit.setCaretForegroundColor(text_color)
        self.script_edit.setMarginsForegroundColor(button_text_color)
        # the sequence relates to the enumerator
        STYLES = {
            QsciLexerPython.Default: text_color,
            QsciLexerPython.Comment: comment_color,
            QsciLexerPython.Number: text_color,
            QsciLexerPython.DoubleQuotedString: string_color,
            QsciLexerPython.SingleQuotedString: string_color,
            QsciLexerPython.Keyword: keyword_color,
            QsciLexerPython.TripleSingleQuotedString: string_color,
            QsciLexerPython.TripleDoubleQuotedString: string_color,
            QsciLexerPython.ClassName: class_color,
            QsciLexerPython.FunctionMethodName: method_color,
            QsciLexerPython.Operator: text_color,
            QsciLexerPython.Identifier: text_color,
            QsciLexerPython.CommentBlock: comment_color,
            QsciLexerPython.UnclosedString: unclosed_color,
            # the next line refers to identifiers defined by us, e.g., measure_system()
            QsciLexerPython.HighlightedIdentifier: own_identifier_color,
            QsciLexerPython.SingleQuotedFString: string_color,
            QsciLexerPython.TripleSingleQuotedFString: string_color,
            QsciLexerPython.DoubleQuotedFString: string_color,
            QsciLexerPython.TripleDoubleQuotedString: string_color,
        }
        for stl, clr in STYLES.items():
            self.lexer.setColor(clr, stl)

    def toggle_toolbar_view(self, checked):
        """Toogles the visibility of the toolbar on and off."""
        if checked:
            self.toolbar.show()
        else:
            self.toolbar.hide()

    def toggle_metadata_view(self, checked):
        """Toggles the visibility of the metadata dock onm and off."""
        if checked:
            self.dockable_metadata.show()
        else:
            self.dockable_metadata.hide()

    def preview_data(self):
        """Launch matrix-preview with current measurement file."""
        matrix_preview.SweepPreview(self, self.measurement_file).show()

    def toggle_preferences(self, checked):
        """Open the preferences pane."""
        if checked:
            self.config_editor.show()
            self.config_editor.raise_()
            self.config_editor.activateWindow()
        else:
            self.config_editor.hide()

    def init_ui(self) -> None:
        """Generate the main GUI."""
        self.setWindowIcon(MIcon("matr1x-matrix-script.png"))
        self.central_widget = DroppableWidget(self)
        self.central_widget.fileDropped.connect(self.load_from_filename)
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout(self.central_widget)
        layout.setSpacing(0)
        layout.setContentsMargins(11, 4, 11, 11)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.dockable_metadata = QDockWidget("Metadata", self)
        self.metadata = MetaDataDialog()
        self.dockable_metadata.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dockable_metadata)
        self.dockable_metadata.setWidget(self.metadata)
        self.toggle_metadata_action = QAction("Show Metadata", self)
        self.toggle_metadata_action.setShortcut(QKeySequence("Ctrl+2"))
        self.toggle_metadata_action.setCheckable(True)
        self.toggle_metadata_action.setChecked(True)
        self.toggle_metadata_action.triggered.connect(self.toggle_metadata_view)
        self.dockable_metadata.visibilityChanged.connect(self.toggle_metadata_action.setChecked)
        self.toggle_toolbar_action = QAction("Show Toolbar", self)
        self.toggle_toolbar_action.setShortcut(QKeySequence("Ctrl+1"))
        self.toggle_toolbar_action.setCheckable(True)
        self.toggle_toolbar_action.setChecked(True)
        self.toggle_toolbar_action.triggered.connect(self.toggle_toolbar_view)
        self.help_system_action = QAction("Show System Help", self)
        self.help_system_action.triggered.connect(self.show_system_commands)
        #
        self.system_list = SystemListWidget()
        self.system_list.orderChanged.connect(self.update_systems)
        self.status_preview = TerminalOutput()
        self.status_preview.document().setMaximumBlockCount(MAX_LINES_STATUS)
        self.script_edit = QScintillaCustom(self.output_stream, self)
        # Connect text edit signals to the slot that checks for changes
        self.script_edit.modificationChanged.connect(self.update_window_title)
        self.lexer = CustomLexer(self)
        self.script_edit.setLexer(self.lexer)
        mono_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono_font.setPointSizeF(self.status_preview.font().pointSize())
        self.lexer.setFont(mono_font)
        autocomp = CompleterPython(self.script_edit)
        autocomp.setEnabled(True)
        # make caret more visible, highlight current line
        self.script_edit.setCaretWidth(2)
        self.script_edit.setCaretLineVisible(True)
        # line numbers in margin
        self.script_edit.setMarginLineNumbers(1, True)
        self.script_edit.setMarginWidth(1, "#000")
        # indentation and wrapping
        self.script_edit.setTabWidth(4)
        self.script_edit.setIndentationsUseTabs(False)
        self.script_edit.setAutoIndent(True)
        self.script_edit.setBackspaceUnindents(True)
        self.script_edit.setWrapMode(QsciScintilla.WrapMode.WrapNone)
        self.script_edit.setScrollWidth(200)
        self.script_edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.script_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # autocompletion, source is document and custom commands
        api = CustomQsciAPI(self.lexer)
        api.prepare()
        self.script_edit.setCallTipsVisible(3)
        self.script_edit.setAutoCompletionSource(QsciScintilla.AutoCompletionSource.AcsAll)
        self.script_edit.setAutoCompletionThreshold(1)
        self.script_edit.setAutoCompletionCaseSensitivity(True)
        self.script_edit.setAutoCompletionFillupsEnabled(True)
        self.script_edit.setBraceMatching(QsciScintilla.BraceMatch.SloppyBraceMatch)
        self.script_edit.setAnnotationDisplay(QsciScintilla.AnnotationDisplay.AnnotationBoxed)
        self.script_edit.fileDropped.connect(self.load_from_filename)
        self.create_actions()
        # initialize widgets in layout
        self.splitter = QSplitter(self)
        self.splitter.addWidget(self.script_edit)
        self.splitter.addWidget(self.status_preview)
        self.find_layout = QHBoxLayout()
        self.find_layout.setSpacing(11)
        self.find_line = QLineEdit()
        self.find_line.textChanged.connect(self.find_update)
        self.script_edit.textChanged.connect(self.find_update)
        self.find_count = QLabel("0")
        self.find_regex = QCheckBox("RegEx mode")
        self.find_regex.clicked.connect(self.find_update)
        find_next = QPushButton("Find Next")
        find_next.clicked.connect(self.find_next)
        find_close = QPushButton()
        find_close.setIcon(MIcon("SP_LineEditClearButton"))
        find_close.clicked.connect(lambda: self.show_layout(self.find_layout, False))
        self.find_layout.addWidget(self.find_line)
        self.find_layout.addWidget(self.find_count)
        self.find_layout.addWidget(self.find_regex)
        self.find_layout.addWidget(find_next)
        self.find_layout.addWidget(find_close)
        self.show_layout(self.find_layout, False)
        layout.addLayout(self.find_layout)
        layout.addWidget(self.splitter)
        # change the size dynamically later and allow vertical streching
        # when floating
        self.system_list.setMinimumHeight(50)
        self.system_list.setMaximumHeight(50)
        # Create menu and toolbar
        self.create_menu()
        self.create_toolbar()
        # set focus to text editor
        self.script_edit.setFocus()
        self.system_command_help = QDialog(self)
        box_layout = QVBoxLayout()
        self.system_command_text_edit = QTextEdit()
        self.system_command_text_edit.setReadOnly(True)
        box_layout.addWidget(self.system_command_text_edit)
        self.system_command_help.setLayout(box_layout)
        title = "Selected systems information"
        self.system_command_help.setWindowTitle(title)
        self.system_command_help.setWindowModality(Qt.WindowModality.NonModal)
        # Initialize the help text
        self.update_system_commands()
        self.update_ui()
        self.update_window_title()
        check_config(matr1x.config)

    def create_actions(self) -> None:
        """Create all required actions and toolbar buttons."""
        self.matrix_settings_action = QAction("Show matrix toml", self)
        self.matrix_settings_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        self.matrix_settings_action.setShortcut(QKeySequence.StandardKey.Preferences)
        self.matrix_settings_action.triggered.connect(open_matrix_toml)
        self.about_action = QAction("About", self)
        self.about_action.setMenuRole(QAction.MenuRole.AboutRole)
        self.about_action.triggered.connect(self.info_box)
        self.config_editor = ConfigEditWidget()
        self.config_editor.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.config_editor)
        self.config_editor.setFloating(True)
        self.config_editor.close()
        self.config_action = QAction(MIcon("CHAR_≡"), "Device config", self)
        self.config_action.setToolTip("Show the devices preferences/ configuration.")
        self.config_action.setCheckable(True)
        self.config_action.toggled.connect(self.toggle_preferences)
        self.config_editor.visibilityChanged.connect(self.config_action.setChecked)
        self.new_file_action = QAction(MIcon("SP_FileIcon"), "New", self)
        self.new_file_action.triggered.connect(self.new_file)
        self.new_file_action.setShortcut(QKeySequence.StandardKey.New)
        self.load_action = QAction(MIcon("SP_DialogOpenButton"), "Open", self)
        self.load_action.setToolTip("Open a script file.")
        self.load_action.triggered.connect(self.load_from_file)
        self.load_action.setShortcut(QKeySequence.StandardKey.Open)
        self.save_action = QAction(MIcon("SP_DialogSaveButton"), "Save", self)
        self.save_action.setToolTip("Save the under the current filename.")
        self.save_action.triggered.connect(self.save_file)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_as_action = QAction(MIcon("SP_DialogSaveButton"), "Save As...", self)
        self.save_as_action.triggered.connect(self.save_file_as)
        self.save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.save_button = QToolButton()
        self.save_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.save_button.setIcon(MIcon("SP_DialogSaveButton"))
        self.save_button.setText("Save")
        self.save_button.setDefaultAction(self.save_action)
        self.save_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        save_pulldown = QMenu(self)
        save_pulldown.addAction(self.save_as_action)
        self.save_button.setMenu(save_pulldown)
        self.add_system_action = QAction(MIcon("CHAR_+"), "Add System", self)
        self.add_system_action.setToolTip("Add a matrix system file.")
        self.add_system_action.triggered.connect(self.add_system)
        self.remove_system_action = QAction(MIcon("CHAR_-"), "Remove System", self)
        self.remove_system_action.setEnabled(False)
        self.remove_system_action.setToolTip("Remove the selected or last matrix system file.")
        self.remove_system_action.triggered.connect(self.delete_selected_system)
        self.quit_action = QAction("Quit", self)
        if os.name == "nt":
            self.quit_action.setShortcut(QKeySequence.StandardKey.Close)
        else:
            self.quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.quit_action.triggered.connect(self.close)
        self.undo_action = self.standard_action("Undo")
        self.redo_action = self.standard_action("Redo")
        self.cut_action = self.standard_action("Cut")
        self.copy_action = self.standard_action("Copy")
        self.paste_action = self.standard_action("Paste")
        self.single_quotes_action = QAction("Add Single Quotes", self)
        self.single_quotes_action.triggered.connect(lambda: self.script_edit.add_quotes(chr(39)))
        self.double_quotes_action = QAction("Add Double Quotes", self)
        self.double_quotes_action.triggered.connect(lambda: self.script_edit.add_quotes(chr(34)))
        self.line_comment_action = QAction("Toggle Line Comment", self)
        self.line_comment_action.triggered.connect(self.script_edit.toggle_commenting)
        self.zoom_in_action = self.standard_action("ZoomIn", "Zoom in")
        self.zoom_out_action = self.standard_action("ZoomOut", "Zoom Out")
        self.print_action = QAction("Print", self)
        self.print_action.setShortcut(QKeySequence.StandardKey.Print)
        self.print_action.triggered.connect(self.print_document)
        self.find_action = QAction("Find", self)
        self.find_action.setShortcut(QKeySequence.StandardKey.Find)
        self.find_action.triggered.connect(self.find)
        self.find_next_action = QAction("Find Next", self)
        self.find_next_action.setShortcut(QKeySequence.StandardKey.FindNext)
        self.find_next_action.triggered.connect(self.find_next)
        self.start_pause_action = QAction(MIcon("CUSTOM_Play"), "Start", self)
        self.start_pause_action.setToolTip("Execute the script.")
        self.start_pause_action.triggered.connect(self.start_process)
        self.start_pause_action.setCheckable(True)
        self.stop_action = QAction(MIcon("CUSTOM_Stop"), "Stop", self)
        self.stop_action.setToolTip("Stop the script and query status.")
        self.stop_action.triggered.connect(lambda: self.abort_thread("q"))
        self.stop_action.setEnabled(False)
        self.abort_action = QAction(MIcon("CUSTOM_Stop"), "Abort", self)
        self.abort_action.triggered.connect(lambda: self.abort_thread("a"))
        self.abort_action.setEnabled(False)
        self.finish_action = QAction(MIcon("CUSTOM_Stop"), "Finish", self)
        self.finish_action.triggered.connect(lambda: self.abort_thread("f"))
        self.finish_action.setEnabled(False)
        self.stop_button = QToolButton()
        self.stop_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.stop_button.setIcon(MIcon("CUSTOM_Stop"))
        self.stop_button.setText("Abort")
        self.stop_button.setDefaultAction(self.stop_action)
        self.stop_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        stop_pulldown = QMenu(self)
        stop_pulldown.addAction(self.abort_action)
        stop_pulldown.addAction(self.finish_action)
        self.stop_button.setMenu(stop_pulldown)
        self.kill_action = QAction(MIcon("SP_DialogCancelButton"), "Kill", self)
        self.kill_action.triggered.connect(self.kill_thread)
        self.kill_action.setEnabled(False)
        self.preview_action = QAction(
            MIcon("matr1x-matrix-preview.png", QColor("RoyalBlue")), "Preview", self
        )
        self.preview_action.triggered.connect(self.preview_data)
        self.preview_action.setEnabled(False)
        self.lint_action = QAction("Lint with Pyflakes", self)
        self.lint_action.triggered.connect(self.script_edit.run_linter)
        self.lint_action.setShortcut(QKeySequence("Ctrl+7"))
        self.pep8_action = QAction("Format with autopep8", self)
        self.pep8_action.triggered.connect(self.script_edit.run_autopep8)
        self.pep8_action.setShortcut(QKeySequence("Ctrl+8"))

    def create_toolbar(self) -> None:
        """Create the toolbar."""
        self.toolbar = QToolBar("Toolbar")
        self.toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.toolbar.setFloatable(False)
        self.toolbar.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.toolbar.setAllowedAreas(
            Qt.ToolBarArea.TopToolBarArea | Qt.ToolBarArea.BottomToolBarArea
        )
        icon_size = get_application_instance().toolbar_icon_size()
        empty = QWidget()
        empty.setFixedWidth(icon_size)
        empty2 = QWidget()
        empty2.setFixedWidth(icon_size)
        empty3 = QWidget()
        empty3.setFixedWidth(icon_size)
        self.toolbar.setIconSize(QSize(icon_size, icon_size))
        self.toolbar.addAction(self.new_file_action)
        self.toolbar.addAction(self.load_action)
        self.toolbar.addWidget(self.save_button)
        self.toolbar.addWidget(empty)
        self.toolbar.addAction(self.start_pause_action)
        self.toolbar.addWidget(self.stop_button)
        self.toolbar.addWidget(empty2)
        self.toolbar.addAction(self.preview_action)
        self.toolbar.addWidget(empty3)
        self.toolbar.visibilityChanged.connect(self.toggle_toolbar_action.setChecked)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.add_system_action)
        self.toolbar.addWidget(self.system_list)
        self.toolbar.addAction(self.remove_system_action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.config_action)
        self.addToolBar(self.toolbar)

    def create_menu(self) -> None:
        """Create the main menu."""
        menu = self.menuBar()
        assert menu is not None
        # Populate the actions
        file_menu = menu.addMenu("&File")
        assert file_menu is not None
        file_menu.addAction(self.new_file_action)
        file_menu.addAction(self.load_action)
        file_menu.addSeparator()
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.add_system_action)
        file_menu.addAction(self.remove_system_action)
        file_menu.addSeparator()
        file_menu.addAction(self.print_action)
        file_menu.addSeparator()
        file_menu.addAction(self.quit_action)  # This gets auto-moved on a Mac
        #
        edit_menu = menu.addMenu("&Edit")
        assert edit_menu is not None
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.cut_action)
        edit_menu.addAction(self.copy_action)
        edit_menu.addAction(self.paste_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.find_action)
        edit_menu.addAction(self.find_next_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.single_quotes_action)
        edit_menu.addAction(self.double_quotes_action)
        edit_menu.addAction(self.line_comment_action)
        edit_menu.addSeparator()
        edit_menu.addAction(self.lint_action)
        edit_menu.addAction(self.pep8_action)
        #
        code_menu = menu.addMenu("&Code")
        assert code_menu is not None
        functions = (
            "init_datafile",
            "measure_system",
            "wait",
            "end_script",
            "input",
            "input_bool",
            "input_numerical",
            "separator",
            "set_value",
            "read_value",
            "trigger_value",
        )
        for function in functions:
            if function == "separator":
                code_menu.addSeparator()
            else:
                action = QAction(function + "()", self)
                action.triggered.connect(
                    lambda checked, function=function: self.insert_code(function)
                )
                code_menu.addAction(action)
        #
        control_menu = menu.addMenu("&Control")
        assert control_menu is not None
        control_menu.addAction(self.start_pause_action)
        control_menu.addAction(self.abort_action)
        control_menu.addAction(self.finish_action)
        control_menu.addAction(self.kill_action)
        control_menu.addSeparator()
        control_menu.addAction(self.preview_action)
        #
        view_menu = menu.addMenu("&View")
        assert view_menu is not None
        view_menu.addAction(self.zoom_in_action)
        view_menu.addAction(self.zoom_out_action)
        view_menu.addSeparator()
        view_menu.addAction(self.toggle_toolbar_action)
        view_menu.addAction(self.toggle_metadata_action)
        view_menu.addAction(self.matrix_settings_action)
        view_menu.addAction(self.config_action)
        #
        help_menu = menu.addMenu("&Help")
        assert help_menu is not None
        help_menu.addAction(self.help_system_action)
        help_menu.addAction(self.about_action)  # This is auto-moved on a Mac

    def update_window_title(self):
        """Indicate if the file was edited with an asterisk."""
        text = "Matrix Script"
        if self.script_edit.isModified() or self.systems_dirty:
            text += ": *"
        elif self.scriptname:
            text += ": "
        if self.scriptname:
            text += basename(self.scriptname)
        elif self.script_edit.isModified() or self.systems_dirty:
            text += "<unsaved>"
        self.setWindowTitle(text)

    def add_system(self) -> None:
        """
        Add a system file to the system list.

        Opens a QFileDialog with filter system*.py. Update help if need
        be.
        """
        directory = matr1x.system_directories[-1]
        if not self.shortcut_dir and len(matr1x.system_names) > 1:
            self.shortcut_dir = create_temp_dir_with_symlinks(
                matr1x.system_names, matr1x.system_directories
            )
        if self.shortcut_dir:
            directory = os.path.join(self.shortcut_dir.name, matr1x.system_names[-1])
        if self.last_loaded_file:
            directory = os.path.dirname(self.last_loaded_file)
        # get filenames from dialog
        filenames = QFileDialog.getOpenFileNames(
            self, "Select system file to add", directory, "system files (system*.py)"
        )[0]
        if filenames == []:
            return
        for filename in filenames:
            self.last_loaded_file = filename
            filename = os.path.realpath(filename)
            module_name = get_importable_module_name(filename)
            if module_name:
                self.system_list.addItem(module_name)
            else:
                self.system_list.addItem(filename)
        self.remove_system_action.setEnabled(True)
        self.systems_dirty = True
        self.update_window_title()
        # update systems to use list for config editor
        self.update_systems()
        if self.system_command_help.isVisible():
            self.show_system_commands()

    def delete_selected_system(self) -> None:
        """
        Remove selected system from system_list.

        If no selection is active the last system will be removed.
        Update help if need be.
        """
        selected = self.system_list.selectedItems()
        if len(selected) > 0:
            self.system_list.takeItem(self.system_list.row(selected[0]))
        elif 0 < self.system_list.count():
            self.system_list.takeItem(self.system_list.count() - 1)
        if self.system_list.count() == 0:
            self.remove_system_action.setEnabled(False)
        self.systems_dirty = True
        self.update_window_title()
        self.update_systems()
        if self.system_command_help.isVisible():
            self.show_system_commands()

    @pyqtSlot(str, str, float, str, object, object, object, object)
    def get_script_input(
        self,
        query: str,
        input_type: str,
        timeout: float = float("inf"),
        default_value: str = "",
        min_value: Optional[float] = None,
        max_value: Optional[float] = None,
        step: Optional[float] = None,
        decimals: Optional[int] = None,
    ):
        """
        Open a dialog and forward input to the script.

        Parameters
        ----------
        query: str
         Label to explain the user what they input
        input_type: str
         Type of expected input. can be 'string' or 'bool' or 'numerical'
        timeout: float, optional
         Timeout in seconds before dialog automatically closes. Default is infinity (no timeout).
        default_value: str, optional
         Default value to show in input field and use if timeout occurs. Default is empty string.
        min_value: float, optional
         Minimum value for numerical input.
        max_value: float, optional
         Maximum value for numerical input.
        step: float, optional
         Step size for numerical input.
        """
        if input_type == "string":
            dialog = TextInputDialog(
                query, parent=self, timeout=timeout, default_value=default_value
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                ret = dialog.get_input_text()
            else:
                # abort executing script
                self.abort_thread()
                return
        elif input_type == "bool":
            dialog = YesNoAbortDialog(
                query, parent=self, timeout=timeout, default_value=default_value
            )
            ret = dialog.exec_and_get_response()
            if ret == "abort":
                self.abort_thread()
                return
        elif input_type == "numerical":
            try:
                # Convert default_value string to float
                numerical_default_value = float(default_value) if default_value else 0.0
            except ValueError:
                print(
                    f"Warning: Invalid default_value '{default_value}' "
                    "for numerical input. Using 0.0"
                )
                numerical_default_value = 0.0

            dialog = NumericalInputDialog(
                query,
                parent=self,
                timeout=timeout,
                default_value=numerical_default_value,
                min_value=min_value,
                max_value=max_value,
                step=step,
                decimals=decimals,
            )
            if dialog.exec() == QDialog.DialogCode.Accepted:
                ret = str(dialog.get_input_value())
            else:
                # abort executing script
                self.abort_thread()
                return
        elif input_type == "__end_script__":
            dialog = TerminationDialog()
            ret = dialog.get_selection()
        else:
            ret = ""
        self.measurement_thread.pass_input(ret)

    def pause_thread(self):
        """Pause thread execution."""
        self.measurement_thread.pause()

    def abort_thread(self, char="q"):
        """
        Abort thread execution and define measurement state as per `char`.

        Parameters
        ----------
            char : str
                Single length string that is passed to the process.
                - "q" stops and queries user for state
                - "a" stops and sets state to `aborted`
                - "f" stops and sets state to `finished`
        """
        if self.start_pause_action.isChecked():
            self.start_pause_action.setChecked(False)
        self.measurement_thread.abort(char)

    def kill_thread(self):
        """Kill the thread."""
        self.measurement_thread.kill()
        self.print_colored("Script terminated by user - " + "file integrity might be compromised")

    def show_editor_commands(self):
        """Print shortcuts and editor functions."""
        help_string = textwrap.dedent(
            """
        The editor includes following features:
          ctrl+/ - toggling of comments in selection
          " or ' with selection - make block comment
        """
        )
        print(help_string)

    def get_settables(
        self,
    ) -> Tuple[Union[List[int], None], Union[List[bool], None], Union[List[str], None]]:
        """
        Get the settables of the system files.

        This is used to find errors in the script and
        the help message box.

        Returns
        -------
        indexes: list [int] or None
            The indexes of the columns.
        settables : list[bool] or None
            True, if the property is settable.
        columns : list[str] or None
            The names of the columns.
        """
        # Use cached system info if available
        if hasattr(self, "_cached_system_info") and self._cached_system_info:
            return self._process_system_data(self._cached_system_info)

        json_data = get_system_info(self.systems)
        if json_data is None:
            return (None, None, None)

        return self._process_system_data(json_data)

    def _extract_parameter_index(self, key, data):
        """Extract index from parameter key or description."""
        if key.startswith("param_"):
            try:
                return key.split("_")[1]
            except IndexError:
                return ""
        elif "at index" in data.get("description", ""):
            try:
                return data["description"].split("at index ")[1]
            except IndexError:
                return ""
        return ""

    def _process_system_data(self, output):
        """Process the parsed JSON data and extract system information."""
        indexes = []
        settables = []
        columns = []

        # Process parameters section (indexed items)
        if "parameters" in output:
            for key, data in output["parameters"].items():
                index = self._extract_parameter_index(key, data)
                indexes.append(index)
                settables.append(data.get("description", ""))
                columns.append(data.get("name", ""))

        # Process devices section (no indices)
        if "devices" in output:
            for dev_id, data in output["devices"].items():
                indexes.append("")
                settables.append(data.get("description", ""))
                columns.append(data.get("name", ""))

        # Process methods section (no indices)
        if "methods" in output:
            for method_id, data in output["methods"].items():
                indexes.append("")
                settables.append(data.get("description", ""))
                columns.append(data.get("name", ""))

        return (indexes, settables, columns)

    def update_system_commands(self, cached_info: dict = None) -> None:
        """
        Update the help info about the current system(s).

        Parameters
        ----------
        cached_info : dict, optional
            Dictionary containing cached system information.
            If provided, this will be used instead of calling
            :meth:`get_settables`.  By default, None
        """
        if len(self.systems) == 0:
            text = "<p style='margin: 20px;'><b>No system file selected!</b></p>"
            text += "<p style='margin: 20px;'>"
            text += "Please add a system file using the 'Add System' button or File menu.</p>"
            text += "<p style='margin: 20px;'>"
            text += "Once a system is loaded, this dialog will show information about:</p>"
            text += "<ul style='margin-left: 40px;'>"
            text += "<li>Available parameters that can be set or read</li>"
            text += "<li>Connected devices and their configurations</li>"
            text += "<li>System methods and variables</li>"
            text += "</ul>"
        else:
            if cached_info is not None:
                # Use cached information
                indexes = cached_info.get("indexes")
                settables = cached_info.get("settables")
                columns = cached_info.get("columns")
            else:
                # Fall back to getting settables normally
                indexes, settables, columns = self.get_settables()

            if indexes and settables and columns:
                text = "The following systems were selected:<br><b>"
                for system in self.systems:
                    text = text + system + "<br>"
                text += "<br></b>These systems provide the following:<br><br>"

                # Group parameters, devices, and methods
                parameters = []
                devices = []
                methods = []

                for i in range(len(indexes)):
                    desc_str = str(settables[i]) if settables[i] is not None else ""
                    if "parameter" in desc_str.lower():
                        # Check if parameter is settable
                        is_settable = "settable" in desc_str.lower()
                        parameters.append((indexes[i], columns[i], settables[i], is_settable))
                    elif "device" in desc_str.lower():
                        devices.append((indexes[i], columns[i], settables[i]))
                    elif "method" in desc_str.lower() or "variable" in desc_str.lower():
                        methods.append((indexes[i], columns[i], settables[i]))
                    else:
                        # Fallback - anything not categorized goes to parameters
                        parameters.append((indexes[i], columns[i], settables[i], False))

                # Display parameters table
                if parameters:
                    text += "<h3>Parameters</h3>"
                    text += '<table border="1" cellpadding="5" cellspacing="0" '
                    text += 'style="border-collapse: collapse; text-align: left; '
                    text += 'margin-bottom: 20px;">'
                    text += '<tr style="background-color: #f0f0f0; text-align: left;">'
                    text += '<th style="text-align: left;">Index</th>'
                    text += '<th style="text-align: left;">Name</th>'
                    text += '<th style="text-align: left;">Description</th></tr>'
                    # Sort parameters by index for correct display order
                    parameters.sort(key=lambda x: int(x[0]) if x[0] and x[0].isdigit() else 999)
                    for idx, col, desc, is_settable in parameters:
                        if is_settable:
                            text += f"<tr><td>{idx}</td><td><b>{col}</b></td><td>{desc}</td></tr>"
                        else:
                            text += f"<tr><td>{idx}</td><td>{col}</td><td>{desc}</td></tr>"
                    text += "</table>"

                # Display devices table
                if devices:
                    text += "<h3>Devices</h3>"
                    text += '<table border="1" cellpadding="5" cellspacing="0" '
                    text += 'style="border-collapse: collapse; text-align: left; '
                    text += 'margin-bottom: 20px;">'
                    text += '<tr style="background-color: #f0f0f0; text-align: left;">'
                    text += '<th style="text-align: left;">Name</th>'
                    text += '<th style="text-align: left;">Description</th></tr>'
                    for idx, col, desc in devices:
                        text += f"<tr><td><b>{col}</b></td><td>{desc}</td></tr>"
                    text += "</table>"

                # Display methods table
                if methods:
                    text += "<h3>System Methods and Variables</h3>"
                    text += '<table border="1" cellpadding="5" cellspacing="0" '
                    text += 'style="border-collapse: collapse; text-align: left; '
                    text += 'margin-bottom: 20px;">'
                    text += '<tr style="background-color: #f0f0f0; text-align: left;">'
                    text += '<th style="text-align: left;">Name</th>'
                    text += '<th style="text-align: left;">Description</th></tr>'
                    for idx, col, desc in methods:
                        text += f"<tr><td><b>{col}</b></td><td>{desc}</td></tr>"
                    text += "</table>"

                text += "<br>"
            else:
                text = "Could not parse the system file(s)!"
        self.system_command_text_edit.setText(text)

    def show_system_commands(self) -> None:
        """Print information about current system(s) in a help window."""
        # Store current geometry if dialog is already visible
        current_geometry = None
        if self.system_command_help.isVisible():
            current_geometry = self.system_command_help.geometry()

        # Ensure the help text is updated
        self.update_system_commands()

        # Set minimum size to sizeHint
        self.system_command_help.setMinimumSize(self.system_command_help.sizeHint())

        # Load size and position from settings (only if not already visible)
        if not self.system_command_help.isVisible():
            self.settings.beginGroup("system_command_help")
            saved_size = self.settings.value("size", self.system_command_help.sizeHint())
            saved_position = self.settings.value("position", self.system_command_help.pos())
            self.settings.endGroup()
            self.system_command_help.resize(saved_size)
            self.system_command_help.move(saved_position)

        self.system_command_help.show()
        self.system_command_help.raise_()

        # Restore previous geometry if available (this will override the
        # saved settings if dialog was already visible)
        if current_geometry:
            self.system_command_help.setGeometry(current_geometry)

        # Mark that the help dialog has been shown at least once
        self._help_dialog_shown = True

    def output_written(self, text):
        """
        Append most recent text to the end of the display, place cursor at end.

        This function also tries to mimick the behavior of a carriage
        return in the output text. At the position of a carriage return
        the current line is deleted and replaced by the new text.
        """
        if len(text) > 20000:
            # if receiving very long print statements, limit display to 20k
            # symbols. This is necessary because performance of QTextEdit is
            # insufficient to handle very large texts
            prefix = "Received very long print statement, first 20k symbols:\n"
            text = prefix + text[:20000]
        self.status_preview.moveCursor(QTextCursor.MoveOperation.End)
        if "\r" in text:
            before, after = text.split("\r", maxsplit=1)
            self.status_preview.insertPlainText(before)
            # make sure cursor is at the end of the inserted text (required
            # if there is a \n in `before`).
            self.status_preview.moveCursor(QTextCursor.MoveOperation.End)
            # return cursor to beginning of line by deleting its content
            cursor = self.status_preview.textCursor()
            # select the content of the last line and clear the text
            self.status_preview.moveCursor(
                QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.MoveAnchor
            )
            self.status_preview.moveCursor(
                QTextCursor.MoveOperation.StartOfLine, QTextCursor.MoveMode.KeepAnchor
            )
            cursor.removeSelectedText()
            if "\r" in after:
                # recursion for long strings
                self.output_written(after)
            else:
                # insert text after \r at the cursor location
                self.status_preview.insertPlainText(after)
        else:
            self.status_preview.insertPlainText(text)
            self.status_preview.moveCursor(QTextCursor.MoveOperation.End)
        sb = self.status_preview.verticalScrollBar()
        sb.setValue(sb.maximum())

    def update_filename(self, path: str) -> None:
        """
        Update the current measurement filename.

        Parameters
        ----------
            path:str - path to current measurement file
        """
        self.measurement_file = path
        self.preview_action.setEnabled(True)

    def highlight(self, number: int) -> None:
        """
        Clear all annotations and highlight the currently executed line.

        Parameters
        ----------
            number:int - line number to be highlighted
        """
        self.clear_annotations()
        # this should be simpler...
        red = self.executed_line_color.red()
        green = self.executed_line_color.green()
        blue = self.executed_line_color.blue()
        highlighter = QColor(red, green, blue, 64)
        self.script_edit.setIndicatorForegroundColor(highlighter)
        self.script_edit.setIndicatorOutlineColor(self.executed_line_color)
        self.script_edit.indicatorDefine(QsciScintilla.IndicatorStyle.FullBoxIndicator, 1)
        self.script_edit.fillIndicatorRange(number, 0, number + 1, 0, 1)

    def clear_annotations(self):
        """Clear all annotations in the QScintilla edit."""
        self.script_edit.clearAnnotations()
        code_lines = self.script_edit.text().splitlines()
        last_line = len(code_lines) - 1
        if last_line >= 0:
            len_last = len(code_lines[-1])
        else:
            len_last = 0
        self.script_edit.clearIndicatorRange(0, 0, last_line, len_last, 1)

    def enable_buttons(self, flag):
        """
        Switch the buttons from thread running to thread stopped mode.

        Parameters
        ----------
            flag : bool
                True means script is running
        """
        self.is_running = flag

        if flag:
            self.start_pause_action.setIcon(MIcon("CUSTOM_Pause"))
            self.start_pause_action.setText("Pause")
            self.start_pause_action.setToolTip("Pause the currently running script.")
            self.start_pause_action.triggered.disconnect(self.start_process)
            self.start_pause_action.triggered.connect(self.pause_thread)
        else:
            self.clear_annotations()
            self.start_pause_action.setIcon(MIcon("CUSTOM_Play"))
            self.start_pause_action.setText("Start")
            self.start_pause_action.setToolTip("Execute the script.")
            self.start_pause_action.triggered.disconnect(self.pause_thread)
            self.start_pause_action.triggered.connect(self.start_process)
            self.clear_annotations()

        self.start_pause_action.setChecked(False)
        self.stop_action.setEnabled(flag)
        self.abort_action.setEnabled(flag)
        self.finish_action.setEnabled(flag)
        self.kill_action.setEnabled(flag)
        self.script_edit.setReadOnly(flag)
        self.new_file_action.setEnabled(not flag)
        self.load_action.setEnabled(not flag)
        self.help_system_action.setEnabled(not flag)
        self.add_system_action.setEnabled(not flag)
        self.remove_system_action.setEnabled(not flag)
        self.metadata.setEnabled(not flag)

    def process_finished(self):
        """
        Handle GUI changes and clean up thread after it has finished.

        Return buttons to original state, delete the finished process.
        """
        self.enable_buttons(False)
        self.print_colored("\nExecution finished")
        del self.measurement_thread

    def start_process(self):
        """
        Start the matrix_script process.

        Disable/enable buttons to reflect run state and get selected
        systems. Then runs the script defined in the edit.
        """
        if 0 == len(self.systems):
            self.start_pause_action.setChecked(False)
            self.print_colored("No system selected")
            return
        # avoid script execution for empty scripts?
        # if self.script_edit.text().strip() == "":
        #    print("No script to execute")
        #    print("==========")
        #    return
        # run linter to make sure there are no errors
        if -1 == self.script_edit.run_linter():
            self.print_colored("Script execution was halted because of linter errors")
            qApp = get_application_instance()
            qApp.processEvents()
            # open a popup window to inform about the error
            a = QMessageBox(parent=self)
            a.setText("Linter error")
            a.setInformativeText("Error found in script, continue anyway?")
            a.setStandardButtons(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            a.setDefaultButton(QMessageBox.StandardButton.Ok)
            ret = a.exec()
            if ret == QMessageBox.StandardButton.Cancel:
                self.start_pause_action.setChecked(False)
                return
        self.print_colored("### Running script now")
        # define basic part of script, imports relevant commands
        user_script = self.script_edit.text()
        script = generate_script(self.systems, user_script)
        meta_data = self.metadata.get_metadata()
        temp_config = self.config_editor.write_config()
        self.measurement_thread = ExecThread(meta_data, script, self.scriptname, temp_config)
        self.measurement_thread.lineno_signal.connect(self.highlight)
        self.measurement_thread.input_signal.connect(self.get_script_input)
        self.measurement_thread.filename_signal.connect(self.update_filename)
        self.measurement_thread.finished.connect(self.process_finished)
        logger.info("The following user script was run:\n%s", user_script)
        self.measurement_thread.start()
        self.enable_buttons(True)

    def update_systems(self, update_config=True):
        """
        Update the systems list and config editor.

        Parameters
        ----------
        update_config (bool): Whether to update the config editor.
        """
        new_systems = [
            os.path.normpath(self.system_list.item(j).text())
            for j in range(self.system_list.count())
        ]

        # Clear cache if systems changed
        if not hasattr(self, "systems") or self.systems != new_systems:
            self._cached_system_info = None

        self.systems = new_systems

        # Get system information using subprocess (cache for reuse)
        if self._cached_system_info is None and self.systems:
            try:
                self._cached_system_info = get_system_info(self.systems)
                if not self._cached_system_info:
                    print("Warning: subprocess returned empty system info")
                    self._cached_system_info = {}
            except Exception as e:
                print(f"Warning: Could not get system info for config editor: {e}")
                self._cached_system_info = {}

        # only systems that are part of matrix or ifwlib can be configured via files
        configurable = [system for system in self.systems if not os.path.exists(system)]
        matr1x.reload_config()
        if update_config:
            self.config_editor.set_systemfile(configurable)
            self.config_editor.set_full_system_list(self.systems)
            self.config_editor.set_system_info(self._cached_system_info or {})
            self.config_editor.update_data()

        # Update system commands with cached info
        self.update_system_commands(self._cached_system_info)

    def get_settable_info(self):
        """Verify that the systems match the ones from the loaded script."""
        # Use cached system info if available
        if hasattr(self, "_cached_system_info") and self._cached_system_info:
            try:
                return self._extract_settable_info(self._cached_system_info)
            except Exception:
                pass

        # Fallback to fresh system info
        try:
            system_info = get_system_info(self.systems)
            if system_info:
                self._cached_system_info = system_info
                return self._extract_settable_info(system_info)
        except Exception:
            pass

        return None

    def _extract_settable_info(self, system_info):
        """Extract settable information from system info."""
        if not system_info or "parameters" not in system_info:
            return None

        indexes = []
        columns = []
        units = []

        for param_key, param_info in system_info["parameters"].items():
            if isinstance(param_info, dict) and "name" in param_info:
                # Extract index from param_key (e.g., "param_0" -> 0)
                try:
                    index = int(param_key.split("_")[1])
                    param_name = param_info["name"]
                    param_unit = param_info.get("unit", "")

                    # Handle compound columns (names/units joined with ", ")
                    if ", " in param_name:
                        # Split compound columns back into individual columns
                        name_parts = [name.strip() for name in param_name.split(", ")]
                        unit_parts = [unit.strip() for unit in param_unit.split(", ")]

                        # Ensure we have the same number of names and units
                        if len(unit_parts) != len(name_parts):
                            unit_parts = [""] * len(name_parts)

                        for name, unit in zip(name_parts, unit_parts):
                            indexes.append(index)
                            columns.append(name)
                            units.append(unit)
                    else:
                        indexes.append(index)
                        columns.append(param_name)
                        units.append(param_unit)
                except (ValueError, IndexError):
                    continue

        return (indexes, columns, units)

    def save_file_as(self):
        """Ask for the filename and calls write_file()."""
        filename = QFileDialog.getSaveFileName(
            self,
            "Specify filename to save",
            (matr1x.usersfolder if "" == self.scriptname else dirname(self.scriptname)),
            f"matrix files (*{self.extension})",
        )
        filename = filename[0]
        return self.write_file(filename)

    def save_file(self):
        """
        Try to save under the last name and call write_file().

        if no last filename exists calls save_file_as().
        """
        if self.last_filename == "":
            return self.save_file_as()
        else:
            return self.write_file(self.last_filename)

    def write_file(self, filename):
        """Save script to file and write system information to header."""
        if "" == filename:
            self.print_colored("Please specify file")
            return -1
        elif not filename.endswith(self.extension):
            filename += self.extension
        try:
            output_file = open(filename, "w")
        except (OSError, IOError):
            self.print_colored("File cannot be opened")
            return -1
        self.scriptname = filename
        self.update_systems(update_config=False)
        # set new script in editor and save it to the file
        newscript = self.generate_save_content()
        self.script_edit.setText(newscript)
        output_file.write(newscript)
        output_file.close()
        self.last_filename = filename
        self.script_edit.setModified(False)
        self.systems_dirty = False
        self.update_window_title()
        return 0

    def generate_save_content(self):
        """Add the systems in the header of a script."""
        header = ""
        if 0 < len(self.systems):
            # only attempt generating a header if a system is selected
            try:
                # get settable information to put into the header
                # (columns/units)
                settable_info = self.get_settable_info()

                if settable_info is not None and len(settable_info) >= 3:
                    # write matrix file header
                    header += (
                        "# system def : "
                        + ",".join(repr(s).strip("'") for s in self.systems)
                        + "\n"
                    )

                    # Extract column names and units from settable_info
                    # settable_info = (indexes, columns, units)
                    column_names = [str(col).strip() for col in settable_info[1]]
                    units = [str(unit).strip() for unit in settable_info[2]]

                    header += "# system names : " + ",".join(column_names) + "\n"
                    header += "# system units : " + ",".join(units) + "\n"
                    header += "# file v8, time stamp : " + time.strftime(
                        f"{matr1x.datetimefmt}\n", time.localtime()
                    )
                else:
                    self.print_colored(
                        "warning: settable_info is incomplete, creating basic header"
                    )
                    header += (
                        "# system def : "
                        + ",".join(repr(s).strip("'") for s in self.systems)
                        + "\n"
                    )
                    header += "# file v8, time stamp : " + time.strftime(
                        f"{matr1x.datetimefmt}\n", time.localtime()
                    )
            except Exception as e:
                self.print_colored(
                    f"error in generating settable_info from file: {e}, telemetry "
                    "header could not be generated"
                )
        # take out script and remove trailling newlines
        script = self.script_edit.text().rstrip()
        newscript = header
        for i, line in enumerate(script.splitlines()):
            if i < 4 and (line.startswith("# system ") or line.startswith("# file v")):
                # if there are already definitions of the system, skip them
                continue
            newscript += line + "\n"
        return newscript

    def load_from_filename(self, filename):
        """
        Load the script from file denoted by filename.

        Also, make sure that header information specified still agree
        with the corresponding system.
        """
        if self.is_running:
            return
        if "" == filename:
            self.print_colored("Please specify file")
            return
        try:
            input_file = open(filename, "r")
        except (OSError, IOError):
            self.print_colored("File cannot be opened")
            return
        self.scriptname = filename
        self.script_edit.clear()
        self.system_list.clear()
        settable_info = None
        sys_err = False
        for i, line in enumerate(input_file):
            if 0 == i:
                if "# system def : " in line:
                    # load system from definition in file
                    system_line = line.replace("# system def : ", "").strip()
                    for syst in system_line.split(","):
                        try:
                            self.system_list.addItem(syst)
                            self.update_systems()
                            settable_info = self.get_settable_info()
                        except KeyError:
                            sys_err = True
                            self.print_colored(
                                "System that was used to generate the "
                                "script was not found in installed systems."
                                " Please check .matrix.conf file."
                            )
                else:
                    self.print_colored("No system defined in script, " + "please choose system(s)")
            elif 1 == i and not sys_err:
                # make sure that system column definition agrees with
                # current system
                if (
                    "# system names : " in line
                    and settable_info is not None
                    and len(settable_info) >= 2
                ):
                    system_names = line.strip().replace("# system names : ", "")
                    current_columns = [str(col).strip() for col in settable_info[1]]
                    # Handle both "," and ", " as separators since compound columns use ", "
                    loaded_columns = []
                    for col in system_names.split(","):
                        col = col.strip()
                        if col:
                            loaded_columns.append(col)
                    if current_columns != loaded_columns:
                        self.print_colored(
                            "Column names have changed between generation "
                            "of script and now, please make sure that "
                            "columns are set correctly before running the "
                            "script"
                        )
                else:
                    self.print_colored(
                        "Could not verify column names, please verify"
                        " that columns have not changed"
                    )
            elif 2 == i and not sys_err:
                # make sure that system unit definition agrees with
                # current system
                if (
                    "# system units : " in line
                    and settable_info is not None
                    and len(settable_info) >= 3
                ):
                    system_units = line.strip().replace("# system units : ", "")
                    current_units = [str(unit).strip() for unit in settable_info[2]]
                    # Handle both "," and ", " as separators since compound columns use ", "
                    loaded_units = []
                    for unit in system_units.split(","):
                        unit = unit.strip()
                        if unit:
                            loaded_units.append(unit)
                    if current_units != loaded_units:
                        self.print_colored(
                            "Column units have changed between generation "
                            "of script and now, please make sure that "
                            "columns are set correctly before running the "
                            "script"
                        )
                else:
                    self.print_colored(
                        "Could not verify column units, please verify"
                        " that columns have not changed"
                    )
            self.script_edit.append(line)
        input_file.close()
        self.script_edit.setModified(False)
        self.systems_dirty = False
        self.last_filename = filename
        self.update_window_title()
        if self.system_list.count() > 0:
            self.remove_system_action.setEnabled(True)

    def load_from_file(self) -> None:
        """Open file dialog and call load_from_filename."""
        # First, check if unsaved changes exist
        if self.script_edit.isModified() or self.systems_dirty:
            qApp = get_application_instance()
            qApp.processEvents()
            ret = save_messagebox(self)
            if ret == QMessageBox.StandardButton.Cancel:
                return
            if ret == QMessageBox.StandardButton.Save:
                saved = self.save_file()
                if saved == -1:
                    return
        # Now, proceed opeing the file
        filename = QFileDialog.getOpenFileName(
            self,
            "Select filename to open",
            (matr1x.usersfolder if "" == self.scriptname else dirname(self.scriptname)),
            f"matrix files (*{self.extension})",
        )
        filename = filename[0]
        self.load_from_filename(filename)

    def new_file(self) -> None:
        """
        Start over with a blank script.

        Ask the user to write unsaved changes to a file, remove the
        'system dirty' flag and forget last filename.
        """
        if self.script_edit.isModified() or self.systems_dirty:
            qApp = get_application_instance()
            qApp.processEvents()
            ret = save_messagebox(self)
            if ret == QMessageBox.StandardButton.Cancel:
                return
            if ret == QMessageBox.StandardButton.Save:
                saved = self.save_file()
                if saved == -1:
                    return
        self.systems_dirty = False
        self.last_filename = ""
        self.script_edit.clear()
        self.script_edit.setModified(False)


def main():
    """Set the basic GUI parameters and run."""
    app = Matr1xApplication(sys.argv)
    if os.name == "nt":
        # enable modern mode on windows which allows for darkmode
        app.setStyle("fusion")
    elif sys.platform == "darwin":
        set_correct_mac_appname("Matrix Script")
    appname = "matrix-script"
    app.setDesktopFileName(appname)
    with QtGracefulKiller():
        ex = MainWindow(filename=sys.argv[1] if len(sys.argv) >= 2 else None)
        if config["duplicate_output_to_logfile"]:
            sys.stdout = OutputDuplication(sys.stdout, prefix=appname)
            sys.stderr = OutputDuplication(sys.stderr, prefix=appname, fallbackname="stderr")
        ex.show()
        ex.restore_window_state()
        ret = app.exec()
    if config["duplicate_output_to_logfile"]:
        sys.stdout.close()
        sys.stderr.close()
    sys.stderr = sys.__stderr__
    sys.stdout = sys.__stdout__
    sys.exit(ret)
