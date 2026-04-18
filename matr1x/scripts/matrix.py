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
Performs measurements utilizing several input files.

matrix.py takes an input file, a system file (can be specified in the
input file) and an output file as arguments to perform a measurement.
The measurement setup itself is specified in the system, while the
parameters that are to be applied are specified in the input file. For
each line of the input file, all parameters are read out and saved into
a file of ascii or hdf5 format, depending on the system specifications.
"""

import argparse
import io
import math
import os
import re
import shlex
import sys
import time
import traceback
from collections.abc import Callable, Generator
from enum import Enum
from pathlib import Path
from typing import NoReturn, cast

import urwid
from pydantic import BaseModel, RootModel

from matr1x import reload_config
from matr1x.error_handling import Error
from matr1x.system import MergedSystem
from matr1x.util import (
    flatten,
    generate_col_index,
    open_and_error,
    print_formatted_line,
    telemetry_string,
)

from .. import VALID_META_KEYS

# conditional import for non-blocking io
if os.name == "nt":
    import msvcrt
else:
    import termios
    from select import select

stdout = cast(io.TextIOWrapper, sys.stdout)
stdout.reconfigure(line_buffering=True)

abortmap = {"q": 1, "a": 2, "f": 3}
# define abort conditions for different keys


class OutputType(Enum):
    """Define different output types."""

    PLAIN = 1
    QUIET = 2
    JSON = 3
    URWID = 4


output_type: OutputType


class SetValues(BaseModel):
    """Model for the set values."""

    set: list


class MeasuredValues(BaseModel):
    """Model for the measured values."""

    measured: list


class Header(BaseModel):
    """Model for the header of a measurement output."""

    columns: list
    units: list


class Telemetry(BaseModel):
    """Model for the telemetry data."""

    point: int
    points: int
    elapsed: float
    remaining: float | None
    settime: float | None
    readtime: float | None


class LogMessage(BaseModel):
    """Model for the log message."""

    message: str


class ErrorMessage(BaseModel):
    """Model for the error message."""

    error: str


class Datafile(BaseModel):
    """Model for the datafile."""

    datafile: str


PayloadType = (
    SetValues | MeasuredValues | Header | Telemetry | LogMessage | ErrorMessage | Datafile
)


class Envelope(RootModel[PayloadType]):
    """Simplify received data handling."""

    @property
    def payload(self) -> PayloadType:
        """Return the parsed payload."""
        return self.root


def flush_input():
    """Flush the input buffer to get only fresh input later on."""
    if sys.platform == "win32":
        while msvcrt.kbhit():
            msvcrt.getch()
    else:
        try:
            termios.tcflush(sys.stdin, termios.TCIOFLUSH)
        except termios.error:
            pass  # errors in none proper terminal, e.q.  Github actions


def parse_cmd_line() -> argparse.Namespace:
    """
    Create and apply an argument parser for the measurement script.

    This function sets up an argparse.ArgumentParser with various
    command-line options for customizing the output of the measurement.

    Returns
    -------
    argparse.Namespace
       The parsed command-line arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--inputfile", help="tuple input filename", required=True)
    parser.add_argument("-s", "--systemfile", nargs="*", help="specifies system(s)")
    parser.add_argument("-o", "--outputfile", default=None, help="Output filename")
    parser.add_argument(
        "-c",
        "--optional-config",
        help="Path to an optional TOML configuration file to override settings.",
        default=None,
    )
    parser.add_argument(
        "-af",
        "--append",
        action="store_true",
        help="instead of appending a continuous number "
        + "to the output file, append to output file.",
    )
    parser.add_argument(
        "-p",
        "--plain",
        action="store_true",
        help="use plain output instead of the urwid library",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="produce reduced output (no measurement data), requires plain",
    )
    group.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="produce machine readable output (json), requires plain",
    )

    # add keys to allow transmitting meta data
    for key in VALID_META_KEYS.keys():
        parser.add_argument(
            f"-d{key[:2].lower()}",
            f"--dc_{key.lower()}",
            default=None,
            help=f"Dublin Core meta data entry {key}",
        )

    options = parser.parse_args()

    if options.json and not options.plain:
        parser.error("--json can only be used together with --plain")
    if options.quiet and not options.plain:
        parser.error("--quiet can only be used together with --plain")

    global output_type
    if options.plain:
        if options.quiet:
            output_type = OutputType.QUIET
        elif options.json:
            output_type = OutputType.JSON
        else:
            output_type = OutputType.PLAIN
    else:
        output_type = OutputType.URWID

    return options


