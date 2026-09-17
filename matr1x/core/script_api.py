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
"""Script API for matrix-script user scripts.

This module implements the functions that are available inside
matrix-script user scripts (`set_value`, `wait`, `measure_system`,
...). The generated script (see `_matrix_script_template.py`) calls
`install` with the execution context of the `ExecThread` and imports
the functions into the script namespace, so user scripts can call them
as plain functions.

Keeping the API in a regular importable module makes it typecheckable,
unit-testable, and usable as the documentation source for the
matrix-script API. Each script is executed in its own process, so the
module-level state is isolated per script run.
"""

import builtins
import datetime
import inspect
import textwrap
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import matr1x.core.config as core_config
from matr1x.core.execthread import Status
from matr1x.core.models import (
    Datafile,
    ExecutionLines,
    Header,
    MeasuredValues,
    MeasurementData,
    Message,
    SetValues,
    Telemetry,
)
from matr1x.core.script_analysis import PointCounts, infer_point_counts
from matr1x.core.system import MergedSystem
from matr1x.core.util import get_user_script_line_range

__all__ = [
    "capture_initial_meta_data",
    "checkpoint",
    "end_script",
    "init_datafile",
    "input",
    "input_bool",
    "input_numerical",
    "install",
    "measure_system",
    "print",
    "read_value",
    "set_value",
    "show_lineno",
    "trigger_value",
    "wait",
]


@dataclass
class _ScriptState:
    """Per-run execution context and state of the script API."""

    system: MergedSystem
    report: Callable[[MeasurementData], None]
    interrupt: Callable[..., None]
    input: Callable[..., str]
    status: Status
    scriptname: str
    start_line: int
    end_line: int
    inferred_point_counts: PointCounts
    setvalues: list[Any]
    npoints: int
    ntot: int | None
    starttime: float
    preset: float
    measurement_atomic_depth: int
    initial_meta_data: dict[str, Any]


_state: _ScriptState | None = None


def _get_state() -> _ScriptState:
    """Return the current script state, raising if not installed."""
    if _state is None:
        raise RuntimeError("The script API is not installed. Call install() first.")
    return _state


def install(
    system: MergedSystem,
    report: Callable[[MeasurementData], None],
    interrupt: Callable[..., None],
    input_fn: Callable[..., str],
    status: Status,
    script: str,
    scriptname: str,
) -> None:
    """
    Install the script API for the current script execution.

    Called once by the generated script with the execution context of
    the `ExecThread` before any user code runs.

    Parameters
    ----------
    system : MergedSystem
        The merged system of the selected system files.
    report : callable
        Callback that forwards measurement data to the GUI/CLI
        (`ExecThread.report`).
    interrupt : callable
        Callback that pauses execution, e.g. for waits and breakpoints
        (`ExecThread.interrupt`).
    input_fn : callable
        Callback that requests user input (`ExecThread.input`).
    status : Status
        Status object tracking whether the script is finished.
    script : str
        The full generated script, used to locate the user-script area.
    scriptname : str
        Name of the user script.
    """
    global _state
    start_line, end_line = get_user_script_line_range(script)
    user_script = textwrap.dedent("\n".join(script.splitlines()[start_line - 1 : end_line]))
    starttime = time.time()
    _state = _ScriptState(
        system=system,
        report=report,
        interrupt=interrupt,
        input=input_fn,
        status=status,
        scriptname=scriptname,
        start_line=start_line,
        end_line=end_line,
        inferred_point_counts=infer_point_counts(user_script),
        setvalues=[],
        npoints=0,
        ntot=None,
        starttime=starttime,
        preset=starttime,
        measurement_atomic_depth=0,
        initial_meta_data={},
    )
    _reset_setvalues()  # initialize the setvalues variable


def _find_caller_lines() -> list[int]:
    """Find the active user-script lines, from innermost to outermost."""
    state = _get_state()
    frame = inspect.currentframe()
    lines: list[int] = []
    seen_lines: set[int] = set()

    try:
        while frame is not None:
            line = frame.f_lineno
            if (
                frame.f_code.co_filename == "<string>"
                and state.start_line <= line <= state.end_line
                and line not in seen_lines
            ):
                lines.append(line)
                seen_lines.add(line)
            frame = frame.f_back
    finally:
        # Explicitly break the frame reference cycle created by currentframe().
        del frame

    return lines


