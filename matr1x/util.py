# This file is part of a software collection for data aquisition (matr1x).
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
"""Utility functions for the matr1x data acquisition software.

This module includes functions for file handling, script generation, sweep calculations,
and various helper functions for data processing and system configuration.
"""
import datetime
import importlib.util
import os
import re
import subprocess
import sys
import sysconfig
import tempfile
import textwrap
import time
from contextlib import contextmanager
from os.path import abspath, isabs, isdir, isfile, join, relpath

import h5py
import numpy as np

# conditional import for non-blocking io
if os.name == "nt":
    import msvcrt
else:
    import termios
    from select import select

# conditional import for Mac: Required to correctly set the app name and left-most menu
if sys.platform == "darwin":
    from AppKit import NSApplication
    from Foundation import NSBundle

# appendable meta keys:
APP_META_KEY = ["description"]

# allow error handling while using with


@contextmanager
def open_and_error(filename, mode="r"):
    """
    Context manager to handle file opening with error handling.

    Parameters
    ----------
    filename : str
        Name of the file to open.
    mode : str, optional
        Mode in which to open the file. Default is "r" (read mode).

    Yields
    ------
    tuple
        A tuple containing the file object and None if successful,
        or None and the error if an exception occurs.
    """
    try:
        f = open(filename, mode)
    except Exception as error:
        yield None, error
    else:
        try:
            yield f, None
        finally:
            f.close()

# default separator
default_separator = "\t"

# telemetry string template
telemetry_string = (" {:d}/{:d} - elapsed: {:.1f}m - remaining: " +
                    "{:.1f}m - set/read: {:.1f}s/{:.1f}s")


def get_package_path(package_name):
    """
    Determine the path of a Python package.

    Parameters
    ----------
    package_name : str
        Name of the package.

    Returns
    -------
    str or None
        Path to the package if found, None otherwise.
    """
    spec = importlib.util.find_spec(package_name)
    if spec and spec.origin:
        return os.path.dirname(spec.origin)
    return None


def get_importable_module_name(filename):
    """
    Get importable module name if filename point to an installed module.

    If the filename does not correspond to an installed Python (sub)module
    this method returns False.

    Parameters
    ----------
    filename : str
        Path to the file.

    Returns
    -------
    str or bool
        Module name if importable, False otherwise.
    """
    # Normalize the path
    filename = abspath(filename)

    # Check if the file exists and is a Python file or
    # a directory with __init__.py
    if filename.endswith('.py') and isfile(filename):
        module_path = filename[:-3]  # Remove the .py extension
    elif isdir(filename) and isfile(join(filename, '__init__.py')):
        module_path = filename
    else:
        return False

    # Find the most specific base path in sys.path that matches
    # the start of the module_path
    best_match = None
    best_len = 0

    for base_path in sys.path:
        base_path = abspath(base_path)
        if module_path.startswith(base_path) and len(base_path) > best_len:
            best_match = base_path
            best_len = len(base_path)

    if best_match:
        # Remove the base_path from the module_path and convert to module name
        relative_path = relpath(module_path, best_match)
        module_name = relative_path.replace(os.sep, ".")

        # Check if the module is installed
        try:
            spec = importlib.util.find_spec(module_name)
            if spec is not None:
                return module_name
            return False
        except ImportError:
            return False
    else:
        return False


def create_temp_dir_with_symlinks(names, targets):
    """
    Create temporary directory with symlinks.

    This function works similarly on all major platforms,
    but uses different ways to achieve this.

    Parameters
    ----------
    names : list
        Names of the symlinks.
    targets : list
        Target folders for the links.

    Returns
    -------
    TemporaryDirectory
        Temporary directory instance.
    """
    # Create a temporary directory
    temp_dir = tempfile.TemporaryDirectory(prefix="systemdir-links-")

    # Create symbolic links in the temporary directory
    for name, target in zip(names, targets):
        if not os.path.isdir(target):
            raise ValueError(f"The target {target} is not a directory.")
        link_name = os.path.join(temp_dir.name, name)
        if os.name == 'nt':
            subprocess.check_call(
                ['cmd', '/c', 'mklink', '/J', link_name, target],
                stdout=subprocess.DEVNULL,
            )
        else:
            os.symlink(target, link_name)

    # Return the temporary directory object
    return temp_dir


def get_matrix_binary():
    """
    Find matrix binary from PATH and otherwise try known Python binary folders.

    This executes "matrix --help" to test if this works without error. If no
    executable is found an FileNotFoundError will be raised.

    Returns
    -------
    str
        Name of the matrix binary.

    Raises
    ------
    FileNotFoundError
        If matrix executable could not be found.
    """
    user_scripts_path = sysconfig.get_path('scripts', f'{os.name}_user')
    system_scripts_path = sysconfig.get_path('scripts')
    for matrixname in ("matrix",
                       os.path.join(user_scripts_path, "matrix"),
                       os.path.join(system_scripts_path, "matrix")):
        try:
            subprocess.check_call([matrixname, "--help"],
                                  stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL)
            return matrixname
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    raise FileNotFoundError("matrix executable could not be found")


