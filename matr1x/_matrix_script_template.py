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
INTERNAL TEMPLATE FILE - DO NOT RUN OR IMPORT DIRECTLY.

This file is a template used by matr1x.util.generate_script() to create
executable scripts for matrix-script. It contains placeholder variables
and markers that must be replaced before execution.
"""

import builtins as _builtins
import datetime as _datetime
import inspect as _inspect
import math as _math
import os as _os
import re as _re
import sys as _sys
import textwrap as _textwrap
import time as _time
import traceback as _traceback
import types as _types
import typing as _typing
from pathlib import Path as _Path

import wrapt as _wrapt

import matr1x as _matr1x
import matr1x.util as _matrix_util
from matr1x.models import Datafile as _Datafile
from matr1x.models import Header as _Header
from matr1x.models import LineNumber as _LineNumber
from matr1x.models import MeasuredValues as _MeasuredValues
from matr1x.models import Message as _Message
from matr1x.models import SetValues as _SetValues
from matr1x.models import Telemetry as _Telemetry
from matr1x.system import MergedSystem as _MergedSystem

if _typing.TYPE_CHECKING:
    from matr1x.execthread import ExecThread

    class _ThreadAPI:
        def __init__(self, exec_thread: ExecThread):
            self._exec_thread = exec_thread

    _thread_api = _ThreadAPI(ExecThread("", {}, "", None, []))

    # This has to match _vars in the run method of ExecThread
    _interrupt = _thread_api._exec_thread.interrupt
    _status = _thread_api._exec_thread.stop_status
    _report = _thread_api._exec_thread.report
    _input = _thread_api._exec_thread.input
    _meta_data = _thread_api._exec_thread.meta_data
    _scriptname = _thread_api._exec_thread.scriptname
    _script = _thread_api._exec_thread.script
    _system = _thread_api._exec_thread.system

# load config section from toml file
_validated_config = _matr1x.config.matr1x.scripts.matrix_script

# pass meta information
for _key, _value in _meta_data.items():
    if _key in _matr1x.VALID_META_KEYS.keys():
        if _matr1x.VALID_META_KEYS[_key]:
            _system.dcdata[_key] = _value
_setvalues = []  # buffer for set values for printing
_npoints = 0  # internal measurement point counter
_ntot = None  # total number of measurement points for telemetry
_starttime = _time.time()
_preset = _starttime
_reset_kwargs = {}
_user_script_start_line, _user_script_end_line = _matrix_util.get_user_script_line_range(_script)


def _configure_execution_path(scriptname: str | _Path) -> None:
    """Change execution path if requested in config."""
    script_path = _Path(scriptname)
    if _validated_config.script_path is None:
        if script_path.parent != _Path.cwd():
            _os.chdir(script_path.parent)
    else:
        config_path = _Path(_validated_config.script_path)
        if config_path.exists():
            _os.chdir(config_path)


def _configure_script_storing(system: _MergedSystem, script: str) -> None:
    """Store user script if requested in config."""
    if _validated_config.store_script_in_datafile:
        _, suffix = _matrix_util.generate_script_prefix_suffix()
        npref, nsuff = _matrix_util.get_script_prefix_offset(), len(suffix.splitlines())
        # strip prefix and suffix lines from script for storing
        user_script = _textwrap.dedent("\\n".join(script.splitlines()[npref:-nsuff]))
        if "user script" not in system.system_config_params:
            system.system_config_params["user script"] = user_script
        else:
            _report(
                _Message(
                    "'user script' key already present in system, not overwriting!",
                    to_comment=False,
                )
            )


def _find_caller_frame() -> _types.FrameType | None:
    """Find the nearest stack frame belonging to the user script."""
    frame = _inspect.currentframe()
    while frame:
        if (
            frame.f_code.co_filename == "<string>"
            and _user_script_start_line <= frame.f_lineno <= _user_script_end_line
        ):
            return frame
        frame = frame.f_back

    return None


@_wrapt.decorator
def _lineno_decorator(wrapped, instance, args, kwargs):
    """Report the executing line number back to the GUI."""
    _ = instance  # suppress ty warning
    _show_lineno()
    return wrapped(*args, **kwargs)


def _show_lineno() -> None:
    """Report the executing line number back to the GUI."""
    if frame := _find_caller_frame():
        caller_filename = frame.f_code.co_filename
        if caller_filename == "<string>":
            # report line only if called directly from script
            _report(_LineNumber(frame.f_lineno))


@_wrapt.decorator
def _breakpoint(wrapped, instance, args, kwargs):
    """Add a breakpoint check."""
    # avoid recursive loop (a decorated function calling another)
    # If the wrapped object is a method, attach _calling to the instance
    if instance is not None:
        if not hasattr(instance, "_calling"):
            instance._calling = False

        if instance._calling:
            # do not call decoration recursively
            return wrapped(*args, **kwargs)

        instance._calling = True
        try:
            _interrupt(duration=0)
            result = wrapped(*args, **kwargs)
        finally:
            instance._calling = False
    else:
        # If the wrapped object is a function,
        # attach _calling to the function itself
        if not hasattr(wrapped, "_calling"):
            wrapped._calling = False

        if wrapped._calling:
            # do not call decoration recursively
            return wrapped(*args, **kwargs)

        wrapped._calling = True
        try:
            _interrupt(duration=0)
            result = wrapped(*args, **kwargs)
        finally:
            wrapped._calling = False
    return result


def _inject_decorator(instance, decorator) -> None:
    """Inject decorator into instance methods."""
    for attr_name in dir(instance):
        if attr_name in ["add_comment", "report"]:
            # exclude this methods from decoration since they are
            # potentially called from inside the decorator. anything
            # called inside the _interrupt function should be added
            # here/not decorated.
            continue
        attr = getattr(instance, attr_name)
        if isinstance(attr, _types.MethodType):
            decorated_attr = decorator(attr)
            setattr(instance, attr_name, decorated_attr)


def _reset_setvalues() -> None:
    """Reset the setvalues variable."""
    global _setvalues
    _setvalues = []
    for col in _system.columns:
        value = [None] * len(col) if isinstance(col, (list, tuple)) else None
        _setvalues.append(value)


# inject line number decorator to time.sleep
_time.sleep = _lineno_decorator(_time.sleep)  # type: ignore time shadowing is intended!
# inject breakpoint and line number decorators to system methods
_inject_decorator(_system, _breakpoint)
for subsys in _system.subsys:
    _inject_decorator(subsys, _breakpoint)
    _inject_decorator(subsys, _lineno_decorator)
_reset_setvalues()  # initialize the setvalues variable
# bring meta_data and system into namespace
meta_data = _system.dcdata
system = _system


def set_value(parameter, value):
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
    _show_lineno()
    if parameter in _system.columns:
        i = _system.columns.index(parameter)
    else:
        i = parameter

    setv = _system.set_value(i, value)
    if setv is None and isinstance(_system.columns[i], (list, tuple)):
        _setvalues[i] = [
            None,
        ] * len(_system.columns[i])
    else:
        _setvalues[i] = setv  # ty: ignore[invalid-assignment]
    return setv


def trigger_value(parameter: str | int) -> None:
    """
    Execute trigger_value for the (merged) system.

    Parameters
    ----------
    parameter: str | int
        Parameter name or index.
    """
    _show_lineno()
    _system.trigger_value(parameter)


def read_value(parameter: str | int):
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
    _show_lineno()
    return _system.read_value(parameter)


def wait(
    duration: float | None = None,
    until: _datetime.datetime | str | None = None,
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
    _show_lineno()
    if isinstance(duration, (str, _datetime.datetime)) and not until:
        until = duration
        duration = None
    if duration and until:
        _report(_Message(f"until ({until}) argument of the wait function will be ignored"))
        until = None
    _interrupt(duration=duration, until=until, message=message, silent=silent)


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
    _show_lineno()
    return _input(message=query, timeout=timeout, default_value=default_value)


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
    _show_lineno()
    ret = _input(message=query, input_type="bool", timeout=timeout, default_value=default_value)
    if ret == "yes":
        return True
    return False


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
    _show_lineno()
    ret = _input(
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
    _show_lineno()
    if finished in (None, True, False):
        _status.finished = finished
    raise KeyboardInterrupt


def print(*args, sep: str = " ", end: str = "\n", file=None, flush: bool = False) -> None:  # noqa: A001
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
    _show_lineno()
    if file:
        _builtins.print(*args, sep=sep, end=end, file=file, flush=flush)
    else:
        message_text = sep.join(str(arg) for arg in args)
        _report(_Message(message_text, end=end))


# load execution path of scripts and change to this directory
_configure_execution_path(_scriptname)
# optionally set user script to be stored in data file
_configure_script_storing(_system, _script)
# initialize system and put devs into namespace
# disable to_comment since datafile can't be initialized yet
_report(_Message("setting system", to_comment=False))
# system.set is called before the filename is set. So, we have no
# arguments here -> this is a difference to matrix
_system.set()
devs = _system.devs

# switch meta data to append state
_system.dcdata.append = True
_initial_meta_data = dict(_system.dcdata)


def _reset_meta_data_to_initial() -> None:
    """Reset metadata to the values captured at script start."""
    append_state = _system.dcdata.append
    _system.dcdata.append = False
    try:
        for key, value in _initial_meta_data.items():
            _system.dcdata[key] = value
    finally:
        _system.dcdata.append = append_state


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
        Total number of expected datapoints for estimation of remaining
        measurement time.
    reset_meta_data : bool, optional
        If True, reset metadata to the values captured at script start
        before creating a new file.
    reset_date : bool, optional
        If True, refresh ``meta_data["date"]`` to the current time
        before creating a new file.
    """
    _interrupt(duration=0)  # equivalent to @_breakpoint with transparent signature
    _show_lineno()
    global _ntot, _npoints, _starttime

    if reset_meta_data:
        _reset_meta_data_to_initial()
    if reset_date:
        _system.dcdata["date"] = _time.strftime(f"{_matr1x.datetimefmt}", _time.localtime())

    _ntot = ntot
    _npoints = 0  # reset the number of measurement points
    _starttime = _time.time()

    safe_filename = _system.generate_datafilename(
        outputfile=filename, inputfile=_scriptname, append=append
    )
    if not append or not safe_filename.exists():
        # write header to file
        _system.dcdata["description"] = comment
        msg, outputfile = _system.init_datafile(_scriptname or "matrix script generated")
        _report(_Message(f"{msg}: {outputfile}"))
        _report(_Message("acquired configuration, and initialized file"))
    _report(_Header(columns=_system.columns, units=_system.units, to_stdout=print_header))
    _report(_Datafile(str(safe_filename.resolve())))