def show_lineno() -> None:
    """Report the active user-script call chain back to the GUI."""
    if lines := _find_caller_lines():
        _get_state().report(ExecutionLines(lines=lines))


def checkpoint() -> None:
    """Handle a breakpoint unless a measurement point is in progress."""
    state = _get_state()
    if state.measurement_atomic_depth == 0:
        state.interrupt(duration=0)


def capture_initial_meta_data() -> None:
    """Capture the current metadata as the state to reset to."""
    state = _get_state()
    state.initial_meta_data = dict(state.system.dcdata)


def _reset_setvalues() -> None:
    """Reset the setvalues variable."""
    state = _get_state()
    state.setvalues = []
    for col in state.system.columns:
        value = [None] * len(col) if isinstance(col, (list, tuple)) else None
        state.setvalues.append(value)


def _reset_meta_data_to_initial() -> None:
    """Reset metadata to the values captured at script start."""
    state = _get_state()
    append_state = state.system.dcdata.append
    state.system.dcdata.append = False
    try:
        for key, value in state.initial_meta_data.items():
            state.system.dcdata[key] = value
    finally:
        state.system.dcdata.append = append_state


def set_value(parameter: str | int, value: Any) -> Any:
    """
    Store set parameters and call _system.set_value.

    Parameters
    ----------
    col : str or int
        Parameter name or index.
    value : Any
        Value to set.

    Returns
    -------
    Any
        Set value.
    """
    state = _get_state()
    show_lineno()
    if parameter in state.system.columns:
        i = state.system.columns.index(parameter)  # ty: ignore[invalid-argument-type]
    else:
        i = parameter

    setv = state.system.set_value(i, value)
    if setv is None and isinstance(state.system.columns[i], (list, tuple)):  # ty: ignore[invalid-argument-type]
        n = len(state.system.columns[i])  # ty: ignore[invalid-argument-type]
        state.setvalues[i] = [None] * n  # ty: ignore[invalid-assignment]
    else:
        state.setvalues[i] = setv  # ty: ignore[invalid-assignment]
    return setv


def trigger_value(parameter: str | int) -> None:
    """
    Execute trigger_value for the (merged) system.

    Parameters
    ----------
    parameter: str | int
        Parameter name or index.
    """
    show_lineno()
    _get_state().system.trigger_value(parameter)


def read_value(parameter: str | int) -> Any:
    """
    Execute read_value for the (merged) system.

    Parameters
    ----------
    parameter: str | int
        Parameter name or index.

    Returns
    -------
    Any
        Result of system.read_value.
    """
    show_lineno()
    return _get_state().system.read_value(parameter)


def wait(
    duration: float | None = None,
    until: datetime.datetime | str | None = None,
    message: str = "",
    silent: float = 10,
) -> None:
    """
    Pause for a duration, until a timestamp, or for a relative time.

    Parameters
    ----------
    duration : float or int, optional
        The number of seconds to sleep. If specified, the function will
        sleep for this duration. If paused during this duration the
        remaining wait time continue after unpausing. If a str or
        datetime object is used here it will be redirected to the until
        argument.
    until : str or datetime, optional
        A target time or relative time string. It can be:
            - An absolute timestamp: "YYYY-MM-DD HH:MM:SS" or "HH:MM".
            - A relative time string starting with '+' followed by a number
                and a unit (e.g., "+24h" for 24 hours, "+30m" for 30 min.,
                "+1d" for 1 day).
            - A `datetime` object representing a specific time.
    message : str, optional
        Print this string if the sleep exceeds the silent argument.
    silent : float, optional
        Print a message string if this value is exceeded.

    Examples
    --------
    >>> wait(duration=10)
    Pauses execution for 10 seconds.

    >>> wait(until="2025-11-05 15:30")
    Pauses execution until 15:30 on November 5, 2025.

    >>> wait(until="+2h")
    Pauses execution for 2 hours from the current time.

    >>> wait(until="18:00")
    Pauses execution until 18:00 today,
    or until the same time tomorrow if it has already passed today.
    """
    state = _get_state()
    show_lineno()
    if isinstance(duration, (str, datetime.datetime)) and not until:
        until = duration
        duration = None
    if duration and until:
        state.report(Message(f"until ({until}) argument of the wait function will be ignored"))
        until = None
    state.interrupt(duration=duration, until=until, message=message, silent=silent)