def module_from_path(filename):
    """
    Create a module from a file path.

    Parameters
    ----------
    filename : str
        Path to the file.

    Returns
    -------
    module
        Imported module.
    """
    # module path was defined, check that file exists
    if not isabs(filename):
        # get absolute path
        filename = abspath(filename)
    # create module specification from file and open
    spec = importlib.util.spec_from_file_location("dummyname",
                                                  filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def print_formatted_line(vlist, prefix="", appendix="", column_width=10):
    """
    Output a formatted line with data values.

    Parameters
    ----------
    vlist : list
        List of values to format.
    prefix : str, optional
        Prefix for the line. Default is "".
    appendix : str, optional
        Appendix for the line. Default is "".
    column_width : int, optional
        Width of each column. Default is 10.
    """
    entry_string = "{:>%d}  " % column_width
    outstr = f"{prefix:>6}"
    for v in vlist:
        if isinstance(v, str) and len(v) > column_width:
            vstr = v[-column_width:]
        elif isinstance(v, str):
            vstr = v
        elif v is None:
            vstr = ""
        elif isinstance(v, float):
            vstr = f"{v:8.6g}"
        elif isinstance(v, int):
            vstr = f"{v:d}"
        else:
            # unknown datatype, continue without error
            vstr = "???"
        outstr += entry_string.format(vstr)
    outstr += f"{appendix}"
    print(outstr)


def generate_script_prefix_suffix(systems):
    """
    Define the prefix and suffix of the script used in matrix_script.

    Parameters
    ----------
    systems : list
        List of system (file)names that define the system to be used.

    Returns
    -------
    tuple
        A tuple containing two strings:
        - prefix : str
            Prefix of a script that can be directly executed and allows use of
            the custom matrix_script syntax. Ends with try statement, so use
            script has to be indented by 4 spaces.
        - suffix : str
            Corresponding suffix of the script, finishes the try statement.
    """
    prefix = textwrap.dedent(
        f"""
    import builtins as _builtins
    import datetime as _datetime
    import inspect as _inspect
    import math as _math
    import os as _os
    import sys as _sys
    import textwrap as _textwrap
    import time as _time
    import types as _types

    import wrapt

    import matr1x as _matr1x
    import matr1x.util as _matrix_util

    from matr1x.system import MergedSystem as _MergedSystem

    # load config section from toml file
    _config = _matr1x.get_config_dict("matr1x.scripts.matrix-script")

    _system = _MergedSystem.from_files([{", ".join(repr(s) for s in systems)}])

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
    _reset_kwargs = {{}}


    def _configure_execution_path(scriptname):
        '''Change execution path if requested in config.'''
        if _config["script_path"] == "<script-location>":
            if _os.path.dirname(scriptname):
                _os.chdir(_os.path.dirname(scriptname))
        elif _os.path.exists(_config["script_path"]):
            _os.chdir(_config["script_path"])


    def _configure_script_storing(system, script):
        '''Store user script if requested in config.'''
        if _config["store_script_in_datafile"]:
            prefix, suffix = _matrix_util.generate_script_prefix_suffix("")
            npref, nsuff = len(prefix.splitlines()), len(suffix.splitlines())
            # strip prefix and suffix lines from script for storing
            user_script = _textwrap.dedent("\\n".join(script.splitlines()[npref:-nsuff]))
            if "user script" not in system.system_config_params:
                system.system_config_params["user script"] = user_script
            else:
                print("'user script' key already present in system, not overwriting!")


    def _find_caller_frame():
        '''Find the frame of the actual caller, skipping over decorator frames.'''
        # stepping back on frame, since the inner most frame is from this function
        frame = _inspect.currentframe().f_back
        # Try to find the first __call__ frame, as in Python 3.13+
        while frame:
            if frame.f_code.co_name == "__call__":
                return frame.f_back  # Return the frame just outside __call__
            frame = frame.f_back

        # Fallback for Python 3.12 or earlier: step back a fixed number of frames
        frame = _inspect.currentframe()
        steps_back = 3 if _sys.version_info >= (3, 13) else 2
        for _ in range(steps_back):
            frame = frame.f_back if frame else None

        return frame  # Returns the frame that we believe to be the caller


    @wrapt.decorator
    def _lineno_decorator(wrapped, instance, args, kwargs):
        '''Decorator to report the executing line number back to the GUI.'''
        frame = _find_caller_frame()
        if frame:
            caller_name = frame.f_code.co_name
            caller_filename = frame.f_code.co_filename
            if caller_name == "<module>" and caller_filename == "<string>":
                # report line only if called directly from script
                _report_line(frame.f_lineno)
        return wrapped(*args, **kwargs)


    @wrapt.decorator
    def _breakpoint(wrapped, instance, args, kwargs):
        '''Decorator to add a breakpoint check.'''
        # avoid recursive loop (a decorated function calling another)
        # If the wrapped object is a method, attach _calling to the instance
        if instance is not None:
            if not hasattr(instance, '_calling'):
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
            if not hasattr(wrapped, '_calling'):
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
        '''Inject decorator into instance methods.'''
        for attr_name in dir(instance):
            if attr_name in ['add_comment', '_print']:
                # exclude this methods from decoration since they are
                # potentially called from inside the decorator. anything called
                # inside the _interrupt function should be added here/not
                # decorated.
                continue
            attr = getattr(instance, attr_name)
            if isinstance(attr, _types.MethodType):
                decorated_attr = decorator(attr)
                setattr(instance, attr_name, decorated_attr)


    def _reset_setvalues():
        '''Reset the setvalues variable.'''
        global _setvalues
        _setvalues = []
        for i, col in enumerate(_system.columns):
            if isinstance(col, (list, tuple)):
                _setvalues.append([None, ]*len(col))
            else:
                _setvalues.append(None)

    # inject line number decorator to time.sleep
    _time.sleep = _lineno_decorator(_time.sleep)
    # inject breakpoint and line number decorators to system methods
    _inject_decorator(_system, _breakpoint)
    for subsys in _system.subsys:
        _inject_decorator(subsys, _breakpoint)
        _inject_decorator(subsys, _lineno_decorator)
    _reset_setvalues()  # initialize the setvalues variable
    # bring meta_data and system into namespace
    meta_data = _system.dcdata
    system = _system

    # redefine set_value to limit user typing requirements
    @_lineno_decorator
    def set_value(col, value):
        '''
        Wrapper for _system.set_values to allow storing all set parameters
        between two measurements.

        Parameters
        ----------
        col : str or int
            Column name or index.
        value : Any
            Value to set.

        Returns
        -------
        Any
            Set value.
        '''
        global _setvalues

        if col in _system.columns:
            i = _system.columns.index(col)
        else:
            i = col

        setv = _system.set_value(i, value)
        if setv is None and isinstance(_system.columns[i], (list, tuple)):
            _setvalues[i] = [None, ] * len(_system.columns[i])
        else:
            _setvalues[i] = setv
        return setv


    @_lineno_decorator
    def trigger_value(*args, **kwargs):
        '''
        Execute system.trigger_value. All arguments are forwarded.

        Parameters
        ----------
        *args : tuple
            Positional arguments.
        **kwargs : dict
            Keyword arguments.

        Returns
        -------
        Any
            Result of system.trigger_value.
        '''
        _system.trigger_value(*args, **kwargs)


    @_lineno_decorator
    def read_value(*args, **kwargs):
        '''
        Execute system.read_value. All arguments are forwarded.

        Parameters
        ----------
        *args : tuple
            Positional arguments.
        **kwargs : dict
            Keyword arguments.

        Returns
        -------
        Any
            Result of system.read_value.
        '''
        return _system.read_value(*args, **kwargs)


    @_lineno_decorator
    def wait(duration=None, until=None, message="", silent=10):
        '''
        Pauses execution for a specified duration, until a specified timestamp, or for a relative time.

        Parameters
        ----------
        duration : float or int, optional
            The number of seconds to sleep. If specified, the function will sleep for this duration.
            If paused during this duration the remaining wait time continue after unpausing.
            If a str or datetime object is used here it will be redirected to the until argument.
        until : str or datetime, optional
            A target time or relative time string. It can be:
            - An absolute timestamp in a format like "YYYY-MM-DD HH:MM:SS" or "HH:MM".
            - A relative time string starting with '+' followed by a number and a unit
                (e.g., "+24h" for 24 hours, "+30m" for 30 minutes, "+1d" for 1 day).
            - A `datetime` object representing a specific time.
        message : str, optional
            A string which is printed if the sleep exceeds the silent argument.
        silent : float, optional
            If the wait time exceeds this value a message string will be printed.

        Examples
        --------
        >>> wait(duration=10)
        Pauses execution for 10 seconds.

        >>> wait(until="2025-11-05 15:30")
        Pauses execution until 15:30 on November 5, 2025.

        >>> wait(until="+2h")
        Pauses execution for 2 hours from the current time.

        >>> wait(until="18:00")
        Pauses execution until 18:00 today, or until the same time tomorrow if it has already passed today.
        '''
        if isinstance(duration, (str, _datetime.datetime)) and not until:
            until = duration
            duration = None
        if duration and until:
            print("until (%s) argument of the wait function will be ignored" % until)
            until = None
        _interrupt(duration=duration, until=until, message=message, silent=silent, system=_system)


    @_lineno_decorator
    def input(query: str):
        '''
        Ask user to provide some free text input.

        Parameters
        ----------
        query : str
            Query string presented to the user so they know what to enter.

        Returns
        -------
        str
            User input.
        '''
        return _input(query, system=_system)


    @_lineno_decorator
    def input_bool(query: str):
        '''
        Ask user to answer a yes/no question.

        Parameters
        ----------
        query : str
            Question to ask the user.

        Returns
        -------
        bool
            True if the user answers yes, False otherwise.
        '''
        ret = _input(query, system=_system, input_type='bool')
        if ret == "yes":
            return True
        return False


    @_lineno_decorator
    def end_script(finished: bool = None):
        '''
        End the script execution and define the file status as finished or
        unfinished if not None.

        Parameters
        ----------
        finished : bool, optional
            If True, mark the script as finished. If False, mark as unfinished.
            If None, don't change the status.
        '''
        global _status
        _status.finished = finished
        raise KeyboardInterrupt


    @_lineno_decorator
    def print(*args, **kwargs):
        '''Use system._print to optionally forward the printed message to the datafile.

        The behavior of this function depends on the config option
        matr1x.scripts.matrix-script.print_to_comment
        '''
        _system._print(*args, **kwargs)


    # load execution path of scripts and change to this directory
    _configure_execution_path(_scriptname)
    # optionally set user script to be stored in data file
    _configure_script_storing(_system, _script)
    # initialize system and put devs into namespace
    print("setting devices")
    # system.set is called before the filename is set so we have no arguments
    # here -> this is a difference to matrix
    _system.set()
    devs = _system.devs

    # switch meta data to append state
    _system.dcdata.append = True


    @_lineno_decorator
    @_breakpoint
    def init_datafile(filename, comment=None, append=False, print_header=True,
                      ntot=None):
        '''
        Initialize the datafile for the matrix_script measurement.

        By default a new datafile will be generated whose name is generated in a
        way that no existing datafile can be overwritten.

        Parameters
        ----------
        filename : str
            Name of the datafile to be used.
        comment : str, optional
            Comment to be saved in the file header.
        append : bool, optional
            Flag to tell if an existing datafile should be used. If append is
            False a new datafile with a non-conflicting name will be generated by
            appending "_<number>" to the filename.
        print_header : bool, optional
            Flag to decide if the header information with column names and units
            should be printed.
        ntot : int, optional
            Total number of expected datapoints for estimation of remaining
            measurement time.
        '''
        global _ntot, _npoints, _starttime

        _ntot = ntot
        _npoints = 0  # reset the number of measurement points
        _starttime = _time.time()

        filename = _system.generate_datafilename(
            outputfile=filename,
            inputfile=_scriptname,
            append=append)
        if append == False or not _os.path.exists(filename):
            # write header to file
            _system.dcdata["description"] = comment
            _system.init_datafile(_scriptname or "matrix script generated")
            print("acquired configuration, and initialized file")
        if print_header:
            _matrix_util.print_formatted_line(
                _matrix_util.flatten(_system.columns))
            _matrix_util.print_formatted_line(
                _matrix_util.flatten(_system.units))
        # report file to matrix_script
        _report_path(filename)


    # wrap system.trigger and system.take_measurement_point into measure_system
    @_lineno_decorator
    @_breakpoint
    def measure_system(print_setpoint=True, print_data=True, print_telemetry=True):
        '''
        Perform the measurement of a single data point.

        This means a sequence of system.trigger, and reading the data is performed.

        Parameters
        ----------
        print_setpoint : bool, optional
            Flag to decide if the column values set since the last measurement
            should be printed in a way compatible with the header information of
            init_datafile.
        print_data : bool, optional
            Flag to decide if the measured data values should be printed in a way
            compatible with the header information of init_datafile.
        print_telemetry : bool, optional
            Flag to decide if telemetry data about the measurement duration should
            be printed.

        Returns
        -------
        list
            List of measured values.
        '''
        global _preset, _npoints
        _npoints += 1
        preread = _time.time()
        if not _system.filename:
            init_datafile("")

        if print_setpoint:
            _matrix_util.print_formatted_line(
                _matrix_util.flatten(_setvalues), prefix="Set : ")
        _reset_setvalues()

        _system.trigger()
        return_list = _system.take_measurement_point()
        if print_data:
            _matrix_util.print_formatted_line(
                return_list, prefix="Meas: ")
        if print_telemetry:
            elapsed = (_time.time() - _starttime)
            if _ntot:
                remaining = (elapsed/_npoints*_ntot-elapsed)/60
            else:
                remaining = _math.nan
            # use builtins.print here to make sure the telemetry do not get added to the datafile
            _builtins.print(_matrix_util.telemetry_string.format(
                _npoints, _ntot or -1, elapsed/60, remaining, preread-_preset,
                _time.time()-preread))
        if print_data or print_telemetry or print_setpoint:
            # isolate different iterations of measure system by a space
            _builtins.print("")
        _preset = _time.time()
        return return_list


    # merge user input into script
    # ==== begin user area ====
    try:
    """
    )
    suffix = textwrap.dedent(
        """
    except KeyboardInterrupt:
        print("\\nscript has been aborted by user.")
        # mark script as aborted per default once abort is called
        if _status.finished:
            _reset_kwargs["status"] = "finished"
        elif _status.finished is False:
            # supposed to be marked as aborted
            _reset_kwargs["status"] = "aborted"
        else:
            # finished is None, so ask what is supposed to happen
            _reset_kwargs["status"] = _input("", system=_system, input_type="__end_script__")

    # ===== end user area =====
    # mark last open file as finished, if not labeled elsewhere
    if not "status" in _reset_kwargs.keys():
        _reset_kwargs["status"] = "finished"
    # the reset function is called at the script end only, but we nevertheless
    # specify the last datafile name to be as close as possible to the behavior
    # of matrix
    _system.reset(**_reset_kwargs)
    """
    )
    return prefix, suffix


def generate_script(systems, user_script):
    """
    Define the general part of the script used in matrix_script.

    Parameters
    ----------
    systems : list
        List of system (file)names that define the system to be used.
    user_script : str
        Custom user script that is typically provided by matrix_script, which is
        supposed to be executed.

    Returns
    -------
    str
        Script that can be directly executed and allows use of the custom
        matrix_script syntax. Returned script must be run in the context of the
        matrix_script_process.
    """
    # define basic part of script, imports relevant commands
    prefix, suffix = generate_script_prefix_suffix(systems)
    if user_script.strip() == "":
        # if empty script is passed, avoid indendation error and make script
        # execution possible
        user_script = "pass"
    return prefix + textwrap.indent(user_script, "    ") + suffix


def matrix_script_process(filename, meta_data={}, scriptname=""):
    """
    Process in which the script generated by generate_script is executed.

    Provides functionality to pause and gracefully quit the script execution
    at a breakpoint.

    A temporary file is used to avoid difficulties with passing the full script
    as terminal argument.

    Parameters
    ----------
    filename : str
        Filename to the (temporary) file containing the script to be executed.
        Script in file should have been generated by generate_script.
    meta_data : dict, optional
        Meta data such as, e.g., user name, description.
    scriptname : str, optional
        Script name used as fallback template for the datafile name if it's not
        set in the script and the directory of this file is used as a base
        directory for executing the script. This means Python files inside this
        directory can be imported by the user-script.

    Returns
    -------
    None
    """
    # import required dependencies
    import socket
    import threading
    import traceback

    # only import port here to avoid util import from failing if GUI
    # applications are not installed
    from .scripts import MATRIX_SCRIPT_PORT

    # define killable thread to execute the script
    class ExecThread(threading.Thread):
        """
        Thread that handles the execution of the measurement script.

        Attributes
        ----------
        script : str
            Measurement script generated by generate_script.
        meta_data : dict
            Meta data.
        scriptname : str
            Name of the script.
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
        n_pref : int
            Number of prefix lines.
        socket : socket.socket or None
            Socket for communication.
        """

        class Unbuffered:
            r"""
            Implements a wrapper on stdout to make sure data is passed on immediately.

            This wrapper terminates messages with \0 to allow using \n and \r in print
            conventionally without breaking the formatting.
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

            def __init__(self, value=None):
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
            def finished(self, value):
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

        def __init__(self, script, meta_data, scriptname, socket):
            """Initialize all variables."""
            super().__init__()
            self.script = script
            self.meta_data = meta_data
            self.scriptname = scriptname
            self.stop_status = self.Status()
            self.pause_flag = False
            self.interrupt_flag = False
            self.recv_flag = False
            self.recv = ""
            self.n_pref = 0
            self.socket = socket
            if self.socket is not None:
                # pass on all stdout to socket
                file = socket.makefile("w", buffering=None)
                sys.stdout = self.Unbuffered(file)

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

        def interrupt(
            self, duration=None, until=None, message="", silent=10, system=None
        ):
            """
            Pauses execution for a specified duration, until a specified timestamp, or for a relative time.

            Parameters
            ----------
            duration : float or int, optional
                The number of seconds to sleep. If specified, the function will sleep for this duration.

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
                If neither `duration` nor `until` is provided, or if the `until` format is not recognized.

            TypeError
                If `until` is not a string or `datetime` object.
            """
            now = datetime.datetime.now()
            end_time = None
            sleep_time = None
            msg = "" if not message else f" ({message})"
            print_func = system._print if system else print

            if duration is not None:
                sleep_time = duration
                end_time = now + datetime.timedelta(seconds=sleep_time)
                if sleep_time > silent or msg:
                    print_func(
                        f"Waiting {sleep_time:.0f} seconds{msg} until {end_time.strftime('%H:%M:%S')}"
                    )

            elif until is not None:
                if isinstance(until, str) and until.startswith("+"):
                    # Parse relative time
                    match = re.match(r"\+(\d+\.?\d*)([smhd])", until)
                    if match:
                        value, unit = float(match.group(1)), match.group(2)
                        if unit == "s":
                            end_time = now + datetime.timedelta(seconds=value)
                        elif unit == "m":
                            end_time = now + datetime.timedelta(minutes=value)
                        elif unit == "h":
                            end_time = now + datetime.timedelta(hours=value)
                        elif unit == "d":
                            end_time = now + datetime.timedelta(days=value)
                    else:
                        raise ValueError("Invalid relative time format.")

                elif isinstance(until, datetime.datetime):
                    end_time = until
                else:
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
                        "%d.%m.%Y %H:%M",
                    ]

                    for fmt in formats:
                        try:
                            parsed_time = datetime.datetime.strptime(until, fmt)
                            if fmt in ["%H:%M:%S", "%H:%M"]:
                                parsed_time = parsed_time.replace(
                                    year=now.year, month=now.month, day=now.day
                                )
                                if parsed_time < now:
                                    parsed_time += datetime.timedelta(days=1)
                            end_time = parsed_time
                            break
                        except ValueError:
                            continue
                    if not end_time:
                        raise ValueError("Timestamp format not recognized.")

                if end_time < now:
                    print_func(
                        f"Specified wait until time {end_time.strftime('%Y-%m-%d %H:%M:%S')} is in the past. "
                        "Continuing immediately."
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
                        f"Waiting until {end_time.strftime('%Y-%m-%d %H:%M:%S')} (in {sleeptstr} seconds){msg}"
                    )

            else:
                raise ValueError("Either `duration` or `until` must be provided.")

            # Perform the wait with pause handling
            self._execute_sleep(
                sleep_time, end_time, duration is not None, silent, msg, system
            )
            # Ensure interrupt and pause checks are called at least once, even if `sleep_time` is 0
            self.check_for_interrupt_and_pause(system)

        def _execute_sleep(
            self, sleep_time, end_time, is_duration, silent, message, system
        ):
            """Handle sleeping with interrupt and pause checks.

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
            pause_duration = (
                0  # Tracks cumulative pause duration for duration-based waits
            )
            initial_sleep_time = sleep_time  # Save the initial sleep time for reference
            print_func = system._print if system else print

            while sleep_time > 0:
                # Calculate remaining time based on the end time for "until" waits
                if not is_duration and end_time:
                    sleep_time = (end_time - datetime.datetime.now()).total_seconds()

                # Check for interruption or pause
                pause_start = time.time()  # Record when the pause starts
                if self.check_for_interrupt_and_pause(system):
                    if (
                        not is_duration
                        and end_time
                        and datetime.datetime.now() >= end_time
                    ):
                        print_func(
                            "\nThe target time passed during pause. Continuing immediately."
                        )
                        return
                    elif is_duration:
                        # Calculate pause duration and extend end_time accordingly
                        pause_end = time.time()
                        pause_duration += pause_end - pause_start
                        end_time = datetime.datetime.now() + datetime.timedelta(
                            seconds=(
                                initial_sleep_time
                                - (time.time() - start_time - pause_duration)
                            )
                        )

                        # Recalculate sleep_time after adjusting for pause
                        sleep_time = (
                            end_time - datetime.datetime.now()
                        ).total_seconds()
                        print_func(
                            f"\nResuming wait for {sleep_time:.0f} seconds{message}."
                        )
                    else:
                        # For "until" wait, recalculate based on the current end_time
                        sleep_time = max(
                            0, (end_time - datetime.datetime.now()).total_seconds()
                        )
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
            """Check for interrupt and pause flags and take appropriate action.

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

        def input(self, message="", system=None, input_type="string"):
            """Handle user input requests from the script.

            This method manages the input request workflow, including displaying prompts,
            waiting for user response, and handling timeouts and interrupts.

            Parameters
            ----------
            message : str, optional
                Message to display to user requesting input. Default is empty string.
            system : object, optional
                System object that can be interrupted/paused. Default is None.
            input_type : str, optional
                Type of input expected. Default is "string".

            Returns
            -------
            str
                The user's input response with whitespace stripped.
            """
            t0 = time.time()
            if self.recv != "" and not self.recv_flag:
                self.recv = ""
            if "" == message:
                print(
                    f"__input_{input_type}:User input requested, see executing line for context.__"
                )
            else:
                print(f"__input_{input_type}:{message}__")
            while (self.recv == "" or self.recv_flag is True):
                time.sleep(0.1)
                if (time.time() - t0) > 60:
                    print("still waiting for user input")
                    t0 = time.time()
                self.check_for_interrupt_and_pause(system)
            # remove trailling line feed
            ret = self.recv.strip()
            # print output
            print(f"User input received: {ret}")
            self.recv = ""
            return ret

        # callback function that handles the input
        def handle_input(self, inp):
            """Handle input that is passed to the thread.

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
            lineno -= self.n_pref + 1
            if lineno > -1:
                print(f"__lineno{lineno:d}__", end="")

        def report_path(self, path):
            """
            Report datafile that is currently written by matrix-script.

            The format is __//{path to measurement file}//__

            Parameters
            ----------
            path : str
                Path to the measurement file.
            """
            if self.socket is None:
                # only report filename if connected to a socket
                return
            if path != "":
                print(f"__//{path}//__", end="")

        def run(self):
            """Run the script and provide meaningful error information.

            This method executes the script and handles any errors that occur
            during execution, providing detailed error information.
            """
            try:
                self.n_pref = len(
                    generate_script_prefix_suffix("")[0].splitlines())
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
                    }
                    exec(self.script, _vars)
                except Exception:
                    print("script exited with error:")
                    # get traceback information and format accordingly
                    tbinfo = traceback.format_exception(*sys.exc_info())
                    tbstr = "".join(tbinfo[2:])
                    # get line information from traceback
                    ms = re.search(r"line (\d+)", tbstr)
                    line = int(ms.group(1))
                    # replace line number to match the user defined script
                    # to that end, determine number of lines in prefix
                    tbstr = re.sub(r"line (\d+)",
                                   "line " + str(int(ms.group(1))-self.n_pref),
                                   tbstr)
                    tbstr = tbstr.replace("<module>", "script")
                    tbstr = tbstr.replace("File \"<string>\"",
                                          "\"{}\"".format(
                                              self.script.splitlines()[line-1]))
                    print(tbstr)
                    if line < 1:
                        print(" error during device initialization\n")
            except KeyboardInterrupt:
                print("script interrupted by user")

    # this might be required on windows, needs testing
    if os.name == 'nt':
        def temp_opener(name, flag, mode=0o777):
            return os.open(name, flag | os.O_TEMPORARY,  mode)
    else:
        temp_opener = None

    # reads the script from the temporary file
    script = ""
    with open(filename, "rb", opener=temp_opener) as file:
        for line in file:
            script += line.decode()

    # initialize communication to matrix script
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect(("127.0.0.1", MATRIX_SCRIPT_PORT))
        # make socket non-blocking
        client_socket.settimeout(0.05)
        # timeout should be chosen so that the server socket can receive the
        # full message within the timeout
        # Since currently the server socket delays the receiving by 5 ms every
        # 250 1024 byte segments, once more then 10 of such segments are
        # expected, the timeout will occur (not accounting for the internal
        # delays of the socket operations). Consequently, we impose a maximum
        # message length of < 2.5 MByte here, which I assume is a large print
        # statement and should be completely irrelevant.
        connected = True
    except ConnectionRefusedError:
        # GUI not running - script was not run from graphical user interface.
        connected = False

    # initialize the thread
    if connected is True:
        thread = ExecThread(script, meta_data, scriptname, client_socket)
    else:
        thread = ExecThread(script, meta_data, scriptname, None)

    # start the thread that runs the script
    thread.start()

    # wait until the thread is finished while waiting for input on
    # client_socket in the case it is connected
    while thread.is_alive():
        if connected is True:
            try:
                datachunk = client_socket.recv(1)
                if len(datachunk) > 0:
                    try:
                        thread.handle_input(datachunk.decode("utf-8"))
                    except UnicodeDecodeError:
                        # unicode symbol that consists of two symbols was
                        # likely found, try to recv one more symbol
                        datachunk += client_socket.recv(1)
                        try:
                            thread.handle_input(datachunk.decode("utf-8"))
                        except UnicodeDecodeError:
                            # not the relevant error -> something went wrong
                            pass
            except OSError:  # for Python >= 3.10 this can be TimeoutError
                # recv timed out, no data was sent
                pass
        # this sleep prevents a deadlock scenario which otherwise heavily slows
        # down matrix_script execution
        time.sleep(0.001)
        # this sleep SIGNIFICANTLY slows down matr1x interthread communication
        # can this be made shorter? -> changed to 0.001

    if connected is True:
        # wait for all data from socket to be received by the other side
        # necessary to make sure all output is actually sent to other side
        # before socket is closed.
        client_socket.shutdown(socket.SHUT_WR)
        # close socket
        client_socket.close()