# wrap system.trigger and system.take_measurement_point into
# measure_system
def measure_system(
    print_setpoint: bool = True, print_data: bool = True, print_telemetry: bool = True
) -> list:
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
    _interrupt(duration=0)  # equivalent to @_breakpoint with transparent signature
    _show_lineno()
    global _preset, _npoints
    _npoints += 1
    preread = _time.time()
    if not _system.filename:
        init_datafile("")
    _report(_SetValues(_setvalues, to_stdout=print_setpoint))
    _reset_setvalues()
    _system.trigger()
    return_list = _system.take_measurement_point()
    _report(_MeasuredValues(return_list, to_stdout=print_data))
    elapsed = _time.time() - _starttime
    remaining = (elapsed / _npoints * _ntot - elapsed) / 60 if _ntot else _math.nan
    _report(
        _Telemetry(
            point=_npoints,
            points=_ntot or -1,
            elapsed=elapsed / 60,
            remaining=remaining,
            settime=preread - _preset,
            readtime=_time.time() - preread,
            to_stdout=print_telemetry,
        )
    )
    _preset = _time.time()
    return return_list


try:
    # the pass statement is needed to handle "empty" scripts
    # an empty script is one without code, but only comments
    pass
    # ==== BEGIN USER SCRIPT AREA ====
    # USER_SCRIPT_INSERTION_POINT
