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
"""
Contains a class for creating a (mostly) SCPI compatible measurement device.

The device listens on an ethernet interface and can be fully defined
from a dictionary with Command entries.
"""

import logging
import socketserver
import threading
import time

import numpy

from matr1x.core.config import datetimefmt

DEFAULT_PORT = 8898
logger = logging.getLogger(__name__)


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """
    Reimplemented TCP server to provide proper default behavior.

    This class combines ThreadingMixIn and TCPServer to create a
    threaded TCP server with specific default behaviors.
    """

    daemon_threads = True
    allow_reuse_address = True
    cmd_list: dict


class ThreadedTCPRequestHandler(socketserver.StreamRequestHandler):
    """
    Handles the TCP connection and parses the commands specified in the server's cmd_list.

    This class extends StreamRequestHandler to handle TCP connections
    and parse commands specified in the server's command list.
    """

    server: ThreadedTCPServer

    @staticmethod
    def _normalize_cmd(cmd):
        """
        Reduce all values to only have the first four digits.

        Parameters
        ----------
        cmd : str
            The command to normalize.

        Returns
        -------
        str
            The normalized command.
        """
        return ":".join([s[:4] for s in cmd.strip("?").split(":")])

    def setup(self):
        """
        Set up the server on initial startup.

        This method parses the cmd_list to generate the (normalized)
        keys and the command instructions.
        """
        super().setup()
        self.terminate = False
        self.normkeys = [self._normalize_cmd(cmd) for cmd in self.server.cmd_list]
        self.cmdvalues = list(self.server.cmd_list.values())

    def _handle_get_cmd(self, cmd: str) -> str | bytes | None:
        """
        Handle a get (query) command and return the result.

        Parameters
        ----------
        cmd : str
            The query command string (contains '?').

        Returns
        -------
        str | bytes | None
            The response value, or None if there is no valid getter.
        """
        # normalize command to have same format as keys in cmd_list
        normcmd = self._normalize_cmd(cmd)
        # identify query command in command list
        try:
            idx = self.normkeys.index(normcmd)
        except ValueError:
            print(  # noqa: T201
                f"{time.strftime(datetimefmt)}: invalid cmd ({cmd}) "
                f"sent from {self.client_address}"
            )
            # prepare a response since a response will be expected
            return cmd + " not recognized"
        # Call the getter command and return read value as str.
        # For lists, the values are separated by commas.
        # Will also work for returning lists of lists if the other
        # side interprets the value correctly (e.g. with
        # ast.literal_eval).
        # get command specifications
        c = self.cmdvalues[idx]

        if c.getfunc is None:
            # no getter is set
            logger.debug("getter is None for command: %s", cmd)
            return "None"
        if callable(c.getfunc):
            if isinstance(c.dtype, (tuple, list, numpy.ndarray)):
                return ",".join(str(r) for r in c.getfunc(*c.getargs))
            elif c.dtype is bytes:
                return c.getfunc(*c.getargs)
            else:
                return str(c.getfunc(*c.getargs))
        logger.debug("no valid getter for command: %s", cmd)

    def _handle_set_cmd(self, cmd: str) -> str | None:
        """
        Handle a set command and return the acknowledgement.

        Parameters
        ----------
        cmd : str
            The set command string (does not contain '?').

        Returns
        -------
        str | None
            The ASCII acknowledge character on success, or None if the
            command could not be processed.
        """
        value = ""
        # split at the first space, to separate command from value
        try:
            cmd, value = cmd.split(" ", 1)
        except ValueError:
            # no value was given or space was ommitted, split failed,
            # will not do anything for that command
            if cmd[0] != "*":
                # if what was sent was a * cmd (requires no value),
                # then go on with parsing
                return
        # normalize command to fit to cmd_list
        normcmd = self._normalize_cmd(cmd)
        # identify command
        try:
            idx = self.normkeys.index(normcmd)
        except ValueError:
            print(  # noqa: T201
                f"{time.strftime(datetimefmt)}: invalid cmd ({cmd}) "
                f"sent from {self.client_address}"
            )
            return
        # get command specifications
        c = self.cmdvalues[idx]
        if c.setfunc is None:
            logger.debug("'None' setter for command: %s", cmd)
            # return "acknowledgement" anyways to allow to continue
            # also see comment few lines above why this is in addition needed.
            return "\x06"
        try:
            # for listed values, split value into individual
            # values and cast to approprated "subtypes"
            if isinstance(c.dtype, (tuple, list, numpy.ndarray)):
                values = value.split(",")
                castval = []
                for i, tp in enumerate(c.dtype):
                    if tp is bool:
                        # cast bool via int to avoid wrong
                        # results
                        castval.append(bool(int(values[i])))
                    else:
                        castval.append(tp(values[i]))
            elif c.dtype is None:
                # exclude none for typecasting
                pass
            else:
                # typecast single value
                if c.dtype is bool:
                    castval = bool(int(value))
                else:
                    castval = c.dtype(value)
            # Call the set command with value and the
            # additional parameters specified in the
            # cmd_list
            if callable(c.setfunc):
                if c.dtype is None:
                    c.setfunc(*c.setargs)
                else:
                    c.setfunc(castval, *c.setargs)
                # send back ASCII acknowledge character
                # this is crucial on Linux where the
                # request/reply pattern has to be strictly
                # obeyed, otherwise some ~40ms delay is caused.
                return "\x06"
        except (IndexError, TypeError, ValueError):
            # in case of incorrectly sent command do nothing
            pass

    def parse(self, data):
        """
        Determine reply for received data.

        Parameters
        ----------
        data : str
            The received command data.

        Returns
        -------
        list
            List of responses for the received commands.
        """
        response: list[str | bytes] = []
        # multiple cmds support, separate commands with ;
        cmds = data.strip().split(";")
        for cmd in cmds:
            logger.debug("received command: %s", cmd)
            if "?" in cmd:
                result = self._handle_get_cmd(cmd)
            else:
                result = self._handle_set_cmd(cmd)
            if result is not None:
                response.append(result)
        return response

    def handle(self):
        """
        Handle incoming connections and manage the interface.

        This method runs continuously and parses incoming data to manage
        the interface.
        """
        while not self.terminate:
            response = None
            # read until \n and decode to utf-8
            data = str(self.rfile.readline(), "utf-8").strip().lower()
            if data == "":
                # empty string was passed, connection was closed
                break
            # get response corresponding to commands
            responses = self.parse(data)
            if len(responses) != 0:
                if len(responses) > 1:
                    response = ";".join(responses)
                else:
                    response = responses[0]
            if response is not None:
                response = response.replace("\n", "\\n")
                if not isinstance(response, bytes):
                    response = response.encode()
                self.request.sendall(response + b"\n")


