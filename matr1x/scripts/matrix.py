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

"""
Performs measurements utilizing several input files.

matrix.py takes an input file, a system file (can be specified in the input
file) and an output file as arguments to perform a measurement.
The measurement setup itself is specified in the system, while the parameters
that are to be applied are specified in the input file.
For each line of the input file, all parameters are read out and saved into a
file of ascii or hdf5 format, depending on the system specifications
"""
import argparse
import math
import os
import re
import shlex
import socket
import sys
import time
import traceback

import urwid

from matr1x.system import MergedSystem
from matr1x.util import (
    flatten,
    flush_input,
    generate_col_index,
    nonblocking_getch,
    open_and_error,
    print_formatted_line,
    telemetry_string,
)

from .. import VALID_META_KEYS
from . import MATRIX_GUI_PORT

abortmap = {"q": 1, "a": 2, "f": 3}
# define abort conditions for different keys


def parse_inputfile(inputfile, system):
    """Read the input file and provides point by point set values needed for the measurement."""
    # define sorting algorithm
    def sort(arg):
        # get key
        key = arg[0]
        # properly handles "aa", "ab", "ba" and also logpoint (last)
        return sum((ord(c) - 96) * 26**i for (i, c) in enumerate(key[::-1]))
    # define the line parser for the matrix inputfile
    # parses parameters as 0 = -a val(s), 1 = -b val(s), etc.
    pointparser = argparse.ArgumentParser(add_help=False)
    for i in range(len(system.columns)):
        letter = generate_col_index(i)
        short_option = "-" + letter
        long_option = "-" + letter + "_value"
        pointparser.add_argument(short_option, long_option,
                                 default=system.default_values[i], nargs="*",
                                 type=float)
    # allow point with and without measurements
    pointparser.add_argument("--logpoint", default=1, nargs="?", type=int)
    # start parsing the input file
    with open(inputfile, 'r') as parameterfile:
        for nr, line in enumerate(parameterfile):
            # jump over comments
            if line[0] != "#":
                # divide the string into a list and
                # read the values into datapoint
                parameterlist = shlex.split(line)
                for i, arg in enumerate(parameterlist):
                    if (arg[0] == '-') and arg[1].isdigit():
                        parameterlist[i] = ' ' + arg
                # raw_input is a list: [known_args, unknown_args]
                raw_input = pointparser.parse_known_args(parameterlist)
                if raw_input[1] != []:
                    raise ValueError(
                        "Unrecognized argument in inputfile on "
                        f"line {nr}: {raw_input[1]}")
                # get the list with parameters from the parser and sort so that
                # order is maintained
                datapoint = [value for key, value
                             in sorted(vars(raw_input[0]).items(), key=sort)]
                # prepare values for system.set_value by casting to float
                for i in range(len(system.columns)):
                    # branch executed for parsed values
                    if isinstance(datapoint[i], (list, tuple)):
                        if len(datapoint[i]) == 1:
                            datapoint[i] = float(datapoint[i][0])
                        else:
                            datapoint[i] = [float(dp) for dp in datapoint[i]]
                    elif datapoint[i] is None:
                        pass
                    else:  # branch executed for defaults
                        datapoint[i] = float(datapoint[i])

                yield datapoint


