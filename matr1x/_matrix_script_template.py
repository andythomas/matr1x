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
"""INTERNAL TEMPLATE FILE - DO NOT RUN OR IMORT DIRECTLY.

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

import wrapt

import matr1x as _matr1x
import matr1x.util as _matrix_util
from matr1x.system import MergedSystem as _MergedSystem

if _typing.TYPE_CHECKING:

    def _interrupt(duration=None, until=None, message="", silent=10, system=None): ...
    def _report_line(line_number: int): ...
    def _report_path(path): ...
    def _input(
        message: str = "",
        system: object = None,
        input_type: str = "string",
        timeout: float = float("inf"),
        default_value: str | float = "",
        min_value: float | None = None,
        max_value: float | None = None,
        step: float | None = None,
        decimals: int | None = None,
    ) -> str: ...

    _meta_data = {}
    _scriptname = ""
    _script = ""

    class _StatusStub:
        finished: bool | None = None

    _status = _StatusStub()
    _systems = []

# load config section from toml file
_config = _matr1x.get_config_dict("matr1x.scripts.matrix-script")

_system = _MergedSystem.from_files(_systems)

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


def _configure_execution_path(scriptname: str | _Path):
    """Change execution path if requested in config."""
    script_path = _Path(scriptname)
    if _config["script_path"] == "<script-location>":
        if script_path.parent != _Path.cwd():
            _os.chdir(script_path.parent)
    else:
        config_path = _Path(_config["script_path"])
        if config_path.exists():
            _os.chdir(config_path)


def _configure_script_storing(system, script):
    """Store user script if requested in config."""
    if _config["store_script_in_datafile"]:
        prefix, suffix = _matrix_util.generate_script_prefix_suffix()
        npref, nsuff = _matrix_util.get_script_prefix_offset(), len(suffix.splitlines())
        # strip prefix and suffix lines from script for storing
        user_script = _textwrap.dedent("\\n".join(script.splitlines()[npref:-nsuff]))
        if "user script" not in system.system_config_params:
            system.system_config_params["user script"] = user_script
        else:
            print("'user script' key already present in system, not overwriting!")


def _find_caller_frame():
    """Find the frame of the actual caller, skip decorator frames."""
    # stepping twice back on frame, since the inner most frame is from
    # this and the second one is from the _lineno decorator/function.
    frame = _inspect.currentframe()
    frame = frame.f_back.f_back if (frame and frame.f_back) else None
    # Try to find the first frame called in script environment
    # in Python 3.13+
    while frame:
        if frame.f_code.co_filename == "<string>":
            if frame.f_code.co_name.startswith("_") or frame.f_code.co_name in ["wait", "print"]:
                frame = frame.f_back
                continue
            else:
                return frame

        frame = frame.f_back

    # Fallback for Python <=3.12: step back a fixed number of frames
    frame = _inspect.currentframe()
    steps_back = 3 if _sys.version_info >= (3, 13) else 2
    for _ in range(steps_back):
        frame = frame.f_back if frame else None

    return frame  # Returns the frame that we believe to be the caller


@wrapt.decorator
def _lineno_decorator(wrapped, instance, args, kwargs):
    """Report the executing line number back to the GUI."""
    _show_lineno()
    return wrapped(*args, **kwargs)


def _show_lineno() -> None:
    """Report the executing line number back to the GUI."""
    frame = _find_caller_frame()
    if frame:
        caller_filename = frame.f_code.co_filename
        if caller_filename == "<string>":
            # report line only if called directly from script
            _report_line(frame.f_lineno)


@wrapt.decorator
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
            _interrupt(0, system=_system)
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
            _interrupt(0, system=_system)
            result = wrapped(*args, **kwargs)
        finally:
            wrapped._calling = False
    return result


def _inject_decorator(instance, decorator):
    """Inject decorator into instance methods."""
    for attr_name in dir(instance):
        if attr_name in ["add_comment", "_print"]:
            # exclude this methods from decoration since they are
            # potentially called from inside the decorator. anything
            # called inside the _interrupt function should be added
            # here/not decorated.
            continue
        attr = getattr(instance, attr_name)
        if isinstance(attr, _types.MethodType):
            decorated_attr = decorator(attr)
            setattr(instance, attr_name, decorated_attr)


def _reset_setvalues():
    """Reset the setvalues variable."""
    global _setvalues
    _setvalues = []
    for i, col in enumerate(_system.columns):
        if isinstance(col, (list, tuple)):
            _setvalues.append(
                [
                    None,
                ]
                * len(col)
            )
        else:
            _setvalues.append(None)


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
        _setvalues[i] = setv
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
        print(f"until ({until}) argument of the wait function will be ignored")
        until = None
    _interrupt(duration=duration, until=until, message=message, silent=silent, system=_system)


def input(query: str, timeout: float = float("inf"), default_value: str = "") -> str:  # noqa: A001
    """
    Ask user to provide some free text input.

    Parameters
    ----------
    query : str
        Query string presented to the user so they know what to enter.
    timeout : float, optional
        Max. time in seconds to wait for user input (default=infinity).
    default_value : str, optional
        Value to return if timeout occurs. Default is empty string.

    Returns
    -------
    str
        User input.
    """
    _show_lineno()
    return _input(query, system=_system, timeout=timeout, default_value=default_value)


def input_bool(query: str, timeout: float = float("inf"), default_value: str = "yes") -> bool:
    """
    Ask user to answer a yes/no question.

    Parameters
    ----------
    query : str
        Question to ask the user.
    timeout : float, optional
        Max. time in seconds to wait for user input (default=infinity).
    default_value : str, optional
        Value to return if timeout occurs. Default is yes.

    Returns
    -------
    bool
        True if the user answers yes, False otherwise.
    """
    _show_lineno()
    ret = _input(
        query,
        system=_system,
        input_type="bool",
        timeout=timeout,
        default_value=default_value,
    )
    if ret == "yes":
        return True
    return False


def input_numerical(
    query: str,
    timeout=float("inf"),
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
    timeout : float, optional
        Max. time in seconds to wait for user input (default=infinity).
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
        query,
        system=_system,
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
    _status.finished = finished
    raise KeyboardInterrupt


def print(*args, sep: str = " ", end: str = "\n", file=None, flush: bool = False) -> None:  # noqa: A001
    """
    Print the message and optionally forward it to the datafile.

    The arguments are identical to the Python print builtin. The
    behavior of this function depends on the config option
    matr1x.scripts.matrix-script.print_to_comment.

    Parameters
    ----------
    *args
        Print these values.
    sep: str
        String inserted between values, default a space.
    end: str
        String appended after the last value, default a newline.
    file
        A file-like object (stream); defaults to the output widget.
    flush
        Whether to forcibly flush the stream.
    """
    _show_lineno()
    _system._print(*args, sep=sep, end=end, file=file, flush=flush)


# load execution path of scripts and change to this directory
_configure_execution_path(_scriptname)
# optionally set user script to be stored in data file
_configure_script_storing(_system, _script)
# initialize system and put devs into namespace
print("setting system")
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
    _interrupt(0, system=_system)  # equivalent to @_breakpoint with transparent signature
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
        print(f"{msg}: {outputfile}")
        print("acquired configuration, and initialized file")
    if print_header:
        _matrix_util.print_formatted_line(_matrix_util.flatten(_system.columns))
        _matrix_util.print_formatted_line(_matrix_util.flatten(_system.units))
    # report file to matrix_script
    _report_path(safe_filename.resolve())


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
    _interrupt(0, system=_system)  # equivalent to @_breakpoint with transparent signature
    _show_lineno()
    global _preset, _npoints
    _npoints += 1
    preread = _time.time()
    if not _system.filename:
        init_datafile("")

    if print_setpoint:
        _matrix_util.print_formatted_line(_matrix_util.flatten(_setvalues), prefix="Set : ")
    _reset_setvalues()

    _system.trigger()
    return_list = _system.take_measurement_point()
    if print_data:
        _matrix_util.print_formatted_line(return_list, prefix="Meas: ")
    if print_telemetry:
        elapsed = _time.time() - _starttime
        if _ntot:
            remaining = (elapsed / _npoints * _ntot - elapsed) / 60
        else:
            remaining = _math.nan
        # use builtins.print here to make sure the telemetry do not get
        # added to the datafile
        _builtins.print(
            _matrix_util.telemetry_string.format(
                _npoints,
                _ntot or -1,
                elapsed / 60,
                remaining,
                preread - _preset,
                _time.time() - preread,
            )
        )
    if print_data or print_telemetry or print_setpoint:
        # isolate different iterations of measure system by a space
        _builtins.print("")
    _preset = _time.time()
    return return_list


# ==== BEGIN USER SCRIPT AREA ====
try:
    # the pass statement is needed to handle "empty" scripts
    # an empty script is one without code, but only comments
    pass
    # USER_SCRIPT_INSERTION_POINT
# ==== END USER SCRIPT AREA ====
except KeyboardInterrupt:
    print("\nscript has been aborted by user.")
    # mark script as aborted per default once abort is called
    if _status.finished:
        _reset_kwargs["status"] = "finished"
    elif _status.finished is False:
        # supposed to be marked as aborted
        _reset_kwargs["status"] = "aborted"
    else:
        # finished is None, so ask what is supposed to happen
        _reset_kwargs["status"] = _input("", system=_system, input_type="__end_script__")
except Exception as e:
    print("script exited with error:")
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

        print(tbstr)

        # Check adjusted line instead of original line
        if adjusted_line < 1:
            print(" error during device initialization\n")
    else:
        # No line number found in traceback
        tbstr = tbstr.replace('File "<string>"', '"<script>"')
        print(tbstr)
        print(" error during device initialization\n")

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
print("resetting system")
_system.reset(**_reset_kwargs)
