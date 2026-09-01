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
"""LSP and ty-specific data types (pydantic models)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class TyPosition(BaseModel):
    """A position in a file (line and character)."""

    line: int
    character: int


class TyRange(BaseModel):
    """A range in a file (start and end positions)."""

    start: TyPosition
    end: TyPosition


class TyDiagnostic(BaseModel):
    """A diagnostic message reported by the ty linter."""

    message: str
    range: TyRange
    severity: int
    source: str
    tags: list[int] = []

    def to_monaco(self, line_offset: int, column_offset: int) -> dict:
        """Convert to a Monaco editor diagnostic dictionary."""
        return {
            "severity": {1: 8, 2: 4, 3: 2, 4: 1}.get(self.severity, 2),
            "startLineNumber": self.range.start.line - line_offset + 1,
            "startColumn": self.range.start.character - column_offset + 1,
            "endLineNumber": self.range.end.line - line_offset + 1,
            "endColumn": self.range.end.character - column_offset + 1,
            "message": self.message,
            "source": self.source,
            "tags": self.tags,
        }


class LSPPositionModel(BaseModel):
    """A position in the editor."""

    line: int
    character: int


class LSPHover(BaseModel):
    """A hover announcement."""

    requestId: float
    position: LSPPositionModel


class LSPCompletionRequest(BaseModel):
    """A completion request."""

    requestId: float
    position: LSPPositionModel
    triggerCharacter: str
    code: str


class LSPContentsModel(BaseModel):
    """The contents of an LSP response."""

    kind: Literal["plaintext", "markdown"] = "plaintext"
    value: str


class LSPResponse(BaseModel):
    """A response from the LSP."""

    contents: LSPContentsModel | list[None]