def measurementloop(inputfile, system,
                    setvalcb=lambda s: None, readvalcb=lambda r: None,
                    telemetrycb=lambda s: None, inputcb=lambda n: 0):
    """Measurement loops with callback functions for visualization of the measurement and its progress."""
    # count number of setpoints for telemetry information
    points = 0
    with open(inputfile, 'r') as f:
        for line in f:
            if line.startswith("#"):
                continue
            points += 1
    telemetrycb(telemetry_string.format(0, points, 0, math.nan,
                                        math.nan, math.nan))
    # read the required number of columns in the input/ output file
    # initialize timer and counter for telemetry
    starttime = time.time()
    # every line in the file is one set of parameters
    for point_idx, datapoint in enumerate(parse_inputfile(inputfile, system)):
        # telemerty timer for setting time
        preset = time.time()
        # now apply values from input file
        setvalues = []
        for i, col in enumerate(system.columns):
            setv = system.set_value(i, datapoint[i])
            if setv is None and isinstance(col, (list, tuple)):
                setvalues.append([None, ]*len(col))
            else:
                setvalues.append(setv)
        setvalcb(flatten(setvalues))
        # telemetry timer for reading time
        preread = time.time()
        # do the actual measurements
        if datapoint[-1] == 1:  # logpoint argument
            # all values have been set, and a possible wait time has passed
            # now trigger all parameters in system
            system.trigger()
            # devices have been triggered, now read measurement
            return_list = system.take_measurement_point()
            # measurements have been saved to file, print to screen now
            readvalcb(return_list)

        # print the telemetry string to let people know where they are at
        elapsed = time.time() - starttime
        telemetrycb(
            telemetry_string.format(
                point_idx+1, points, elapsed/60,
                (elapsed/(point_idx+1)*points-elapsed)/60, preread-preset,
                time.time()-preread))
        # handle input on the end of one measurement point
        ret_input = inputcb(point_idx + 1)
        if ret_input != 0:
            return ret_input
    return 0


def measure_plain(inputfile, system, quiet=False):
    """
    Measurement loop with reduced output.

    Measurements can be with plain print output to the terminal or futhrer reduced
    output when quiet is set to True. This measurement mode is mainly used for
    continuous integration on Github actions and use on MS Windows.
    """

    def inputcb(n):
        key = nonblocking_getch()
        if key and key.lower() in ("q", "a", "f"):
            sys.stdout.write(f"Note: aborted with {key} after {n} points\n\n\n")
            system.add_comment(
                f"measurement aborted by keyboard input after {n} points"
            )
            return abortmap[key.lower()]
        if key in ('p', 'P'):
            sys.stdout.write("paused - continue with 'p'\n")
            system.add_comment("measurement paused by keyboard input")
            # wait for unpause with p
            while True:
                time.sleep(0.1)
                key = nonblocking_getch()
                if key and key.lower() in ("q", "a", "f"):
                    sys.stdout.write(f"Note: aborted with {key} after {n} points\n\n\n")
                    system.add_comment(
                        "measurement aborted by keyboard input " f"after {n} points"
                    )
                    return abortmap[key.lower()]
                if key in ('p', 'P'):
                    break
        return 0

    if not quiet:
        # print header
        print_formatted_line(list(flatten(system.columns)))
        print_formatted_line(list(flatten(system.units)))

        ret = measurementloop(inputfile, system,
                              lambda s: print_formatted_line(s, "Set : "),
                              lambda s: print_formatted_line(s, "Meas: "),
                              print, inputcb)
    else:
        ret = measurementloop(inputfile, system,
                              readvalcb=lambda s: print(
                                  ".", end="", flush=True),
                              inputcb=inputcb)
        print("")  # produce newline at end of measurement

    return ret


