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
Utility functions for the matr1x data acquisition software.

This module includes functions for file handling, script generation,
sweep calculations, and various helper functions for data processing and
system configuration.
"""

import codecs
import importlib.util
import logging
import os
import site
import subprocess
import sys
import sysconfig
import textwrap
import threading
from collections.abc import Callable, Sequence
from pathlib import Path, PureWindowsPath
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

import h5py
import numpy as np

from matr1x.error_handling import Error, Result, Success

# conditional import for type checkers
if TYPE_CHECKING:
    import types

    from _typeshed import SupportsWrite

    _T_contra = TypeVar("_T_contra", contravariant=True)

    class SupportsWriteAndFlush(SupportsWrite[_T_contra], Protocol[_T_contra]):
        """Provide a type for a stream that have write and flush methods."""

        def flush(self) -> None:
            """Add flush to the existing write."""
            ...


# default separator
default_separator = "\t"

_USER_SCRIPT_START_MARKER = "# ==== BEGIN USER SCRIPT AREA ===="
_USER_SCRIPT_END_MARKER = "# ==== END USER SCRIPT AREA ===="
_USER_SCRIPT_INSERTION_POINT = "    # USER_SCRIPT_INSERTION_POINT"


def resolve_config_path(config: Any, path: str) -> Any:
    """
    Resolve a configuration path string (dot notation) to a value from the config object.

    If any part of the path is missing, an empty dictionary is returned.

    Parameters
    ----------
    config : Any
        The configuration object (typically a Pydantic model).
    path : str
        The configuration path (e.g., 'matr1x.devices.visadevice').

    Returns
    -------
    Any
        The value at the specified path, or an empty dictionary if not found.
    """
    current = config
    for sec in path.split("."):
        try:
            current = getattr(current, sec)
        except (AttributeError, TypeError):
            return {}
    return current


def get_package_path(package_name: str) -> Path | None:
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
        return Path(spec.origin).parent
    return None


def resolve_pkgroot_path(path: str | Path, package_path: Path | None) -> Path:
    """Resolve a path that starts with the ``<pkgroot>`` placeholder."""
    placeholder = "<pkgroot>"
    parts = PureWindowsPath(path).parts

    if parts and parts[0] == placeholder and package_path is not None:
        return package_path.joinpath(*parts[1:])

    return Path(path).expanduser()


def create_temp_dir_with_symlinks(
    names: Sequence[str], targets: Sequence[str | Path]
) -> TemporaryDirectory[str]:
    """
    Create temporary directory with symlinks.

    This function works similarly on all major platforms,
    but uses different ways to achieve this.

    Parameters
    ----------
    names : Sequence[str]
        Names of the symlinks.
    targets : Sequence[str | Path]
        Target folders for the links.

    Returns
    -------
    TemporaryDirectory
        Temporary directory instance.
    """
    # Create a temporary directory
    temp_dir = TemporaryDirectory(prefix="systemdir-links-")
    temp_path = Path(temp_dir.name)

    # Create symbolic links in the temporary directory
    for name, target in zip(names, targets):
        target_path = Path(target)

        if not target_path.is_dir():
            raise ValueError(f"The target {target_path} is not a directory.")

        link_path = temp_path / name

        if os.name == "nt":
            subprocess.check_call(
                ["cmd", "/c", "mklink", "/J", str(link_path), str(target_path)],
                stdout=subprocess.DEVNULL,
            )
        else:
            link_path.symlink_to(target_path)

    # Return the temporary directory object
    return temp_dir


def get_matrix_binary() -> str:
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
    user_scripts_path = Path(sysconfig.get_path("scripts", f"{os.name}_user"))
    system_scripts_path = Path(sysconfig.get_path("scripts"))

    for matrix_str in (
        "matrix",  # Check PATH first
        str(user_scripts_path / "matrix"),
        str(system_scripts_path / "matrix"),
    ):
        try:
            subprocess.check_call(
                [matrix_str, "--help"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            return matrix_str
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    raise FileNotFoundError("matrix executable could not be found")


def module_from_path(filename: Path) -> "types.ModuleType":
    """
    Create a module from a file path.

    Parameters
    ----------
    filename : Path
        Path to the file.

    Returns
    -------
    module
        Imported module.
    """
    filename = Path(filename).absolute()
    # create module specification from file and open
    spec = importlib.util.spec_from_file_location("dummyname", filename)
    if spec is None:
        raise ImportError(f"Could not load spec for file '{filename}'")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    if loader is None:
        raise ImportError(f"Could not import {filename}.")
    loader.exec_module(module)
    return module


def get_formatted_line(
    vlist: list, prefix: str = "", appendix: str = "", column_width: int = 10
) -> str:
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
    entry_string = f"{{:>{column_width}}}  "
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
    return outstr


def generate_script_prefix_suffix() -> tuple[str, str]:
    """
    Define the prefix and suffix of the script used in matrix_script.

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
    template_path = Path(__file__).parent / "_matrix_script_template.py"

    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")

    with template_path.open(encoding="utf-8") as f:
        template_content = f.read()

    # Find the markers
    start_marker_pos = template_content.find(_USER_SCRIPT_START_MARKER)
    end_marker_pos = template_content.find(_USER_SCRIPT_END_MARKER)
    insertion_point_pos = template_content.find(_USER_SCRIPT_INSERTION_POINT)

    if start_marker_pos == -1:
        raise ValueError(f"Start marker '{_USER_SCRIPT_START_MARKER}' not found in template")
    if end_marker_pos == -1:
        raise ValueError(f"End marker '{_USER_SCRIPT_END_MARKER}' not found in template")
    if insertion_point_pos == -1:
        raise ValueError(f"Insertion point '{_USER_SCRIPT_INSERTION_POINT}' not found in template")

    # Split the template at the insertion point
    prefix = template_content[:insertion_point_pos]
    suffix = template_content[insertion_point_pos + len(_USER_SCRIPT_INSERTION_POINT) :]

    return prefix, suffix


