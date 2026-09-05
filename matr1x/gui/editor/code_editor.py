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
"""The Monaco-backed code editor and its backend."""

import ast
import hashlib
import html
import json
import re
import socket
import time
from importlib import resources
from typing import Any, ClassVar, cast

import monaco_assets
from pydantic import ValidationError
from PySide6.QtCore import (
    QEventLoop,
    QObject,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from matr1x.core.error_handling import Error
from matr1x.core.models import SystemInfo
from matr1x.core.util import (
    find_binary,
    generate_script,
    get_script_prefix_offset,
    run_python_cmdline,
)
from matr1x.gui.app import MApplication
from matr1x.gui.mixins import AutoSlot, FileDropMixin, LoggerMixin

from .lsp_client import LSPClient
from .lsp_protocol import JsonRpcNotification, LSPServer
from .lsp_types import (
    LSPCompletionRequest,
    LSPHover,
    LSPPositionModel,
    LSPResponse,
    TyDiagnostic,
)

SCRIPT_OFFSET = get_script_prefix_offset()
COLUMN_OFFSET = 4  # The user code is wrapped in a "try:" = 4 chars
HIGHLIGHT_INTERVAL_MS = 15
LINTING_DELAY_MS = 1000
DUMMY_LSP_FILENAME = "untitled:///user_script.py"


class Matr1xFunctionChecker(ast.NodeVisitor):
    """Implements ast-based function checker for matr1x functions."""

    def __init__(self, system_info: SystemInfo):
        self.indexes = []
        self.settables = []
        self.columns = []
        self.system_info = system_info
        for data in system_info.parameters.values():
            self.indexes.append(str(data.index))
            self.settables.append(data.settable)
            self.columns.append(data.name)
        self.errors: int = 0
        self.lineno: int
        self.col: int
        self.end_lineno: int
        self.end_col: int
        self.diagnostics: list[dict[str, str | int]] = []
        self.script_lines: list[str] = []
        self.node: ast.Call
        self.func_name: str

    def _reporter(self, error_text: str, is_error: bool = True) -> None:
        """
        Generate a report in the Monaco format.

        Parameters
        ----------
        error_text: str
            The error text to be displayed.
        is_error: bool
            Is this an error (True) or an info (False).
        """
        if is_error:
            self.errors += 1
        diagnostic = {
            "severity": 2,
            "startLineNumber": self.lineno - (SCRIPT_OFFSET + self.system_info.stub_length),
            "startColumn": self.col - COLUMN_OFFSET + 1,
            "endLineNumber": self.end_lineno - (SCRIPT_OFFSET + self.system_info.stub_length),
            "endColumn": self.end_col - COLUMN_OFFSET + 1,
            "message": f"{error_text}",
            "source": "Matrix checker",
            "code": "value error",
        }
        self.diagnostics.append(diagnostic)

    def set_script(self, script: str) -> None:
        """
        Set the script content for type ignore checking.

        Parameters
        ----------
        script: str
            The script, i.e. the code.
        """
        self.script_lines = script.splitlines() if script else []

    def returnDiagnostics(self) -> list[dict[str, str | int]]:
        """
        Return the value checker diagnostics.

        Returns
        -------
        list[dict[str, str | int]]
            The list of errors in the Monaco format.
        """
        return self.diagnostics

    def _should_ignore_line(self) -> bool:
        """
        Check if current line has type: ignore comment.

        Returns
        -------
        bool
            Line will be ignored (True) or validated (False).
        """
        if not (self.script_lines and self.lineno <= len(self.script_lines)):
            return False
        return bool(re.search(r"#\s*type:\s*ignore\s*$", self.script_lines[self.lineno - 1]))

    def _validate_parameter_count(self) -> bool:
        """
        Check if parameter count is valid.

        Returns
        -------
        bool
            True is parameter count is valid, False otherwise.
        """
        args = self.node.args
        required = 2 if self.func_name == "set_value" else 1
        if len(args) < required:
            if len(args) == 1 and required == 2 and isinstance(args[0], ast.Starred):
                error_text = (
                    "Cannot statically check starred expression"
                    f" in {self.func_name} call in line {args[0].lineno}"
                )
                self._reporter(error_text, False)
                return False
            self._reporter("Too few parameters.")
            return False
        elif len(args) > required:
            self._reporter("Too many parameters.")
            return False
        return True

    def _validate_integer_column(self, value: int) -> None:
        """
        Validate integer column index.

        Parameters
        ----------
        value: int
            The parameter value to be checked.
        """
        if value >= len(self.indexes) or value < 0:
            self._reporter(f"Index <{value}> beyond valid range.")
        elif not self.settables[value] and self.func_name == "set_value":
            self._reporter(f"Index <{value}> not settable.")

    def _validate_string_column(self, value: str) -> None:
        """
        Validate string column name.

        Parameters
        ----------
        value: int
            The parameter value to be checked.
        """
        if value not in self.columns:
            self._reporter(f"<{value}> not a valid column name.")
        elif not self.settables[self.columns.index(value)] and self.func_name == "set_value":
            self._reporter(f"Column <{value}> not settable.")

    def _validate_column(self) -> None:
        """Validate column argument for matr1x functions."""
        col_arg = self.node.args[0]
        if not isinstance(col_arg, ast.Constant):
            self._reporter("Cannot statically check argument.", False)
            return
        value = col_arg.value
        if isinstance(value, int):
            self._validate_integer_column(value)
        elif isinstance(value, str):
            self._validate_string_column(value)
        else:
            self._reporter(f"<{value}> not a valid column identifier.")

    def visit_Call(self, node: ast.Call):
        """Perform custom function parameter-value checking."""
        if not isinstance(node.func, ast.Name):
            return
        if node.func.id not in ("set_value", "read_value", "trigger_value"):
            return
        self.node = node
        self.func_name = node.func.id
        self.lineno = node.func.lineno
        self.col = node.func.col_offset
        self.end_lineno = node.func.end_lineno if node.func.end_lineno else self.lineno
        self.end_col = node.func.end_col_offset if node.func.end_col_offset else self.col
        if self._should_ignore_line():
            return
        if not self._validate_parameter_count():
            return
        self._validate_column()


class EditorBackend(QObject):
    """
    Backend bridge to be used with the Monaco editor.

    When Qt objects are registered with WebChannel, Qt expects certain
    properties to have notify signals for proper data binding. The
    "CodeEditor" inherits from "QWebEngineView" which has many
    properties without notify signals, causing console noise. Therefore,
    a class inheriting only from "QObject" is a clean solution.

    Things are handled here to keep the JavaScript side minimal.
    """

    contentModified = Signal(bool)
    hoverRequested = Signal(LSPPositionModel)
    completionRequested = Signal(LSPCompletionRequest)
    contentChanged = Signal(str)
    cursorPositionChanged = Signal(int, int)
    lintingComplete = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_modified = False
        self._system_info: SystemInfo
        self._tc_diagnostics: list[dict] = []
        self._lint_timer = QTimer(self)
        self._lint_timer.setSingleShot(True)
        self._lint_timer.setInterval(LINTING_DELAY_MS)
        self._lint_timer.timeout.connect(self._run_lint)
        self._current_code: str = ""
        self._last_linted_hash: bytes = b""
        self._issues: int = 0

    @property
    def issues(self) -> int:
        """Return the number of issues found in the last lint pass."""
        return self._issues

    @AutoSlot
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

    @AutoSlot
    def code_changed(self, code: str) -> None:
        """
        Receive updated code from the JS editor.

        Notifies the LSP server immediately via ``contentChanged`` and
        resets the 1s lint timer.

        Parameters
        ----------
        code : str
            The current editor content.
        """
        self._current_code = code
        self.contentChanged.emit(code)
        self._lint_timer.start()

    def _run_lint(self) -> None:
        """Run a lint pass unless the code is unchanged since the last pass."""
        code_hash = hashlib.sha1(self._current_code.encode()).digest()
        if code_hash == self._last_linted_hash:
            return
        self._last_linted_hash = code_hash
        if not self._current_code.strip():
            self._issues = 0
            self.lintingComplete.emit(json.dumps([]))
            return
        diagnostics = self._lint(self._current_code)
        self.lintingComplete.emit(json.dumps(diagnostics))
        self._issues = len(diagnostics)

    def update_system_info(self, system_info: SystemInfo) -> None:
        """
        Update the system info used for value checking and re-lint.

        Parameters
        ----------
        system_info : SystemInfo
            The updated system information.
        """
        self._system_info = system_info
        self._last_linted_hash = b""
        self._run_lint()

    def update_tc_diagnostics(self, diagnostics: list[dict]) -> None:
        """
        Update type-checker diagnostics and immediately re-lint.

        Parameters
        ----------
        diagnostics : list[dict]
            Monaco-format diagnostic objects from the type checker.
        """
        self._tc_diagnostics = diagnostics
        self._last_linted_hash = b""
        self._run_lint()

    @AutoSlot
    def handle_hover(self, payload: str) -> None:
        """Handle hover notifications from the Monaco editor."""
        try:
            hover = LSPHover.model_validate_json(payload)
        except ValidationError:
            return
        hover.position.line = (
            hover.position.line + SCRIPT_OFFSET + self._system_info.stub_length - 1
        )
        hover.position.character = hover.position.character + COLUMN_OFFSET - 1
        self.hoverRequested.emit(hover)

    @AutoSlot
    def handle_completion_request(self, payload: str) -> None:
        """Handle completion requests from the Monaco editor."""
        try:
            completion_request = LSPCompletionRequest.model_validate_json(payload)
        except ValidationError:
            return
        self.contentChanged.emit(completion_request.code)
        completion_request.position.line = (
            completion_request.position.line + SCRIPT_OFFSET + self._system_info.stub_length - 1
        )
        completion_request.position.character = (
            completion_request.position.character + COLUMN_OFFSET - 1
        )
        self.completionRequested.emit(completion_request)

    @AutoSlot
    def cursor_position_changed(self, line: int, column: int) -> None:
        """Handle cursor position change notifications from the editor."""
        self.cursorPositionChanged.emit(line, column)

    def _lint(self, code: str) -> list[dict[str, str | int]]:
        """
        Run linting on Python code and return Monaco-format diagnostics.

        Parameters
        ----------
        code : str
            The user's Python code to lint.

        Returns
        -------
        list[dict[str, str | int]]
            Monaco-format diagnostic objects.
        """
        script = generate_script(self._system_info.stub + code)
        diagnostics: list[dict[str, str | int]] = self._get_value_diagnostics(script)
        diagnostics.extend(self._tc_diagnostics)
        return diagnostics

    def _get_value_diagnostics(self, script: str) -> list[dict[str, str | int]]:
        """
        Get Matr1x value checker diagnostics.

        Parameters
        ----------
        script : str
            The generated script to check for value errors.

        Returns
        -------
        list[dict[str, str | int]]
            Monaco-format diagnostic objects.
        """
        try:
            tree = ast.parse(script, filename="script")
            checker = Matr1xFunctionChecker(self._system_info)
            checker.set_script(script)
            checker.visit(tree)
            return checker.returnDiagnostics()
        except Exception:
            return []


class CodeEditorPage(QWebEnginePage, LoggerMixin):
    """Pipe JavaScript console messages to logger."""

    def __init__(self, parent=None):
        """Init the logger."""
        super().__init__(parent)

    def javaScriptConsoleMessage(
        self,
        level: QWebEnginePage.JavaScriptConsoleMessageLevel,
        message: str,
        lineNumber: int,
        sourceID: str,
    ):
        """
        Override to handle JavaScript console messages and log them.

        Gives full info for errors and warnings and just the message
        otherwise.

        Parameters
        ----------
        level: QWebEnginePage.JavaScriptConsoleMessageLevel
            Error, warning or info. debug level is encoded in message.
        message: str
            The message itself with optional [DEBUG] prefix.
        lineNumber: int
            The line number where the message originated.
        sourceID: str
            The file name where the message originated.
        """
        if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            self.logger.error("%s (line %d)%s", message, lineNumber, sourceID)
        elif level == QWebEnginePage.JavaScriptConsoleMessageLevel.WarningMessageLevel:
            self.logger.warning("%s (line %d)%s", message, lineNumber, sourceID)
        elif message[0:7] == "[DEBUG]":
            self.logger.debug("%s (line %d)%s", message[8:], lineNumber, sourceID)
        else:
            self.logger.info("%s", message)


class CodeEditor(FileDropMixin, QWebEngineView, LoggerMixin):
    """Code editor connected to Monaco."""

    contentModified = Signal(bool)

    ZOOM_STEP = 0.1
    MIN_ZOOM = 0.1
    MAX_ZOOM = 2.0

    THEMES: ClassVar[dict[str, dict[str, str]]] = {
        "Standard": {"Light": "vs", "Dark": "vs-dark"},
        "High contrast": {"Light high contrast": "hc-light", "Dark high contrast": "hc-black"},
    }

    @staticmethod
    def find_free_port(start_port=54529):
        """Find an available port starting from start_port."""
        port = start_port
        while port < start_port + 100:  # Try 100 ports
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.bind(("localhost", port))
                sock.close()
                return port
            except OSError:
                port += 1
        raise RuntimeError("No free ports available")

    def __init__(self):
        super().__init__()
        self.version = 2
        self.column = 1
        self.row = 1
        tc_name = "ty"
        tc_binary = find_binary(tc_name)
        if isinstance(tc_binary, Error):
            raise tc_binary.error
        tc_server = LSPServer(name=tc_name, binary=str(tc_binary.value), parameters=["server"])
        self.lsp_tc = LSPClient(tc_server)
        self.lsp_tc.start()
        self.lsp_initialize()
        # Find free port and start Monaco server
        self.port = self.find_free_port()
        self.server = monaco_assets.MonacoServer(port=self.port)
        timeout = 30  # seconds
        start_time = time.time()
        while not self.server.is_running() and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        if not self.server.is_running():
            self.logger.error("Warning: Monaco server did not start within %d seconds", timeout)
        self.editor_page = CodeEditorPage()
        self.setPage(self.editor_page)
        settings = self.page().settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        settings.setAttribute(QWebEngineSettings.WebAttribute.ErrorPageEnabled, True)
        self.channel = QWebChannel()
        self.backend = EditorBackend(self)
        self.channel.registerObject("editor_backend", self.backend)
        self.page().setWebChannel(self.channel)
        html_path = resources.files("matr1x") / "resources" / "editor.html"
        editor_url = QUrl.fromLocalFile(str(html_path))
        editor_url.setQuery(f"port={self.port}")
        self.load(editor_url)
        loop = QEventLoop()
        success = False

        def _load_finished(ok: bool) -> None:
            nonlocal success
            success = ok
            loop.quit()

        self.loadFinished.connect(_load_finished)
        QTimer.singleShot(30_000, loop.quit)  # safety net: never hang forever
        loop.exec()
        self.loadFinished.disconnect(_load_finished)
        if not success:
            message = (
                f"Editor page failed to load from {html_path}. The renderer "
                "process may have died; check the QtWebEngine installation "
                "and environment (e.g. set QTWEBENGINE_CHROMIUM_FLAGS="
                "--no-sandbox when running inside a restrictive sandbox)."
            )
            self.logger.error(message)
            raise RuntimeError(message)
        self.setAcceptDrops(True)
        self._highlight_timer = QTimer(self)
        self._highlight_timer.setSingleShot(True)
        self._pending_highlight_lines: list[int] | None = None
        self._current_theme: str
        self._system_info: SystemInfo
        self.create_connections()

    def create_connections(self) -> None:
        """Create connections between signals and slots."""
        self.backend.contentModified.connect(self.contentModified.emit)
        self.backend.hoverRequested.connect(self.on_hover_requested)
        self.backend.completionRequested.connect(self.on_completion_requested)
        self.backend.contentChanged.connect(self.on_content_changed)
        self.backend.cursorPositionChanged.connect(self.on_cursor_position_changed)
        self._highlight_timer.timeout.connect(self._apply_pending_highlight)
        MApplication.instance().isDarkSignal.connect(lambda: self.setTheme(self._current_theme))
        self.lsp_tc.notification.connect(self.on_notification)

    def _run_javascript(self, command: str):
        """Execute JavaScript command and return result synchronously."""
        result: Any = None
        loop = QEventLoop()

        def handle_result(js_result):
            nonlocal result
            result = js_result
            loop.quit()

        self.logger.debug("executing: %s", command)
        wrapped_command = f"""
        (function() {{
            try {{
                return {command};
            }} catch (error) {{
                console.error(error.message);
            }}
        }})()
        """
        self.page().runJavaScript(wrapped_command, handle_result)
        loop.exec()
        return result

    def _run_javascript_async(self, command: str):
        """Execute JavaScript command asynchronously without blocking."""
        self.logger.debug("executing async: %s", command)
        wrapped_command = f"""
        (function() {{
            try {{
                return {command};
            }} catch (error) {{
                console.error('JavaScript error:', error.message);
                return null;
            }}
        }})()
        """

        def handle_result(js_result):
            if js_result is not None:
                self.logger.debug("async JS result: %s", js_result)

        self.page().runJavaScript(wrapped_command, handle_result)

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
        self._run_javascript(f'window.editor.setValue("{escaped_code}")')

    def toPlainText(self) -> str:
        """
        Get code from the editor.

        Returns
        -------
        str
            The received code.
        """
        return self._run_javascript("window.editor.getValue()") or ""

    def toggleLineComment(self) -> None:
        """Toggle comment on/off for the active line."""
        self._run_javascript("window.editor.getAction('editor.action.commentLine').run()")

    def show_find(self) -> None:
        """Show the find dialog."""
        self._run_javascript("window.editor.getAction('actions.find').run()")

    def zoomIn(self) -> None:
        """Zoom into the view."""
        self.setZoomFactor(min(CodeEditor.MAX_ZOOM, self.zoomFactor() + CodeEditor.ZOOM_STEP))

    def zoomOut(self) -> None:
        """Zoom out of the view."""
        self.setZoomFactor(max(CodeEditor.MIN_ZOOM, self.zoomFactor() - CodeEditor.ZOOM_STEP))

    def undo(self) -> None:
        """Perform undo."""
        self._run_javascript("window.editor.getModel().undo()")

    def redo(self) -> None:
        """Perform redo."""
        self._run_javascript("window.editor.getModel().redo()")

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
        cmd_args = ["-m", "ruff", "format", "--stdin-filename", "dummy.py", "-"]
        result = run_python_cmdline(cmd_args, stdin=self.toPlainText())
        if isinstance(result, Error):
            return
        self.setPlainText(result.value.stdout)

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
        self._run_javascript(f"window.setModificationState({str(modified).lower()})")

    def setReadOnly(self, read_only: bool) -> None:
        """
        Make the editor readonly (or not).

        Parameters
        ----------
        read_only: bool
            Set readOnly (True) or not (False).
        """
        self._run_javascript(
            f"window.editor.updateOptions({{ readOnly: {str(read_only).lower()} }})"
        )

    def highlight(self, line_numbers: list[int]) -> None:
        """
        Highlight active user-script lines.

        Parameters
        ----------
        line_numbers: list[int]
            Line numbers ordered from the innermost execution point to its
            outermost user-script caller.
        """
        self._pending_highlight_lines = list(dict.fromkeys(line_numbers))
        self._highlight_timer.start(HIGHLIGHT_INTERVAL_MS)

    def removeHighlight(self) -> None:
        """Remove line highlighting."""
        self._highlight_timer.stop()
        self._pending_highlight_lines = None
        self._run_javascript("window.clearLineHighlight()")

    def _apply_pending_highlight(self) -> None:
        """Apply the most recently requested line highlight."""
        if self._pending_highlight_lines is None:
            return
        line_numbers = self._pending_highlight_lines
        self._pending_highlight_lines = None
        self._run_javascript(f"window.highlightLines({json.dumps(line_numbers)})")

    def lsp_initialize(self) -> None:
        """Initialize the server/client communication."""
        capabilities = {
            "textDocument": {
                "hover": {"contentFormat": ["markdown", "plaintext"]},
                "signatureHelp": {
                    "signatureInformation": {"documentationFormat": ["markdown", "plaintext"]}
                },
                "completion": {
                    "completionItem": {"documentationFormat": ["markdown", "plaintext"]}
                },
            }
        }
        init = self.lsp_tc.send_request("initialize", {"capabilities": capabilities})
        if isinstance(init, Error):
            return
        self.lsp_tc.send_notification("initialized", {})
        self.lsp_tc.send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": DUMMY_LSP_FILENAME,
                    "languageId": "python",
                    "version": 1,
                    "text": "",
                }
            },
        )

    @AutoSlot
    def on_notification(self, notification: JsonRpcNotification) -> None:
        """Handle notifications from the LSP server."""
        if notification.method == "textDocument/publishDiagnostics":
            params = cast(dict, notification.params)
            diagnostics = [
                TyDiagnostic.model_validate(d)
                for d in params.get("diagnostics", [])
                if d.get("severity", 1) < 4
            ]
            tc_diagnostics = [
                d.to_monaco(SCRIPT_OFFSET + self._system_info.stub_length, COLUMN_OFFSET)
                for d in diagnostics
            ]
            self.backend.update_tc_diagnostics(tc_diagnostics)

    def on_hover_requested(self, hover: LSPHover) -> None:
        """
        Handle hover requests from Monaco editor.

        Parameters
        ----------
        hover : LSPHover
            Pydantic model with the position and an id.
        """
        hover_result = self.lsp_tc.send_request(
            "textDocument/hover",
            {
                "textDocument": {"uri": DUMMY_LSP_FILENAME},
                "position": hover.position.model_dump(),
            },
        )
        if (
            isinstance(hover_result, Error)
            or hover_result.value.error is not None
            or hover_result.value.result is None
        ):
            return
        try:
            hover_result = LSPResponse.model_validate(hover_result.value.result)
        except ValidationError:
            return
        contents = hover_result.contents
        if isinstance(contents, list):
            popup = [{"value": "Unknown"}]
        else:
            text = html.unescape(contents.value.rsplit("Go to", 1)[0])
            popup = [{"value": text}]
        js_command = f"window.showHover({hover.requestId}, {json.dumps(popup)})"
        self._run_javascript_async(js_command)

    def on_completion_requested(self, completion_request: LSPCompletionRequest) -> None:
        """Handle completion requests from Monaco editor."""
        completion_result = self.lsp_tc.send_request(
            "textDocument/completion",
            {
                "textDocument": {"uri": DUMMY_LSP_FILENAME},
                "position": completion_request.position.model_dump(),
                "context": {
                    "triggerKind": 2,
                    "triggerCharacter": completion_request.triggerCharacter,
                },
            },
        )
        if isinstance(completion_result, Error):
            return
        if completion_result.value.error is not None or completion_result.value.result is None:
            return
        completions = self._process_lsp_completions(completion_result.value.result)
        filtered = [item for item in completions if not item["label"].startswith("_")]
        js_command = (
            f"window.showCompletions({completion_request.requestId}, {json.dumps(filtered)})"
        )
        self._run_javascript_async(js_command)

    def _process_lsp_completions(
        self, lsp_completions: list[dict[str, Any]] | dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Convert LSP completion results to Monaco format."""
        monaco_completions = []
        if isinstance(lsp_completions, list):
            for item in lsp_completions:
                if isinstance(item, dict):
                    doc_field = item.get("documentation", "")
                    monaco_documentation = None
                    if doc_field:
                        if isinstance(doc_field, dict):
                            if "value" in doc_field:
                                doc_field["value"] = html.unescape(doc_field["value"])
                            monaco_documentation = doc_field
                        elif isinstance(doc_field, str) and doc_field.strip():
                            monaco_documentation = {
                                "kind": "markdown",
                                "value": html.unescape(doc_field),
                            }
                    monaco_completion = {
                        "label": item.get("label", ""),
                        "insertText": item.get("insertText", item.get("label", "")),
                        "kind": self._convert_completion_kind(item.get("kind", 1)),
                        "documentation": monaco_documentation,
                    }
                    monaco_completions.append(monaco_completion)
        elif isinstance(lsp_completions, dict) and "items" in lsp_completions:
            return self._process_lsp_completions(lsp_completions["items"])
        return monaco_completions

    def _convert_completion_kind(self, lsp_kind):
        """Convert LSP completion kind to Monaco completion kind."""
        # Map LSP completion kinds to Monaco kinds
        kind_mapping = {
            1: 17,  # Text -> Property
            2: 11,  # Method -> Method
            3: 11,  # Function -> Method
            4: 4,  # Constructor -> Constructor
            5: 7,  # Field -> Field
            6: 6,  # Variable -> Variable
            7: 9,  # Class -> Class
            8: 8,  # Interface -> Interface
            9: 10,  # Module -> Module
            10: 17,  # Property -> Property
            11: 12,  # Unit -> Unit
            12: 13,  # Value -> Value
            13: 15,  # Enum -> Enum
            14: 1,  # Keyword -> Keyword
            15: 2,  # Snippet -> Snippet
            16: 19,  # Color -> Color
            17: 20,  # File -> File
            18: 21,  # Reference -> Reference
        }
        return kind_mapping.get(lsp_kind, 17)

    def on_content_changed(self, text: str) -> None:
        """Increment version counter and process text."""
        self.version += 1
        self.lsp_tc.send_notification(
            "textDocument/didChange",
            {
                "textDocument": {
                    "uri": DUMMY_LSP_FILENAME,
                    "version": self.version,
                },
                "contentChanges": [{"text": generate_script(self._system_info.stub + text)}],
            },
        )

    def on_cursor_position_changed(self, line: int, column: int) -> None:
        """Handle cursor position change notifications from the editor."""
        self.row = line
        self.column = column

    def setTheme(self, theme_selection: str) -> None:
        """
        Set the Monaco editor theme.

        Parameters
        ----------
        theme_selection: str
            Theme name.
        """
        monaco_theme = next(iter(CodeEditor.THEMES["Standard"].values()))
        for name, theme_pair in CodeEditor.THEMES.items():
            if name == theme_selection:
                dark = MApplication.instance().isDark
                self._current_theme = theme_selection
                monaco_theme = list(theme_pair.values())[1 if dark else 0]
            for name, theme in theme_pair.items():
                if name == theme_selection:
                    self._current_theme = theme_selection
                    monaco_theme = theme
        self._run_javascript(f"monaco.editor.setTheme('{monaco_theme}')")

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
        self._run_javascript(f"window.enableTabCompletion({str(enable).lower()})")

    def setSystemInfo(self, system_info: SystemInfo) -> None:
        """
        Receive the system info and update Monaco.

        Parameters
        ----------
        system_info
            The system information required by the linter.
        """
        self._system_info = system_info
        self.backend.update_system_info(system_info)

    def insertText(self, text: str) -> None:
        """
        Insert text at the current cursor position.

        Parameters
        ----------
        text : str
            The text to insert.
        """
        escaped_text = text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        self._run_javascript(f'window.insertText("{escaped_text}")')

    def returnIssues(self) -> int:
        """
        Return the number of issues the linter found.

        Returns
        -------
        int
            The number of issues.
        """
        return self.backend.issues
