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
"""Client for communicating with an LSP server subprocess."""

import json
import subprocess
import sys
import threading
import time
from queue import Empty, Queue

from pydantic import ValidationError
from PySide6.QtCore import (
    QObject,
    Signal,
)

from matr1x.core.error_handling import Error, Result, Success
from matr1x.gui.mixins import LoggerMixin

from .lsp_protocol import (
    JsonRpcNotification,
    JsonRpcRequest,
    JsonRpcResponse,
    LSPServer,
)


class LSPClient(QObject, LoggerMixin):
    """
    Allow communication to an LSP server.

    Parameters
    ----------
    server : LSPServer
        The lsp server with parameters to start in the subprocess.
    """

    notification: Signal = Signal(JsonRpcNotification)

    def __init__(self, server: LSPServer) -> None:
        super().__init__()
        self.server = server
        self.cmd_line = [server.binary] + server.parameters
        self.process: subprocess.Popen | None = None
        self.id: int = 0
        self.pending_requests: dict[int, Queue[JsonRpcResponse | None]] = {}
        self.reader_thread: threading.Thread | None = None
        self.stderr_thread: threading.Thread | None = None
        self.stop_event = threading.Event()

    def start(self) -> None:
        """Start the LSP server process."""
        self.stop_event.clear()
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW
        self.process = subprocess.Popen(
            self.cmd_line,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            creationflags=creationflags,
        )
        time.sleep(0.1)
        self.reader_thread = threading.Thread(target=self._message_reader, daemon=True)
        self.reader_thread.start()
        self.stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self.stderr_thread.start()
        self.logger.info("LSP server started.")

    def stop(self) -> None:
        """Stop the LSP server."""
        self.stop_event.set()
        if self.process:
            self.process.terminate()
            self.process.wait()
        if self.reader_thread:
            self.reader_thread.join(timeout=1.0)
        if self.stderr_thread:
            self.stderr_thread.join(timeout=1.0)
        self.logger.info("LSP server stopped.")

    def send_request(
        self, method: str, params: dict | None = None
    ) -> Result[JsonRpcResponse, None]:
        """
        Send a request to the LSP to trigger a response.

        Parameters
        ----------
        method : str
            A string with the name of the method to be invoked.
        params: dict (optional)
            An object to be passed as parameters to the defined method.
        """
        timeout = 0.05  # timeout should be >0.01 on my Mac
        if (
            self.stop_event.is_set()
            or not self.process
            or not self.process.stdin
            or self.process.poll() is not None
        ):
            return Error(None)
        request_id = self.id
        message = self._build_request(method, params)
        response_queue: Queue[JsonRpcResponse | None] = Queue()
        self.pending_requests[request_id] = response_queue
        try:
            self.process.stdin.write(message.encode())
            self.process.stdin.flush()
            response = response_queue.get(timeout=timeout)
        except (BrokenPipeError, OSError, ValueError):
            self.logger.debug("LSP009: Failed to write request to LSP.")
            return Error(None)
        except Empty:
            self.logger.debug("LSP007: Timeout waiting for response to %s", method)
            return Error(None)
        finally:
            self.pending_requests.pop(request_id, None)
        if response is None:
            return Error(None)
        return Success(response)

    def send_notification(self, method: str, params: dict | None = None) -> None:
        """
        Send a notification to the LSP.

        Parameters
        ----------
        method : str
            A string with the name of the method to be invoked.
        params: dict (optional)
            An object to be passed as parameters tothe defined method.
        """
        if (
            self.stop_event.is_set()
            or not self.process
            or not self.process.stdin
            or self.process.poll() is not None
        ):
            return
        message = self._build_notification(method, params)
        try:
            self.process.stdin.write(message.encode())
            self.process.stdin.flush()
        except (BrokenPipeError, OSError, ValueError):
            self.logger.debug("LSP010: Failed to write notification to LSP.")

    def _handle_response(self, message: str) -> None:
        """
        Handle a JSON-RPC response message.

        Parameters
        ----------
        message : str
            The message string to process as a response.
        """
        try:
            response = JsonRpcResponse.model_validate_json(message)
        except ValidationError:
            self.logger.warning("LSP004: Invalid response message.")
            return
        if response.id is None:
            self.logger.warning("LSP005: id is None in response message.")
            return
        response_queue = self.pending_requests.get(response.id)
        if response_queue is None:
            return
        try:
            response_queue.put_nowait(response)
        except Exception:
            self.logger.warning("LSP003: Exception putting response in queue.")

    def _handle_notification(self, message: str) -> None:
        """
        Handle a JSON-RPC notification message.

        Parameters
        ----------
        message : str
            The message string to process as a notification.
        """
        try:
            notification = JsonRpcNotification.model_validate_json(message)
            self.notification.emit(notification)
        except ValidationError:
            self.logger.warning("LSP006: Invalid notification message.")

    def _drain_stderr(self) -> None:
        """
        Continuously drain stderr from the LSP server process.

        Some LSPs log into stderr. This avoids a stall in that case.
        """
        if not self.process or not self.process.stderr:
            return
        try:
            while not self.stop_event.is_set():
                if not self.process.stderr.read(1024):
                    break
        except (OSError, ValueError):
            self.logger.warning("LSP008: Exception draining stderr.")

    def _message_reader(self) -> None:
        """Read messages from the LSP server."""
        if not self.process or not self.process.stdout:
            return
        try:
            while not self.stop_event.is_set():
                message = self._read_one_message()
                if message is None:
                    break
                if "id" in json.loads(message):
                    self._handle_response(message)
                else:
                    self._handle_notification(message)
        except Exception as e:
            for response_queue in self.pending_requests.values():
                response_queue.put_nowait(None)  # Signal error
            raise RuntimeError("Message reader crashed!") from e

    def _read_one_message(self) -> str | None:
        """
        Read one message from the LSP server.

        Returns
        -------
        str | None
            The message content or None.
        """
        if not self.process or not self.process.stdout:
            return None
        content_length: int = 0
        while not self.stop_event.is_set():
            try:
                line_bytes = self.process.stdout.readline()
                if not line_bytes:
                    return None
                line = line_bytes.decode().strip()
                if line.startswith("Content-Length:"):
                    content_length = int(line.split(":")[1].strip())
                elif line == "":  # Empty line separates headers from content
                    break
            except (OSError, ValueError):
                self.logger.warning("LSP001: Exception reading message.")
                return None
        if content_length <= 0:
            return None
        try:
            content_bytes = self.process.stdout.read(content_length)
            if len(content_bytes) != content_length:
                return None
            result = content_bytes.decode()
            return result
        except (OSError, ValueError):
            self.logger.warning("LSP002: Exception reading message content.")
            return None

    def _add_length(self, json_call: JsonRpcRequest | JsonRpcNotification) -> str:
        """
        Add the required header with the length of the message.

        Parameters
        ----------
        json_call: JsonRpcRequest or JsonRpcNotification
            The request or notification message.

        Returns
        -------
        str
            The message with the added header (Content-Length).
        """
        serialized_call = json_call.model_dump_json()
        content_length = len(serialized_call.encode("utf-8"))
        message = f"Content-Length: {content_length}\r\n\r\n{serialized_call}"
        return message

    def _build_request(self, method: str, params: dict | None = None) -> str:
        """
        Build a compliant JSON RPC2 request to trigger a response.

        Parameters
        ----------
        method : str
            A string with the name of the method to be invoked.
        params: dict (optional)
            An object to be passed as parameters to the defined method.

        Returns
        -------
        str
            The serialized JSON request.
        """
        packet = JsonRpcRequest(jsonrpc="2.0", id=self.id, method=method, params=params)
        self.id += 1
        return self._add_length(packet)

    def _build_notification(self, method: str, params: dict | None = None) -> str:
        """
        Build a compliant JSON RPC2 notification.

        Parameters
        ----------
        method : str
            A string with the name of the method to be invoked.
        params: dict (optional)
            An object to be passed as parameters to the defined method.

        Returns
        -------
        str
            The serialized JSON notification.
        """
        packet = JsonRpcNotification(jsonrpc="2.0", method=method, params=params)
        return self._add_length(packet)