def process_output(message: str) -> None:
    """
    Print general info in the proper format.

    Parameters
    ----------
    message: str
        The message to be printed.
    """
    if output_type == OutputType.JSON:
        print(LogMessage(message=message).model_dump_json())
    else:
        print(message)


def process_error(error: str) -> NoReturn:
    """
    Print an error in the proper format and exit.

    Parameters
    ----------
    error: str
        The error message to be printed.
    """
    if output_type == OutputType.JSON:
        print(ErrorMessage(error=error).model_dump_json())
    else:
        print(f"matrix: error: {error}")
    sys.exit(1)


def process_header(header: Header) -> None:
    """
    Print the header in the proper format.

    Parameters
    ----------
    header: Header
        The header data, i.e. columns and units.
    """
    if output_type == OutputType.JSON:
        print(header.model_dump_json())
    elif output_type == OutputType.PLAIN:
        print_formatted_line(header.columns)
        print_formatted_line(header.units)


class PlainMeasurement:
    """Run a plain measurement."""

    def __init__(self, inputfile: str, system: MergedSystem) -> None:
        """Set all required variables."""
        self._inputfile = inputfile
        self._system = system

    def run(self) -> int:
        """
        Run the measurement.

        Returns
        -------
        int
            The measurement-loop returncode.
        """
        process_header(
            Header(
                columns=list(flatten(self._system.columns)),
                units=list(flatten(self._system.units)),
            )
        )
        return measurementloop(
            self._inputfile,
            self._system,
            setvalcb=self.setvalcb,
            readvalcb=self.readvalcb,
            telemetrycb=self.telemetrycb,
            inputcb=self.inputcb,
        )

    def telemetrycb(self, telemetry: Telemetry) -> None:
        """
        Print the telemetry data in the proper format.

        Parameters
        ----------
        telemetry: Telemetry
            The telemetry data.
        """
        if output_type == OutputType.JSON:
            print(telemetry.model_dump_json())
        elif output_type == OutputType.PLAIN:
            print(
                telemetry_string.format(
                    telemetry.point,
                    telemetry.points,
                    telemetry.elapsed,
                    telemetry.remaining,
                    telemetry.settime,
                    telemetry.readtime,
                )
            )

    def setvalcb(self, values: SetValues) -> None:
        """
        Print the set values in the proper format.

        Parameters
        ----------
        values: SetValues
            The set values.
        """
        if output_type == OutputType.JSON:
            print(values.model_dump_json())
        elif output_type == OutputType.PLAIN:
            print_formatted_line(values.set, "Set: ")

    def readvalcb(self, values: MeasuredValues) -> None:
        """
        Print the read values in the proper format.

        Parameters
        ----------
        value: MeasuredValues
            The read values.
        """
        if output_type == OutputType.JSON:
            print(values.model_dump_json())
        elif output_type == OutputType.PLAIN:
            print_formatted_line(values.measured, "Meas: ")
        elif output_type == OutputType.QUIET:
            print(".", end="", flush=True)

    def _nonblocking_getch(self) -> str | None:
        """
        Cross-platform nonblocking implementation of getch.

        In a linux terminal, enter has been pressed to trigger the
        getch, as otherwise the stdin is not flushed.

        Returns
        -------
        str | None
            Key that has been pressed.
        """
        if sys.platform == "win32":
            if msvcrt.kbhit():
                return msvcrt.getch().decode("utf-8")
        else:
            if select([sys.stdin], [], [], 0) == ([sys.stdin], [], []):
                return sys.stdin.read(1)

    def inputcb(self, points: int) -> int:
        """
        Provide the key detection for plain measurments.

        Parameters
        ----------
        points: int
            The number of points measured so far.

        Returns
        -------
        int
            The result of the key press (0 = no special key pressed).
        """
        key = self._nonblocking_getch()
        if key and key.lower() in ("q", "a", "f"):
            process_output(f"Note: aborted with {key} after {points} points\n\n\n")
            self._system.add_comment(
                f"measurement aborted by keyboard input after {points} points"
            )
            return abortmap[key.lower()]
        if key in ("p", "P"):
            process_output("paused - continue with 'p'\n")
            self._system.add_comment("measurement paused by keyboard input")
            # wait for unpause with p
            while True:
                time.sleep(0.1)
                key = self._nonblocking_getch()
                if key and key.lower() in ("q", "a", "f"):
                    process_output(f"Note: aborted with {key} after {points} points\n\n\n")
                    self._system.add_comment(
                        f"measurement aborted by keyboard input after {points} points"
                    )
                    return abortmap[key.lower()]
                if key in ("p", "P"):
                    break
        return 0