def input(query: str, timeout: float | None = None, default_value: str = "") -> str:  # noqa: A001
    """
    Ask user to provide some free text input.

    Parameters
    ----------
    query : str
        Query string presented to the user so they know what to enter.
    timeout : float or None, optional
        Max. time in seconds to wait for user input (default=None, no timeout).
    default_value : str, optional
        Value to return if timeout occurs. Default is empty string.

    Returns
    -------
    str
        User input.
    """
    show_lineno()
    return _get_state().input(message=query, timeout=timeout, default_value=default_value)


def input_bool(query: str, timeout: float | None = None, default_value: str = "yes") -> bool:
    """
    Ask user to answer a yes/no question.

    Parameters
    ----------
    query : str
        Question to ask the user.
    timeout : float or None, optional
        Max. time in seconds to wait for user input (default=None, no timeout).
    default_value : str, optional
        Value to return if timeout occurs. Default is yes.

    Returns
    -------
    bool
        True if the user answers yes, False otherwise.
    """
    show_lineno()
    ret = _get_state().input(
        message=query, input_type="bool", timeout=timeout, default_value=default_value
    )
    return ret == "yes"


def input_numerical(
    query: str,
    timeout: float | None = None,
    default_value: float = 0.0,
    min_value: float = -100e9,
    max_value: float = 100e9,
    step: float = 1.0,
    decimals: int = 2,
) -> float:
    """
    Ask user to answer a yes/no question.

    Parameters
    ----------
    query : str
        Question to ask the user.
    timeout : float or None, optional
        Max. time in seconds to wait for user input (default=None, no timeout).
    default_value : float, optional
        Value to return if timeout occurs. Default is 0.0.
    min_value : float, optional
        Minimal input value. Default is -1e9
    max_value : float, optional
        Maximum input value. Default is 1e9
    step : float, optional
        Allowed steps between user input values. Default is 1.0
    decimals : int, optional
        Number of decimals of the input number

    Returns
    -------
    float
        numerical user input value.
    """
    show_lineno()
    ret = _get_state().input(
        message=query,
        input_type="numerical",
        timeout=timeout,
        default_value=default_value,
        min_value=min_value,
        max_value=max_value,
        step=step,
        decimals=decimals,
    )
    return float(ret)


def end_script(finished: bool | None = None) -> None:
    """
    End the script execution and set the file status acordingly.

    Parameters
    ----------
    finished : bool, optional
        Mark the script as finished (True), unfinished (False) or do not
        change the status (None).
    """
    show_lineno()
    if finished in (None, True, False):
        _get_state().status.finished = finished
    raise KeyboardInterrupt


def print(  # noqa: A001
    *args: object,
    sep: str = " ",
    end: str = "\n",
    file: Any = None,
    flush: bool = False,
) -> None:
    """
    Print the message and optionally forward it to the datafile.

    When 'file' is None (default), the output is sent to the reporting
    system. Depending on project configuration, this output may be
    automatically recorded as a comment in the measurement datafile.

    Parameters
    ----------
    *args
        Print these values.
    sep: str
        String inserted between values, default a space.
    end: str
        String appended after the last value, default a newline.
    file
        A file-like object (stream); defaults to the GUI/CLI output.
        Note: Output to custom streams is NOT recorded in the datafile.
    flush
        Whether to forcibly flush the stream.
    """
    show_lineno()
    if file:
        builtins.print(*args, sep=sep, end=end, file=file, flush=flush)
    else:
        message_text = sep.join(str(arg) for arg in args)
        _get_state().report(Message(message_text, end=end))


