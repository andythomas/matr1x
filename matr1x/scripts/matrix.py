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
from pathlib import Path
from typing import NoReturn, cast

import urwid
from pydantic import ValidationError

from matr1x import reload_config
from matr1x.error_handling import Error
from matr1x.models import (
    Datafile,
    Envelope,
    ErrorMessage,
    Header,
    MeasuredValues,
    MeasurementData,
    Message,
    SetValues,
    SystemInfo,
    Telemetry,
)
from matr1x.system import MergedSystem
from matr1x.util import (
    flatten,
    generate_col_index,
    open_and_error,
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
    parser.add_argument(
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
    if os.name == "nt" and not options.plain:
        options.plain = True  # enforce plain interface on Windows because urwid would fail

    return options


class PlainMeasurement:
    """Base class for all dispatchers."""

    def __init__(self):
        self.msg = ""

    def set_inputfile(self, inputfile: str) -> None:
        """Set the input file."""
        self._inputfile = inputfile

    def set_system(self, system: MergedSystem) -> None:
        """Set the system."""
        self._system = system

    def run(self) -> int:
        """
        Run the measurement.

        Returns
        -------
        int
            The measurement-loop returncode.
        """
        self.dispatch(
            Header(
                columns=list(flatten(self._system.columns)),
                units=list(flatten(self._system.units)),
            )
        )
        return measurementloop(
            self._inputfile,
            self._system,
            datacb=self.dispatch,
            inputcb=self.inputcb,
        )

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
            self.dispatch(Message(message="Note: aborted with {key} after {points} points\n\n\n"))
            self._system.add_comment(
                f"measurement aborted by keyboard input after {points} points"
            )
            return abortmap[key.lower()]
        if key in ("p", "P"):
            self.dispatch(Message(message="paused - continue with 'p'\n"))
            self._system.add_comment("measurement paused by keyboard input")
            # wait for unpause with p
            while True:
                time.sleep(0.1)
                key = self._nonblocking_getch()
                if key and key.lower() in ("q", "a", "f"):
                    self.dispatch(
                        Message(message=f"Note: aborted with {key} after {points} points\n\n\n")
                    )
                    self._system.add_comment(
                        f"measurement aborted by keyboard input after {points} points"
                    )
                    return abortmap[key.lower()]
                if key in ("p", "P"):
                    break
        return 0

    def receive(self, data: str) -> None:
        """Validate the received data and send to dispatcher."""
        try:
            env = Envelope.model_validate_json(data)
        except ValidationError:
            self.unknown_data(data)
            return
        payload = env.payload
        self.dispatch(payload)

    def dispatch(self, payload: MeasurementData) -> None:
        """Dispatch the payload to the appropriate function."""
        if isinstance(payload, Header):
            self.header(payload)
        elif isinstance(payload, SetValues):
            self.set_values(payload)
        elif isinstance(payload, MeasuredValues):
            self.measured_values(payload)
        elif isinstance(payload, Telemetry):
            self.telemetry(payload)
        elif isinstance(payload, Message):
            self.message(payload)
        elif isinstance(payload, ErrorMessage):
            self.error_message(payload)

    def unknown_data(self, data: str) -> None:
        """Print unknown or corrupted data."""
        print(data)  # noqa: T201

    def header(self, header: Header) -> None:
        """Print a formatted header."""
        print(header)  # noqa: T201

    def set_values(self, set_values: SetValues) -> None:
        """Print formatted set values."""
        print(set_values)  # noqa: T201

    def measured_values(self, measured_values: MeasuredValues) -> None:
        """Print formatted measured values."""
        print(measured_values)  # noqa: T201

    def telemetry(self, telemetry: Telemetry) -> None:
        """Print formatted telemetry."""
        print(telemetry)  # noqa: T201

    def message(self, message: Message) -> None:
        """Print a message."""
        print(message.message)  # noqa: T201

    def error_message(self, error_message: ErrorMessage) -> NoReturn:
        """Print an error message and exit."""
        print(f"matrix: error: {error_message.error}")  # noqa: T201
        sys.exit(1)


class JSONMeasurement(PlainMeasurement):
    """Dispatches measurement data with JSON output."""

    def dispatch(self, payload: MeasurementData) -> None:
        """Dump and print the payload as JSON."""
        print(payload.model_dump_json())  # noqa: T201
        if isinstance(payload, ErrorMessage):
            sys.exit(1)


class UrwidMeasurement(PlainMeasurement):
    """Dispatch messages for an urwid-based measurement."""

    def prepare(self) -> None:
        """Prepare the urwid interface."""
        columns_flat = list(flatten(self._system.columns))
        units_flat = list(flatten(self._system.units))
        columns_flat = cast(list[str], columns_flat)
        units_flat = cast(list[str], units_flat)
        info = urwid.Text("Pause/Quit graciously with p/q after current cycle", align="center")
        outf = urwid.Text(f" output filename : {self._system.filename}\n", wrap="clip")
        self.inpf = urwid.Text(f" Input filename  : {self._inputfile}\n", wrap="clip")
        self.systemf = urwid.Text(f" systemfile      : {','.join(self._systemfile)}", wrap="clip")
        self.telemetry_text = urwid.Text("")
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
        cont = urwid.Pile(
            [info, outf, self.inpf, self.systemf, self.telemetry_text, self.status, columns]
        )
        self.filler = urwid.Filler(cont)
        screen = None
        if os.environ.get("CI") == "true":
            screen = urwid.raw_display.Screen(input=None)
        self.loop = urwid.MainLoop(self.filler, screen=screen)
        self.loop.screen.set_input_timeouts(max_wait=0)  # type: ignore

    def set_inputfile(self, inputfile: str) -> None:
        """Set the input file."""
        self._inputfile = inputfile

    def set_systemfile(self, systemfile: list[str]) -> None:
        """Set the system file."""
        self._systemfile = systemfile

    def set_system(self, system: MergedSystem) -> None:
        """Set the system."""
        self._system = system

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
                self.dispatch,
                self.inputcb,
            )
        finally:
            self.loop.stop()
        return ret

    def inputcb(self, points: int) -> int:
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
                self.msg += f"Note: aborted with {key} after {points} points"
                self._system.add_comment(
                    f"measurement aborted by keyboard input after {points} points"
                )
                return abortmap[key.lower()]
            if key in ("p", "P"):
                self.msg += f"paused at {time.time()} after {points} points\n"
                self.status.set_text("paused - continue with 'p'")
                self._system.add_comment("measurement paused by keyboard input")
                self.loop.draw_screen()
                # wait for unpause with p
                flag = True
                while flag:
                    time.sleep(0.1)
                    for key in self.loop.screen.get_input():  #  type: ignore
                        if key.lower() in ("q", "f", "a"):
                            self.msg += f"Note: aborted with {key} after {points} points"
                            self._system.add_comment(
                                f"measurement aborted by keyboard input after {points} points"
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

    def header(self, header: Header) -> None:
        """Set no plain header in the urwid measurement."""

    def set_values(self, set_values: SetValues) -> None:
        """Set the values in the urwid measurement."""
        setvalues = set_values.set
        for i, setv in enumerate(flatten(setvalues)):
            if setv is not None:
                self.setval[i].set_text(str(setv))
        self.loop.draw_screen()

    def measured_values(self, measured_values: MeasuredValues) -> None:
        """Set the measured values in the urwid measurement."""
        return_list = measured_values.measured
        for i, ret in enumerate(return_list):
            self.readval[i].set_text(str(ret))
        self.loop.draw_screen()

    def telemetry(self, telemetry: Telemetry) -> None:
        """Set the telemetry in the urwid measurement."""
        self.telemetry_text.set_text(str(telemetry))
        self.loop.draw_screen()


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
    datacb: Callable[[MeasurementData], None] = lambda s: None,
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
    datacb : Callable[[MeasurementData], None], optional
        Callback function data processing
    inputcb : Callable[[int], int], optional
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
    datacb(
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

        datacb(SetValues(set=flatten(setvalues)))
        preread = time.time()
        if datapoint[-1] == 1:  # logpoint argument
            system.trigger()
            return_list = system.take_measurement_point()
            datacb(MeasuredValues(measured=return_list))

        elapsed = time.time() - starttime
        datacb(
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


def reset_system_and_exit(
    dispatcher: PlainMeasurement,
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
        dispatcher.dispatch(Message(message=error_message))
    if immediate_error:
        reset_kwargs["status"] = "errored"
        if exception:
            system.add_comment(f"Matrix errored: {type(exception).__name__}: {exception}")
    dispatcher.dispatch(Message(message="resetting devices"))
    system.reset(**reset_kwargs)
    sys.exit(exit_code)


def read_inputfile_header(
    inputfile: str, dispatcher: PlainMeasurement
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
            dispatcher.dispatch(ErrorMessage(error=str(f.error)))
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


def verify_columns(
    system: MergedSystem,
    settable_names_file: list[str] | None,
    settable_units_file: list[str] | None,
    options: argparse.Namespace,
    dispatcher: PlainMeasurement,
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
    flat_parameters = SystemInfo.model_validate(system.grab_information()).flat_parameters
    settable_names = [p.name for p in flat_parameters if p.settable]
    settable_units = [p.unit for p in flat_parameters if p.settable]
    if settable_names != settable_names_file or settable_units != settable_units_file:
        dispatcher.dispatch(Message(message=str(settable_names) + str(settable_names_file)))
        dispatcher.dispatch(Message(message=str(settable_units) + str(settable_units_file)))
        if options.json:
            dispatcher.dispatch(
                ErrorMessage(error="System columns do not match input file columns.")
            )
        else:
            dispatcher.dispatch(
                Message(
                    message="System seems to have changed since the input file was generated."
                    " The input file might lead to unexpected values being set! "
                    "Are you sure you want to continue?\n"
                )
            )
            resp = input("Please enter (y/n): ").strip()
            if resp != "y":
                sys.exit(0)


def main() -> None:
    """Perform the measurement with input files and parameters."""
    options = parse_cmd_line()
    if options.optional_config:
        reload_config(options.optional_config)
    flush_input()

    if options.plain:
        if options.json:
            measurement = JSONMeasurement()
        else:
            measurement = PlainMeasurement()
    else:
        measurement = UrwidMeasurement()

    systemfile_header, settable_names_file, settable_units_file = read_inputfile_header(
        options.inputfile, measurement
    )
    if options.systemfile is not None:
        resolved_systemfile: list[str] = options.systemfile
    elif systemfile_header is not None:
        resolved_systemfile = systemfile_header
    else:
        measurement.dispatch(ErrorMessage(error="no system file specified"))
    system = MergedSystem.from_files(resolved_systemfile)
    if isinstance(system, Error):
        measurement.dispatch(ErrorMessage(error=system.error))
        sys.exit(1)
    system = system.value
    verify_columns(system, settable_names_file, settable_units_file, options, measurement)
    output_filename = system.generate_datafilename(
        options.outputfile, options.inputfile, options.append
    )
    measurement.dispatch(Datafile(datafile=str(output_filename)))
    for key, editable in VALID_META_KEYS.items():
        if editable:
            opt_val = getattr(options, f"dc_{key.lower()}")
            if opt_val is not None:
                system.dcdata[key] = opt_val
    measurement.dispatch(Message(message="setting devices"))
    system.set(input_file=options.inputfile, output_file=output_filename)
    reset_kwargs = {"input_file": options.inputfile, "output_file": output_filename}
    ret = 0
    try:
        measurement.dispatch(
            Message(message="devices set, acquiring configuration and writing header")
        )
        try:
            msg, outputfile = system.init_datafile(options.inputfile)
            measurement.dispatch(Message(message=f"{msg}: {outputfile}"))
        except OSError as e:
            reset_system_and_exit(
                measurement,
                system,
                reset_kwargs,
                1,
                "matrix: error: cannot create output file",
                e,
                immediate_error=True,
            )
        except Exception as e:
            reset_system_and_exit(
                measurement,
                system,
                reset_kwargs,
                1,
                "matrix: error: could not acquire configuration.",
                e,
                immediate_error=True,
            )
        measurement.dispatch(Message(message="entering loop now"))
        measurement.set_system(system)
        measurement.set_inputfile(options.inputfile)
        if isinstance(measurement, UrwidMeasurement):
            measurement.set_systemfile(resolved_systemfile)
            measurement.prepare()
        else:
            control_string = "To pause or quit after next point, press p/q"
            if os.name != "nt":
                control_string += " and enter"
            if sys.stdout.isatty():
                measurement.dispatch(Message(message=control_string))
        try:
            ret = measurement.run()
        except KeyboardInterrupt as e:
            measurement.dispatch(
                Message(
                    message="Received keyboard interrupt, file may be corrupt!\n"
                    + "Some devices may be in unknown state. Check traceback!\n"
                    + "Traceback of error:\n"
                )
            )
            traceback.print_tb(e.__traceback__)
            ret = 1
        measurement.dispatch(Message(message=measurement.msg))
        if ret == 1:
            x = input(
                "Shall the termination of the sequence lead to "
                "marking the datafile as aborted? (Y/n)"
            )
            if x.lower().startswith("y") or x == "":
                measurement.dispatch(Message(message="marking file as aborted"))
                reset_kwargs["status"] = "aborted"
        if ret == 2:
            reset_kwargs["status"] = "aborted"
        if "status" not in reset_kwargs.keys():
            reset_kwargs["status"] = "finished"
    except Exception as e:
        traceback.print_exc()
        reset_system_and_exit(
            measurement,
            system,
            reset_kwargs,
            1,
            error_message=f"matrix exited with error:\n{type(e).__name__}: {e}",
            exception=e,
            immediate_error=True,
        )
    reset_system_and_exit(measurement, system, reset_kwargs, ret)