def sort(arg):
    """Define sorting algorithm."""
    key = arg[0]
    # properly handles "aa", "ab", "ba" and also logpoint (last)
    return sum((ord(c) - 96) * 26**i for (i, c) in enumerate(key[::-1]))


def _cast_datapoint_value(
    value: list[float] | tuple[float, ...] | float | None,
) -> float | list[float] | None:
    """
    Cast a single datapoint value to float or list of floats.

    Parameters
    ----------
    value : list[float] | tuple[float, ...] | float | None
        The raw value from the argument parser.

    Returns
    -------
    float | list[float] | None
        The converted value(s).
    """
    if isinstance(value, (list, tuple)):
        if len(value) == 1:
            return float(value[0])
        return [float(dp) for dp in value]
    elif value is None:
        return None
    else:  # branch executed for defaults
        return float(value)


def parse_inputfile(inputfile: str, system: MergedSystem) -> Generator:
    """
    Read the input file.

    Provide point by point set values needed for the measurement,
    define the line parser for the matrix inputfile and parse
    parameters as 0 = -a val(s), 1 = -b val(s), etc.

    Parameters
    ----------
    inputfile: str
        The input file.
    system: MergedSystem
        The merged system.

    Yields
    ------
    dict
        A list containing the parsed parameters.
    """
    pointparser = argparse.ArgumentParser(add_help=False)
    for i in range(len(system.columns)):
        letter = generate_col_index(i)
        short_option = "-" + letter
        long_option = "-" + letter + "_value"
        pointparser.add_argument(
            short_option, long_option, default=system.default_values[i], nargs="*", type=float
        )
    # allow point with and without measurements
    pointparser.add_argument("--logpoint", default=1, nargs="?", type=int)
    # start parsing the input file
    with Path(inputfile).open() as parameterfile:
        for nr, line in enumerate(parameterfile):
            # jump over comments
            if line[0] != "#":
                # divide the string into a list and
                # read the values into datapoint
                parameterlist = shlex.split(line)
                for i, arg in enumerate(parameterlist):
                    if (arg[0] == "-") and arg[1].isdigit():
                        parameterlist[i] = " " + arg
                # raw_input is a list: [known_args, unknown_args]
                raw_input = pointparser.parse_known_args(parameterlist)
                if raw_input[1] != []:
                    raise ValueError(
                        f"Unrecognized argument in inputfile on line {nr}: {raw_input[1]}"
                    )
                # get the list with parameters from the parser and sort so that
                # order is maintained
                datapoint = [value for key, value in sorted(vars(raw_input[0]).items(), key=sort)]
                # prepare values for system.set_value by casting to float
                for i in range(len(system.columns)):
                    datapoint[i] = _cast_datapoint_value(datapoint[i])

                yield datapoint


