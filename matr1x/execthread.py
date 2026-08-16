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
Execution thread control for matrix-script.

This module includes function and variable definitions used for
execution of the matrix-script process.
"""

import logging
import re
import socket
import threading
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

import matr1x
from matr1x.error_handling import Error, InternalInvariantError
from matr1x.models import (
    ErrorMessage,
    Header,
    InputParameters,
    LogEntry,
    MeasuredValues,
    MeasurementData,
    Message,
    Modifier,
    SetValues,
    Telemetry,
)
from matr1x.system import MergedSystem
from matr1x.util import log_multiline

__all__ = ["ExecThread"]


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


@dataclass
class Status:
    finished: bool | None = None


class _CaptureHandler(logging.Handler):
    """Logging handler that captures log records and feeds a callback."""

    def __init__(self, cb: Callable[[LogEntry], None]):
        """Initialize the handler with a callback function."""
        super().__init__()
        self.send: Callable[[LogEntry], None] = cb

    def emit(self, record: logging.LogRecord):
        log = LogEntry(
            name=record.name,
            level=record.levelno,
            getMessage=record.getMessage(),
            created=record.created,
            lineno=record.lineno,
        )
        self.send(log)


class ExecThread(threading.Thread):
    """
    Thread that handles the execution of the measurement script.

    The thread is designed to be killable, allowing for graceful
    termination of the script execution.

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
        systems: list[str],
        /,
    ):
        """
        Initialize the execution thread.

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
        systems : list[str]
            List of system files to load.
        """
        super().__init__()
        self.logger = logging.getLogger(f"{self.__module__}")
        self.logger.propagate = False
        capture_handler = _CaptureHandler(self._send2socket)
        self.logger.addHandler(capture_handler)

        self.script = script
        self.meta_data = meta_data
        self.scriptname = scriptname
        validation_error_count = len(matr1x.validation_errors)
        system = MergedSystem.from_files(systems)
        if isinstance(system, Error):
            raise InternalInvariantError(
                "Systems should not contain errors at this point. "
                f"Nevertheless this happened: {system.error}"
            )
        if system_config_errors := matr1x.validation_errors[validation_error_count:]:
            raise ValueError("Invalid system configuration:\n" + "".join(system_config_errors))
        self.system: MergedSystem = system.value
        self.stop_status = Status()
        self.pause_flag = False
        self.interrupt_flag = False
        self.recv_flag = False
        self.recv: str = ""
        self.socket = socket

    def pause(self, state: bool) -> None:
        """
        Pause the execution at the breakpoint.

        Parameters
        ----------
        state : bool
            True to pause, False to resume.
        """
        self.pause_flag = bool(state)
        if state is True:
            self.report(Message("\npaused", to_comment=False))

    def stop(self, state: bool | None = None) -> None:
        """
        Set the interrupt flag, to stop execution at next breakpoint.

        Parameters
        ----------
        state : bool or None, optional
            The state to set for stop_status.finished.
        """
        self.pause_flag = False
        self.stop_status.finished = state
        self.interrupt_flag = True

    def interrupt(
        self,
        *,
        duration: float | None = None,
        until: str | datetime | None = None,
        message: str = "",
        silent: float = 10,
    ):
        """
        Pauses execution for a specified duration.

        Do this until a specified timestamp, or for a relative time.

        Parameters
        ----------
        duration : float, optional
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

        Raises
        ------
        ValueError
            If neither `duration` nor `until` is provided,
            or if the `until` format is not recognized.
        """
        now = datetime.now()
        msg = "" if not message else f" ({message})"

        if duration is not None:
            sleep_time = duration
            end_time = now + timedelta(seconds=sleep_time)
            if sleep_time > silent or msg:
                text = (
                    f"Waiting {sleep_time:.0f} seconds{msg} until {end_time.strftime('%H:%M:%S')}"
                )
                self.report(Message(text))

        elif until is not None:
            end_time = _parse_until_time(until, now)

            if end_time < now:
                text = (
                    f"Specified wait until time {end_time.strftime('%Y-%m-%d %H:%M:%S')} "
                    "is in the past. Continuing immediately."
                )
                self.report(Message(text))
                self.check_for_interrupt_and_pause()
                return

            sleep_time = (end_time - now).total_seconds()

            if sleep_time > silent or msg:
                if sleep_time < 3:
                    sleeptstr = f"{sleep_time:.2f}"
                else:
                    sleeptstr = f"{sleep_time:.0f}"
                text = (
                    f"Waiting until {end_time.strftime('%Y-%m-%d %H:%M:%S')} "
                    f"(in {sleeptstr} seconds){msg}"
                )
                self.report(Message(text))

        else:
            raise ValueError("Either `duration` or `until` must be provided.")

        # Perform the wait with pause handling
        self._execute_sleep(sleep_time, end_time, duration is not None, silent, msg)
        # Ensure interrupt and pause checks are called at least once, even if `sleep_time` is 0
        self.check_for_interrupt_and_pause()

    def _execute_sleep(
        self, sleep_time: float, end_time: datetime, is_duration: bool, silent: float, message: str
    ):
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
        """
        start_time = time.time()
        pause_duration = 0  # Tracks cumulative pause duration for duration-based waits
        initial_sleep_time = sleep_time  # Save the initial sleep time for reference

        while sleep_time > 0:
            # Calculate remaining time based on the end time for "until" waits
            if not is_duration and end_time:
                sleep_time = (end_time - datetime.now()).total_seconds()

            # Check for interruption or pause
            pause_start = time.time()  # Record when the pause starts
            if self.check_for_interrupt_and_pause():
                if not is_duration and end_time and datetime.now() >= end_time:
                    text = "\nThe target time passed during pause. Continuing immediately."
                    self.report(Message(text))
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
                    text = f"\nResuming wait for {sleep_time:.0f} seconds{message}."
                    self.report(Message(text))
                else:
                    # For "until" wait, recalculate based on the current end_time
                    sleep_time = max(0, (end_time - datetime.now()).total_seconds())
                    text = (
                        f"\nResuming wait until {end_time.strftime('%Y-%m-%d %H:%M:%S')} "
                        f"({sleep_time:.0f} seconds remaining)."
                    )
                    self.report(Message(text))

            # Sleep in precise intervals, adjusting each time
            if sleep_time > 1:
                if initial_sleep_time > silent:
                    self.report(
                        Message(
                            f"{int(sleep_time)} seconds remaining",
                            end="",
                            to_comment=False,
                            to_logfile=False,
                            modifier=Modifier.DELETE_CURRENT_LINE,
                        )
                    )
                time.sleep(min(1, sleep_time))  # Sleep in chunks
                sleep_time -= 1
            else:
                time.sleep(sleep_time)
                break

        if initial_sleep_time > silent:
            self.report(Message("Waiting done", modifier=Modifier.DELETE_CURRENT_LINE))

    def check_for_interrupt_and_pause(self) -> bool:
        """
        Check for interrupt and pause flags and take appropriate action.

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
            self.system.add_comment("measurement aborted on user request")
            self.interrupt_flag = False
            raise KeyboardInterrupt("Execution interrupted by user.")
        if self.pause_flag:
            self.system.add_comment("measurement paused on user request")
            while self.pause_flag and not self.interrupt_flag:
                # execution paused, wait for 100ms and recheck
                time.sleep(0.1)
            return True
        return False

    def input(
        self,
        *,
        message: str = "",
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
        if message == "":
            base_message = "User input requested, see executing line for context"
        else:
            # replace newline characters with placeholders (URL-encoding)
            base_message = message.replace("\n", "%0A")
        self.report(
            InputParameters(
                query=base_message,
                input_type=input_type,
                timeout=timeout,
                default_value=str(default_value),
                min_value=min_value,
                max_value=max_value,
                step=step,
                decimals=decimals,
            )
        )
        while self.recv == "" or self.recv_flag is True:
            time.sleep(0.1)
            if (time.time() - t0) > 60:
                self.report(Message("still waiting for user input", to_comment=False))
                t0 = time.time()
            self.check_for_interrupt_and_pause()
        # remove trailling line feed
        ret = self.recv.strip()
        self.logger.info("User input received: %s", ret)
        self.recv = ""
        return ret

    # callback function that handles the input
    def handle_input(self, inp: str) -> None:
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

    def report(self, data: MeasurementData) -> None:
        """
        Report data currently written by the matrix-script script.

        Parameters
        ----------
        data : ScriptData
            The data to report.
        """
        conf = matr1x.config.matr1x
        if isinstance(data, Message):
            if data.should_comment:
                self.system.add_comment(data.message)
            if data.should_log:
                log_multiline(self.logger, data.message.lstrip("\n"))
        elif isinstance(data, (Telemetry, Header, SetValues, MeasuredValues)):
            if data.to_stdout and conf.duplicate_output_to_logfile:
                log_multiline(self.logger, str(data))
        elif isinstance(data, InputParameters):
            self.logger.info(data)
        self._send2socket(data)

    def _send2socket(self, data: MeasurementData) -> None:
        """Send data via the socket across the air-gap."""
        if self.socket is None:
            return
        try:
            self.socket.sendall(data.model_dump_json().encode("utf-8") + b"\0")
        except OSError:
            self.logger.propagate = True
            self.logger.exception("Could not report matrix script data to GUI")

    def run(self):
        """Run the script and allow to cancel at the start."""
        try:
            _vars = {
                "_interrupt": self.interrupt,
                "_status": self.stop_status,
                "_report": self.report,
                "_input": self.input,
                "_meta_data": self.meta_data,
                "_scriptname": self.scriptname,
                "_script": self.script,
                "_system": self.system,
            }
            self.system.set_reporter(self.report)
            exec(self.script, _vars)
        except KeyboardInterrupt:
            self.report(Message("Script interrupted during initialization", to_comment=False))
        except Exception as e:
            error_message = "script exited with error:\n" + "".join(
                traceback.format_exception(type(e), e, e.__traceback__)
            )
            self.logger.propagate = True
            self.logger.exception("Unhandled exception in matrix script")
            self.report(ErrorMessage(error_message))
            try:
                self.system.reset(status="errored")
            except Exception:
                self.logger.propagate = True
                self.logger.exception("Failed to reset system after matrix script exception")
