# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2024 matr1x developers. All rights reserved.
# ---
"""
This module contains a class for creating a (mostly) SCPI compatible
measurement device listening on an ethernet interface, that can be fully
defined from one dictionary.
"""
import logging
import socketserver
import threading
import time

import numpy

from . import datetimefmt

PORT = 8898
logger = logging.getLogger(__name__)


class ThreadedTCPRequestHandler(socketserver.StreamRequestHandler):
    """
    Handles the TCP connection and parses the commands specified
    in the servers cmd_list
    """
    @staticmethod
    def _normalize_cmd(cmd):
        """
        reduce all values to only have the first four digits
        """
        return ":".join([s[:4] for s in cmd.strip("?").split(":")])

    def setup(self):
        """
        setup the server on initial startup, parses the cmd_list to generate
        the (normalized) keys and the command instructions
        """
        super().setup()
        self.terminate = False
        self.normkeys = [self._normalize_cmd(cmd) for cmd in
                         self.server.cmd_list]
        self.cmdvalues = list(self.server.cmd_list.values())

    def parse(self, data):
        """
        determine reply for received data
        """
        response = []
        # multiple cmds support, separate commands with ;
        cmds = data.strip().split(";")
        for cmd in cmds:
            logger.debug("received command: %s", cmd)
            # cmd is a get request
            if "?" in cmd:
                # normalize command to have same format as keys in cmd_list
                normcmd = self._normalize_cmd(cmd)
                # identify query command in command list
                try:
                    idx = self.normkeys.index(normcmd)
                except ValueError:
                    print(f"{time.strftime(datetimefmt)}: invalid cmd ({cmd}) "
                          f"sent from {self.client_address}")
                    # prepare a response since a response will be expected
                    response.append(cmd + " not recognized")
                else:
                    # Call the getter command and append read value as str to
                    # response. For lists, the values are separated by commas.
                    # Will also work for returning lists of lists if the other
                    # side interprets the value correctly (e.g. with
                    # ast.literal_eval).
                    # get command specifications
                    c = self.cmdvalues[idx]

                    if c.getfunc is None:
                        # no getter is set
                        logger.debug("getter is None for command: %s", cmd)
                        response.append("None")
                        continue
                    if callable(c.getfunc):
                        if isinstance(c.dtype, (tuple, list, numpy.ndarray)):
                            response.append(",".join(
                                str(r) for r in c.getfunc(*c.getargs)))
                        elif c.dtype is bytes:
                            response.append(c.getfunc(*c.getargs))
                        else:
                            response.append(str(c.getfunc(*c.getargs)))
                    else:
                        logger.debug("no valid getter for command: %s", cmd)
            # cmd is a set request
            else:
                # split at the first space, to separate command from value
                try:
                    cmd, value = cmd.split(" ", 1)
                except ValueError:
                    # no value was given or space was ommitted, split failed,
                    # will not do anything for that command
                    if not "*" == cmd[0]:
                        # if what was sent was a * cmd (requires no value),
                        # then go on with parsing
                        continue
                # normalize command to fit to cmd_list
                normcmd = self._normalize_cmd(cmd)
                # identify command
                try:
                    idx = self.normkeys.index(normcmd)
                except ValueError:
                    print(f"{time.strftime(datetimefmt)}: invalid cmd ({cmd}) "
                          f"sent from {self.client_address}")
                else:
                    # get command specifications
                    c = self.cmdvalues[idx]
                    if c.setfunc is not None:
                        try:
                            # for listed values, split value into individual
                            # values and cast to approprated "subtypes"
                            if isinstance(c.dtype, (tuple, list, numpy.ndarray)):
                                values = value.split(",")
                                castval = []
                                for i, tp in enumerate(c.dtype):
                                    if tp == bool:
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
                                if c.dtype == bool:
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
                        except (IndexError, TypeError, ValueError):
                            # in case of incorrectly sent command do nothing
                            pass
                    else:
                        logger.debug("no valid setter for command: %s", cmd)
        return response

    def handle(self):
        """
        handle that runs continuously and parses takes care of managing the
        interface
        """
        while not self.terminate:
            response = None
            # read until \n and decode to utf-8
            data = str(self.rfile.readline(), 'utf-8').strip().lower()
            if "" == data:
                # empty string was passed, connection was closed
                break
            # get response corresponding to commands
            responses = self.parse(data)
            if 0 != len(responses):
                if 1 < len(responses):
                    response = ";".join(responses)
                else:
                    response = responses[0]
            if response is not None:
                if not isinstance(response, bytes):
                    response = response.encode()
                self.request.sendall(response + b'\n')


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """
    reimplement TCP server to provide proper default behavior
    """

    daemon_threads = True
    allow_reuse_address = True


class SCPI_TCP_Server:
    """
    Define Polling Server

    Syntax for the command list:
        {scpi string:[type of value(s), set function to call, list/tuple of
        additional parameters for set function, get function to call,
        list/tuple of additional parameters for get function], ...}

      * scpi string is string type, e.g. ":field:set", use only lower case
        literals and make sure the commands are unique if only the first
        four characters within each pair of :: is used.
      * type of value can be:

        * [type val1, type val2, ...], can also be tuple of types
        * float
        * int
        * str
        * bool
        * None - if no set function is to be defined

      * set function e.g. ex.setField (do not add brackets!)
      * additional parameters, e.g. (2) if set function is ex.setField(value,
        axis) will call the function with value and axis=2
      * get function, again do not add brackets
      * additional parameters for get function, see above

      get function is called when ? is appended to scpi string upon calling
      the function, otherwise set function is called and value is split
      format is either:

      * set:
          scpiStr value
      * get:
          scpiStr?
      * value can be:

        * list
            e.g. value="1, 2, 3", also mixed lists,
            e.g. "1, 2.3432, abc", will be passed as list to set
            function.
            Take care to check correct type for list enties
        * int
            e.g. value="1"
        * bool
            e.g. value="0"
        * float
            e.g. value="-1.343e-23"
        * str
            e.g. value="curvename"
    """

    def __init__(self, cmd_list, host='localhost', port=PORT):
        # run on localhost at port 8898 (default), take care, can be
        # accessible also from the internet if PC is accessible from there and
        # the host is not set to localhost!
        self.running = False
        self.server = ThreadedTCPServer((host, port),
                                        ThreadedTCPRequestHandler)
        self.server.cmd_list = cmd_list

    def start(self):
        if self.running is False:
            server_thread = threading.Thread(target=self.server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            logger.info(f"server started on {self.server.server_address}")
            self.running = True

    def stop(self):
        if self.running is True:
            self.server.shutdown()
            self.server.socket.close()
            self.server.server_close()
            self.server.RequestHandlerClass.terminate = True
            self.running = False
            logger.info(f"server stopped on {self.server.server_address}")