def flush_input():
    """Flush the input buffer to get only fresh input later on."""
    if os.name == "nt":
        while msvcrt.kbhit():
            msvcrt.getch()
    else:
        try:
            termios.tcflush(sys.stdin, termios.TCIOFLUSH)
        except termios.error:
            pass  # errors in none proper terminal, e.q.  Github actions


def nonblocking_getch(callback=None):
    """
    Cross-platform nonblocking implementation of getch.

    In a linux terminal, enter has been pressed to trigger the getch, as
    otherwise the stdin is not flushed.

    Parameters
    ----------
    callback : function handle (optional)
        should be a function that takes the character and performs some
        action with it

    Returns
    -------
    c : str
      Key that has been pressed, only if callback is None
    """
    if os.name == "nt":
        if msvcrt.kbhit():
            # key has been pressed
            c = msvcrt.getch().decode("utf-8")
            if callback is None:
                return c
            else:
                callback(c)
    else:
        if select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
            # note that enter has to be pressed in the linux terminal, as
            # otherwise stdin is not flushed
            c = sys.stdin.read(1)
            if callback is None:
                return c
            else:
                callback(c)


# sweep functions
def calculate_sweep(sweepParms, loopOver, upDown, repeat):
    """
    Generate a list of sweeps defined by given parameters.

    Parameters
    ----------
    sweepParms : list
        List of lists containing the sweep parameters (as 3 item list).
    loopOver : list
        List of integers (<len(loopOver)) defining the looping scheme.
    upDown : list
        List of bools defining if the sweep is going both ways.
    repeat : list
        List of integers defining how often the sweep ranges are repeated.

    Returns
    -------
    list
        List of sweeps that contains all parameters that are to be set. Individual
        sweeps from columns still need to be stretched to equal length (sparse).
        Otherwise, loop over is not handled properly.

    Examples
    --------
    The example was generate dusing np.set_printoptions(legacy='1.25')
    >>> sweepParms = [[[1, 2, 2], [3, 4, 2]], [], [[-1, 1, 2]]]
    >>> loopOver = [-1, -1, 0]
    >>> upDown = [True, False, False]
    >>> repeat = [1, 1, 1]
    >>> calculate_sweep(sweepParms, loopOver, upDown, repeat)
    [[1.0, 2.0, 3.0, 4.0, 4.0, 3.0, 2.0, 1.0], [],
     [-1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0,
      -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0]]
    """
    lenA = len(sweepParms)
    if len(loopOver) != lenA or len(upDown) != lenA or len(repeat) != lenA:
        return None  # Sanity 1
    sweeps = []
    for indexS, parmSets in zip(range(lenA), sweepParms):
        i = 0
        sweeps.append([])
        while i < repeat[indexS]:
            tempSweep = []
            for parm in parmSets:
                # generate the sweepRange using np.linspace, has to be list
                # so += works

                sweepRange = np.linspace(float(parm[0]), float(parm[1]), int(parm[2]))
                if any(np.isnan(sweepRange)) or any(np.isinf(sweepRange)):
                    return "Inf or Nan in sweep, check parameters"
                tempSweep += list(sweepRange)
            if upDown[indexS]:
                # if up down is true, add the reversed sweep to the sweep
                tempSweep += list(reversed(tempSweep))
            sweeps[indexS] += tempSweep
            i += 1
    # check if there are loops of loops and detect hirarchy so we
    # can properly generate the sweep
    hirarchy = []
    for i in range(lenA):
        hirarchy.append(check_dep(i, loopOver))
    if -1 in hirarchy:
        # Recursive loop, you should really not do that!
        # (i.e. don't loop col(a) over col(b) over col(a)!)
        return "Recursive loop, please check loop over"
    hCnt = max(hirarchy)
    while (0 <= hCnt):
        for indexS in range(lenA):
            if indexS == loopOver[indexS]:
                # looping a column over itself is not how it's done!
                loopOver[indexS] = -1
            elif -1 != loopOver[indexS] and hCnt == hirarchy[indexS]:
                # start with highest hirarchy first (i.e. column which is
                # the most fundamental)
                col = loopOver[indexS]
                tempSweep = sweeps[indexS].copy()
                # copy the initial sweep to be looped
                for j in range(len(sweeps[col])-1):
                    # for each element in the looped over column append the
                    # initial sweep
                    sweeps[indexS] += tempSweep
                loopOver[indexS] = -1
        hCnt -= 1
    # Stretch sweep version 1
    return sweeps