def measure_urwid(inputfile, systemfile, system):
    """Measurement loop with urwid based output to the terminal."""
    msg = ""
    # display some info
    info = urwid.Text(
        "Pause/Quit graciously with p/q after current cycle", align='center')
    outf = urwid.Text(" output filename : " +
                      system.filename + "\n", wrap='clip')
    inpf = urwid.Text(" Input filename  : " +
                      inputfile + "\n", wrap='clip')
    systemf = urwid.Text(" systemfile      : " +
                         ",".join(systemfile), wrap='clip')
    telemetry = urwid.Text("")
    status = urwid.Text("")
    parname = urwid.Text("par-name")
    setc = urwid.Text("set-val")
    readc = urwid.Text("readout")
    unitn = urwid.Text("unit")
    # create display containers
    columns_flat = list(flatten(system.columns))
    units_flat = list(flatten(system.units))
    params = [urwid.Text(col) for col in columns_flat]
    setval = [urwid.Text("") for col in columns_flat]
    readval = [urwid.Text("") for col in columns_flat]
    units = [urwid.Text(u) for u in units_flat]
    columns = urwid.Columns([urwid.Pile([parname, ] + params),
                             urwid.Pile([setc, ] + setval),
                             urwid.Pile([readc, ] + readval),
                             urwid.Pile([unitn, ] + units)])

    cont = urwid.Pile([info, outf, inpf, systemf, telemetry, status, columns])
    filler = urwid.Filler(cont)

    class UrwidContext(object):
        def __init__(self, topwidget):
            screen = None
            if os.environ.get('CI') == "true":
                screen = urwid.raw_display.Screen(input=None)
            self.loop = urwid.MainLoop(topwidget, screen=screen)
            self.loop.screen.set_input_timeouts(max_wait=0)

        def __enter__(self):
            self.loop.start()
            return self.loop

        def __exit__(self, exc_type, value, traceback):
            self.loop.stop()

    with UrwidContext(filler) as loop:
        loop.draw_screen()

        def setvalcb(setvalues):
            for i, setv in enumerate(flatten(setvalues)):
                if setv is not None:
                    setval[i].set_text(str(setv))
            loop.draw_screen()

        def readvalcb(return_list):
            for i, ret in enumerate(return_list):
                readval[i].set_text(str(ret))
            loop.draw_screen()

        def telemetrycb(tstr):
            telemetry.set_text(tstr)

        def inputcb(n):
            nonlocal msg
            for key in loop.screen.get_input():
                if isinstance(key, tuple):
                    # mouse presses result in tuple of shape
                    #  ("mouse release", 1, 35, 20)
                    # -> ignore those.
                    continue
                if key.lower() in ("q", "f", "a"):
                    msg += f"Note: aborted with {key} after {n} points"
                    system.add_comment(
                        "measurement aborted by keyboard input " f"after {n} points"
                    )
                    return abortmap[key.lower()]
                if key in ('p', 'P'):
                    msg += f"paused at {time.time()} after {n} points\n"
                    status.set_text("paused - continue with 'p'")
                    system.add_comment("measurement paused by keyboard input")
                    loop.draw_screen()
                    # wait for unpause with p
                    flag = True
                    while flag:
                        time.sleep(0.1)
                        for key in loop.screen.get_input():
                            if key.lower() in ("q", "f", "a"):
                                msg += f"Note: aborted with {key} after {n} points"
                                system.add_comment(
                                    "measurement aborted by "
                                    f"keyboard input after {n} "
                                    "points"
                                )
                                return abortmap[key.lower()]
                            if key in ('p', 'P'):
                                flag = False
                    status.set_text("")
                    loop.draw_screen()
                elif key == 'window resize':
                    loop.screen_size = None
            loop.draw_screen()
            return 0

        ret = measurementloop(inputfile, system, setvalcb,
                              readvalcb, telemetrycb, inputcb)

    return ret, msg


