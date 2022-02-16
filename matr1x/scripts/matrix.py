# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2022 matr1x developers. All rights reserved.
# ---
"""
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
import shlex
import socket
import sys
import time
import traceback

import urwid
from matr1x.util import (flatten, flush_input, generate_col_index,
                         generate_datafilename, get_settable_columns,
                         merge_systems, nonblocking_getch, print_formatted_line,
                         take_measurement_point, telemetry_string,
                         trigger_system, write_matrix_header)

from . import MATRIX_GUI_PORT


def report_filename_to_gui(filename):
    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        clientSocket.connect(("127.0.0.1", MATRIX_GUI_PORT))
    except ConnectionRefusedError:
        # GUI not running, just ignore this error
        return
    clientSocket.send(filename.encode())


def parse_inputfile(inputfile, system):
    """
    reads the input file and provides point by point set values needed for the
    measurement
    """
    # define sorting algorithm
    def sort(arg):
        # get key
        key = arg[0]
        # properly handles "aa", "ab", "ba" and also logpoint (last)
        return sum([(ord(c)-96)*26**i for i, c in enumerate(key[::-1])])
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
            if (line[0] != "#"):
                # divide the string into a list and read the values into datapoint
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


def measurementloop(inputfile, output_filename, system,
                    setvalcb=lambda s: None, readvalcb=lambda r: None,
                    telemetrycb=lambda s: None, inputcb=lambda n: 0):
    """
    measurement loops with callback functions for visualization of the
    measurement and its progress
    """
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
            trigger_system(system)
            # devices have been triggered, now read measurement
            return_list = take_measurement_point(output_filename, system)
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
        if inputcb(point_idx+1) != 0:
            break
    return 0


def measure_plain(inputfile, output_filename, system):
    """
    measurement loop with plain print output to the terminal
    (mainly for continuous integration on Github actions)
    """

    def inputcb(n):
        key = nonblocking_getch()
        if key in ('q', 'Q'):
            sys.stdout.write(f"Note: aborted with q after {n} points\n\n\n")
            return 1
        elif key in ('p', 'P'):
            sys.stdout.write("paused - continue with 'p'\n")
            # wait for unpause with p
            while True:
                time.sleep(0.1)
                key = nonblocking_getch()
                if key in ('q', 'Q'):
                    sys.stdout.write(
                        f"Note: aborted with q after {n} points\n\n\n")
                    return 1
                elif key in ('p', 'P'):
                    break
        return 0

    # print header
    print_formatted_line(list(flatten(system.columns)))
    print_formatted_line(list(flatten(system.units)))
    ret = measurementloop(inputfile, output_filename, system,
                          lambda s: print_formatted_line(s, "Set : "),
                          lambda r: print_formatted_line(r, "Meas: "),
                          lambda t: print(t),
                          inputcb)

    return ret


def measure_urwid(inputfile, output_filename, systemfile, system):
    """
    measurement loop with urwid based output to the terminal
    """
    msg = ""
    # display some info
    info = urwid.Text(
        "Pause/Quit graciously with p/q after current cycle", align='center')
    outf = urwid.Text(" output filename : " +
                      output_filename + "\n", wrap='clip')
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

        def __exit__(self, type, value, traceback):
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
                if key in ('q', 'Q'):
                    msg += f"Note: aborted with q after {n} points"
                    return 1
                elif key in ('p', 'P'):
                    msg += f"paused at {time.time()} after {n} points\n"
                    status.set_text("paused - continue with 'p'")
                    loop.draw_screen()
                    # wait for unpause with p
                    flag = True
                    while flag:
                        time.sleep(0.1)
                        for key in loop.screen.get_input():
                            if key in ('q', 'Q'):
                                msg += f"Note: aborted with q after {n} points"
                                return 1
                            elif key in ('p', 'P'):
                                flag = False
                    status.set_text("")
                    loop.draw_screen()
                elif key == 'window resize':
                    loop.screen_size = None
            loop.draw_screen()
            return 0

        ret = measurementloop(inputfile, output_filename, system, setvalcb,
                              readvalcb, telemetrycb, inputcb)

    return ret, msg


def main():
    # define the possible command line parameters
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--inputfile",
                        help="tuple input filename", required=True)
    parser.add_argument("-s", "--systemfile", nargs='*',
                        help="specifies system(s)")
    parser.add_argument("-o", "--outputfile", default=None,
                        help="Output filename")
    parser.add_argument("-m", "--comment", default=None,
                        help="arbritary comment string")
    parser.add_argument("-u", "--user", default=None,
                        help="Name of the operator/user for the data file header")
    parser.add_argument("-S", "--sample", default=None,
                        help="sample identification for the data file header")
    parser.add_argument("-af", "--append", default=0, type=int,
                        help="instead of appending a continuous number" +
                        "to the output file, append to last file")
    parser.add_argument("-p", "--plain", action='store_true',
                        help="use plain output instead of the urwid library")

    # parse the command line
    options = parser.parse_args()

    # flush input buffer to avoid old inputs to mess with a new measurement
    flush_input()

    # check input file header for system file information
    systemfile = None
    with open(options.inputfile, 'r') as f:
        for line in f:
            if "# System" in line:
                systemfile = line.replace(
                    "# System filename : ", "").split(",")
            if "# Settable columns" in line:
                settable_names_file = line.strip().replace(
                    "# Settable columns : ", "").split(",")
            if "# Settable units" in line:
                settable_units_file = line.strip().replace(
                    "# Settable units : ", "").split(",")
            if "#" != line[0]:
                break

    # import self made libraries
    if options.systemfile is None:
        if systemfile is None:
            exit("no system file specified")
        else:
            # find system from input file
            options.systemfile = systemfile
            # replace option with correct systems

    # merge all systems into new system (works also for single systems)
    system = merge_systems(options.systemfile)

    # get columns from input file to verify input file was generated with the
    # same system version (i.e. has the same parameter names and units)
    settable, settable_names, settable_units = get_settable_columns(system)

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
            exit()

    # obtain output file name and mode used to open the file
    output_filename, output_filemode = generate_datafilename(
        system, options.outputfile, options.inputfile, options.append)
    report_filename_to_gui(output_filename)

    # initialize devices and notify user what is going on
    print("setting devices")
    system.set(input_file=options.inputfile, output_file=output_filename)

    # acquire configuration from devices and notify user what is going on
    print("devices set, acquiring configuration")
    query_dict = system.query()

    # initialize header and insert command line options into measurement
    # file (can include device config etc.)
    if options.comment is not None:
        system.dcdata["Description"] = options.comment
    if options.user is not None:
        system.dcdata["Creator"] = options.user
    if options.sample is not None:
        system.dcdata["Identifier"] = options.sample
    write_matrix_header(output_filename, output_filemode,
                        options.inputfile, system, query_dict)

    # do the loop
    print("entering loop now")
    # read the parameter input file
    try:
        # enforce plain interface on Windows because urwid would fail
        if options.plain or os.name == 'nt':
            control_string = "To pause or quit after next point, press p/q"
            if os.name != 'nt':
                control_string += " and enter"
                # print help string for pause in plain version on windows
            print(control_string)
            ret = measure_plain(options.inputfile, output_filename, system)
        else:
            ret, msg = measure_urwid(options.inputfile, output_filename,
                                     options.systemfile, system)
            if msg:
                print(msg)
    except KeyboardInterrupt as e:
        print("Received keyboard interrupt, file may be corrupt!\n" +
              "Some devices may be in unknown state. Check traceback!\n" +
              "Traceback of error:\n")
        traceback.print_tb(e.__traceback__)
        ret = 1
    print("resetting devices")
    # reset system/devices
    system.reset()
    # set returncode of the measurementloop as our exit status
    sys.exit(ret)
