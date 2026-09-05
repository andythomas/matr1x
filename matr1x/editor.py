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
"""Re-export shim for `matr1x.gui.editor`.

The editor now lives in the `matr1x.gui.editor` package (split into
``lsp_protocol``, ``lsp_types``, ``lsp_client`` and ``code_editor``). This
module re-exports the public names so that ``from matr1x.editor import ...``
keeps working.
"""

from matr1x.gui.editor import CodeEditor
from matr1x.gui.editor.lsp_client import LSPClient
from matr1x.gui.editor.lsp_protocol import (
    JsonRpcNotification,
    JsonRpcRequest,
    JsonRpcResponse,
    LSPServer,
)
from matr1x.gui.editor.lsp_types import (
    LSPCompletionRequest,
    LSPContentsModel,
    LSPHover,
    LSPPositionModel,
    LSPResponse,
    TyDiagnostic,
    TyPosition,
    TyRange,
)

__all__ = [
    "CodeEditor",
    "JsonRpcNotification",
    "JsonRpcRequest",
    "JsonRpcResponse",
    "LSPClient",
    "LSPCompletionRequest",
    "LSPContentsModel",
    "LSPHover",
    "LSPPositionModel",
    "LSPResponse",
    "LSPServer",
    "TyDiagnostic",
    "TyPosition",
    "TyRange",
]
