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
Test that a slow initial Monaco asset download does not break startup.

The assets are downloaded in a background thread and ``CodeEditor``
waits for them before loading the editor page.
"""

import time

import monaco_assets
import pytest
from PySide6.QtCore import QEventLoop, QTimer
from pytestqt.qtbot import QtBot

from matr1x.editor import CodeEditor


@pytest.mark.timeout(120)
def test_slow_asset_download(qtbot: QtBot, qapp, monkeypatch):
    """
    Construct a CodeEditor while the asset "download" takes several seconds.

    Asserts
    -------
    the editor is created from the (delayed) assets
    """
    real_path = monaco_assets.get_path()

    def slow_get_path():
        time.sleep(3)  # simulate a slow download
        return real_path

    monkeypatch.setattr(monaco_assets, "get_path", slow_get_path)

    editor = CodeEditor()
    qtbot.addWidget(editor)

    def js(code: str):
        result = []
        loop = QEventLoop()
        editor.page().runJavaScript(code, lambda value: (result.append(value), loop.quit()))
        QTimer.singleShot(30_000, loop.quit)
        loop.exec()
        return result[0] if result else None

    try:
        qtbot.waitUntil(lambda: js("!!window.editor") is True, timeout=60_000)
        assert js("window.editor.getValue()") == ""
    finally:
        editor.lsp_tc.stop()