def init_datafile(
    filename: str,
    comment: str | None = None,
    append: bool = False,
    print_header: bool = True,
    ntot: int | None = None,
    reset_meta_data: bool = True,
    reset_date: bool = True,
) -> None:
    """
    Initialize the datafile for the matrix_script measurement.

    By default a new datafile will be generated whose name is generated
    in a way that no existing datafile can be overwritten.

    Parameters
    ----------
    filename : str
        Name of the datafile to be used.
    comment : str, optional
        Comment to be saved in the file header.
    append : bool, optional
        Flag to tell if an existing datafile should be used. If append
        is False a new datafile with a non-conflicting name will be
        generated by appending "_<number>" to the filename.
    print_header : bool, optional
        Flag to decide if the header information with column names and
        units should be printed.
    ntot : int, optional
        Deprecated manual total number of expected datapoints. When omitted,
        matrix-script infers the total from statically analyzable source.
    reset_meta_data : bool, optional
        If True, reset metadata to the values captured at script start
        before creating a new file.
    reset_date : bool, optional
        If True, refresh `meta_data["date"]` to the current time
        before creating a new file.
    """
    state = _get_state()
    checkpoint()  # equivalent to @_breakpoint with transparent signature
    show_lineno()

    if reset_meta_data:
        _reset_meta_data_to_initial()
    if reset_date:
        state.system.dcdata["date"] = time.strftime(f"{core_config.datetimefmt}", time.localtime())

    if ntot is None:
        caller_lines = [line - state.start_line + 1 for line in _find_caller_lines()]
        state.ntot = state.inferred_point_counts.for_call_lines(caller_lines)
    else:
        state.ntot = ntot
        state.report(
            Message(
                "[MATR1X_DEPRECATED] init_datafile(ntot=...) is deprecated; "
                "the point total is inferred automatically.",
                to_comment=False,
            )
        )
    state.npoints = 0  # reset the number of measurement points
    state.starttime = time.time()

    safe_filename = state.system.generate_datafilename(
        outputfile=filename, inputfile=state.scriptname, append=append
    )
    if not append or not safe_filename.exists():
        # write header to file
        if comment is not None:
            state.system.dcdata["description"] = comment
        msg, outputfile = state.system.init_datafile(state.scriptname or "matrix script generated")
        state.report(Message(f"{msg}: {outputfile}"))
        state.report(Message("acquired configuration, and initialized file"))
    state.report(
        Header(columns=state.system.columns, units=state.system.units, to_stdout=print_header)
    )
    state.report(Datafile(str(safe_filename.resolve())))


def measure_system(
    print_setpoint: bool = True, print_data: bool = True, print_telemetry: bool = True
) -> list[Any]:
    """
    Perform the measurement of a single data point.

    A sequence of system.trigger, and reading the data is performed.

    Parameters
    ----------
    print_setpoint : bool, optional
        Flag to decide if the column values set since the last
        measurement should be printed in a way compatible with the
        header information of init_datafile.
    print_data : bool, optional
        Flag to decide if the measured data values should be printed in
        a way compatible with the header information of init_datafile.
    print_telemetry : bool, optional
        Flag to decide if telemetry data about the measurement duration
        should be printed.

    Returns
    -------
    list
        List of measured values.
    """
    state = _get_state()
    checkpoint()  # equivalent to @_breakpoint with transparent signature
    show_lineno()
    state.measurement_atomic_depth += 1
    try:
        if not state.system.filename:
            init_datafile("")
        state.npoints += 1
        preread = time.time()
        state.report(SetValues(state.setvalues, to_stdout=print_setpoint))
        _reset_setvalues()
        state.system.trigger()
        return_list = state.system.take_measurement_point()
        state.report(MeasuredValues(return_list, to_stdout=print_data))
        elapsed = time.time() - state.starttime
        remaining = (elapsed / state.npoints * state.ntot - elapsed) / 60 if state.ntot else None
        state.report(
            Telemetry(
                point=state.npoints,
                points=state.ntot or -1,
                elapsed=elapsed / 60,
                remaining=remaining,
                settime=preread - state.preset,
                readtime=time.time() - preread,
                to_stdout=print_telemetry,
            )
        )
        state.preset = time.time()
    finally:
        state.measurement_atomic_depth -= 1
    checkpoint()
    return return_list
