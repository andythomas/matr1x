# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2024 matr1x developers. All rights reserved.
# ---
from __future__ import unicode_literals

import ast
import getpass
import logging
import os
import re
import socket
import subprocess
import sys
import tempfile
import textwrap
import warnings
from os.path import basename, dirname, join

import autopep8
import matr1x
import pyflakes.checker
import pyflakes.messages
import pyflakes.reporter
from matr1x.control.util import QtGracefulKiller
from matr1x.util import (create_temp_dir_with_symlinks, generate_script,
                         generate_script_prefix_suffix,
                         get_importable_module_name)

# Try to import Qt6 and fallback to Qt5 if not available
try:
    from PyQt6.Qsci import QsciAPIs, QsciLexerPython, QsciScintilla
    from PyQt6.QtCore import QEvent, QObject, Qt, QThread, pyqtSignal
    from PyQt6.QtGui import (QColor, QFont, QIcon, QKeySequence, QPalette,
                             QShortcut, QTextCursor)
    from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QFileDialog,
                                 QGridLayout, QLineEdit, QListWidget,
                                 QMainWindow, QMessageBox, QPushButton,
                                 QSplitter, QTextEdit, QWidget)
except ImportError:
    warnings.warn("PyQt5 support will be removed in 2024. Switch to PyQt6",
                  DeprecationWarning)
    from PyQt5.QtCore import QEvent, QThread, QObject, Qt, pyqtSignal
    from PyQt5.QtGui import (QColor, QFont, QIcon, QKeySequence, QPalette,
                             QTextCursor)
    from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QFileDialog,
                                 QGridLayout, QLineEdit, QListWidget,
                                 QMainWindow, QMessageBox, QPushButton,
                                 QShortcut, QSplitter, QTextEdit, QWidget)
    from PyQt5.Qsci import QsciScintilla, QsciLexerPython, QsciAPIs

from ..gui_util import EmittingStream

logger = logging.getLogger(os.path.split(__file__)[-1])
logger.info("matrix-script starting")

# define syntax styles, currently only a single style for ~white background
# is implemented, in the future also support dark mode?
STYLES = {
    QsciLexerPython.Default: QColor('black'),
    QsciLexerPython.Keyword: QColor('blue'),
    QsciLexerPython.Operator: QColor('red'),
    QsciLexerPython.FunctionMethodName: QColor('darkGreen'),
    QsciLexerPython.ClassName: QColor('darkBlue'),
    QsciLexerPython.HighlightedIdentifier: QColor('darkCyan'),
    QsciLexerPython.SingleQuotedString: QColor('darkMagenta'),
    QsciLexerPython.SingleQuotedFString: QColor('darkMagenta'),
    QsciLexerPython.TripleSingleQuotedString: QColor('darkMagenta'),
    QsciLexerPython.TripleSingleQuotedFString: QColor('darkMagenta'),
    QsciLexerPython.DoubleQuotedString: QColor('darkRed'),
    QsciLexerPython.DoubleQuotedFString: QColor('darkRed'),
    QsciLexerPython.TripleDoubleQuotedString: QColor('darkRed'),
    QsciLexerPython.TripleDoubleQuotedString: QColor('darkRed'),
    QsciLexerPython.Comment: QColor("#666666"),
    QsciLexerPython.Identifier: QColor('black'),
    QsciLexerPython.Number: QColor('brown'),
}

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

SCRIPT_OFFSET = len(generate_script_prefix_suffix("")[0].split('\n'))


class Matr1xApplication (QApplication):
    openfile = pyqtSignal(str)

    def event(self, event):
        if event.type() == QEvent.Type.FileOpen:
            filename = event.file()
            self.openfile.emit(filename)
        return QApplication.event(self, event)


class DroppableWidget(QWidget):
    fileDropped = pyqtSignal(str)  # Custom signal to emit file path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)  # Enable drag and drop for this widget

    def is_valid_extension(self, file_path):
        return file_path.endswith(MainWindow.extension)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1:
            file_path = urls[0].toLocalFile()
            if self.is_valid_extension(file_path):
                self.fileDropped.emit(file_path)
            else:
                QMessageBox.warning(
                    self,
                    "Invalid Action",
                    f"Only files with {MainWindow.extension} extension can be dropped.")
        else:
            QMessageBox.warning(self, "Multiple Files",
                                "Please drop only a single file.")


class CustomReporter(pyflakes.reporter.Reporter):

    def __init__(self, stream, hook):
        """
        only use a single stream from errors and warnings
        provide a hook to handle the linter errors

        Parameters:
            hook : function
                callback to call on script errors. Should accept the line,
                column (cursor position), a message, its arguments, and
                a number which styles the response
        """
        super().__init__(stream, stream)
        self.linter_hook = hook

    def flake(self, message):
        """
        Reimplementing the flaker function, called if formatting or similar
        error is found (naming etc.)
        """
        style = 0
        if message.__class__.__name__ in LINTER_ERRORS:
            style = 1
        self.linter_hook(message.lineno-SCRIPT_OFFSET, message.col-4,
                         message.message % message.message_args,
                         message.message_args, style)

    def syntaxError(self, filename, msg, lineno, offset, text):
        """
        Reimplementing the syntax error function, handles the messages
        and properly initializes the linter hook
        """
        if text is None:
            line = None
        else:
            line = text.splitlines()[-1]

        m = re.search(r'line (\d+)', msg)
        if m is not None:
            lineno = int(m.groups(0)[0])
            line = None
        else:
            # lineno might be None if the error was during tokenization
            # lineno might be 0 if the error came from stdin
            lineno = max(lineno or 0, 1)

        lineno -= SCRIPT_OFFSET

        msg = re.sub(r'line (\d+)', f"line {lineno+1}", msg)

        if offset is not None:
            if offset >= 4:
                offset -= 5
        else:
            offset = 0
        if line is not None:
            ret = (f"{msg} : {line.lstrip()}", (f"{line.lstrip()[offset:]}",))
        else:
            ret = (f"{msg}", ("",))
        self.linter_hook(lineno, offset, *ret, 1)