# ==== END USER SCRIPT AREA ====
except KeyboardInterrupt:
    _report(_Message("\nscript has been aborted by user."))
    # mark script as aborted per default once abort is called
    if _status.finished:
        _reset_kwargs["status"] = "finished"
    elif _status.finished is False:
        # supposed to be marked as aborted
        _reset_kwargs["status"] = "aborted"
    else:
        # finished is None, so ask what is supposed to happen
        _reset_kwargs["status"] = _input(message="", input_type="__end_script__", timeout=None)
except Exception as e:
    _report(_Message("script exited with error:", to_comment=False))
    # get traceback information and format accordingly
    exc_type, exc_value, exc_traceback = _sys.exc_info()

    tbinfo = _traceback.format_exception(exc_type, exc_value, exc_traceback)

    # Don't skip the traceback lines - we need them for line number
    # extraction
    tbstr = "".join(tbinfo[1:])  # Skip only the first line (Traceback header)

    tbstr = tbstr.replace("<module>", "script")

    # get line information from traceback
    ms = _re.search(r"line (\d+)", tbstr)

    if ms:
        line = int(ms.group(1))
        n_pref = _matrix_util.get_script_prefix_offset()
        adjusted_line = line - n_pref
        tbstr = _re.sub(r"line (\d+)", "line " + str(adjusted_line), tbstr)

        # Fix file replacement - get the actual script content
        # Since we're executing from a string, we need to get the script
        # content differently
        try:
            # Get the current script content from the _script variable
            # that was injected
            script_lines = _script.splitlines()
            if 1 <= line <= len(script_lines):
                actual_line = script_lines[line - 1].strip()
                tbstr = tbstr.replace('File "<string>"', f'"{actual_line}"')
            else:
                tbstr = tbstr.replace('File "<string>"', '"<unknown line>"')
        except Exception:
            tbstr = tbstr.replace('File "<string>"', '"<script>"')

        _report(_Message(tbstr, to_comment=False))

        # Check adjusted line instead of original line
        if adjusted_line < 1:
            _report(_Message(" error during device initialization", to_comment=False))
    else:
        # No line number found in traceback
        tbstr = tbstr.replace('File "<string>"', '"<script>"')
        _report(_Message(tbstr, to_comment=False))
        _report(_Message(" error during device initialization", to_comment=False))

    _reset_kwargs["status"] = "errored"
    if exc_type is None:
        _system.add_comment(f"Script errored: {e}")
    else:
        _system.add_comment(f"Script errored: {exc_type.__name__}: {e}")
# mark last open file as finished, if not labeled elsewhere
if "status" not in _reset_kwargs.keys():
    _reset_kwargs["status"] = "finished"
# the reset function is called at the script end only, but we
# nevertheless specify the last datafile name to be as close as possible
# to the behavior of matrix
_report(_Message("resetting system"))
_system.reset(**_reset_kwargs)