def measurementloop(
    inputfile: str,
    system: MergedSystem,
    setvalcb: Callable[[SetValues], None] = lambda s: None,
    readvalcb: Callable[[MeasuredValues], None] = lambda r: None,
    telemetrycb: Callable[[Telemetry], None] = lambda s: None,
    inputcb: Callable[[int], int] = lambda n: 0,
) -> int:
    """
    Measurement loops with callback functions for visualization.

    Parameters
    ----------
    inputfile : str
        Path to the input file containing measurement data.
    system : MergedSystem
        The merged system object containing all devices and parameters.
    setvalcb : Callable[[SetValues], None], optional
        Callback function for setting values.
    readvalcb : Callable[[MeasuredValues], None], optional
        Callback function for reading values.
    telemetrycb : Callable[[TelemetryContent], None], optional
        Callback function for telemetry content.
    inputcb : Callable[[int, MergedSystem], int], optional
        Callback function for input handling.

    Returns
    -------
    int
        The exit code of the measurement loop.
    """
    points = 0
    with Path(inputfile).open() as f:
        for line in f:
            if line.startswith("#"):
                continue
            points += 1
    telemetrycb(
        Telemetry(
            point=0,
            points=points,
            elapsed=0,
            remaining=math.nan,
            settime=math.nan,
            readtime=math.nan,
        )
    )
    starttime = time.time()
    for point_idx, datapoint in enumerate(parse_inputfile(inputfile, system)):
        preset = time.time()
        setvalues = []
        for i, col in enumerate(system.columns):
            setv = system.set_value(i, datapoint[i])
            if setv is None and isinstance(col, (list, tuple)):
                setvalues.append(
                    [
                        None,
                    ]
                    * len(col)
                )
            else:
                setvalues.append(setv)

        setvalcb(SetValues(set=flatten(setvalues)))
        preread = time.time()
        if datapoint[-1] == 1:  # logpoint argument
            system.trigger()
            return_list = system.take_measurement_point()
            readvalcb(MeasuredValues(measured=return_list))

        elapsed = time.time() - starttime
        telemetrycb(
            Telemetry(
                point=point_idx + 1,
                points=points,
                elapsed=elapsed / 60,
                remaining=(elapsed / (point_idx + 1) * points - elapsed) / 60,
                settime=preread - preset,
                readtime=time.time() - preread,
            )
        )
        ret_input = inputcb(point_idx + 1)
        if ret_input != 0:
            return ret_input
    return 0