def check_dep(index, array, depth=0):
    """
    Recursive function to determine the hierarchical depth of an item in an array.

    This function checks how deeply nested an item is within a given array structure.
    It recursively follows references until it reaches the deepest level or detects
    a circular reference.

    Parameters
    ----------
    index : int
        Index of the item in array for which the hierarchy is to be determined.
    array : list
        The array defining the hierarchy.
    depth : int, optional
        Recursion depth, does not need to be set when calling the function.

    Returns
    -------
    int
        Hierarchy of the item index within the given array.

    Examples
    --------
    >>> check_dep(0, [-1, -1, 1, 2])
    0
    >>> check_dep(1, [-1, -1, 1, 2])
    2
    >>> check_dep(2, [-1, -1, 1, 2])
    1
    >>> check_dep(3, [-1, -1, 1, 2])
    0
    """
    if depth > 50:
        # break the recursion, something went wrong
        return -1
    if index in array:
        cnt = len([i for i, x in enumerate(array) if x == index])
        # adds the position of the occurences of the index to a list
        if cnt > 1:
            # multiple occurences of index in array
            d = []
            occ = -1
            for _ in range(cnt):
                # follow all branches of the occurences to get the actual
                # maximum hirarchy of the occurence
                occ = array.index(index, occ+1)
                d.append(check_dep(occ, array, depth+1))
            return max(d)
        return check_dep(array.index(index), array, depth+1)
    # if no more occurence is in the array, then return the current depth
    return depth