def get_user_script_line_range(script: str) -> tuple[int, int]:
    """
    Return the inclusive generated-source line range containing user code.

    Parameters
    ----------
    script : str
        Script produced by :func:`generate_script`.

    Returns
    -------
    tuple[int, int]
        First and last line belonging to the user-script insertion area.

    Raises
    ------
    ValueError
        If the generated-script boundary markers are missing or out of order.
    """
    lines = script.splitlines()
    start_lines = [
        line_number
        for line_number, line in enumerate(lines, start=1)
        if line.strip() == _USER_SCRIPT_START_MARKER
    ]
    end_lines = [
        line_number
        for line_number, line in enumerate(lines, start=1)
        if line.strip() == _USER_SCRIPT_END_MARKER
    ]

    if not start_lines:
        raise ValueError(
            f"Start marker '{_USER_SCRIPT_START_MARKER}' not found in generated script"
        )
    if not end_lines:
        raise ValueError(f"End marker '{_USER_SCRIPT_END_MARKER}' not found in generated script")

    first_line = start_lines[0] + 1
    last_line = end_lines[-1] - 1
    if first_line > last_line:
        raise ValueError("User-script boundary markers are out of order")

    return first_line, last_line


def get_script_prefix_offset() -> int:
    """
    Get the number of lines in the script prefix.

    This centralizes the calculation of the script offset that is used
    in multiple places throughout the codebase for line number adjustment.

    Returns
    -------
    int
        Number of lines in the script prefix (n_pref)
    """
    prefix, _ = generate_script_prefix_suffix()
    return len(prefix.splitlines())


def generate_script(user_script: str) -> str:
    """
    Define the general part of the script used in matrix_script.

    Parameters
    ----------
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
    prefix, suffix = generate_script_prefix_suffix()
    if user_script and not user_script.endswith("\n"):
        user_script += "\n"
    return prefix + textwrap.indent(user_script, "    ") + suffix


def matrix_script_process(
    filename: str,
    meta_data: dict,
    scriptname: str,
    port: int | None,
    systems: list[str],
) -> None:
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
    meta_data : dict
        Meta data such as, e.g., user name, description.
    scriptname : str
        Script name used as fallback template for the datafile name if it's not
        set in the script and the directory of this file is used as a base
        directory for executing the script. This means Python files inside this
        directory can be imported by the user-script.
    port : int or None
        Port number used for communication between the script and the graphical
        user interface.
    systems : list
        List of system files to load.

    Returns
    -------
    None
    """
    # import required dependencies
    import socket

    from matr1x.execthread import ExecThread

    # this is required on windows to enable correct opening of a temporary file
    if sys.platform == "win32":

        def temp_opener(name, flag, mode=0o777):
            return os.open(name, flag | os.O_TEMPORARY, mode)
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
        client_socket.connect(("127.0.0.1", port))
        connected = True
    except (ConnectionRefusedError, TypeError):
        # GUI not running - script was not run from graphical user interface.
        # or port is not set
        connected = False

    # initialize the thread
    if connected is True:
        thread = ExecThread(script, meta_data, scriptname, client_socket, systems)
    else:
        thread = ExecThread(script, meta_data, scriptname, None, systems)

    control_thread = None
    stop_event: threading.Event | None = None

    if connected:
        stop_event = threading.Event()

    # start the thread that runs the script
    thread.start()

    if connected:

        def _control_listener() -> None:
            """Forward GUI control commands to the execution thread."""
            decoder = codecs.getincrementaldecoder("utf-8")()
            while True:
                if stop_event is not None and stop_event.is_set():
                    break
                try:
                    datachunk = client_socket.recv(32)
                except OSError:
                    # Socket was closed or shutdown, terminate listener.
                    break
                if len(datachunk) == 0:
                    break
                try:
                    decoded = decoder.decode(datachunk)
                except UnicodeDecodeError:
                    # invalid byte sequence, skip this chunk
                    continue
                for char in decoded:
                    thread.handle_input(char)
            try:
                tail = decoder.decode(b"", final=True)
            except UnicodeDecodeError:
                tail = ""
            for char in tail:
                thread.handle_input(char)

        control_thread = threading.Thread(
            target=_control_listener,
            name="matrix-script-control-listener",
            daemon=True,
        )
        control_thread.start()

    # wait until the execution thread is finished
    thread.join()

    if connected is True:
        if stop_event is not None:
            stop_event.set()
        # unblock the control listener and close the communication socket
        try:
            client_socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        if control_thread is not None:
            control_thread.join(timeout=1)
        # close socket
        client_socket.close()


