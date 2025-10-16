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
Editor IDE functionality for matrix-script.

This packages 'translates' to the JavaScript interface of Monaco. No
JavaScript should be used outside of this module!
"""

import ast
import json
import subprocess
import sys
import tempfile
from importlib import resources
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QEventLoop,
    QObject,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView

from matr1x.gui_util import FileDropMixin, get_application_instance
from matr1x.util import (
    generate_script,
    generate_script_prefix_suffix,
)

SCRIPT_OFFSET = len(generate_script_prefix_suffix()[0].splitlines())
COLUMN_OFFSET = 4  # The user code is wrapped in a "try:" = 4 chars

__all__ = ["CodeEditor"]


class Matr1xFunctionChecker(ast.NodeVisitor):
    """Implements ast-based function checker for matr1x functions."""

    def __init__(self, parent, indexes, settables, columns):
        self.parent = parent
        self.indexes = indexes
        self.settables = settables
        self.columns = columns
        self.errors = 0
        self.lineno: int
        self.col: int
        self.end_lineno: int
        self.end_col: int
        self.diagnostics: list[dict] = []

    def reporter(self, error_text: str) -> None:
        """
        Generate a report in the Monaco format.

        Parameters
        ----------
        error_text: str
            The error text to be displayed.
        """
        diagnostic = {
            "severity": 2,
            "startLineNumber": self.lineno - SCRIPT_OFFSET,
            "startColumn": self.col - COLUMN_OFFSET + 1,
            "endLineNumber": self.end_lineno - SCRIPT_OFFSET,
            "endColumn": self.end_col - COLUMN_OFFSET + 1,
            "message": f"{error_text}",
            "source": "Matrix checker",
            "code": "value error",
        }
        self.diagnostics.append(diagnostic)

    def returnDiagnostics(self) -> list[dict]:
        """
        Return the value checker diagnostics.

        Returns
        -------
        list[dict]
            The list of errors in the Monaco format.
        """
        return self.diagnostics

    def visit_Call(self, node):
        """Reimplemented function to perform custom function checking."""
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            self.lineno = node.func.lineno
            self.col = node.func.col_offset
            self.end_lineno = node.func.end_lineno
            self.end_col = node.func.end_col_offset

            if func_name in ("set_value", "read_value", "trigger_value"):
                args = node.args

                num_required = 2 if func_name == "set_value" else 1

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
                            self.reporter(error_text)
                            return
                        else:
                            self.errors += 1
                            error_text = "too few parameters."
                            self.reporter(error_text)
                            return
                    else:
                        self.errors += 1
                        error_text = "too few parameters."
                        self.reporter(error_text)
                        return
                elif len(args) > num_required:
                    self.errors += 1
                    error_text = "too many parameters."
                    self.reporter(error_text)
                    return
                col_name = args[0]
                if isinstance(col_name, ast.Constant):
                    value = col_name.value
                    if isinstance(value, int):
                        if value >= len(self.indexes) or value < 0:
                            # make sure column index is in valid range
                            self.errors += 1
                            error_text = f"index <{value}> beyond valid range."
                            self.reporter(error_text)
                        elif not self.settables[value] and func_name == "set_value":
                            # make sure column is settable in set_value
                            self.errors += 1
                            error_text = f"index <{value}> not settable."
                            self.reporter(error_text)
                    elif value not in self.columns:
                        # check validity of string based columns
                        self.errors += 1
                        error_text = f"<{value}> not a valid column name."
                        self.reporter(error_text)
                    elif (
                        not self.settables[self.columns.index(value)] and func_name == "set_value"
                    ):
                        # make sure column is settable in set_value function
                        self.errors += 1
                        error_text = f"column <{value}> not settable."
                        self.reporter(error_text)
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
                    self.reporter(error_text)


class Linter(QObject):
    """
    Ruff linting to be used with the Monaco Editor.

    This is the Python backend class for the JavaScript editor.
    """

    lintingComplete = Signal(str)

    def __init__(self, parent=None):
        super().__init__()
        self.parent = parent
        self.current_diagnostics_count = 0
        self.issues: int = 0

    RUFF_RULES = [
        "F821",
        "F822",
        "F823",
        "ARG003",
        "F706",
        "F704",
        "F702",
        "F701",
        "F634",
        "F631",
        "F632",
        "F522",
        "F523",
        "F524",
        "F501",
        "F502",
        "F503",
        "F504",
    ]

    @Slot(str)
    def lint_code(self, code: str) -> None:
        """
        Lint Python code utilizing Ruff.

        Parameters
        ----------
        code: str
            The Python code to lint.
        """
        if code.strip() == "" or len(code.strip().splitlines()) <= 0:
            return
        script = generate_script(code)
        try:
            diagnostics = self._run_ruff_check(script)
            if self.parent and hasattr(self.parent, "settables"):
                value_diagnostics = self._get_value_diagnostics(script)
                diagnostics.extend(value_diagnostics)
            self.lintingComplete.emit(json.dumps(diagnostics))
            self.issues = len(diagnostics)
        except Exception as e:
            error_diagnostic = self._ruff_error_diagnostic(f"Linting error: {str(e)}")
            self.lintingComplete.emit(json.dumps(error_diagnostic))
            self.issues = 1

    def returnIssues(self) -> int:
        """
        Return the number of ruff and value-check issues.

        Returns
        -------
        int
           The number of issues.
        """
        return self.issues

    def _get_value_diagnostics(self, script: str) -> list:
        """
        Get Matr1x value checker diagnostics.

        Parameters
        ----------
        script: str
            The generated script to check for value errors.
        """
        try:
            tree = ast.parse(script, filename="script")
            checker = Matr1xFunctionChecker(self.parent, *self.parent.settables)
            checker.visit(tree)
            return checker.returnDiagnostics()
        except Exception:
            return []

    def _ruff_error_diagnostic(self, error: str) -> list[dict]:
        """
        Format a general error in the required way.

        Parameters
        ----------
        error : str
            The error string to be included.

        Returns
        -------
        list[dict]
            A dictionary as the only element in a list.
        """
        error_diagnostic = [
            {
                "severity": 1,
                "startLineNumber": 1,
                "startColumn": 1,
                "endLineNumber": 1,
                "endColumn": 1,
                "message": f"{error}",
                "source": "ruff",
            }
        ]
        return error_diagnostic

    def _run_ruff_check(self, code: str) -> list[dict[str, Any]]:
        """
        Utilize Ruff to lint code and convert to Monaco diagnostics.

        Parameters
        ----------
        code: str
            Script to check for errors.

        Returns
        -------
            List of diagnostics in Monaco Editor format.
        """
        code = code.replace("\r\n", "\n").replace("\r", "\n")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, newline=""
        ) as temp_file:
            temp_file.write(code)
            temp_file_path = temp_file.name

        python_exec = Path(sys.executable)

        if sys.platform == "win32":
            if python_exec.name == "pythonw.exe":
                python_exec = python_exec.parent / "python.exe"

        try:
            cmd_args = [
                python_exec,
                "-m",
                "ruff",
                "check",
                "--output-format=json",
                "--select",
                ",".join(Linter.RUFF_RULES),
                "--no-cache",
                temp_file_path,
            ]

            kwargs = {
                "capture_output": True,
                "text": True,
                "timeout": 10,
            }

            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

            result = subprocess.run(cmd_args, **kwargs)  # ty: ignore [no-matching-overload]

            if result.stdout:
                ruff_issues = json.loads(result.stdout)
                return self._convert_ruff_to_monaco_diagnostics(ruff_issues)
            else:
                return []

        except subprocess.TimeoutExpired:
            return self._ruff_error_diagnostic("Ruff check timed out")

        except subprocess.CalledProcessError as e:
            if e.stdout:
                try:
                    ruff_issues = json.loads(e.stdout)
                    return self._convert_ruff_to_monaco_diagnostics(ruff_issues)
                except json.JSONDecodeError:
                    pass

            return self._ruff_error_diagnostic(
                f"Ruff execution error: {e.stderr or 'Unknown error'}"
            )

        except FileNotFoundError:
            return self._ruff_error_diagnostic("Ruff not found. Please install ruff.")

        finally:
            try:
                Path(temp_file_path).unlink()
            except Exception:
                pass

    def _convert_ruff_to_monaco_diagnostics(self, ruff_issues: list[dict]) -> list[dict[str, Any]]:
        """
        Convert Ruff JSON output to Monaco Editor diagnostics format.

        Parameters
        ----------
        ruff_issues: list[dict]
            List of issues from Ruff JSON output.

        Returns
        -------
            List of diagnostics in Monaco Editor format.
        """
        diagnostics = []

        for issue in ruff_issues:
            location = issue.get("location", {})
            end_location = issue.get("end_location", location)

            # Map Ruff severity to Monaco severity
            # Monaco: 1=Error, 2=Warning, 4=Info, 8=Hint
            severity_map = {"error": 1, "warning": 2, "info": 4, "hint": 8}

            # Ruff doesn't always provide severity, default to warning
            ruff_severity = issue.get("severity", "warning").lower()
            monaco_severity = severity_map.get(ruff_severity, 2)

            diagnostic = {
                "severity": monaco_severity,
                "startLineNumber": location.get("row", 1) - SCRIPT_OFFSET,
                "startColumn": location.get("column", 1) - COLUMN_OFFSET,
                "endLineNumber": end_location.get("row", location.get("row", 1)) - SCRIPT_OFFSET,
                "endColumn": end_location.get("column", location.get("column", 1)) - COLUMN_OFFSET,
                "message": f"{issue.get('code', '')}: {issue.get('message', 'Unknown issue')}",
                "source": "ruff",
                "code": issue.get("code", ""),
            }

            diagnostics.append(diagnostic)

        return diagnostics


class EditorBackend(QObject):
    """
    Modification tracking to be used with the Monaco editor.

    This is the Python backend class for the JavaScript editor.
    """

    contentModified = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_modified = False

    @Slot(bool)
    def content_changed(self, is_modified: bool) -> None:
        """Handle content modification notifications from the editor."""
        self._is_modified = is_modified
        self.contentModified.emit(is_modified)

    def isModified(self) -> bool:
        """Return True if the editor content has been modified."""
        return self._is_modified

    def setModified(self, modified: bool) -> None:
        """Set the modification state."""
        self._is_modified = modified


class CodeEditor(FileDropMixin, QWebEngineView):
    """Code editor connected to Monaco."""

    contentModified = Signal(bool)

    ZOOM_STEP = 0.1
    MIN_ZOOM = 0.1
    MAX_ZOOM = 2.0

    THEMES = {
        "Standard": {"Light": "vs", "Dark": "vs-dark"},
        "High contrast": {"Light high contrast": "hc-light", "Dark high contrast": "hc-black"},
    }

    def __init__(self, extensions: list):
        super().__init__()
        self.channel = QWebChannel()
        self.linter = Linter(self)
        self.backend = EditorBackend(self)
        self.backend.contentModified.connect(self.contentModified.emit)
        self.channel.registerObject("linter", self.linter)
        self.channel.registerObject("editor_backend", self.backend)
        self.page().setWebChannel(self.channel)
        html_path = resources.files("matr1x") / "resources" / "editor.html"
        self.load(QUrl.fromLocalFile(str(html_path)))
        loop = QEventLoop()
        self.loadFinished.connect(lambda success: loop.quit() if success else None)
        loop.exec()
        self.setAcceptDrops(True)
        self._current_theme: str
        get_application_instance().isDarkSignal.connect(lambda: self.setTheme(self._current_theme))
        self.setValidExtensions(extensions)

    def setPlainText(self, code: str) -> None:
        """
        Send code to the editor.

        The existing code is replaced.

        Parameters
        ----------
        code: str
            The code to send.
        """
        escaped_code = code.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        self.page().runJavaScript(f'window.editor.setValue("{escaped_code}")')

    def toPlainText(self) -> str:
        """
        Get code from the editor.

        Returns
        -------
        str
            The received code.
        """
        code = ""
        loop = QEventLoop()

        def handle_result(result):
            nonlocal code
            code = result
            loop.quit()

        self.page().runJavaScript("window.editor.getValue()", handle_result)
        loop.exec()
        return code

    def toggleLineComment(self) -> None:
        """Toggle comment on/off for the active line."""
        self.page().runJavaScript("""
            if (window.editor) {
                window.editor.getAction('editor.action.commentLine').run();
            }
        """)

    def find(self) -> None:
        """Show the find dialog."""
        self.page().runJavaScript("""
            if (window.editor) {
                window.editor.getAction('actions.find').run();
            }
        """)

    def zoomIn(self) -> None:
        """Zoom into the view."""
        self.setZoomFactor(min(CodeEditor.MAX_ZOOM, self.zoomFactor() + CodeEditor.ZOOM_STEP))

    def zoomOut(self) -> None:
        """Zoom out of the view."""
        self.setZoomFactor(max(CodeEditor.MIN_ZOOM, self.zoomFactor() - CodeEditor.ZOOM_STEP))

    def undo(self) -> None:
        """Perform undo."""
        self.page().runJavaScript("""
            if (window.editor && window.editor.getModel()) {
                window.editor.getModel().undo();
            }
        """)

    def redo(self) -> None:
        """Perform redo."""
        self.page().runJavaScript("""
            if (window.editor && window.editor.getModel()) {
                window.editor.getModel().redo();
            }
        """)

    def cut(self) -> None:
        """Perform cut."""
        self.triggerPageAction(QWebEnginePage.WebAction.Cut)

    def copy(self) -> None:
        """Perform copy."""
        self.triggerPageAction(QWebEnginePage.WebAction.Copy)

    def paste(self) -> None:
        """Perform paste."""
        self.triggerPageAction(QWebEnginePage.WebAction.Paste)

    def formatCode(self) -> None:
        """Format Python code utilizing 'ruff format'."""
        try:
            result = subprocess.run(
                ["ruff", "format", "--stdin-filename", "dummy.py", "-"],
                input=self.toPlainText(),
                text=True,
                capture_output=True,
                check=True,
            )
            formatted_code = result.stdout
            self.setPlainText(formatted_code)
        except subprocess.CalledProcessError:
            return

    def isModified(self) -> bool:
        """Return True if the editor content has been modified."""
        return self.backend.isModified()

    def setModified(self, modified: bool) -> None:
        """
        Set the modification state.

        Parameters
        ----------
        modified: bool
            Set modified (True) or clean (False).
        """
        self.backend.setModified(modified)
        # Notify the JavaScript editor about the modification state
        self.page().runJavaScript(f"""
            if (window.setModificationState) {{
                window.setModificationState({str(modified).lower()});
            }}
        """)

    def setReadOnly(self, read_only: bool) -> None:
        """
        Make the editor readonly (or not).

        Parameters
        ----------
        read_only: bool
            Set readOnly (True) or not (False).
        """
        self.page().runJavaScript(f"""
            if (window.editor) {{
                window.editor.updateOptions({{ readOnly: {str(read_only).lower()} }});
            }}
        """)

    def highlight(self, line_number: int) -> None:
        """
        Highlight this line number.

        Parameters
        ----------
        line_number: int
            The line number to highlight.
        """
        self.page().runJavaScript(f"""
            if (window.editor && window.highlightLine) {{
                window.highlightLine({line_number});
            }}
        """)

    def removeHighlight(self) -> None:
        """Remove line highlighting."""
        self.page().runJavaScript("""
            if (window.clearLineHighlight) {
                window.clearLineHighlight();
            }
        """)

    def setTheme(self, theme_selection: str) -> None:
        """
        Set the Monaco editor theme.

        Parameters
        ----------
        theme: str
            Theme name.
        """
        for name, theme_pair in CodeEditor.THEMES.items():
            if name == theme_selection:
                dark = get_application_instance().isDark
                self._current_theme = theme_selection
                monaco_theme = list(theme_pair.values())[1 if dark else 0]
            for name, theme in theme_pair.items():
                if name == theme_selection:
                    self._current_theme = theme_selection
                    monaco_theme = theme

        self.page().runJavaScript(f"""
            if (window.editor) {{
                monaco.editor.setTheme('{monaco_theme}');
            }}
        """)

    def supportedThemes(self) -> list:
        """
        Return the supported themes.

        Returns
        -------
        list
            The keys of the original dictionary as a list.
        """
        themes = list(CodeEditor.THEMES)
        themes += [theme for pair in CodeEditor.THEMES.values() for theme in pair]
        return themes

    def enableTabCompletion(self, enable: bool = True) -> None:
        """
        Enable and disable tab completion.

        Parameters
        ----------
        enable: bool
            Enable (True) or disable (False) tab completion.
        """
        self.page().runJavaScript(f"""
            if (window.editor) {{
                window.editor.updateOptions({{
                    tabCompletion: {str(enable).lower() and "'on'" or "'off'"},
                    acceptSuggestionOnEnter: {str(enable).lower() and "'on'" or "'off'"},
                    quickSuggestions: {str(enable).lower()}
                }});
            }}
        """)

    def setSettables(self, settables) -> None:
        """
        Receive the (settable) column names and update Monaco.

        Parameters
        ----------
        settables
            The settables of the system files.
        """
        self.settables = settables
        self.page().runJavaScript("if (window.triggerLinting) window.triggerLinting();")

    def insertText(self, text: str) -> None:
        """
        Insert text at the current cursor position.

        Parameters
        ----------
        text : str
            The text to insert.
        """
        escaped_text = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        self.page().runJavaScript(f"""
        if (window.editor) {{
          const position = window.editor.getPosition();
          const range = new monaco.Range(
            position.lineNumber,
            position.column,
            position.lineNumber,
            position.column,
          );
          window.editor.executeEdits("insertText", [
            {{
              range: range,
              text: "{escaped_text}",
            }},
          ]);
        }}
        """)

    def returnIssues(self) -> int:
        """
        Return the number of issues the linter found.

        Returns
        -------
        int
            The number of issues.
        """
        return self.linter.returnIssues()