class SCPI_TCP_Server:
    """
    Define Polling Server.

    This class creates a TCP server that implements SCPI-like command handling.

    Parameters
    ----------
    cmd_list : dict
        A dictionary defining the SCPI commands and their associated functions.
        The values of the dictionary should be derived from Command.
    host : str, optional
        The host address to bind the server to. Default is 'localhost'.
    port : int, optional
        The port number to listen on. Default is 8898.

    Attributes
    ----------
    running : bool
        Indicates whether the server is currently running.
    server : ThreadedTCPServer
        The actual TCP server instance.

    Notes
    -----
    Syntax for the command list:
        {scpi string:[type of value(s), set function to call, list/tuple of
        additional parameters for set function, get function to call,
        list/tuple of additional parameters for get function], ...}

    - scpi string is string type, e.g. ":field:set", use only lower case
      literals and make sure the commands are unique if only the first
      four characters within each pair of :: is used.
    - type of value can be:
      * [type val1, type val2, ...], can also be tuple of types
      * float
      * int
      * str
      * bool
      * None - if no set function is to be defined
    - set function e.g. ex.setField (do not add brackets!)
    - additional parameters, e.g. (2) if set function is ex.setField(value,
      axis) will call the function with value and axis=2
    - get function, again do not add brackets
    - additional parameters for get function, see above

    get function is called when ? is appended to scpi string upon calling
    the function, otherwise set function is called and value is split
    format is either:

    - set:
        scpiStr value
    - get:
        scpiStr?
    - value can be:
      * list
          e.g. value="1, 2, 3", also mixed lists,
          e.g. "1, 2.3432, abc", will be passed as list to set
          function.
          Take care to check correct type for list entries
      * int
          e.g. value="1"
      * bool
          e.g. value="0"
      * float
          e.g. value="-1.343e-23"
      * str
          e.g. value="curvename"
    """

    def __init__(self, cmd_list: dict, host: str = "localhost", port: int = DEFAULT_PORT):
        # run on localhost at port 8898 (default), take care, can be
        # accessible also from the internet if PC is accessible from there and
        # the host is not set to localhost!
        self.running = False
        self.server = ThreadedTCPServer((host, port), ThreadedTCPRequestHandler)
        self.server.cmd_list = cmd_list

    def start(self):
        """
        Start the server.

        This method starts the server if it's not already running.
        """
        if self.running is False:
            server_thread = threading.Thread(target=self.server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            logger.info("server started on %s", self.server.server_address)
            self.running = True

    def stop(self):
        """
        Stop the server.

        This method stops the server if it's currently running.
        """
        if self.running is True:
            self.server.shutdown()
            self.server.socket.close()
            self.server.server_close()
            # the next line apparently does not do anything and was commented 20260725
            # self.server.RequestHandlerClass.terminate: bool = True
            self.running = False
            logger.info("server stopped on %s", self.server.server_address)