def generate_col_index(index: int) -> str:
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
        letter = chr(index + 97)
    elif index < 702:
        letter = chr(index // 26 + 96) + chr(index % 26 + 97)
    else:
        raise ValueError("index out of range, talk to the developer")
    return letter


def construct_query_string(query_dict: dict, depth: int = 2) -> str:
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
            ret += "#" * depth + f" {k}\n"
            ret += construct_query_string(v, depth + 1)
        else:
            if isinstance(v, str):
                # ignore carriage returns (would break the datafile!)
                v = v.replace("\r", "\n")
                v = v.replace("\n", "\n" + "#" * (depth + 1) + " ")
                v = v.replace(
                    "\\n", "\n" + "#" * (depth + 1) + " "
                )  # make newlines appear as extra lines
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
    group = hdf5_file.require_group(root_group)

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


def init_hdf5_skel(
    file_handle, columns: list[str], units: list[str], dtypes, chunks: list[int]
) -> None:
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
            data_grp.create_dataset(
                col,
                (0, *chu),
                maxshape=(None, *chu),
                chunks=(1, *chu),
                dtype=dtype,
                compression=True,
            )
        else:
            data_grp.create_dataset(
                col,
                (0,),
                maxshape=(None,),
                chunks=(chu,),
                dtype=dtype,
                compression=True,
            )
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
        if isinstance(el, types) and not isinstance(el, (str, bytes)):
            yield from flatten(el, types=types)
        else:
            yield el


# utility functions
def get_pt100_temp(res: float) -> float:
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
    return (-a * r0 + np.sqrt((a * r0) ** 2 - 4 * b * r0 * (r0 - res))) / (2 * b * r0)


class Command:
    """
    Class representing a command provided by a ControlGUI.

    A command contains the data type of the connected variable and
    functions for setting and getting and their respective arguments.
    """

    def __init__(
        self,
        dtype: Callable[..., Any]
        | list[Callable[..., Any]]
        | tuple[Callable[..., Any], ...]
        | None,
        setfunc: Callable[..., None] | str | list[str] | tuple[str, ...] | None,
        getfunc: Callable[..., Any] | str | list[str] | tuple[str, ...] | None,
        setargs: tuple | list | None = None,
        getargs: tuple | list | None = None,
        polling_cmd: str | None = None,
    ):
        """
        Initialize the Command object.

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
        self.dtype: (
            Callable[..., Any] | list[Callable[..., Any]] | tuple[Callable[..., Any], ...] | None
        ) = dtype
        self.setfunc: Callable[..., None] | str | list[str] | tuple[str, ...] | None = setfunc
        self.getfunc: Callable[..., Any] | str | list[str] | tuple[str, ...] | None = getfunc
        self.setargs: tuple
        self.getargs: tuple
        if setargs is None:
            self.setargs = ()
        else:
            self.setargs = tuple(setargs)
        if getargs is None:
            self.getargs = ()
        else:
            self.getargs = tuple(getargs)
        self.polling_cmd: str | None = polling_cmd

    def __repr__(self) -> str:
        """
        Return a string representation of the Command object.

        Returns
        -------
        str
            A string representation of the Command object.
        """
        return self.__str__()

    def __str__(self) -> str:
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

    def reset_to_None(self) -> None:
        """
        Reset the Command object's setter and getter functions and arguments to None.

        This method sets the setter function, getter function, and their
        respective arguments to None or empty lists.
        """
        self.setfunc = None
        self.getfunc = None
        self.setargs = ()
        self.getargs = ()


class Get(Command):
    """Class representing a Getter-command of a ControlGUI."""

    def __init__(
        self,
        dtype: Callable[..., Any]
        | list[Callable[..., Any]]
        | tuple[Callable[..., Any], ...]
        | None,
        getfunc: Callable[..., Any] | str | list[str] | tuple[str, ...],
        getargs: tuple | None = None,
    ):
        """
        Initialize the Get command.

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

    def __init__(
        self,
        dtype: Callable[..., Any]
        | list[Callable[..., Any]]
        | tuple[Callable[..., Any], ...]
        | None,
        setfunc: Callable[..., None] | str | list[str] | tuple[str, ...],
        setargs: tuple | None = None,
        polling_cmd: str | None = None,
    ):
        """
        Initialize the Set command.

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
        super().__init__(dtype, setfunc, getfunc=None, setargs=setargs, polling_cmd=polling_cmd)


def normalize_cmds(cmds):
    """
    Validate that all commands are Command instances.

    Parameters
    ----------
    cmds : dict
        Dictionary of commands to normalize.

    Returns
    -------
    None
    """
    for cmd, val in cmds.items():
        if not isinstance(val, Command):
            raise TypeError(
                f"Command entry {cmd!r} must be a Command instance, got {type(val).__name__}."
            )


def run_python_cmdline(
    cmd: list[str],
    stdin: str | None = None,
    timeout: float | None = 10,
) -> Result[subprocess.CompletedProcess[str], Exception | str]:
    """
    Run a python command line and return the result.

    It utilizes subprocess.run to execute the command, captures its
    output and avoids the creation of a new console window on Windows.

    Parameters
    ----------
    cmd : list[str]
        The "command" to be placed after the python binary,
        e.g. ["-m", "ruff", "check"].
    stdin: str or None, optional
        The string to utilize as stdin
    timeout: float, optional
        An optional timeout value

    Returns
    -------
    Result
        Either a string with the output, a string with the error from
        the commandline or the exception in case of an subprocess.run
        error.
    """
    python_exec = Path(sys.executable)
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW
        if python_exec.name == "pythonw.exe":
            python_exec = python_exec.parent / "python.exe"
    cmd = [str(python_exec)] + cmd

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=stdin,
            creationflags=creationflags,
            check=False,
        )
        if result.returncode != 0:
            return Error(result.stderr or result.stdout)
        return Success(result)
    except Exception as e:
        return Error(e)


def find_binary(binary: str) -> Result[Path, FileNotFoundError]:
    """
    Find a binary.

    Parameters
    ----------
    binary : str
        The name of the binary to find.

    Returns
    -------
    Result[str, Exception]
        Either the path to the binary or an exception.
    """
    if sys.platform.startswith("win"):
        possible_locations = [
            Path(sys.prefix) / "Scripts" / f"{binary}.exe",
            Path(sys.executable).parent / f"{binary}.exe",
            Path(sys.executable).parent / "Scripts" / f"{binary}.exe",
        ]
        if site.USER_BASE is not None:
            possible_locations += [
                Path(site.USER_BASE)
                / f"Python{sys.version_info[0]}{sys.version_info[1]}"
                / "Scripts"
                / f"{binary}.exe",
                Path(site.USER_BASE) / "Scripts" / f"{binary}.exe",
            ]

        for location in possible_locations:
            if location.exists():
                return Success(location)
        locations_str = "\n".join(f"  - {loc}" for loc in possible_locations)
        return Error(
            FileNotFoundError(
                f"LSP binary '{binary}.exe' not found in any of these locations:\n{locations_str}"
            )
        )
    else:
        result = Path(sys.prefix) / "bin" / binary
        if not result.exists():
            return Error(FileNotFoundError(f"LSP binary not found: {result}"))
        return Success(result)


class StreamToLogger:
    """
    Helper to pipe streams into a logger.

    Parameters
    ----------
    logger: logging.Logger
        The logger to use.
    level: int
        The utilized log-level.
    """

    def __init__(self, logger: logging.Logger, level: int):
        self.logger: logging.Logger = logger
        self.level: int = level
        self._buffer: str = ""

    def write(self, message: str):
        """
        Write a log message considering new lines.

        Parameters
        ----------
        message: str
            The message to log.
        """
        if not message:
            return
        self._buffer += message
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.rstrip()
            if line:
                self.logger.log(self.level, line)

    def flush(self):
        """Flush the buffer."""
        if self._buffer:
            self.logger.log(self.level, self._buffer.rstrip())
            self._buffer = ""


def log_multiline(logger: logging.Logger, message: str, level=logging.INFO):
    """Log a multi-line message to the given logger."""
    for line in message.splitlines():
        logger.log(level, line)