# below code is adapted from the eric7 editor
# -*- coding: utf-8 -*-
# Copyright (c) 2007 - 2023 Detlev Offenbach <detlev@die-offenbachs.de>
# license is GPLv3
#
def rxIndex(rx, txt):
    """
    Function to get the index (start position) of a regular expression match
    within some text.

    @param rx regular expression object as created by re.compile()
    @type re.Pattern
    @param txt text to be scanned
    @type str
    @return start position of the match or -1 indicating no match was found
    @rtype int
    """
    match = rx.search(txt)
    if match is None:
        return -1
    else:
        return match.start()


class CompleterPython(QObject):
    """
    Class implementing a python completer
    """

    def __init__(self, editor, parent=None):
        """
        Constructor

        @param editor reference to the editor object (QScintilla.Editor)
        @param parent reference to the parent object (QObject)
            If parent is None, we set the editor as the parent.
        """
        if parent is None:
            parent = editor

        super().__init__(parent)

        self.editor = editor
        self.enabled = False

        self.__defRX = re.compile(
            r"^[ \t]*(async[ \t]+)?(def|cdef|cpdef) \w+\(")
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

        self.__openBrackets = ('(', '[', '{')
        self.__closeBrackets = (')', ']', '}')

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

        @param enable flag indicating the new enabled state (boolean)
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

        @return enabled state (boolean)
        """
        return self.enabled

    def charAdded(self, charNumber):
        """
        Public slot called to handle the user entering a character.

        @param charNumber value of the character entered (integer)
        """
        char = chr(charNumber)
        if char not in ["(", ")", "{", "}", "[", "]", " ", ",", "'",
                        '"', "\n", ":"]:
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
                    self.__classRX.fullmatch(
                        txt) is not None and txt.endswith("(")
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
                        self.editor.setSelection(
                            line - 1, startBlanks, line - 1, endBlanks
                        )
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
                            self.editor.setCursorPosition(line,
                                                          lastOpenIndex + 1)
                self.editor.endUndoAction()

    def __dedentToIf(self):
        """
        Private method to dedent the last line to the last if statement with
        less (or equal) indentation.
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
                rxIndex(self.__ifRX, txt) == 0 or rxIndex(
                    self.__elifRX, txt) == 0
            ) and edInd <= indentation:
                self.editor.cancelList()
                self.editor.setIndentation(line, edInd)
                break
            ifLine -= 1

    def __dedentElseToIfWhileForTry(self):
        """
        Private method to dedent the line of the else statement to the last
        if, while, for or try statement with less (or equal) indentation.
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
                rxIndex(self.__elifRX, txt) == 0
                and edInd == indentation
                and edInd == prevInd
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
        Private method to dedent the line of the except statement to the last
        try statement with less (or equal) indentation.
        """
        line, col = self.editor.getCursorPosition()
        indentation = self.editor.indentation(line)
        tryLine = line - 1
        while tryLine >= 0:
            txt = self.editor.text(tryLine)
            edInd = self.editor.indentation(tryLine)
            if (
                rxIndex(self.__exceptcRX, txt) == 0
                or rxIndex(self.__finallyRX, txt) == 0
            ) and edInd <= indentation:
                indentation = edInd - 1
            elif (
                rxIndex(self.__exceptRX, txt) == 0 or rxIndex(
                    self.__tryRX, txt) == 0
            ) and edInd <= indentation:
                self.editor.cancelList()
                self.editor.setIndentation(line, edInd)
                break
            tryLine -= 1

    def __dedentFinallyToTry(self):
        """
        Private method to dedent the line of the except statement to the last
        try statement with less (or equal) indentation.
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
        Private method to dedent the line of the def statement to a previous
        def statement or class statement.
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
                    newInd = edInd + (
                        self.editor.indentationWidth() or
                        self.editor.tabWidth()
                    )
                if newInd >= 0:
                    self.editor.cancelList()
                    self.editor.setIndentation(line, newInd)
                    break
            tryLine -= 1

    def __isClassMethod(self):
        """
        Private method to check, if the user is defining a class method.

        @return flag indicating the definition of a class method (boolean)
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
                    (
                        rxIndex(self.__defSelfRX, txt) == 0
                        or rxIndex(self.__defClsRX, txt) == 0
                    )
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
        Private method to check, if the user is defing a class method
        (@classmethod).

        @return flag indicating the definition of a class method (boolean)
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
        Private method to check, if the user is defing a static method
        (@staticmethod) method.

        @return flag indicating the definition of a static method (boolean)
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
        Private method to check, if the cursor is inside a comment.

        @param line current line (integer)
        @param col current position within line (integer)
        @return flag indicating, if the cursor is inside a comment (boolean)
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
        Private method to check, if the cursor is within a double quoted
        string.

        @return flag indicating, if the cursor is inside a double
            quoted string (boolean)
        """
        return self.editor.currentStyle() == QsciLexerPython.DoubleQuotedString

    def __inTripleDoubleQuotedString(self):
        """
        Private method to check, if the cursor is within a triple double
        quoted string.

        @return flag indicating, if the cursor is inside a triple double
            quoted string (boolean)
        """
        return (self.editor.currentStyle() ==
                QsciLexerPython.TripleDoubleQuotedString)

    def __inSingleQuotedString(self):
        """
        Private method to check, if the cursor is within a single quoted
        string.

        @return flag indicating, if the cursor is inside a single
            quoted string (boolean)
        """
        return self.editor.currentStyle() == QsciLexerPython.SingleQuotedString

    def __inTripleSingleQuotedString(self):
        """
        Private method to check, if the cursor is within a triple single
        quoted string.

        @return flag indicating, if the cursor is inside a triple single
            quoted string (boolean)
        """
        return (self.editor.currentStyle() ==
                QsciLexerPython.TripleSingleQuotedString)


class QScintillaCustom(QsciScintilla, DroppableWidget):
    """
    Commenting functionality adapted from
    https://github.com/matkuki/qscintilla_docs/blob/master/examples/commenting.py
    License is GPLv3.
    """
    comment_string = "# "
    line_ending = "\n"
    fileDropped = pyqtSignal(str)

    def __init__(self, stream, parent=None):
        super().__init__(parent=parent)
        self.output_stream = stream
        self.reporter = CustomReporter(self.output_stream,
                                       self.handle_linter)

    def keyPressEvent(self, event):
        # Check pressed key information
        key = event.key()
        key_modifiers = QApplication.keyboardModifiers()
        if (key == Qt.Key.Key_Slash and
                key_modifiers == Qt.KeyboardModifier.ControlModifier):
            # toggle comment on selected lines
            self.toggle_commenting()
            return
        if (key == Qt.Key.Key_8 and
                key_modifiers == Qt.KeyboardModifier.ControlModifier):
            # reformat code using autopep8
            self.setText(autopep8.fix_code(self.text(), options=None))
            return
        if (key == Qt.Key.Key_L and
                key_modifiers == Qt.KeyboardModifier.ControlModifier):
            # run the linter
            self.run_linter()
            return
        if key == Qt.Key.Key_QuoteDbl:
            # check that something is selected
            if bool(self.SendScintilla(self.SCI_GETSELECTIONEMPTY)) is False:
                self.add_block_commenting('"')
                return
        if key == Qt.Key.Key_Apostrophe:
            # check that something is selected
            if bool(self.SendScintilla(self.SCI_GETSELECTIONEMPTY)) is False:
                self.add_block_commenting("'")
                return
        # Execute the superclasses event
        super().keyPressEvent(event)

    def run_linter(self):
        """
        convenience function to call the linter, generates the script
        according to what matrix_script would do when one presses the run
        button. Custom definitions for parameters that are passed by the
        process are made here.

        Returns -1 if a syntax error was found
        """
        # remove potential annotations from previous linting run
        self.clearAnnotations()
        last_line = len(self.text().splitlines()) - 1
        len_last = len(self.text().splitlines()[-1])
        # remove potential indicators from previous linting run
        for i in range(2):
            self.clearIndicatorRange(0, 0, last_line, len_last, i)
        if self.text().strip() != "":
            # add initial definitions that are passed to the script
            # externally to avoid linter errors, make sure not to add an
            # additional line here
            script = "_wait=lambda x:x;_print=lambda x:x;_input=lambda x:x;"
            script += "_report_line=lambda x:x;_user='';_sample='';"
            script += "_scriptname='';"
            script += generate_script("", self.text())
            # reimplement the pyflakes.api.check function
            scriptname = "sc"
            ret_err = 0
            try:
                tree = ast.parse(script, filename=scriptname)
            except SyntaxError as e:
                self.reporter.syntaxError(scriptname, e.args[0], e.lineno,
                                          e.offset, e.text)
                ret_err = -1
            except Exception:
                self.reporter(scriptname, "problem decoding source")
                ret_err = -1
            if ret_err == -1:
                print("Linter found a syntax error.")
                return ret_err
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
            print_str = "Linter found "
            if n_msg == 0:
                print_str += "no issues."
                print(print_str)
            else:
                if n_err > 0:
                    print_str += f"{n_err} error{'s' if n_err > 1 else ''}"
                    print_str += " and " if n_warn > 0 else "."
                if n_warn > 0:
                    print_str += f"{n_warn} warning{'s' if n_warn > 1 else ''}."
                print(print_str)
            return ret_err
        print("Nothing to lint")
        return 0

    def handle_linter(self, line, col, message, message_args, style):
        """
        call back function that is passed to the reporter of the linter.
        """
        if line < 0 or line >= len(self.text().splitlines()):
            print("error outside script", message)
            return
        # remove comment to add verbose output of linter to status_preview
        # print(f"Error in line {line+1} at position {col+1} : \n  {message}")
        self.indicatorDefine(QsciScintilla.IndicatorStyle.FullBoxIndicator,
                             style)
        offset = 0
        if len(message_args) > 0:
            # TODO: Look at all message_args and see which make sense to
            # include here
            if isinstance(message_args[0], (str, tuple, list)):
                offset = len(message_args[0])
        self.fillIndicatorRange(line, col, line, col+offset, style)
        self.annotate(line, message, style)
        # move the cursor to the position of the last error
        self.setCursorPosition(line, col)

    def add_block_commenting(self, char):
        """
        function to handle the block commenting
        """
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
            end_index = self.positionFromLineIndex(sel[1], sel[3]+increment)
            if i == 0:
                self.SendScintilla(
                    self.SCI_SETSELECTION, start_index, end_index)
            else:
                self.SendScintilla(
                    self.SCI_ADDSELECTION, start_index, end_index)
        # Set the end of the undo action
        self.endUndoAction()

    def toggle_commenting(self):
        """
        function to handle the comment toggling using # comments
        if one of the lines is not commented, adds a # to one line,
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
                sel[0], lmax-1,
                self._uncomment if all_commented else self._comment)
        # Select back the previously selected regions
        self.SendScintilla(self.SCI_CLEARSELECTIONS)
        # shift depending on the comment
        shift = -2 if all_commented else 2
        for i, sel in enumerate(selections):
            # shift the start index by the commenting string
            start_index = self.positionFromLineIndex(sel[0],
                                                     sel[2] + shift)
            if sel[3] == 0:
                end_index = self.positionFromLineIndex(
                    sel[1], sel[3])
            else:
                end_index = self.positionFromLineIndex(
                    sel[1], sel[3] + shift)
            if i == 0:
                self.SendScintilla(
                    self.SCI_SETSELECTION, start_index, end_index)
            else:
                self.SendScintilla(
                    self.SCI_ADDSELECTION, start_index, end_index)
        # Set the end of the undo action
        self.endUndoAction()

    def get_selections(self):
        """
        Obtain the selections
        """
        # Get the selection and store them in a list
        selections = []
        for i in range(self.SendScintilla(self.SCI_GETSELECTIONS)):
            selection = (
                self.SendScintilla(self.SCI_GETSELECTIONNSTART, i),
                self.SendScintilla(self.SCI_GETSELECTIONNEND, i)
            )
            # Add selection to list
            from_line, from_index = self.lineIndexFromPosition(selection[0])
            to_line, to_index = self.lineIndexFromPosition(selection[1])
            selections.append((from_line, to_line, from_index, to_index))
        selections.sort()
        # Return selection list
        return selections

    def merge_test(self, selections):
        """
        Test if merging of selections is needed
        """
        for i in range(1, len(selections)):
            # Get the line numbers
            previous_end_line = selections[i-1][1]
            current_start_line = selections[i][0]
            if previous_end_line == current_start_line:
                return True
        # Merging is not needed
        return False

    def merge_selections(self, selections):
        """
        This function merges selections with overlapping lines
        """
        # Test if merging is required
        if len(selections) < 2:
            return selections
        merged_selections = []
        skip_flag = False
        for i in range(1, len(selections)):
            # Get the line numbers
            previous_start_line = selections[i-1][0]
            previous_end_line = selections[i-1][1]
            current_start_line = selections[i][0]
            current_end_line = selections[i][1]
            # Test for merge
            if previous_end_line == current_start_line and skip_flag is False:
                merged_selections.append(
                    (previous_start_line, current_end_line)
                )
                skip_flag = True
            else:
                if skip_flag is False:
                    merged_selections.append(
                        (previous_start_line, previous_end_line)
                    )
                skip_flag = False
                # Add the last selection only if it was not merged
                if i == (len(selections) - 1):
                    merged_selections.append(
                        (current_start_line, current_end_line)
                    )
        # Return the merged selections
        return merged_selections

    def set_block_commenting(self, from_line, to_line, from_index,
                             to_index, char):
        # Set the selection from the beginning of the cursor line
        # to the end of the last selection line
        self.setSelection(
            from_line, from_index, to_line, to_index
        )
        # Get the selected text and split it into lines
        selected_text = self.selectedText()
        replace_text = char + selected_text + char
        # Replace the whole selected text with the merged lines
        # containing the commenting characters
        self.replaceSelectedText(replace_text)

    def set_commenting(self, arg_from_line, arg_to_line, func):
        # Get the cursor information
        from_line = arg_from_line
        to_line = arg_to_line
        # Check if ending line is the last line in the editor
        last_line = to_line
        if last_line == self.lines() - 1:
            to_index = len(self.text(to_line))
        else:
            to_index = len(self.text(to_line))-1
        # Set the selection from the beginning of the cursor line
        # to the end of the last selection line
        self.setSelection(
            from_line, 0, to_line, to_index
        )
        # Get the selected text and split it into lines
        selected_text = self.selectedText()
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
            return (line[:indent_level] + self.comment_string +
                    line[indent_level:])
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

        @param pos position in the text (integer)
        @return style at the requested position or 0, if the position
            is negative or past the end of the document (integer)
        """
        return self.SendScintilla(QsciScintilla.SCI_GETSTYLEAT, pos)

    def currentStyle(self):
        """
        Public method to get the style at the current position.

        @return style at the current position (integer)
        """
        return self.styleAt(self.currentPosition())

    def currentPosition(self):
        """
        Public method to get the current position.

        @return absolute position of the cursor (integer)
        """
        return self.SendScintilla(QsciScintilla.SCI_GETCURRENTPOS)

    def editorCommand(self, cmd):
        """
        Public method to perform a simple editor command.

        @param cmd the scintilla command to be performed (integer)
        """
        self.SendScintilla(cmd)


class CustomLexer(QsciLexerPython):

    def keywords(self, val):
        # reimplement a custom lexer to also handle the matrix_script custom
        # commands for code highlighting
        if 2 != val:
            return super().keywords(val)
        return ("init_datafile measure_system wait set_value trigger_value "
                "read_value meta_data devs sys input")


class CustomQsciAPI(QsciAPIs):
    # definition of custom commands that are supposed to be autocompleted
    autocompletions = [
        "sys", "meta_data", "meta_data['Creator']", "meta_data['Identifier']",
        "devs", "wait(float seconds, str message='', float silent=10)",
        "input(str message='')",
        "init_datafile(str filename, str comment='', bool append=False, "
        "bool print_header=True, int ntot=None)",
        "measure_system(bool print_setpoint=True, bool print_data=True, bool print_telemetry=True)",
        "set_value(int value_index, value)",
        "set_value(str name, value)",
        "read_value(int value_index)",
        "read_value(str name)",
        "trigger_value(int value_index)",
        "trigger_value(str name)", ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for ac in self.autocompletions:
            self.add(ac)


if os.name == 'nt':
    try:
        from ctypes import windll  # Only exists on Windows.
        myappid = 'python.matr1x.matrix-script.version'
        windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except ImportError:
        pass


class ExecThread(QThread):

    def __init__(self, sample, user, script, fallbackname, callback):
        """
        initialize thread that handles script execution with meta data and
        script

        Parameters:
            sample : string
                sample name from gui that will be used in the meta data
            user : string
                user name from gui that will be used in the meta data
            script : string
                user script that is supposed to be run by the ExecThread.
            fallbackname : string
                filename used to initialize the data file if not specified
                in the script. Its directory path will be used as execution
                directory.
            callback : function
                callback to report the currently executing line number to.
                Must accept a single integer parameter.
        """
        super().__init__()
        self.proc = None
        self.conn = None
        self.sample = sample
        self.user = user
        self.script = script
        self.datafilefallback = fallbackname
        self.callback = callback

    def pass_input(self, inp):
        """ communicate user input to the subprocess """
        if self.proc is None or self.conn is None:
            return
        if inp == "":
            return
        if inp[-1] != "\n":
            # input needs to have terminating character
            inp += "\n"
        self.conn.send(("i"+inp).encode("utf-8"))

    def pause(self):
        """ communicate pause to the subprocess """
        if self.proc is None or self.conn is None:
            return
        self.conn.send("p".encode())

    def abort(self):
        """ communicate stop to the subprocess' stdin """
        if self.proc is None or self.conn is None:
            return
        self.conn.send("q".encode())

    def kill(self):
        """ kill the process and make sure it is indeed stopped """
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
            print("please verify all devices are operational before starting",
                  "another script")
        except OSError:
            # this will likely not happen
            print("thread terminated gracefully")

    def recv_line(self, inp):
        """
        receives a line from the input and extracts the current line
        executing from the message, all other input is printed.

        TODO: not tolerant against split strings, i.e. if sent string
        is longer than 1024, one can expect a problematic behavior. Migrate
        to ZMQ and directly pass strings as python objects?
        """
        pattern = r"__lineno(-?\d+)__"
        lines = inp.split(os.linesep)
        for i, line in enumerate(lines[:-1]):
            # add "\n" to all but the last element in split
            # (last element contains everything after last "\n")
            lines[i] += "\n"
        for line in lines:
            match = re.search(pattern, line)
            if match:
                digits = match.group(1)
                if int(digits) > 0:
                    self.callback(int(digits))
            printstr = re.sub(pattern, "", line)
            if printstr != "":
                print(printstr, end="")

    def run(self):
        """
        runs the subprocess
            first writes the user script into a temporary file to make sure all
            formating is conserved, then passes that file to the interpreter to
            run the script
            the purpose of using a subprocess is to keep the namespace clear of
            all system files. That allows changes to the system while
            matrix-script is running.
        """
        with tempfile.NamedTemporaryFile(mode="w+b") as tf:
            for line in self.script:
                tf.write(line.encode())
            # all information has been written to temporary file, make sure it
            # is updated
            tf.flush()
            # pass the script that we want to execute and generate correct
            # parameters to pass to matr1x/utils.py:matrix_script_process
            cmd = (f"""import matr1x.util as mu
mu.matrix_script_process({repr(tf.name)}, {repr(self.user)} ,
                         {repr(self.sample)}, {repr(self.datafilefallback)})""")
            # start socket that is used to communicate with the child process
            # that runs the script
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # only accept local connections and start listening
            s.bind(('127.0.0.1', matr1x.scripts.MATRIX_SCRIPT_PORT))
            s.listen(1)
            # start subprocess, stderr is piped to stdout, and both of them are
            # piped so that we can read them
            self.proc = subprocess.Popen([sys.executable, "-c", cmd],
                                         stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, bufsize=0)
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