def generate_col_index(index):
    """
    Generate column indices for matrix/sweep generator.

    Generate column indices using the format "a" -> "z" -> "aa" -> "az" -> "ba" -> etc.
    Currently can handle 701 columns and is easily extendable.

    Parameters
    ----------
    index : int
        The index for which to generate the column label.

    Returns
    -------
    str
        The generated column label.

    Raises
    ------
    ValueError
        If the index is out of range (>701).
    """
    if index < 26:
        letter = chr(index+97)
    elif index < 702:
        letter = chr(index//26+96) + chr(index % 26+97)
    else:
        raise ValueError("index out of range, talk to the developer")
    return letter


def construct_query_string(query_dict, depth=2):
    """
    Prepare query string from output of system.query to include in file header.

    Format is specified as:
    ## dev1
    ### key1 : value1
    ### key2 : value2
    ## dev2 ... and so on

    Parameters
    ----------
    query_dict : dict
        Dictionary containing the query results.
    depth : int, optional
        Current depth in the nested dictionary structure, by default 2.

    Returns
    -------
    str
        Formatted query string.
    """
    ret = ""
    for k, v in query_dict.items():
        if isinstance(v, dict):
            ret += "#"*depth + f" {k}\n"
            ret += construct_query_string(v, depth+1)
        else:
            if isinstance(v, str):
                # ignore carriage returns (would break the datafile!)
                v = v.replace("\r", "\n")
                v = v.replace("\n", "\n" + "#" * (depth + 1) + " ")
                v = v.replace('"', r"\"")
                ret += "#" * depth + f' {k} : "{v}"\n'
            else:
                ret += "#" * depth + f" {k} : {v}\n"
    return ret


def save_dict_to_hdf5(data_dict: dict, hdf5_file: h5py.File, root_group: str) -> None:
    """
    Save a dictionary to an HDF5 file in a hierachical data group.

    Parameters
    ----------
    data_dict : dict
        The dictionary to be saved.
    hdf5_file : h5py.File
        File handle of the HDF5 file to save the data to.
    root_group : str
        The name of the root group in the HDF5 file.

    Notes
    -----
    This function recursively writes nested dictionaries to HDF5 groups and
    datasets. Lists are converted to datasets, and scalar values are saved as
    attributes.
    """

    def write_dict(group: h5py.Group, d: dict) -> None:
        """Recursively write a dictionary to an HDF5 group."""
        for key, value in d.items():
            if isinstance(value, dict):
                # Create a subgroup for nested dictionaries
                subgroup = group.create_group(key)
                write_dict(subgroup, value)
            elif isinstance(value, list):
                # Convert lists to datasets
                group.create_dataset(key, data=value)
            else:
                # Save scalar values
                group.attrs[key] = value

    # Create or get the specified root group
    if root_group in hdf5_file:
        group = hdf5_file[root_group]
    else:
        group = hdf5_file.create_group(root_group)

    write_dict(group, data_dict)


def init_ascii_header(file_handle, columns, units, separator):
    """
    Initialize the header of the measurement file using the given telemetry.

    Parameters
    ----------
    file_handle : file
        File that the header should be written to.
    columns : list
        Column names written into the header.
    units : list
        Column units to be written into the header.
    separator : str
        Separator to use between columns.
    """
    file_handle.write(separator.join(columns) + "\n")
    file_handle.write(separator.join(units) + "\n")


def init_hdf5_skel(file_handle, columns, units, dtypes, chunks):
    """
    Initialize a HDF5 file skeleton for a measurement file.

    Parameters
    ----------
    file_handle : h5py.File
        Opened HDF5 file that the header should be written to.
    columns : list
        Column names written into the header.
    units : list
        Column units to be written into the header.
    chunks : list
        List of ints that define the chunk length of the individual datasets.
    dtypes : list
        List of strings specifying the dtype of the individual datasets.
    """
    # lazy import of h5py to only load it when it is required
    import h5py
    data_grp = file_handle.create_group("data")
    dt = np.dtype(
        [
            ("message", h5py.string_dtype(encoding="utf-8")),
            ("timestamp", h5py.string_dtype(encoding="utf-8")),
        ]
    )
    # Create an empty dataset for comments
    file_handle.create_dataset("comments", shape=(0,), maxshape=(None,), dtype=dt)
    for col, uni, chu, dtype in zip(columns, units, chunks, dtypes):
        if isinstance(chu, tuple):
            data_grp.create_dataset(col, (0, *chu), maxshape=(None, *chu),
                                    chunks=(1, *chu), dtype=dtype,
                                    compression=True)
        else:
            data_grp.create_dataset(col, (0,), maxshape=(None,),
                                    chunks=(chu,), dtype=dtype,
                                    compression=True)
        data_grp[col].attrs["unit"] = uni


def flatten(iterable, types=(tuple, list, np.ndarray)):
    """
    Recursively flatten an iterable to have only one dimension.

    Parameters
    ----------
    iterable : iterable
        The iterable to be flattened.
    types : tuple, optional
        Types to be considered for flattening, by default (tuple, list, np.ndarray).

    Yields
    ------
    Any
        Elements from the flattened iterable.
    """
    for el in iterable:
        if ((isinstance(el, types) and not
             isinstance(el, (str, bytes)))):
            yield from flatten(el, types=types)
        else:
            yield el


# utility functions
def get_pt100_temp(res):
    """
    Calculate the Pt100 equivalent temperature using Wikipedia coefficients.

    Parameters
    ----------
    res : float
        Resistance value of the Pt100 sensor in ohms.

    Returns
    -------
    float
        Equivalent temperature in degrees Celsius.
    """
    a = 3.9083e-3
    b = -5.775e-7
    r0 = 100
    return (-a*r0+np.sqrt((a*r0)**2-4*b*r0*(r0 - res)))/(2*b*r0)


class Command:
    """
    Class representing a command provided by a ControlGUI.

    A command contains the data type of the connected variable and functions for
    setting and getting and their respective arguments.
    """

    def __init__(self, dtype, setfunc, getfunc, setargs=None, getargs=None,
                 polling_cmd=None):
        """Initialize the Command object.

        Parameters
        ----------
        dtype : type
            Data type of the connected variable.
        setfunc : callable or tuple
            Setter function to change the connected variable.
            Can also be a tuple with a device name and device property.
        getfunc : callable or tuple
            Getter function to obtain the value of the variable.
            Can also be a tuple with a device name and device property.
        setargs : tuple, optional
            Additional arguments for the setter function.
        getargs : tuple, optional
            Additional arguments for the getter function.
        polling_cmd : str, optional
            Command to poll to check if the setpoint was reached.
        """
        self.dtype = dtype
        self.setfunc = setfunc
        self.getfunc = getfunc
        if setargs is None:
            self.setargs = []
        else:
            self.setargs = setargs
        if getargs is None:
            self.getargs = []
        else:
            self.getargs = getargs
        self.polling_cmd = polling_cmd

    def __repr__(self):
        """
        Return a string representation of the Command object.

        Returns
        -------
        str
            A string representation of the Command object.
        """
        return self.__str__()

    def __str__(self):
        """
        Return a string representation of the Command object.

        Returns
        -------
        str
            A string representation of the Command object, including its class name,
            data type, setter function, getter function, and their respective arguments.
        """
        r = f"{self.__class__.__name__}: {self.dtype}, {self.setfunc}"
        if self.setargs:
            r += f"({self.setargs})"
        r += f", {self.getfunc}"
        if self.getargs:
            r += f"({self.getargs})"
        return r

    def reset_to_None(self):
        """
        Reset the Command object's setter and getter functions and arguments to None.

        This method sets the setter function, getter function, and their respective
        arguments to None or empty lists.
        """
        self.setfunc = None
        self.getfunc = None
        self.setargs = []
        self.getargs = []

    @classmethod
    def from_deprecated_list(cls, dlist):
        """
        Create a Command from the deprecated list format.

        Parameters
        ----------
        dlist: list
          list containing:
          [type, setFunction, additional set args, GetFunction,
           additional get args, [optional polling command]]

        Returns
        -------
        a Command object with the settings equivalent to dlist
        """
        if len(dlist) < 5 or len(dlist) > 6:
            raise ValueError(
                "command entries must be a list of lenth 5 or 6")
        if len(dlist) > 5:
            pcmd = dlist[5]
        else:
            pcmd = None
        return cls(dlist[0], dlist[1], dlist[3], setargs=dlist[2],
                   getargs=dlist[4], polling_cmd=pcmd)


class Get(Command):
    """Class representing a Getter-command of a ControlGUI."""

    def __init__(self, dtype, getfunc, getargs=None):
        """Initialize the Get command.

        Parameters
        ----------
        dtype : type
            Data type of the connected variable.
        getfunc : callable
            Getter function to obtain the value of the variable.
        getargs : tuple or None, optional
            Optional arguments for the getter function.
        """
        super().__init__(dtype, setfunc=None, getfunc=getfunc, getargs=getargs)


class Set(Command):
    """Class representing a Setter-command of a ControlGUI."""

    def __init__(self, dtype, setfunc, setargs=None, polling_cmd=None):
        """Initialize the Set command.

        Parameters
        ----------
        dtype : type
            Data type of the connected variable.
        setfunc : callable
            Setter function to change the connected variable.
        setargs : tuple or None, optional
            Optional additional arguments for the setter function.
        polling_cmd : str or None, optional
            Optional command to poll to check if the setpoint was reached.
        """
        super().__init__(dtype, setfunc, getfunc=None, setargs=setargs,
                         polling_cmd=polling_cmd)


def normalize_cmds(cmds):
    """
    Make all commands instances of Command.

    Changes are performed in-place.

    Parameters
    ----------
    cmds : dict
        Dictionary of commands to normalize.

    Returns
    -------
    None
    """
    # harmonize the cmds dictionary -> convert all to Command
    for cmd, val in cmds.items():
        if not isinstance(val, Command):
            cmds[cmd] = Command.from_deprecated_list(val)
    # harmonize the cmds dictionary -> convert all to Command
    for cmd, val in cmds.items():
        if not isinstance(val, Command):
            cmds[cmd] = Command.from_deprecated_list(val)


def set_correct_mac_appname(name: str) -> None:
    """
    Set the correct app name on a Mac.

    Parameters
    ----------
    name : str
        The desired name of the application.
    """
    bundle = NSBundle.mainBundle()
    if bundle:
        info_dict = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        info_dict["CFBundleName"] = name
    # Correct the menu
    app = NSApplication.sharedApplication()
    mainMenu = app.mainMenu()
    # Get left-most menu with app-specific items
    app_menu = mainMenu.itemAtIndex_(0).submenu()
    for i in range(app_menu.numberOfItems()):
        item = app_menu.itemAtIndex_(i)
        item.setTitle_(item.title().replace("Python", name))


class DcDict(dict):
    """
    Custom dictionary class that only allows append if key already exists.

    This class extends the built-in dictionary class to modify its behavior
    when in append mode or when a merged system exists.
    In append mode non-empty entries are extended.

    Methods
    -------
    overwrite_value(key, value)
        Overwrite the value for a given key.
    """

    def __init__(self, system_ref, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.append = False
        self.system_ref = system_ref

    def __setitem__(self, key, value):
        """
        Set item in the dictionary with modified behavior.

        This method wraps dict.__setitem__ to change behavior when in append mode
        or when a merged system exists (append in that case).

        Parameters
        ----------
        key : hashable
            The key to set.
        value : Any
            The value to set for the given key.
        """
        if self.system_ref.merged_system:
            # initialized subsystem, write into merged parent
            if key not in APP_META_KEY:
                # is meta key is non-editable, no append is allowed
                super().__setitem__(key, value)
                return
            self._append_value(
                key, value, ";@set:", ref=self.system_ref.merged_system.dcdata
            )
        elif self.append and self[key]:
            # read only mode is enabled, append values
            if key not in APP_META_KEY:
                # is meta key is non-editable, no append is allowed
                super().__setitem__(key, value)
                return
            self._append_value(key, value, ";@ap:")
        else:
            super().__setitem__(key, value)

    def _append_value(self, key, value, sep, ref=None):
        if not value:
            # only append values that are not None
            return
        if ref:
            # reference system is defined, write meta_data to that system
            if key in ref.keys():
                if ref[key]:
                    # only append to available value if it exists (not None)
                    ref[key] = sep.join([ref[key], value])
                    return
            ref[key] = sep[1:] + value
        else:
            # append meta data to current current array
            if key in self.keys():
                if self[key]:
                    super().__setitem__(key, sep.join([self[key], value]))
                    return
            super().__setitem__(key, sep[1:] + value)
