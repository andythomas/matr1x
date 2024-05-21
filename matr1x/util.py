# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2023 matr1x developers. All rights reserved.
# ---
import datetime
import importlib.util
import os
import re
import subprocess
import sys
import sysconfig
import textwrap
import time
from os.path import abspath, exists, expanduser, isabs, splitext

import numpy as np

# conditional import for non-blocking io
if os.name == "nt":
    import msvcrt
else:
    import termios
    from select import select

# sweep functions for sweep generator
sweepFunctions = {"x^2": lambda x: np.power(x, 2), "sqrt": np.sqrt,
                  "ln": np.log, "log10": np.log10, "exp": np.exp,
                  "10^x": lambda x: np.power(10, x), "None": lambda x: x}

# default separator
default_separator = "\t"

# default output extension
output_extension = ".ma7"
# telemetry string template
telemetry_string = (" {:d}/{:d} - elapsed: {:.1f}m - remaining: " +
                    "{:.1f}m - set/read: {:.1f}s/{:.1f}s")


def get_matrix_binary():
    """
    check if matrix binary is on the path and otherwise try known python binary
    folders.

    This executes "matrix --help" to test if this works without error. If no
    executable is found an FileNotFoundError will be raised

    Returns
    -------
    binary_name
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
    # module path was defined, check that file exists
    if not isabs(filename):
        # get absolute path
        filename = abspath(filename)
    # create module specification from file and open
    spec = importlib.util.spec_from_file_location("dummyname",
                                                  filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # set the name of the system to reflect the filename
    mod.sys.__name__ = filename
    return mod


def generate_datafilename(system, outputfile="", inputfile="", append=False):
    """
    generate output datafile name. No file should be overwritten. If
    append=True an existing datafile can be amended. In all other cases a new
    file will name is generated.

    The datafilename will be generated either from the outputfile (preferred)
    or the inputfile-name. An appropriate extension is generated.

    Parameters
    ----------
    system: System instance
    outputfile: str, optional
      output filename which should be used. Potentially a running number will
      be added to avoid overwriting an existing file
    inputfile: str, optional
      if outputfile is empty this string will be used to generate a datafile
      name
    append: bool, optional
      flag to decide if one should append to an potentially existing datafile

    Returns
    -------
    datafilename, filemode
    """
    # check whether hdf5 is required and change output extensions
    if system.hdf5 is True:
        # append h5 to filename to discern filetypes
        file_extension = ".h5" + output_extension
    else:
        file_extension = output_extension
    refileext = file_extension.replace('.', r'\.')

    if outputfile:
        datafile = expanduser(outputfile)
    else:  # no output file given -> input filename as template
        datafile = expanduser(splitext(inputfile)[0])
    # check if file extension was provided
    if not re.search(f"{refileext}$", datafile):
        datafile = re.sub(r"(\.h5)?\.ma\d$", "", datafile) + file_extension
    if not exists(datafile):
        # use the unmodified file name
        return datafile, "w"
    elif append is True:
        return datafile, "w"  # here we return "w" because file does not exist
    else:
        # in case extension and running number are already attached to
        # the filename, replace in outputfile
        outfile = re.sub(r"(_\d+)?(\.h5)?\.ma\d$", "", datafile)

        # check filename and increase "extension number" to protect existing
        # data
        for extension in range(1, 10000):
            if exists(f"{outfile}_{extension}{file_extension}"):
                continue
            else:
                break

        if bool(append) is True and 0 != extension:
            # if there is a file with that name already, change to the append mode
            return f"{outfile}_{extension-1}{file_extension}", "a"
        else:
            # in this case start a new file
            # append the next possible number as file extension
            return f"{outfile}_{extension}{file_extension}", "w"


def print_formatted_line(vlist, prefix="", appendix="", column_width=10):
    """
    print a formated line with data values
    """
    entry_string = "{:>%d}  " % column_width
    sys.stdout.write(f"{prefix:>6}")
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
        sys.stdout.write(entry_string.format(vstr))
    sys.stdout.write(f"{appendix}\n")
    sys.stdout.flush()  # flush here is important for matrix_script


def generate_script_prefix_suffix(systems):
    """
    Definition of the prefix and suffix of the script used in matrix_script

    Parameters
    ----
    systems : list of system (file)names
      defines system that is supposed to be used

    Returns
    ----
    prefix : str
      prefix of a script that can be directly executed and allows to use
      the custom matrix_script syntax.
      Ends with try statement, so use script has to be indented by 4 spaces
    suffix : str
      corresponding suffix of the scriot, finishes the try statement
    """
    prefix = textwrap.dedent(f"""
    import inspect as _inspect
    import math as _math
    import os as _os
    import time as _time

    import matr1x as _matr1x
    import matr1x.util as _matrix_util

    from matr1x.system import MergedSystem as _MergedSystem

    _system = _MergedSystem.from_files([{", ".join(repr(s) for s in systems)}])

    # pass meta information
    _system.dcdata['Identifier'] = _sample
    _system.dcdata['Creator'] = _user
    _filename = ""  # datafile name
    _setvalues = []  # buffer for set values for printing
    _npoints = 0  # internal measurement point counter
    _ntot = None  # total number of measurement points for telemetry
    _starttime = _time.time()
    _preset = _starttime

    def lineno_decorator(func):
        def wrapper(*args, **kwargs):
            _report_line(_inspect.currentframe().f_back.f_lineno)
            return func(*args, **kwargs)
        return wrapper

    def _reset_setvalues():
        global _setvalues
        _setvalues = []
        for i, col in enumerate(_system.columns):
            if isinstance(col, (list, tuple)):
                _setvalues.append([None, ]*len(col))
            else:
                _setvalues.append(None)

    _reset_setvalues()  # initialize the setvalues variable
    # bring meta_data into namespace
    meta_data = _system.dcdata

    # redefine set_value to limit user typing requirements
    @lineno_decorator
    def set_value(col, value):
        '''
        wrapper for _system.set_values to allow storing all set parameters
        between two measurements
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

    @lineno_decorator
    def trigger_value(*args, **kwargs):
        _system.trigger_value(*args, **kwargs)

    @lineno_decorator
    def read_value(*args, **kwargs):
        return _system.read_value(*args, **kwargs)

    @lineno_decorator
    def wait(*args, **kwargs):
        _wait(*args, **kwargs)

    @lineno_decorator
    def print(*args, **kwargs):
        _print(*args, **kwargs)

    @lineno_decorator
    def input(*args, **kwargs):
        _input(*args, **kwargs)

    # initialize system and put devs into namespace
    print("setting devices")
    _system.set()  # here is a difference to matrix (no arguments), see PR #203
    devs = _system.devs

    @lineno_decorator
    def init_datafile(filename, comment="", append=False, print_header=True,
                      ntot=None):
        '''
        initialize the datafile for the matrix_script measurement. By default a
        new datafile will be generated whose name is generated in a way that no
        existing datafile can be overwritten.

        Parameters
        ----------
        filename: str
          name of the datafile to be used.
        comment: str, optional
          comment to be saved in the file header
        append: bool, optional
          flag to tell if an existing datafile should be used. If append is
          False a new datafile with a non-conflicting name will be generated by
          appending "_<number>" to the filename
        print_header: bool, optional
         flag to decide if the header information with column names and units
         should be printed
        ntot: int, optional
          total number of expected datapoints for estimation of remaining
          measurement time.
        '''
        global _filename, _ntot, _npoints, _starttime

        _ntot = ntot
        _npoints = 0  # reset the number of measurement points
        _starttime = _time.time()

        # generate fallback option for the datafile name
        systemstring = "__".join(['{"', '".join(map(os.path.basename, systems))}'])
        timestamp = _time.strftime(_matr1x.datetimefmt, _time.localtime())
        fallbackname = "%s_%s" % (timestamp, systemstring)

        _filename, mode = _matrix_util.generate_datafilename(
            _system,
            outputfile=filename,
            inputfile=_os.path.basename(_scriptname) or fallbackname,
            append=append)
        if append == False or not _os.path.exists(_filename):
            # write header to file
            print("running config query")
            query_dict = _system.query()
            print("configuration acquired, initializing file")
            _system.dcdata["Description"] = comment
            _matrix_util.write_matrix_header(
                _filename, mode, _scriptname or "matrix script generated",
                _system, query_dict)
        if print_header:
            _matrix_util.print_formatted_line(_matrix_util.flatten(_system.columns))
            _matrix_util.print_formatted_line(_matrix_util.flatten(_system.units))


    # wrap system.trigger and system.take_measurement_point into measure_system
    @lineno_decorator
    def measure_system(print_setpoint=True, print_data=True, print_telemetry=True):
        '''
        Perform the measurment of a single data point. This means a sequence of
        system.trigger, and reading the data is performed.

        Parameters
        ----------
        print_setpoint: bool, optional
         flag to decide if the column values set since the last measurement
         should be printed in a way combatible with the header information of
         init_datafile
        print_data: bool, optional
         flag to decide if the measured data values should be printed in a way
         combatible with the header information of init_datafile
        print_telemetry: bool, optional
         flag to decide if telemetry data about the measurement duration should
         be printed
        '''
        global _preset, _npoints
        if print_setpoint:
            _matrix_util.print_formatted_line(
                _matrix_util.flatten(_setvalues), prefix="Set : ")
        _reset_setvalues()
        # wait(0) to have breakpoint even when user does not use it in script
        wait(0)
        _npoints += 1
        preread = _time.time()
        if _filename == "":
            init_datafile("")
        _system.trigger()
        return_list = _system.take_measurement_point(_filename)
        if print_data:
            _matrix_util.print_formatted_line(return_list, prefix="Meas: ")
        if print_telemetry:
            elapsed = (_time.time() - _starttime)
            if _ntot:
                remaining = (elapsed/_npoints*_ntot-elapsed)/60
            else:
                remaining = _math.nan
            print(_matrix_util.telemetry_string.format(
                _npoints, _ntot or -1, elapsed/60, remaining, preread-_preset,
                _time.time()-preread))
        _preset = _time.time()
        return return_list


    # merge user input into script
    # ==== begin user area ====
    try:
    """)
    suffix = textwrap.dedent("""
    except KeyboardInterrupt:
        print("\\nscript has been aborted by user, calling reset")
    # ===== end user area =====
    # the reset function is called at the script end only, but we nevertheless
    # specify the last datafile name to be as close as possible to the behavior
    # of matrix
    _system.reset(output_file=_filename)
    """)
    return prefix, suffix


def generate_script(systems, user_script):
    """
    Definition of the general part of the script used in matrix_script

    Parameters
    ----
    systems : list of system (file)names
      defines system that is supposed to be used
    user_script : str
      custom user script that is typically provided by matrix_script, which is
      supposed to be executed.

    Returns
    ----
    script : str
      Script that can be directly executed and allows to use the custom
      matrix_script syntax.
      Returned script must be run in the context of the matrix_script_process
    """
    # define basic part of script, imports relevant commands
    prefix, suffix = generate_script_prefix_suffix(systems)
    if user_script.strip() == "":
        # if empty script is passed, avoid indendation error but otherwise
        # make script execution possible
        user_script = "pass"
    return prefix + textwrap.indent(user_script, "    ") + suffix


def matrix_script_process(filename, user="", sample="",
                          scriptname=""):
    """
    Process in which the script generated by generate_script is executed.
    Provides functionality to pause and gracefully quit the script execution
    at a breakpoint.

    temporary file is used to avoid difficulties with passing the full script
    as terminal argument.

    Arguments
    ----
    filename : str
      filename to the (temporary) file containing the script to be executed.
      Script in file should have been generated by generate_script.
    user : str
      user name that is written into the meta data of the output file
    sample : str
      sample name that is written into the meta data of the output file
    scriptname: str
      script name used as fallback template for the datafile name if its not
      set in the script.
    """
    # import required dependencies
    import re
    import socket
    import threading
    import traceback

    # only import port here to avoid util import from failing if GUI
    # applications are not installed
    from .scripts import MATRIX_SCRIPT_PORT

    # define killable thread to execute the script
    class ExecThread(threading.Thread):
        """
        Thread that handles the execution of the measurement script

        Arguments
        -----
        script : str
          Measurement script generated by generate_script
        sample : str
          sample name
        user : str
          user name
        """

        def __init__(self, script, sample, user, scriptname, socket):
            """ initialize all variable """
            super().__init__()
            self.script = script
            self.sample = sample
            self.user = user
            self.scriptname = scriptname
            self.pause_flag = False
            self.interrupt_flag = False
            self.recv_flag = False
            self.recv = ""
            self.n_pref = ""
            self.socket = socket

        def pause(self, state):
            """ pause the execution at the breakpoint """
            self.pause_flag = bool(state)
            if state is True:
                self.print("\npaused")

        def stop(self):
            """ set the interrupt flag, so that the execution is stopped at
                the breakpoint the execution at the breakpoint """
            self.interrupt_flag = True

        def breakpoint(self, sleep, message="", silent=10):
            """ breakpoint function that handles the interrupt as well
                as the waiting/sleep times

            The function prints out some message if the wait time exceeds the
            value of the silent argument.
            """
            t0 = time.time()
            end = datetime.datetime.today() + datetime.timedelta(seconds=sleep)
            if sleep > silent:
                msg = "" if not message else f" ({message})"
                until = f" until {end.strftime('%H:%M:%S')}"
                self.print(f"Waiting {sleep:.0f} seconds{msg}{until}")

            while (time.time() - t0) < sleep:
                now = time.time()
                remaining = sleep - (now - t0)
                if remaining > 1.1:
                    # if multiple seconds remaining, wait in chunks of 1s
                    if sleep > silent:
                        self.print(
                            f"\r{remaining:.0f} seconds remaining", end="")
                    time.sleep(1)
                else:
                    # wait remaining time
                    time.sleep(remaining)
                    if sleep > silent:
                        self.print("\rWaiting done")
                    break
                # interrupt during long waits to stop clock from ticking
                # is ignored for short waits
                self.check_for_interrupt_and_pause()
            # force one breakpoint independent of wait time (also for wait(0))
            self.check_for_interrupt_and_pause()

        def check_for_interrupt_and_pause(self):
            if self.interrupt_flag is True:
                # script will be aborted
                raise KeyboardInterrupt
            while self.pause_flag is True and self.interrupt_flag is False:
                # execution paused, wait for 100ms and recheck
                time.sleep(0.1)

        def input(self, message=""):
            t0 = time.time()
            if self.recv != "" and not self.recv_flag:
                self.recv = ""
            if "" == message:
                self.print("waiting for user input")
            else:
                self.print(message)
            while (self.recv == "" or self.recv_flag is True):
                time.sleep(0.1)
                if (time.time() - t0) > 60:
                    self.print("still waiting for user input")
                    t0 = time.time()
                self.check_for_interrupt_and_pause()
            # remove trailling line feed
            ret = self.recv.strip()
            # print output
            self.print(f"User input received: {ret}")
            self.recv = ""
            return ret

        # callback function that handles the input
        def handle_input(self, inp):
            """ handles input that is passed to the thread """
            if self.recv_flag is False:
                if inp == "p":
                    self.pause(not self.pause_flag)
                elif inp == "q":
                    self.stop()
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
            reports currently executing line number to the
            matrix-script
            format is __lineno{+-number of line}__
            """
            if self.socket is None:
                # only print line number if connected to a socket
                return
            self.print(f"__lineno{lineno-self.n_pref-1:d}__")

        def print(self, *args, **kwargs):
            """ reimplemented print that communicates via the socket  """
            end = kwargs.get("end", "\n")
            sep = kwargs.get("sep", " ")
            sendstr = sep.join(map(str, args)) + end + "\0"
            if self.socket is None:
                print(sendstr[:-1])
            else:
                self.socket.sendall(sendstr.encode("utf-8"))

        def run(self):
            """ run the script and provide meaningful error information
                if the script exits with an error """
            try:
                self.n_pref = len(
                    generate_script_prefix_suffix("")[0].split('\n')) - 1
                try:
                    _vars = {"_wait": self.breakpoint,
                             "_print": self.print,
                             "_report_line": self.report_line,
                             "_input": self.input,
                             "_user": self.user,
                             "_sample": self.sample,
                             "_scriptname": self.scriptname}
                    exec(self.script, _vars)
                except Exception:
                    self.print("script exited with error:")
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
                    tbstr = tbstr.replace("file \"<string>\"",
                                          "\"{}\"".format(
                                              self.script.split("\n")[line-1]))
                    self.print(tbstr)
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
        thread = ExecThread(script, sample, user, scriptname, client_socket)
    else:
        thread = ExecThread(script, sample, user, scriptname, None)

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
        # close socket
        client_socket.close()


def flush_input():
    """
    flush the input buffer to get only fresh input later on
    """
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
    offers a cross-platform nonblocking implementation of getch

    In a linux terminal, enter has been pressed to trigger the getch, as
    otherwise the stdin is not flushed.

    Arguments
    ----
    callback : function handle (optional)
        should be a function that takes the character and performs some
        action with it

    Returns
    ----
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
def calculate_sweep(sweepParms, loopOver, upDown, repeat, functions):
    """
    Generates a list of sweeps defined by given parameters

    Arguments
    ------
    sweepParms : list
      List of lists containing the sweep parameters (as 3 item list)
    loopOver : list
      List of integers(<len(loopOver)) defining the looping scheme
    upDown : list
      List of bools defining if the sweep is going both ways
    repeat : list
      List of integers defining how often the sweep ranges are repeated

    Returns
    ------
    sweep : list
      List of sweep that contains all parameters that are to be set, individual
      sweeps from columns still need to be stretched to equal length (sparse).
      Otherwise, loop over is not handled properly.

    Example
    -----
    sweepParms -- [[[1, 2, 2], [3, 4, 2]], [], [[-1, 1, 2]]]
    loopOver -- [-1, -1, 0]
    upDown -- [True, False, False]
    repeat -- [1, 1, 1]
    functions -- [None, sin, None]
    returns [[1.0, 2.0, 3.0, 4.0, 4.0, 3.0, 2.0, 1.0], [],
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

                sweepRange = sweepFunctions[functions[indexS]](
                    np.linspace(float(parm[0]), float(parm[1]),
                                int(parm[2])))
                if any(np.isnan(sweepRange)) or any(np.isinf(sweepRange)):
                    return ("Inf or Nan in sweep, check functions and " +
                            "parameters")
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
    Recursive function for checking the occurence of occurences.

    Arguments
    -----
    index : int
      index of the item in array for which the hirarchy is to be determined
    array : list
      the array defining the hirarchy
    depth : int, optional
      recursion depth, does not need to be set when calling the function

    Returns
    -----
    hirarchy : int
      hirarchy of the item index within the given array

    Example
    -----
      * check_dep(0, [-1, -1, 1, 2]) returns 0 as index 0 is not referenced
      * check_dep(1, [-1, -1, 1, 2]) returns 2 as index 1 is referenced by
        index 2 which is in turn referenced by index 3
      * check_dep(2, [-1, -1, 1, 2]) returns 1 as index 2 is referenced by
        index 3
      * check_dep(3, [-1, -1, 1, 2]) returns 0 as index 3 is not referenced
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
            for j in range(cnt):
                # follow all branches of the occurences to get the actual
                # maximum hirarchy of the occurence
                occ = array.index(index, occ+1)
                d.append(check_dep(occ, array, depth+1))
            return max(d)
        else:
            return check_dep(array.index(index), array, depth+1)
    else:
        # if no more occurence is in the array, then return the current depth
        return depth


def generate_col_index(index):
    """
    generates the column indices for matrix/sweep generator etc.
    currently can handle 701 columns and is easily extendable
    format is "a" -> "z" -> "aa" -> "az" -> "ba" -> etc.
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
    prepares query_string from output of system.query to include in file header
    Format is specified as
    ## dev1
    ### key1 : value1
    ### key2 : value2
    ## dev2 ... and so on
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
                v = v.replace("\n", "\n" + "#"*(depth+1))
                v = v.replace('"', '\"')
            ret += "#"*depth + f" {k} : \"{v}\"\n"
    return ret


def write_matrix_header(output_filename, output_filemode, inputfile, system,
                        query_dict):
    """
    prepares the header of a matrix file for the matrix program, inserts all
    relevant information including the setstr

    Arguments
    ----
    output_filename : str
      filename of the ouput file
    output_filemode : str
      controls whether append is true, can be "w" or "a", if mode is "a" do not
      add the header a second time
    inputfile : str
      filename of the inputfile to be placed in the header
    system : System
      The System object that is used for the measurement.
    query_dict : dict
        Gives the device settings returned by the device_query
        function to be appended to the file header
    """
    if "a" == output_filemode:
        # in case append is true, do not create a new header
        return
    # prepare file definitions (column header and units)
    telemetry = [list(flatten(system.columns)),
                 list(flatten(system.units))]
    # prepare datafile
    print(f"Creating new datafile: {output_filename}")
    if system.hdf5 is True:
        telemetry.append(list(flatten(system.chunks, types=(list, ))))
        import h5py
        with h5py.File(output_filename, 'w', libver='latest') as data_file:
            data_file.swmr_mode = True
            assert data_file.swmr_mode
            data_file.attrs["Input filename"] = inputfile
            data_file.attrs["System filename"] = system.__name__
            data_file.attrs["Device query"] = construct_query_string(
                query_dict)
            for dckey, dcvalue in system.dcdata.items():
                if dcvalue is None:
                    # mark non-existing value
                    data_file.attrs[f"DC.{dckey}"] = "__None__"
                else:
                    data_file.attrs[f"DC.{dckey}"] = dcvalue

            init_hdf5_skel(data_file, *telemetry)
    else:
        telemetry += [default_separator]
        with open(output_filename, 'w', encoding="utf-8") as data_file:
            for dckey, dcvalue in system.dcdata.items():
                if dcvalue is None:
                    data_file.write(f"# DC.{dckey} : None\n")
                else:
                    dcentry = dcvalue.replace("\n", "\n## ")
                    dcentry = dcentry.replace('"', '\"')
                    data_file.write(f"# DC.{dckey} : \"{dcentry}\"\n")
            data_file.write(f"# Input filename : \"{inputfile}\"\n")
            data_file.write("# System filename : ")
            data_file.write("\"" + system.__name__ + "\"\n")
            data_file.write("# Device query : \n")
            data_file.write(construct_query_string(query_dict))

            init_ascii_header(data_file, *telemetry)


def init_ascii_header(file_handle, columns, units, separator):
    """
    Initialize the header of the measurement file using the given telemetry

    Parameters
    -----
    file_handle : opened file
      file that the header should be written to
    columns : list
      column names written into the header
    units : list
      column units to be written into the header
    """
    file_handle.write(separator.join(columns) + "\n")
    file_handle.write(separator.join(units) + "\n")
    file_handle.write(separator.join(columns) + "\n")


def init_hdf5_skel(file_handle, columns, units, chunks):
    """
    Initialize a HDF5 file skeleton for a measurement file.

    Parameters
    -----
    file_handle : opened file
      h5py file that the header should be written to
    columns : list
      column names written into the header
    units : list
      column units to be written into the header
    chunks : list
      list of ints that define the chunk length of the individual datasets
    """
    data_grp = file_handle.create_group("data")
    for col, uni, chu in zip(columns, units, chunks):
        if isinstance(chu, tuple):
            data_grp.create_dataset(col, (0, *chu), maxshape=(None, *chu),
                                    chunks=(1, *chu), dtype="f8")
        else:
            data_grp.create_dataset(col, (0,), maxshape=(None,),
                                    chunks=(chu,), dtype="f8")
        data_grp[col].attrs["unit"] = uni


def flatten(iterable, types=(tuple, list, np.ndarray)):
    """
    Recursively flatten a list to have only one dimension left
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
    returns the Pt100 equivalent temperature according to Wikipedia
    coefficients
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
        """
        Parameters
        ----------
        dtype: int, float, str, ...
          data-type of the connected variable
        setfunc: function(value, *args)
          setter function to change the connected variable
        getfunc: function(value, *args)
          getter function to obtain the value of the variable
        setargs: tuple, or None
          optional additonal arguments for the setter function
        getargs: tuple, or None
          optional arguments for the getter function
        polling_cmd: str or None
          optional command to poll to check if the setpoint was reached

        Note: setfunc/getfunc can also be a list/tuple with a device name and
        device property.
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
        return self.__str__()

    def __str__(self):
        r = f"{self.__class__.__name__}: {self.dtype}, {self.setfunc}"
        if self.setargs:
            r += "({self.setargs})"
        r += f", {self.getfunc}"
        if self.getargs:
            r += f"({self.getargs})"
        return r

    def reset_to_None(self):
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
    """
    Class representing a Getter-command of a ControlGUI
    """

    def __init__(self, dtype, getfunc, getargs=None):
        """
        Parameters
        ----------
        dtype: int, float, str, ...
          data-type of the connected variable
        getfunc: function(value, *args)
          getter function to obtain the value of the variable
        getargs: tuple, or None
          optional arguments for the getter function
        """
        super().__init__(dtype, setfunc=None, getfunc=getfunc, getargs=getargs)


class Set(Command):
    """
    Class representing a Setter-command of a controlGUI
    """

    def __init__(self, dtype, setfunc, setargs=None, polling_cmd=None):
        """
        Parameters
        ----------
        dtype: int, float, str, ...
          data-type of the connected variable
        setfunc: function(value, *args)
          setter function to change the connected variable
        setargs: tuple, or None
          optional additonal arguments for the setter function
        polling_cmd: str or None
          optional command to poll to check if the setpoint was reached
        """
        super().__init__(dtype, setfunc, getfunc=None, setargs=setargs,
                         polling_cmd=polling_cmd)


def normalize_cmds(cmds):
    """
    make all commands instances of Command

    changes are performed inplace
    """
    # harmonize the cmds dictionary -> convert all to Command
    for cmd, val in cmds.items():
        if not isinstance(val, Command):
            cmds[cmd] = Command.from_deprecated_list(val)