def main():
    """Read the command line and perform measurement accordingly."""
    # define the possible command line parameters
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--inputfile",
                        help="tuple input filename", required=True)
    parser.add_argument("-s", "--systemfile", nargs='*',
                        help="specifies system(s)")
    parser.add_argument("-o", "--outputfile", default=None,
                        help="Output filename")
    parser.add_argument("-af", "--append", action='store_true',
                        help="instead of appending a continuous number " +
                        "to the output file, append to output file.")
    parser.add_argument("-p", "--plain", action='store_true',
                        help="use plain output instead of the urwid library")
    parser.add_argument("-q", "--quiet", action='store_true',
                        help="produce reduced output (no measurement data)")

    # add keys to allow transmitting meta data
    for key in VALID_META_KEYS.keys():
        parser.add_argument(
            f"-d{key[:2].lower()}",
            f"--dc_{key.lower()}",
            default=None,
            help=f"Dublin Core meta data entry {key}",
        )

    # parse the command line
    options = parser.parse_args()

    # flush input buffer to avoid old inputs to mess with a new measurement
    flush_input()

    # initialize socket to GUI, done in the beginning to ensure that the GUI
    # is not stuck waiting for the connection
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect(("127.0.0.1", MATRIX_GUI_PORT))
    except ConnectionRefusedError:
        # GUI not running, just ignore this error
        client_socket = None

    # check input file header for system file information
    systemfile = None
    with open_and_error(options.inputfile, 'r') as (f, err):
        if err:
            print("matrix: error:", err)
            sys.exit(1)
        else:
            for line in f:
                system_pattern = r"^# [Ss]ystem filename : (.+)"
                settable_names_pattern = r"^# [Ss]ettable columns : (.+)"
                settable_units_pattern = r"^# [Ss]ettable units : (.+)"
                if match := re.match(system_pattern, line.strip()):
                    systemfile = match.group(1).split(",")
                elif match := re.match(settable_names_pattern, line.strip()):
                    settable_names_file = match.group(1).split(",")
                elif match := re.match(settable_units_pattern, line.strip()):
                    settable_units_file = match.group(1).split(",")
                if "#" != line[0]:
                    break

    # import self made libraries
    if options.systemfile is None:
        if systemfile is None:
            print("matrix: error: no system file specified")
            sys.exit(1)
        else:
            # find system from input file
            options.systemfile = systemfile
            # replace option with correct systems

    # merge all systems into new system (works also for single systems)
    try:
        system = MergedSystem.from_files(options.systemfile)
    except ModuleNotFoundError:
        print("matrix: error: system file does not exist")
        sys.exit(1)
    except PermissionError:
        print("matrix: error: system file not readable")
        sys.exit(1)

    # get columns from input file to verify input file was generated with the
    # same system version (i.e. has the same parameter names and units)
    _, settable_names, settable_units = system.settable_columns()

    # verify that input file has correct columns and units
    if ((settable_names != settable_names_file or
         settable_units != settable_units_file)):
        print(settable_names, settable_names_file)
        print(settable_units, settable_units_file)
        print("System seems to have changed since the input file was generated."
              " The input file might lead to unexpected values being set! "
              "Are you sure you want to continue?\n")
        resp = input("Please enter (y/n): ").strip()
        if "y" != resp:
            sys.exit(0)

    # obtain output file name and mode used to open the file
    output_filename = system.generate_datafilename(
        options.outputfile, options.inputfile, options.append)

    # report filename to GUI if GUI is active and close socket
    if client_socket is not None:
        client_socket.send(output_filename.encode())
        client_socket.close()

    # update the meta data with potential user input
    for key, editable in VALID_META_KEYS.items():
        if editable:
            # only parse user editable keys
            opt_val = getattr(options, f"dc_{key.lower()}")
            if opt_val is not None:
                system.dcdata[key] = opt_val

    # initialize devices and notify user what is going on
    print("setting devices")
    system.set(input_file=options.inputfile, output_file=output_filename)

    # acquire configuration from devices and notify user what is going on
    print("devices set, acquiring configuration and writing header")
    # initialize datefile and insert device query
    try:
        system.init_datafile(options.inputfile)
    except IOError:
        print("matrix: error: cannot create output file")
        sys.exit(1)
    except Exception:
        print("matrix: error: could not acquire configuration.")
        sys.exit(1)

    # do the loop
    print("entering loop now")
    # read the parameter input file
    try:
        # enforce plain interface on Windows because urwid would fail
        if options.plain or options.quiet or os.name == 'nt':
            control_string = "To pause or quit after next point, press p/q"
            if os.name != 'nt':
                control_string += " and enter"
            # print help string for pause in plain version
            print(control_string)
            ret = measure_plain(options.inputfile, system, quiet=options.quiet)
        else:
            ret, msg = measure_urwid(
                options.inputfile, options.systemfile, system)
            if msg:
                print(msg)
    except KeyboardInterrupt as e:
        print("Received keyboard interrupt, file may be corrupt!\n" +
              "Some devices may be in unknown state. Check traceback!\n" +
              "Traceback of error:\n")
        traceback.print_tb(e.__traceback__)
        ret = 1
    reset_kwargs = {
        "input_file": options.inputfile,
        "output_file": output_filename,
    }
    if ret == 1:
        x = input(
            "Shall the termination of the sequence lead to marking the "
            "datafile as aborted? (Y/n)"
        )
        if x.lower().startswith("y") or x == "":
            print("marking file as aborted")
            reset_kwargs["status"] = "aborted"
    if ret == 2:
        reset_kwargs["status"] = "aborted"
    if "status" not in reset_kwargs.keys():
        reset_kwargs["status"] = "finished"
    print("resetting devices")
    # reset system/devices
    system.reset(**reset_kwargs)
    # set returncode of the measurementloop as our exit status
    sys.exit(ret)