class UrwidMeasurement:
    """Run an urwid measurement."""

    def __init__(self, inputfile: str, systemfile, system: MergedSystem):
        self.msg = ""
        self._inputfile = inputfile
        self._system = system
        columns_flat = list(flatten(system.columns))
        units_flat = list(flatten(system.units))
        columns_flat = cast(list[str], columns_flat)
        units_flat = cast(list[str], units_flat)
        info = urwid.Text("Pause/Quit graciously with p/q after current cycle", align="center")
        outf = urwid.Text(f" output filename : {system.filename}\n", wrap="clip")
        inpf = urwid.Text(f" Input filename  : {inputfile}\n", wrap="clip")
        systemf = urwid.Text(f" systemfile      : {','.join(systemfile)}", wrap="clip")
        self.telemetry = urwid.Text("")
        self.status = urwid.Text("")
        parname = urwid.Text("par-name")
        setc = urwid.Text("set-val")
        readc = urwid.Text("readout")
        unitn = urwid.Text("unit")
        params = [urwid.Text(col) for col in columns_flat]
        self.setval = [urwid.Text("") for col in columns_flat]
        self.readval = [urwid.Text("") for col in columns_flat]
        units = [urwid.Text(u) for u in units_flat]
        columns = urwid.Columns(
            [
                urwid.Pile([parname] + params),
                urwid.Pile([setc] + self.setval),
                urwid.Pile([readc] + self.readval),
                urwid.Pile([unitn] + units),
            ]
        )
        cont = urwid.Pile([info, outf, inpf, systemf, self.telemetry, self.status, columns])
        self.filler = urwid.Filler(cont)
        screen = None
        if os.environ.get("CI") == "true":
            screen = urwid.raw_display.Screen(input=None)
        self.loop = urwid.MainLoop(self.filler, screen=screen)
        self.loop.screen.set_input_timeouts(max_wait=0)  # type: ignore

    def run(self) -> int:
        """
        Start the Urwid loop, run the measurement, and stop the loop.

        Returns
        -------
        int
            The return state from the measurement loop.
        """
        self.loop.start()
        try:
            self.loop.draw_screen()
            ret = measurementloop(
                self._inputfile,
                self._system,
                self.setvalcb,
                self.readvalcb,
                self.telemetrycb,
                self.inputcb,
            )
        finally:
            self.loop.stop()
        return ret

    def setvalcb(self, values: SetValues) -> None:
        """
        Print the set values in the urwid environment.

        Parameters
        ----------
        values: SetValues
            The set values.
        """
        setvalues = values.set
        for i, setv in enumerate(flatten(setvalues)):
            if setv is not None:
                self.setval[i].set_text(str(setv))
        self.loop.draw_screen()

    def readvalcb(self, values: MeasuredValues) -> None:
        """
        Print the read values in the urwid environment.

        Parameters
        ----------
        value: MeasuredValues
            The read values.
        """
        return_list = values.measured
        for i, ret in enumerate(return_list):
            self.readval[i].set_text(str(ret))
        self.loop.draw_screen()

    def telemetrycb(self, telemetry: Telemetry) -> None:
        """
        Print the telemetry data in the urwid environment.

        Parameters
        ----------
        telemetry: TelemetryContent
            The telemetry data.
        """
        tstr = telemetry_string.format(
            telemetry.point,
            telemetry.points,
            telemetry.elapsed,
            telemetry.remaining,
            telemetry.settime,
            telemetry.readtime,
        )
        self.telemetry.set_text(tstr)

    def inputcb(self, n: int) -> int:
        """
        Provide the key detection for urwid measurments.

        Parameters
        ----------
        n: int
            The number of points measured so far.

        Returns
        -------
        int
            The result of the key press (0 = no special key pressed).
        """
        for key in self.loop.screen.get_input():  #  type: ignore
            if isinstance(key, tuple):
                # mouse presses result in tuple of shape
                #  ("mouse release", 1, 35, 20)
                # -> ignore those.
                continue
            if key.lower() in ("q", "f", "a"):
                self.msg += f"Note: aborted with {key} after {n} points"
                self._system.add_comment(f"measurement aborted by keyboard input after {n} points")
                return abortmap[key.lower()]
            if key in ("p", "P"):
                self.msg += f"paused at {time.time()} after {n} points\n"
                self.status.set_text("paused - continue with 'p'")
                self._system.add_comment("measurement paused by keyboard input")
                self.loop.draw_screen()
                # wait for unpause with p
                flag = True
                while flag:
                    time.sleep(0.1)
                    for key in self.loop.screen.get_input():  #  type: ignore
                        if key.lower() in ("q", "f", "a"):
                            self.msg += f"Note: aborted with {key} after {n} points"
                            self._system.add_comment(
                                f"measurement aborted by keyboard input after {n} points"
                            )
                            return abortmap[key.lower()]
                        if key in ("p", "P"):
                            flag = False
                self.status.set_text("")
                self.loop.draw_screen()
            elif key == "window resize":
                self.loop.screen_size = None
        self.loop.draw_screen()
        return 0


