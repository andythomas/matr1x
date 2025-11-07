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
execution thread control for matrix-script.

This module includes class definitions used for execution of the matrix-script process.
"""

import io
import logging
import re
import socket
import sys
import threading
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path

__all__ = ["ExecThread"]

logger = logging.getLogger("ExecThread")


def _parse_until_time(until: str | datetime, current_time: datetime) -> datetime:
    """
    Parse the 'until' parameter into a datetime object.

    Parameters
    ----------
    until : str or datetime
        A target time or relative time string, or datetime object.
    current_time : datetime
        The current time to use as reference for relative time parsing.

    Returns
    -------
    datetime
        The parsed end time.

    Raises
    ------
    ValueError
        If the until format is not recognized.
    TypeError
        If until is not a string or datetime object.
    """
    if isinstance(until, datetime):
        return until

    if isinstance(until, str) and until.startswith("+"):
        # Parse relative time
        match = re.match(r"\+(\d+\.?\d*)([smhd])", until)
        if match:
            value, unit = float(match.group(1)), match.group(2)
            if unit == "s":
                return current_time + timedelta(seconds=value)
            elif unit == "m":
                return current_time + timedelta(minutes=value)
            elif unit == "h":
                return current_time + timedelta(hours=value)
            elif unit == "d":
                return current_time + timedelta(days=value)
        else:
            raise ValueError("Invalid relative time format.")

    # Parse absolute time with multiple date formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%H:%M:%S",
        "%H:%M",
        "%Y/%m/%d %H:%M",
        "%d.%m.%Y %H:%M",
    ]

    for fmt in formats:
        try:
            parsed_time = datetime.strptime(until, fmt)
            if fmt in ["%H:%M:%S", "%H:%M"]:
                parsed_time = parsed_time.replace(
                    year=current_time.year, month=current_time.month, day=current_time.day
                )
                if parsed_time < current_time:
                    parsed_time += timedelta(days=1)
            return parsed_time
        except ValueError:
            continue

    raise ValueError("Timestamp format not recognized.")


class Unbuffered:
    r"""
    Implements a wrapper on stdout to make sure data is passed on immediately.

    This wrapper terminates messages with \0 to allow using \n
    and \r in print conventionally without breaking the
    formatting.
    """

    def __init__(self, stream):
        """
        Initialize the Unbuffered wrapper.

        Parameters
        ----------
        stream : file-like object
            The stream to wrap.
        """
        self.stream = stream

    def write(self, data):
        """
        Write data to the stream.

        Parameters
        ----------
        data : str
            Data to write.

        Returns
        -------
        None
        """
        self.stream.write(data + "\0")
        self.stream.flush()

    def writelines(self, datas):
        """
        Write multiple lines to the stream.

        Parameters
        ----------
        datas : iterable of str
            Lines to write.

        Returns
        -------
        None
        """
        self.stream.writelines(datas)
        self.stream.flush()

    def __getattr__(self, attr):
        """
        Get attribute from the underlying stream.

        Parameters
        ----------
        attr : str
            Attribute name.

        Returns
        -------
        Any
            The attribute value.
        """
        return getattr(self.stream, attr)


class Status:
    """Status class that stores the finished status for aborting."""

    def __init__(self, value: bool | None = None):
        """
        Initialize the Status object.

        Parameters
        ----------
        value : bool or None, optional
            Initial finished value.
        """
        self.finished = value

    @property
    def finished(self):
        """
        Get the finished status.

        Returns
        -------
        bool or None
            The finished status.
        """
        return self._finished

    @finished.setter
    def finished(self, value: bool | None):
        """
        Set finished value to either None, True or False.

        Parameters
        ----------
        value : bool or None
            The value to set.

        Returns
        -------
        None
        """
        if value in (None, True, False):
            self._finished = value


class ExecThread(threading.Thread):
    """
    Thread that handles the execution of the measurement script.

    The thread is designed to be killable, allowing for graceful termination
    of the script execution.

    Attributes
    ----------
    stop_status : Status
        Status object to track if the script is finished.
    pause_flag : bool
        Flag to indicate if the script is paused.
    interrupt_flag : bool
        Flag to indicate if the script should be interrupted.
    recv_flag : bool
        Flag to indicate if input is being received.
    recv : str
        Received input.
    """

    def __init__(
        self,
        script: str,
        meta_data: dict,
        scriptname: str,
        socket: socket.socket | None,
        n_pref: int = 0,
        systems: list | None = None,
    ):
        """Initialize the execution thread.

        Parameters
        ----------
        script : str
            Script to execute, should be generated by util.generate_script
        meta_data : dict
            Meta data.
        scriptname : str
            Name of the script.
        socket : socket.socket or None
            Socket for communication.
        n_pref : int, optional
            Number of prefix lines.
        systems : list, optional
            List of system files to load.
        """
        super().__init__()
        self.script = script
        self.meta_data = meta_data
        self.scriptname = scriptname
        self.systems = systems or []
        self.stop_status = Status()
        self.pause_flag = False
        self.interrupt_flag = False
        self.recv_flag = False
        self.recv = ""
        self.n_pref = n_pref
        self.socket = socket
        if self.socket is not None:
            # pass on all stdout to socket
            file = self.socket.makefile("w", buffering=None)
            sys.stdout = Unbuffered(file)

    def pause(self, state):
        """
        Pause the execution at the breakpoint.

        Parameters
        ----------
        state : bool
            True to pause, False to resume.

        Returns
        -------
        None
        """
        self.pause_flag = bool(state)
        if state is True:
            print("\npaused")

    def stop(self, state=None):
        """
        Set the interrupt flag, to stop execution at next breakpoint.

        Parameters
        ----------
        state : bool or None, optional
            The state to set for stop_status.finished.

        Returns
        -------
        None
        """
        self.pause_flag = False
        self.stop_status.finished = state
        self.interrupt_flag = True

    def interrupt(self, duration=None, until=None, message="", silent=10, system=None):
        """
        Pauses execution for a specified duration.

        Do this until a specified timestamp, or for a relative time.

        Parameters
        ----------
        duration : float or int, optional
            The number of seconds to sleep. If specified, the
            function will sleep for this duration.

        until : str or datetime, optional
            A target time or relative time string. It can be:
            - An absolute timestamp in a format like "YYYY-MM-DD HH:MM:SS" or "HH:MM".
            - A relative time string starting with '+' followed by a number and a unit
            (e.g., "+24h" for 24 hours, "+30m" for 30 minutes, "+1d" for 1 day).
            - A `datetime` object representing a specific time.

        message : str, optional
            Message to display during the wait.

        silent : float, optional
            Time threshold above which to display messages about the wait.

        system : object, optional
            System object to log comments if a pause or interrupt occurs.

        Raises
        ------
        ValueError
            If neither `duration` nor `until` is provided,
            or if the `until` format is not recognized.

        TypeError
            If `until` is not a string or `datetime` object.
        """
        now = datetime.now()
        msg = "" if not message else f" ({message})"
        print_func = system._print if system else print

        if duration is not None:
            sleep_time = duration
            end_time = now + timedelta(seconds=sleep_time)
            if sleep_time > silent or msg:
                text = (
                    f"Waiting {sleep_time:.0f} seconds{msg} until {end_time.strftime('%H:%M:%S')}"
                )
                print_func(text)

        elif until is not None:
            end_time = _parse_until_time(until, now)

            if end_time < now:
                print_func(
                    f"Specified wait until time {end_time.strftime('%Y-%m-%d %H:%M:%S')} "
                    "is in the past. Continuing immediately."
                )
                self.check_for_interrupt_and_pause(system)
                return

            sleep_time = (end_time - now).total_seconds()

            if sleep_time > silent or msg:
                if sleep_time < 3:
                    sleeptstr = f"{sleep_time:.2f}"
                else:
                    sleeptstr = f"{sleep_time:.0f}"
                print_func(
                    f"Waiting until {end_time.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"(in {sleeptstr} seconds){msg}"
                )

        else:
            raise ValueError("Either `duration` or `until` must be provided.")

        # Perform the wait with pause handling
        self._execute_sleep(sleep_time, end_time, duration is not None, silent, msg, system)
        # Ensure interrupt and pause checks are called at least once, even if `sleep_time` is 0
        self.check_for_interrupt_and_pause(system)

    def _execute_sleep(self, sleep_time, end_time, is_duration, silent, message, system):
        """
        Handle sleeping with interrupt and pause checks.

        Parameters
        ----------
        sleep_time : float
            Total time to sleep in seconds.
        end_time : datetime
            The target end time for the sleep.
        is_duration : bool
            Whether the initial wait was specified with a duration or until a timestamp.
        silent : float
            Threshold for showing status messages.
        message : str
            Message to display during waiting.
        system :
            System object to log comments if a pause or interrupt occurs.
        """
        start_time = time.time()
        pause_duration = 0  # Tracks cumulative pause duration for duration-based waits
        initial_sleep_time = sleep_time  # Save the initial sleep time for reference
        print_func = system._print if system else print

        while sleep_time > 0:
            # Calculate remaining time based on the end time for "until" waits
            if not is_duration and end_time:
                sleep_time = (end_time - datetime.now()).total_seconds()

            # Check for interruption or pause
            pause_start = time.time()  # Record when the pause starts
            if self.check_for_interrupt_and_pause(system):
                if not is_duration and end_time and datetime.now() >= end_time:
                    print_func("\nThe target time passed during pause. Continuing immediately.")
                    return
                elif is_duration:
                    # Calculate pause duration and extend end_time accordingly
                    pause_end = time.time()
                    pause_duration += pause_end - pause_start
                    end_time = datetime.now() + timedelta(
                        seconds=(initial_sleep_time - (time.time() - start_time - pause_duration))
                    )

                    # Recalculate sleep_time after adjusting for pause
                    sleep_time = (end_time - datetime.now()).total_seconds()
                    print_func(f"\nResuming wait for {sleep_time:.0f} seconds{message}.")
                else:
                    # For "until" wait, recalculate based on the current end_time
                    sleep_time = max(0, (end_time - datetime.now()).total_seconds())
                    print_func(
                        f"\nResuming wait until {end_time.strftime('%Y-%m-%d %H:%M:%S')} "
                        f"({sleep_time:.0f} seconds remaining)."
                    )

            # Sleep in precise intervals, adjusting each time
            if sleep_time > 1:
                if initial_sleep_time > silent:
                    # use normal print here to avoid having updates in datafile
                    print(f"\r{int(sleep_time)} seconds remaining", end="")
                time.sleep(min(1, sleep_time))  # Sleep in chunks
                sleep_time -= 1
            else:
                time.sleep(sleep_time)
                break

        if initial_sleep_time > silent:
            print_func("\rWaiting done")

    def check_for_interrupt_and_pause(self, system):
        """
        Check for interrupt and pause flags and take appropriate action.

        Parameters
        ----------
        system :
            System class providing add_comment to write a message to the datafile.

        Returns
        -------
        bool
            True if execution was paused, False otherwise

        Raises
        ------
        KeyboardInterrupt
            If the interrupt_flag is True
        """
        # This function is used as part of the decorator of many functions
        # inside the script. Make sure that all functions called here are
        # not decorated themselves. (e.g. system.add_comment)
        if self.interrupt_flag:
            # script will be aborted
            if system:
                system.add_comment("measurement aborted on user request")
            self.interrupt_flag = False
            raise KeyboardInterrupt("Execution interrupted by user.")
        if self.pause_flag:
            if system:
                system.add_comment("measurement paused on user request")
            while self.pause_flag and not self.interrupt_flag:
                # execution paused, wait for 100ms and recheck
                time.sleep(0.1)
            return True
        return False

    def input(
        self,
        message: str = "",
        system: object = None,
        input_type: str = "string",
        timeout: float = float("inf"),
        default_value: str | float = "",
        min_value: float | None = None,  # Optional: minimum value for numerical input
        max_value: float | None = None,  # Optional: maximum value for numerical input
        step: float | None = None,  # Optional: step size for numerical input
        decimals: int | None = None,  # Optional: number of decimals for numerical input
    ) -> str:
        """
        Handle user input requests from the script.

        This method manages the input request workflow, including
        displaying prompts, waiting for user response, and handling
        timeouts and interrupts.

        Parameters
        ----------
        message : str, optional
            Message to display to user requesting input. Default is
            empty string.
        system : object, optional
            System object that can be interrupted/paused. Default is
            None.
        input_type : str, optional
            Type of input expected. Default is "string".
        timeout : float, optional
            Timeout in seconds. Will be handled by GUI layer.
            Default is infinity.
        default_value : str | float, optional
            Default value if timeout occurs. Will be handled by GUI
            layer. Default is empty string.

        Returns
        -------
        str
            The user's input response with whitespace stripped.
        """
        t0 = time.time()
        if self.recv != "" and not self.recv_flag:
            self.recv = ""
        # Format the input pattern with proper handling of empty timeout slot
        if "" == message:
            base_message = "User input requested, see executing line for context"
        else:
            # replace newline characters with placeholders (URL-encoding)
            base_message = message.replace("\n", "%0A")

        # Handle cases for timeout and default value:
        # Construct the pattern based on input_type and provided parameters
        if input_type == "string":
            # Handle cases for timeout and default value for string input:
            # 1. Both timeout and default_value: __input_type:message:timeout:default__
            # 2. Only timeout: __input_type:message:timeout__
            # 3. Only default_value: __input_type:message::default__
            # 4. Neither: __input_type:message__
            if timeout != float("inf") and default_value:
                pattern = f"__input_{input_type}:{base_message}:{timeout}:{default_value}__"
            elif timeout != float("inf"):
                pattern = f"__input_{input_type}:{base_message}:{timeout}__"
            elif default_value:
                pattern = f"__input_{input_type}:{base_message}::{default_value}__"
            else:
                pattern = f"__input_{input_type}:{base_message}__"
        elif input_type == "numerical":
            # For numerical input,
            # always include placeholders for min, max, step
            # Pattern:
            # __input_numerical:message:timeout:default_value:
            # min_value:max_value:step:decimals__
            pattern = (
                f"__input_numerical:{base_message}:{timeout}:{default_value}:"
                f"{min_value}:{max_value}:{step}:{decimals}__"
            )
        else:
            # Default pattern for other types (e.g., bool, __end_script__)
            if timeout != float("inf") and default_value:
                pattern = f"__input_{input_type}:{base_message}:{timeout}:{default_value}__"
            elif timeout != float("inf"):
                pattern = f"__input_{input_type}:{base_message}:{timeout}__"
            elif default_value:
                pattern = f"__input_{input_type}:{base_message}::{default_value}__"
            else:
                pattern = f"__input_{input_type}:{base_message}__"

        print(pattern, end="")

        while self.recv == "" or self.recv_flag is True:
            time.sleep(0.1)
            if (time.time() - t0) > 60:
                print("still waiting for user input")
                t0 = time.time()
            self.check_for_interrupt_and_pause(system)
        # remove trailling line feed
        ret = self.recv.strip()
        # print output
        logger.info("User input received: %s", ret)
        self.recv = ""
        return ret

    # callback function that handles the input
    def handle_input(self, inp):
        """
        Handle input that is passed to the thread.

        Parameters
        ----------
        inp : str
            The input string to be handled.
        """
        if self.recv_flag is False:
            if inp == "p":
                self.pause(not self.pause_flag)
            elif inp == "q":
                self.stop()
            elif inp == "f":
                self.stop(True)
            elif inp == "a":
                self.stop(False)
            elif inp == "i":
                # reset input if already available
                self.recv = ""
                self.recv_flag = True
            return
        if inp == "\n":
            self.recv_flag = False
        self.recv += inp

    def report_line(self, lineno):
        """
        Report currently executing line number to the matrix-script.

        Reports the line number in the format __lineno{+-number of line}__.

        Parameters
        ----------
        lineno : int
            The line number to report.
        """
        if self.socket is None:
            # only print line number if connected to a socket
            return
        lineno -= self.n_pref
        if lineno > -1:
            print(f"__lineno{lineno:d}__", end="")

    def report_path(self, path: str | Path):
        """
        Report datafile that is currently written by matrix-script.

        The format is __//{path to measurement file}//__

        Parameters
        ----------
        path : str | Path
            Path to the measurement file.
        """
        if self.socket is None:
            # only report filename if connected to a socket
            return
        if path != "":
            print(f"__//{path}//__", end="")

    def run(self):
        """
        Run the script and provide meaningful error information.

        This method executes the script and handles any errors that
        occur during execution, providing detailed error
        information.
        """
        try:
            try:
                _vars = {
                    "_interrupt": self.interrupt,
                    "_status": self.stop_status,
                    "_report_line": self.report_line,
                    "_report_path": self.report_path,
                    "_input": self.input,
                    "_meta_data": self.meta_data,
                    "_scriptname": self.scriptname,
                    "_script": self.script,
                    "_systems": self.systems,
                }
                exec(self.script, _vars)
            except Exception:
                # This catches errors during template initialization or cleanup,
                # not user script errors (those are handled in the template itself)
                print("script initialization/cleanup error:")

                # Get the traceback and improve the file context
                tb_str = io.StringIO()
                traceback.print_exc(file=tb_str)
                tb_output = tb_str.getvalue()

                # Replace <string> with more descriptive context
                lines = tb_output.split("\n")
                for i, line in enumerate(lines):
                    if 'File "<string>"' in line and ", line " in line:
                        # Extract line number from the traceback
                        match = re.search(r"line (\d+)", line)
                        if match:
                            line_num = int(match.group(1))
                            # Add template context
                            replacement = f'File "<template script, line {line_num}>"'
                            lines[i] = line.replace('File "<string>"', replacement)

                print("\n".join(lines))
        except KeyboardInterrupt:
            print("script interrupted during initialization")