class MainWindow(QMainWindow):
    """
    Define layout, runs everything
    """
    # signal that is used to handle the highlighting of code execution
    highlight_line = pyqtSignal(int)
    extension = ".matrix"

    def __init__(self, filename=None):
        """
        Initialize the GUI for scripted matrix control
        """
        super().__init__()
        self.systems = []
        self.scriptname = ""
        self.systems_dirty = False
        self.last_loaded_file = None
        self.is_running = False
        self.shortcut_dir = None

        self.output_stream = EmittingStream(text_written=self.output_written)

        self.init_ui()
        # set outputStream as stdout (i.e. all output is written to status
        # preview
        sys.stdout = self.output_stream

        welcome_string = textwrap.dedent(f"""\
        Welcome {getpass.getuser()},
        Available functions are:

          init_datafile(filename, comment="", append=False,
                        print_header=True, ntot=None)
            # ntot is total number of points in a given measurement
            # and is used to calculate measurement duration
          measure_system(print_setpoint=True, print_data=True,
                         print_telemetry=True)
            # performs a single measurement as specified in system
          wait(seconds, message="", silent=10)
            # waits for seconds and acts as a breakpoint to pause and
            # abort the execution, for seconds>silent, prints message
          input(message="")
            # waits for user input via the send button

        System parameters can be accessed via:

          set_value(value_index/name, value)
          trigger_value(value_index/name)
          read_value(value_index/name)
          devs  # dictionary that contains all devices
          sys  # merged system object from the selected systems
          meta_data  # dictionary that contains all meta information
                     # Keywords "Creator" and "Identifier" contain
                     # user and sample information from the line edits

        Use the help button to get a list of available parameters and devices.

        Note that no variable names should start with an underscore!""")
        print(welcome_string)
        print("==========")
        # If filename is passed when matrix-script is started, start
        # by loading the file
        if filename is not None:
            self.load_from_filename(filename)

    def closeEvent(self, event):
        """
        Capture the close event to query user whether he still wants to
        save changes to the script

        do we also want to terminate/abort the currently executing script when
        matrix is terminated?
        """
        if self.systems_dirty and "" != self.scriptname:
            # if no file is given, nothing is saved
            self.update_systems()
            newscript = self.generate_save_content()
            with open(self.scriptname, "r") as f:
                saved_text = f.read()
                if saved_text == newscript:
                    self.systems_dirty = False

        if self.script_edit.isModified() or self.systems_dirty:
            qApp = QApplication.instance()
            qApp.processEvents()
            a = QMessageBox(parent=self)
            a.setIcon(QMessageBox.Icon.Question)
            a.setText("The script has been modified")
            a.setInformativeText("Do you want to save your changes?")
            a.setStandardButtons(QMessageBox.StandardButton.Save |
                                 QMessageBox.StandardButton.Discard |
                                 QMessageBox.StandardButton.Cancel)
            a.setDefaultButton(QMessageBox.StandardButton.Save)
            # Is this the best default button?
            ret = a.exec()
            if ret == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if ret == QMessageBox.StandardButton.Save:
                # save the file
                if -1 == self.save_to_file():
                    # if save fails, ignore message
                    event.ignore()
                    return
        event.accept()

    def init_ui(self):
        icondir = join(dirname(__file__), 'icons')
        self.setWindowIcon(QIcon(join(icondir, 'matr1x-matrix-script.png')))
        self.central_widget = DroppableWidget(self)
        self.central_widget.fileDropped.connect(self.load_from_filename)
        self.setCentralWidget(self.central_widget)
        layout = QGridLayout(self.central_widget)

        # Buttons
        self.start_button = QPushButton("Start recipe")
        self.start_button.clicked.connect(self.start_process)
        self.abort_button = QPushButton("Abort")
        self.abort_button.setEnabled(False)
        self.abort_button.clicked.connect(self.abort_thread)
        self.send_button = QPushButton("Send to matrix")
        self.send_button.setVisible(False)
        self.send_button.clicked.connect(self.send_to_thread)
        self.kill_button = QPushButton("Kill")
        self.kill_button.setEnabled(False)
        self.kill_button.clicked.connect(self.kill_thread)
        self.pause_button = QPushButton("Pause")
        self.pause_button.setCheckable(True)
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self.pause_thread)
        self.save_button = QPushButton("Save recipe")
        self.save_button.clicked.connect(self.save_to_file)
        # enable saving of script by Ctrl+S
        self.save_scriptsc = QShortcut(QKeySequence('Ctrl+S'), self)
        self.save_scriptsc.activated.connect(self.save_to_file)
        self.load_button = QPushButton("Load recipe")
        self.load_button.clicked.connect(self.load_from_file)
        self.help_sys_button = QPushButton("Help system")
        self.help_sys_button.clicked.connect(self.show_commands)
        self.help_edit_button = QPushButton("Help editor")
        self.help_edit_button.clicked.connect(self.show_editor_commands)
        self.system_list = QListWidget()
        self.system_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection)
        self.system_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove)
        self.add_button = QPushButton('add system')
        self.add_button.clicked.connect(self.show_file_dialog)
        self.del_button = QPushButton('remove system')
        self.del_button.clicked.connect(self.delete_selected_system)

        # LineEdits
        self.send_edit = QLineEdit(self)
        self.send_edit.setPlaceholderText("text to send to script")
        self.send_edit.setVisible(False)
        self.sample_edit = QLineEdit(self)
        self.sample_edit.setPlaceholderText("sample name")
        self.user_edit = QLineEdit(self)
        self.user_edit.setPlaceholderText("user name")
        # Font
        mono_font = QFont("Monospace")
        mono_font.setStyleHint(QFont.StyleHint.TypeWriter)
        # TextEdits
        self.status_preview = QTextEdit(self)
        self.status_preview.setReadOnly(True)
        self.status_preview.setCurrentFont(mono_font)
        # self.status_preview.textChanged.connect(self.status_preview.setMarkdown)
        palette = self.status_preview.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(233, 233, 233))
        palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
        self.status_preview.setPalette(palette)
        # CodeEditor
        self.script_edit = QScintillaCustom(self.output_stream, self)
        # Connect text edit signals to the slot that checks for changes
        self.script_edit.modificationChanged.connect(self.update_window_title)
        lexer = CustomLexer(self)
        self.script_edit.setLexer(lexer)
        lexer.setDefaultColor(QColor('#000000'))
        lexer.setPaper(QColor(233, 233, 233))
        lexer.setFont(mono_font)
        for stl, clr in STYLES.items():
            lexer.setColor(clr, stl)
        autocomp = CompleterPython(self.script_edit)
        autocomp.setEnabled(True)
        # make caret more visible, highlight current line
        self.script_edit.setCaretWidth(2)
        self.script_edit.setCaretLineVisible(True)
        self.script_edit.setCaretLineBackgroundColor(QColor(225, 225, 225))
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
        self.script_edit.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.script_edit.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # autocompletion, source is document and custom commands
        api = CustomQsciAPI(lexer)
        api.prepare()
        self.script_edit.setCallTipsVisible(3)
        self.script_edit.setAutoCompletionSource(
            QsciScintilla.AutoCompletionSource.AcsAll)
        self.script_edit.setAutoCompletionThreshold(1)
        self.script_edit.setAutoCompletionCaseSensitivity(True)
        self.script_edit.setAutoCompletionFillupsEnabled(True)
        self.script_edit.setBraceMatching(
            QsciScintilla.BraceMatch.SloppyBraceMatch)
        self.script_edit.setAnnotationDisplay(
            QsciScintilla.AnnotationDisplay.AnnotationBoxed)
        self.script_edit.fileDropped.connect(self.load_from_filename)

        # initialize widgets in layout
        splitter = QSplitter(self)
        splitter.addWidget(self.script_edit)
        splitter.addWidget(self.status_preview)
        layout.addWidget(splitter, 4, 0, 4, 8)
        layout.addWidget(self.sample_edit, 8, 0, 1, 4)
        layout.addWidget(self.user_edit, 8, 4, 1, 4)
        layout.addWidget(self.send_edit, 8, 0, 1, 6)
        layout.addWidget(self.send_button, 8, 6, 1, 2)
        layout.addWidget(self.start_button, 9, 6, 1, 2)
        layout.addWidget(self.abort_button, 11, 6, 1, 2)
        layout.addWidget(self.kill_button, 12, 6, 1, 2)
        layout.addWidget(self.pause_button, 10, 6, 1, 2)
        layout.addWidget(self.save_button, 9, 0, 1, 2)
        layout.addWidget(self.load_button, 10, 0, 1, 2)
        layout.addWidget(self.help_sys_button, 11, 0, 1, 2)
        layout.addWidget(self.help_edit_button, 12, 0, 1, 2)
        layout.addWidget(self.system_list, 9, 2, 3, 4)
        layout.addWidget(self.add_button, 12, 2, 1, 2)
        layout.addWidget(self.del_button, 12, 4, 1, 2)

        # configure stretch to go only into textEdits
        layout.setRowStretch(4, 1)

        # set focus to text editor
        self.script_edit.setFocus()

        self.update_window_title()

    def update_window_title(self):
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

    def show_file_dialog(self):
        """
        Opens a QFileDialog with filter system*.py
        """
        directory = matr1x.system_directories[-1]
        if not self.shortcut_dir and len(matr1x.system_names) > 1:
            self.shortcut_dir = create_temp_dir_with_symlinks(
                matr1x.system_names, matr1x.system_directories)
        if self.shortcut_dir:
            directory = os.path.join(self.shortcut_dir.name,
                                     matr1x.system_names[-1])
        if self.last_loaded_file:
            directory = os.path.dirname(self.last_loaded_file)
        # get filenames from dialog
        filename = QFileDialog.getOpenFileName(
            self, 'Select system file', directory,
            "system files (system*.py)")[0]
        if "" == filename:
            return
        self.last_loaded_file = filename
        filename = os.path.realpath(filename)
        module_name = get_importable_module_name(filename)
        if module_name:
            self.system_list.addItem(module_name)
        else:
            self.system_list.addItem(filename)
        self.systems_dirty = True
        self.update_window_title()

    def delete_selected_system(self):
        """
        Removes selected system from system_list. If no selection is active
        the last system will be removed.
        """
        selected = self.system_list.selectedItems()
        if len(selected) > 0:
            self.system_list.takeItem(self.system_list.row(selected[0]))
        elif 0 < self.system_list.count():
            self.system_list.takeItem(self.system_list.count()-1)
        self.systems_dirty = True
        self.update_window_title()

    def send_to_thread(self):
        """ passes input to thread """
        self.thread.pass_input(self.send_edit.text())

    def pause_thread(self):
        """ pauses thread execution """
        # disable send button during pause
        self.send_button.setEnabled(not self.pause_button.isChecked())
        self.thread.pause()

    def abort_thread(self):
        """ aborts thread execution """
        self.thread.abort()

    def kill_thread(self):
        """ kills the thread """
        self.thread.kill()
        print("Script terminated by user - " +
              "file integrity might be compromised")

    def show_editor_commands(self):
        """ prints shortcuts and editor functions """
        help_string = textwrap.dedent("""
        The editor includes following features:
          ctrl+l - Linting with pyflakes
          ctrl+8 - autoformatting with autopep8
          ctrl+/ - toggling of comments in selection
          " or ' with selection - make block comment
          ctrl+z - undo command (including block comments with ' or ")
          ctrl+y - undo undo
          ctrl+s - save script to file
        """)
        print(help_string)

    def show_commands(self):
        """ prints information about current system to the status display """
        self.update_systems()
        if 0 == len(self.systems):
            print("No system selected")
            print("==========")
            return
        # use external process to not have the systems in the namespace
        info = subprocess.run(
            [sys.executable, '-c',
             "from matr1x.system import MergedSystem;"
             f"print(MergedSystem.from_files({self.systems})."
             "grab_information())"
             ],
            capture_output=True)
        # print information string
        if info.returncode != 0:
            print("Error when trying to import system")
            print("----------")
            self.status_preview.append((info.stderr).decode())
            self.status_preview.moveCursor(QTextCursor.MoveOperation.End)
        else:
            print("Devices and commands for " + ", ".join(self.systems))
            print("----------")
            self.status_preview.append((info.stdout).decode())
            self.status_preview.moveCursor(QTextCursor.MoveOperation.End)
        print("==========")
        self.status_preview.moveCursor(QTextCursor.MoveOperation.End)

    def output_written(self, text):
        """
        appends the most recent text to the end of the display and makes sure
        that the cursor remains at the end. This function also tries to mimick
        the behavior of a carriage return in the output text. At the position
        of a carriage return the current line is deleted and replaced by the
        new text.
        """
        if len(text) > 20000:
            # if receiving very long print statements, limit display to 20k
            # symbols. This is necessary because performance of QTextEdit is
            # insufficient to handle very large texts
            prefix = "Received very long print statement, first 20k symbols:\n"
            text = prefix + text[:20000]
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
                QTextCursor.MoveOperation.EndOfLine,
                QTextCursor.MoveMode.MoveAnchor)
            self.status_preview.moveCursor(
                QTextCursor.MoveOperation.StartOfLine,
                QTextCursor.MoveMode.KeepAnchor)
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

    def highlight(self, number):
        """
        clears all annotations and highlights the line that is currently being
        executed

        Parameters:
            number:integer - line number to be highlighted
        """
        self.clear_annotations()
        self.script_edit.indicatorDefine(
            QsciScintilla.IndicatorStyle.FullBoxIndicator, 1)
        self.script_edit.fillIndicatorRange(number, 0, number+1, 0, 1)

    def clear_annotations(self):
        """
        helper function that clears all annotations in the QScntilla edit
        """
        self.script_edit.clearAnnotations()
        last_line = len(self.script_edit.text().splitlines()) - 1
        len_last = len(self.script_edit.text().splitlines()[-1])
        self.script_edit.clearIndicatorRange(
            0, 0, last_line, len_last, 1)

    def enable_buttons(self, flag):
        """
        helper function to switch the buttons from thread running to
        thread stopped mode

        Parameters:
            flag:boolean - True means script is running
        """
        self.is_running = flag
        if flag is True:
            self.highlight_line.connect(self.highlight)
        else:
            self.highlight_line.disconnect()
            self.clear_annotations()
        self.pause_button.setEnabled(flag)
        self.pause_button.setChecked(False)
        self.abort_button.setEnabled(flag)
        self.send_button.setVisible(flag)
        self.send_edit.setVisible(flag)
        self.user_edit.setVisible(not flag)
        self.sample_edit.setVisible(not flag)
        self.kill_button.setEnabled(flag)
        self.script_edit.setReadOnly(flag)
        self.start_button.setEnabled(not flag)
        self.load_button.setEnabled(not flag)
        self.help_sys_button.setEnabled(not flag)
        self.add_button.setEnabled(not flag)
        self.del_button.setEnabled(not flag)

    def emit_line_signal(self, lineno):
        """
        emits signal that highlights the currently executing line number,
        used as callback for ExecThread
        """
        self.highlight_line.emit(lineno)

    def process_finished(self):
        """
        once the process is finished, return all buttons to original state and
        clean up thread
        """
        self.enable_buttons(False)
        print("\nExecution finished")
        print("==========")
        del self.thread

    def start_process(self):
        """
        disables/enables buttons to reflect the run state and extracts selected
        systems.
        Then runs the script defined in the edit
        """
        self.update_systems()
        if 0 == len(self.systems):
            print("No system selected")
            print("==========")
            return
        # avoid script execution for empty scripts?
        # if self.script_edit.text().strip() == "":
        #    print("No script to execute")
        #    print("==========")
        #    return
        # run linter to make sure there are no errors
        if -1 == self.script_edit.run_linter():
            print("Script execution was halted because of linter errors")
            print("==========")
            qApp = QApplication.instance()
            qApp.processEvents()
            # open a popup window to inform about the error
            a = QMessageBox(parent=self)
            a.setText("Linter error")
            a.setInformativeText("Error found in script, "
                                 "continue anyway?")
            a.setStandardButtons(QMessageBox.StandardButton.Ok |
                                 QMessageBox.StandardButton.Cancel)
            a.setDefaultButton(QMessageBox.StandardButton.Ok)
            ret = a.exec()
            if ret == QMessageBox.StandardButton.Cancel:
                return
        print("### Running script now")
        # define basic part of script, imports relevant commands
        user_script = self.script_edit.text()
        script = generate_script(self.systems, user_script)
        self.thread = ExecThread(self.sample_edit.text(),
                                 self.user_edit.text(),
                                 script,
                                 self.scriptname,
                                 self.emit_line_signal)
        self.thread.finished.connect(self.process_finished)
        logger.info("The following user script was run:\n%s", user_script)
        self.thread.start()
        self.enable_buttons(True)

    def update_systems(self):
        self.systems = [os.path.normpath(self.system_list.item(j).text())
                        for j in range(self.system_list.count())]

    def get_settable_info(self):
        """
        helper function to verify that the currents system and the one
        used for the loaded script match
        """
        try:
            settable_info = subprocess.run(
                [sys.executable, '-c',
                 "from matr1x.system import MergedSystem;"
                 f"print(MergedSystem.from_files({self.systems})."
                 "grab_information(settables=True))"
                 ],
                capture_output=True)
            return ast.literal_eval(
                settable_info.stdout.decode().splitlines()[-1])
        except Exception:
            return None

    def save_to_file(self):
        """
        saves the script to file, putting information about the system into
        the header
        """
        filename = QFileDialog.getSaveFileName(
            self, 'Specify Script',
            (matr1x.usersfolder if "" == self.scriptname
                else dirname(self.scriptname)),
            f"matrix files (*{self.extension})")
        filename = filename[0]
        if "" == filename:
            print("Please specify file")
            print("==========")
            return -1
        elif not filename.endswith(self.extension):
            filename += self.extension
        try:
            output_file = open(filename, 'w')
        except (OSError, IOError):
            print("File cannot be opened")
            print("==========")
            return -1
        self.scriptname = filename
        self.update_systems()
        # set new script in editor and save it to the file
        newscript = self.generate_save_content()
        self.script_edit.setText(newscript)
        output_file.write(newscript)
        output_file.close()
        self.script_edit.setModified(False)
        self.systems_dirty = False
        self.update_window_title()
        return 0

    def generate_save_content(self):
        header = ""
        if 0 < len(self.systems):
            # only attempt generating a header if a system is selected
            try:
                # get settable information to put into the header
                # (columns/units)
                settable_info = self.get_settable_info()

                # write matrix file header
                header += "# system def : " + \
                    ",".join(repr(s).strip("'") for s in self.systems) + "\n"
                header += "# system names : " + \
                    ",".join(settable_info[1]) + "\n"
                header += "# system units : " + \
                    ",".join(settable_info[2]) + "\n"
            except Exception:
                print("error in generating settable_info from file, telemetry "
                      "header could not be generated")
        # take out script and remove trailling newlines
        script = self.script_edit.text().rstrip()
        newscript = header
        for i, line in enumerate(script.splitlines()):
            if i < 3 and "# system " in line:
                # if there are already definitions of the system, skip them
                continue
            newscript += line + "\n"
        return newscript

    def load_from_filename(self, filename):
        """
        loads the script from file denoted by filename, making sure that
        header information specified still agree with the corresponding system
        """
        if self.is_running:
            return
        if "" == filename:
            print("Please specify file")
            print("==========")
            return
        try:
            input_file = open(filename, 'r')
        except (OSError, IOError):
            print("File cannot be opened")
            print("==========")
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
                    system_line = line.replace(
                        "# system def : ", "").strip()
                    for syst in system_line.split(","):
                        try:
                            self.system_list.addItem(syst)
                            self.update_systems()
                            settable_info = self.get_settable_info()
                        except KeyError:
                            sys_err = True
                            print("System that was used to generate the "
                                  "script was not found in installed systems."
                                  " Please check .matrix.conf file.")
                            print("==========\n")
                else:
                    print("No system defined in script, " +
                          "please choose system(s)")
                    print("==========\n")
            elif 1 == i and not sys_err:
                # make sure that system column definition agrees with
                # current system
                if "# system names : " in line and settable_info is not None:
                    system_names = line.strip().replace("# system names : ",
                                                        "")
                    if settable_info[1] != system_names.split(","):
                        print("Column names have changed between generation "
                              "of script and now, please make sure that "
                              "columns are set correctly before running the "
                              "script")
                        print("==========\n")
                else:
                    print("Could not verify column names, please verify"
                          " that columns have not changed")
                    print("==========\n")
            elif 2 == i and not sys_err:
                # make sure that system unit definition agrees with
                # current system
                if "# system units : " in line and settable_info is not None:
                    system_units = line.strip().replace("# system units : ",
                                                        "")
                    if settable_info[2] != system_units.split(","):
                        print("Column units have changed between generation "
                              "of script and now, please make sure that "
                              "columns are set correctly before running the "
                              "script")
                        print("==========\n")
                else:
                    print("Could not verify column units, please verify"
                          " that columns have not changed")
                    print("==========\n")
            self.script_edit.append(line)
        input_file.close()
        self.script_edit.setModified(False)
        self.systems_dirty = False
        self.update_window_title()

    def load_from_file(self):
        """
        wrapper function for load_from_filename, that opens file dialog first
        """
        filename = QFileDialog.getOpenFileName(
            self, 'Select Script',
            (matr1x.usersfolder if "" == self.scriptname
                else dirname(self.scriptname)),
            f"matrix files (*{self.extension})")
        filename = filename[0]
        self.load_from_filename(filename)


def main():
    if "_" in basename(sys.argv[0]):
        warnings.warn(
            "The executable name 'matrix_script' is deprecated. "
            "Use 'matrix-script' instead.",
            FutureWarning)
    app = Matr1xApplication(sys.argv)
    if os.name == 'nt':
        # enable modern mode on windows which allows for darkmode
        app.setStyle('fusion')
    app.setDesktopFileName("matrix-script")
    with QtGracefulKiller():
        if len(sys.argv) < 2:
            ex = MainWindow()
        else:
            ex = MainWindow(filename=sys.argv[1])
        ex.show()
        ret = app.exec()
        sys.stdout = sys.__stdout__
    sys.exit(ret)