def reset_system_and_exit(
    system: MergedSystem,
    reset_kwargs: dict,
    exit_code: int,
    error_message: str | None = None,
    exception: Exception | None = None,
    immediate_error: bool = False,
):
    """
    Reset system and exit with proper error handling.

    This eliminates code duplication in error handling paths.

    Parameters
    ----------
    system : System
        The system to reset
    reset_kwargs : dict
        Arguments to pass to system.reset()
    exit_code : int
        Exit code for sys.exit()
    error_message : str, optional
        Error message to print
    exception : Exception, optional
        Exception to be added as a comment to the system
    immediate_error : bool, optional
        True for immediate error exits.
    """
    if error_message:
        process_output(error_message)
    if immediate_error:
        reset_kwargs["status"] = "errored"
        if exception:
            system.add_comment(f"Matrix errored: {type(exception).__name__}: {exception}")
    process_output("resetting devices")
    system.reset(**reset_kwargs)
    sys.exit(exit_code)


def read_inputfile_header(
    inputfile: str,
) -> tuple[list[str] | None, list[str] | None, list[str] | None]:
    """
    Read system file and column metadata from the input file header.

    Parameters
    ----------
    inputfile : str
        Path to the input file.

    Returns
    -------
    tuple[list[str] | None, list[str] | None, list[str] | None]
        The system filenames, settable column names, and settable units
        found in the header, or None if not present.
    """
    systemfile: list[str] | None = None
    settable_names_file: list[str] | None = None
    settable_units_file: list[str] | None = None

    with open_and_error(inputfile, "r") as f:
        if isinstance(f, Error):
            process_error(str(f.error))
        for line in f.value:
            system_pattern = r"^# [Ss]ystem filename : (.+)"
            settable_names_pattern = r"^# [Ss]ettable columns : (.+)"
            settable_units_pattern = r"^# [Ss]ettable units : (.+)"
            if match := re.match(system_pattern, line.strip()):
                systemfile = match.group(1).split(",")
            elif match := re.match(settable_names_pattern, line.strip()):
                settable_names_file = match.group(1).split(",")
            elif match := re.match(settable_units_pattern, line.strip()):
                settable_units_file = match.group(1).split(",")
            if line[0] != "#":
                break

    return systemfile, settable_names_file, settable_units_file


def load_system(systemfile: list[str]) -> MergedSystem:
    """
    Load and merge all system files into a single system.

    Parameters
    ----------
    systemfile: list[str]
        Paths to the system files to load.

    Returns
    -------
    MergedSystem
        The merged system. Exits with an error message on failure.
    """
    try:
        return MergedSystem.from_files(systemfile)
    except ModuleNotFoundError:
        process_error("system file does not exist")
    except PermissionError:
        process_error("system file not readable")


def verify_columns(
    system: MergedSystem,
    settable_names_file: list[str] | None,
    settable_units_file: list[str] | None,
    options: argparse.Namespace,
) -> None:
    """
    Verify that the system columns match those of the input file.

    Prompts the user to confirm if a mismatch is detected. Exits if the
    user declines to continue or in json mode.

    Parameters
    ----------
    system : MergedSystem
        The loaded system.
    settable_names_file : list[str] or None
        Settable column names read from the input file header.
    settable_units_file : list[str] or None
        Settable units read from the input file header.
    """
    _, settable_names, settable_units = system.settable_columns()
    if settable_names != settable_names_file or settable_units != settable_units_file:
        process_output(str(settable_names) + str(settable_names_file))
        process_output(str(settable_units) + str(settable_units_file))
        if options.json:
            process_error("System columns do not match input file columns.")
        else:
            process_output(
                "System seems to have changed since the input file was generated."
                " The input file might lead to unexpected values being set! "
                "Are you sure you want to continue?\n"
            )
            resp = input("Please enter (y/n): ").strip()
            if resp != "y":
                sys.exit(0)


