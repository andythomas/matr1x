# This file is part of a software collection for data aquisition (matr1x).
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
Proof of concept: serve the Monaco assets without an HTTP server.

Instead of running ``monaco_assets.MonacoServer`` (uvicorn on a probed
free port), the Monaco files are served from disk inside the Qt process
via a ``monaco://`` URL scheme handler
(``QWebEngineUrlSchemeHandler`` + ``QWebEngineUrlRequestJob.reply``).

Findings baked into this test:

- The scheme must be registered before QWebEngine is initialized
  (done in ``conftest.py::pytest_configure``).
- The main page itself must be served from the scheme: Chromium blocks
  subresource requests from a ``file://`` page to the custom scheme
  before they ever reach the handler. Serving the page from
  ``monaco://`` makes all requests same-origin.
- The ``QBuffer`` handed to ``job.reply`` must be kept alive from
  Python until the reply has been consumed.

The test loads the real Monaco build (``monaco_assets.get_path()``)
through the scheme in a ``QWebEngineView`` and checks that the editor
is created and usable - no port, no server, no daemon thread.
"""

import json
import mimetypes
from pathlib import Path
from typing import Any

import monaco_assets
import pytest
from PySide6.QtCore import QBuffer, QEventLoop, QIODevice, QTimer, QUrl
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineUrlRequestJob,
    QWebEngineUrlSchemeHandler,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

PAGE_PREFIX = "page/"


def assets_dir() -> Path:
    """Return the local Monaco asset cache directory (downloads on first use)."""
    return monaco_assets.get_path()


# Minimal page mirroring the essential parts of editor.js: the AMD
# loader and the Monaco modules are fetched from the monaco:// scheme.
EDITOR_HTML = """
<!doctype html>
<html>
    <head>
        <meta charset="utf-8" />
    </head>
    <body>
        <div id="container" style="height: 100%; width: 100%"></div>
        <script src="monaco://localhost/min/vs/loader.js"></script>
        <script>
            require.config({
                paths: { vs: "monaco://localhost/min/vs" },
            });
            require(["vs/editor/editor.main"], () => {
                window.editor = monaco.editor.create(
                    document.getElementById("container"),
                    {
                        value: "x = 1\\n",
                        language: "python",
                        automaticLayout: true,
                    }
                );
                window.monacoReady = true;
            });
        </script>
    </body>
</html>
"""


class MonacoAssetHandler(QWebEngineUrlSchemeHandler):
    """Serve monaco:// requests from disk.

    ``page/*`` maps to a local directory (for the test page), all other
    paths map to the Monaco asset cache.
    """

    def __init__(self, page_dir: Path, parent=None):
        super().__init__(parent)
        self._page_dir = page_dir
        self._buffers: list[QBuffer] = []

    def requestStarted(self, job: QWebEngineUrlRequestJob) -> None:
        """Reply to a monaco:// request with the file content from disk."""
        rel = job.requestUrl().path().lstrip("/")
        if rel.startswith(PAGE_PREFIX):
            file_path = self._page_dir / rel[len(PAGE_PREFIX) :]
        else:
            file_path = assets_dir() / rel
        if not file_path.is_file():
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)
            return
        mime_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        buffer = QBuffer()
        buffer.setData(file_path.read_bytes())
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self._buffers.append(buffer)  # Keep alive until the reply is consumed.
        job.reply(mime_type.encode(), buffer)


class CollectingPage(QWebEnginePage):
    """Collect JavaScript console error messages."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.errors: list[str] = []

    def javaScriptConsoleMessage(
        self,
        level: QWebEnginePage.JavaScriptConsoleMessageLevel,
        message: str,
        lineNumber: int,
        sourceID: str,
    ) -> None:
        """Collect error-level console messages and forward to the base class."""
        if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            self.errors.append(f"{message} ({sourceID}:{lineNumber})")
        super().javaScriptConsoleMessage(level, message, lineNumber, sourceID)


def run_js(page: QWebEnginePage, code: str, timeout: int = 30_000) -> Any:
    """Run JavaScript on the page and return the result synchronously."""
    result: list[Any] = []
    loop = QEventLoop()
    page.runJavaScript(code, lambda value: (result.append(value), loop.quit()))
    QTimer.singleShot(timeout, loop.quit)
    loop.exec()
    return result[0] if result else None


@pytest.mark.timeout(120)
def test_monaco_via_url_scheme(qtbot, qapp, tmp_path):
    """
    Load the real Monaco build via the monaco:// scheme, without a server.

    Asserts
    -------
    the editor is created from monaco:// URLs
    the python language is registered and tokenizes
    values can be set and read back
    no JavaScript errors occurred
    """
    page_dir = tmp_path / "page"
    page_dir.mkdir()
    (page_dir / "editor.html").write_text(EDITOR_HTML)

    view = QWebEngineView()
    page = CollectingPage(view)
    view.setPage(page)
    handler = MonacoAssetHandler(page_dir, view)
    profile = view.page().profile()
    profile.installUrlSchemeHandler(b"monaco", handler)
    try:
        with qtbot.waitSignal(view.loadFinished, timeout=30_000):
            view.load(QUrl("monaco://localhost/page/editor.html"))

        # Wait until the AMD loader has fetched and executed editor.main.
        qtbot.waitUntil(
            lambda: run_js(page, "window.monacoReady === true", timeout=5_000) is True,
            timeout=30_000,
        )

        assert run_js(page, "window.editor.getValue()") == "x = 1\n"
        # The python language contribution tokenizes -> language assets
        # (fetched via monaco:// XHR) are working.
        tokens = run_js(page, "JSON.stringify(monaco.editor.tokenize('x = 1', 'python'))")
        token_list = json.loads(tokens)
        assert token_list and len(token_list[0]) > 0

        run_js(page, 'window.editor.setValue("y = 2\\n")')
        assert run_js(page, "window.editor.getValue()") == "y = 2\n"

        assert not page.errors, f"JavaScript errors: {page.errors}"
    finally:
        profile.removeUrlSchemeHandler(handler)
