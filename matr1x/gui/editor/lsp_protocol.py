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
"""JSON-RPC protocol models and the LSP server descriptor."""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


class JsonRpcResponse(BaseModel):
    """A JSON RPC 2 response."""

    jsonrpc: str = Field("2.0")
    id: int | None
    result: Any | None = None
    error: Any | None = None


class JsonRpcNotification(BaseModel):
    """A JSON RPC 2 notification."""

    jsonrpc: str = Field("2.0")
    method: str
    params: Any | None = None


class JsonRpcRequest(BaseModel):
    """A JSON RPC 2 request."""

    jsonrpc: str = Field("2.0")
    id: int
    method: str
    params: Any | None = None


@dataclass
class LSPServer:
    """A server for the LSP."""

    name: str
    binary: str
    parameters: list[str]