def run_measurement(
    options: argparse.Namespace, systemfile: list[str], system: MergedSystem
) -> int:
    """
    Run the appropriate measurement interface and return the exit code.

    Selects between plain and urwid on the given options and platform.

    Parameters
    ----------
    options : argparse.Namespace
        Parsed command-line options.
    systemfile : list[str]
        Paths to the system files in use.
    system : MergedSystem
        The active merged system.

    Returns
    -------
    int
        The measurement exit code.
    """
    try:
        # enforce plain interface on Windows because urwid would fail
        if options.plain or options.quiet or os.name == "nt":
            control_string = "To pause or quit after next point, press p/q"
            if os.name != "nt":
                control_string += " and enter"
            if sys.stdout.isatty():
                process_output(control_string)
            return PlainMeasurement(options.inputfile, system).run()
        else:
            measurement = UrwidMeasurement(options.inputfile, systemfile, system)
            ret = measurement.run()
            if measurement.msg != "":
                process_output(measurement.msg)
            return ret
    except KeyboardInterrupt as e:
        process_output(
            "Received keyboard interrupt, file may be corrupt!\n"
            + "Some devices may be in unknown state. Check traceback!\n"
            + "Traceback of error:\n"
        )
        traceback.print_tb(e.__traceback__)
        return 1


def main() -> None:
    """Perform the measurement with input files and parameters."""
    options = parse_cmd_line()
    if options.optional_config:
        reload_config(options.optional_config)
    flush_input()
    systemfile_header, settable_names_file, settable_units_file = read_inputfile_header(
        options.inputfile
    )
    if options.systemfile is not None:
        resolved_systemfile: list[str] = options.systemfile
    elif systemfile_header is not None:
        resolved_systemfile = systemfile_header
    else:
        process_error("no system file specified")
    system = load_system(resolved_systemfile)
    verify_columns(system, settable_names_file, settable_units_file, options)
    output_filename = system.generate_datafilename(
        options.outputfile, options.inputfile, options.append
    )
    if options.json:
        print(Datafile(datafile=str(output_filename)).model_dump_json())
    for key, editable in VALID_META_KEYS.items():
        if editable:
            opt_val = getattr(options, f"dc_{key.lower()}")
            if opt_val is not None:
                system.dcdata[key] = opt_val
    process_output("setting devices")
    system.set(input_file=options.inputfile, output_file=output_filename)
    reset_kwargs = {"input_file": options.inputfile, "output_file": output_filename}
    ret = 0
    try:
        process_output("devices set, acquiring configuration and writing header")
        try:
            msg, outputfile = system.init_datafile(options.inputfile)
            process_output(f"{msg}: {outputfile}")
        except OSError as e:
            reset_system_and_exit(
                system,
                reset_kwargs,
                1,
                "matrix: error: cannot create output file",
                e,
                immediate_error=True,
            )
        except Exception as e:
            reset_system_and_exit(
                system,
                reset_kwargs,
                1,
                "matrix: error: could not acquire configuration.",
                e,
                immediate_error=True,
            )
        process_output("entering loop now")
        ret = run_measurement(options, resolved_systemfile, system)
        if ret == 1:
            x = input(
                "Shall the termination of the sequence lead to "
                "marking the datafile as aborted? (Y/n)"
            )
            if x.lower().startswith("y") or x == "":
                process_output("marking file as aborted")
                reset_kwargs["status"] = "aborted"
        if ret == 2:
            reset_kwargs["status"] = "aborted"
        if "status" not in reset_kwargs.keys():
            reset_kwargs["status"] = "finished"
    except Exception as e:
        traceback.print_exc()
        reset_system_and_exit(
            system,
            reset_kwargs,
            1,
            error_message=f"matrix exited with error:\n{type(e).__name__}: {e}",
            exception=e,
            immediate_error=True,
        )
    reset_system_and_exit(system, reset_kwargs, ret)
