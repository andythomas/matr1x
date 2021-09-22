# Library containing all independent functionality for GUI
# applications and measurement procedures

import importlib
import os
import sys
import threading
import time
from os.path import abspath, isabs, isfile, splitext

import h5py
import numpy as np

from . import system as sl

# conditional import for non-blocking io
if os.name == "nt":
    import msvcrt
else:
    from select import select

# sweep functions for sweep generator
sweepFunctions = {"x^2": lambda x: np.power(x, 2), "sqrt": np.sqrt,
                  "ln": np.log, "log10": np.log10, "exp": np.exp,
                  "10^x": lambda x: np.power(10, x), "None": lambda x: x}

# default separator
default_separator = "\t"

# default output extension
output_extension = ".ma7"


def import_system(filename):
    """
    Utility function to load system files from an arbitrary directory. If a
    file with the given name cannot be found the system installed files are
    searched for.

    Parameters
    ------
    filename : string
      path to file (can include '.py' extension)

    Returns
    -----
    system : System
      System as defined in the file
    """
    # this is necessary for sweep_generator and likely matrix_script as
    # otherwise some parameters might be still stored in the matr1x.system
    # module
    importlib.reload(sl)

    normfilename = filename.strip()
    if isfile(normfilename):
        # module path was defined, check that file exists
        if not isabs(normfilename):
            # get absolute path
            normfilename = abspath(normfilename)
        # create module specification from file and open
        spec = importlib.util.spec_from_file_location("dummyname",
                                                      normfilename)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # set the name of the system to reflect the filename
        mod.sys.__name__ = normfilename
    else:  # no file found, try installed system files
        modname = splitext(normfilename)[0]
        mod = importlib.import_module("." + modname, "matr1x.systems")
        mod.sys.__name__ = modname
    return mod.sys


def merge_systems(system_filenames):
    """
    Merges two systems, where the first should be the magnet setup
    and the second one the one used for measurements

    Parameters
    -----
    system_filenames : list
      list of system paths that should be merged

    Returns
    ----
    system : MergedSystem
      MergedSystem instance that contains the descirption of all subsystems
    """
    systems = []
    for filename in system_filenames:
        # import the individual systems
        systems.append(import_system(filename))
    # this is necessary for sweep_generator and likely matrix_script as
    # otherwise some parameters might be still stored in the matr1x.system
    # module
    importlib.reload(sl)
    # return merged system
    return sl.MergedSystem(systems)


def grab_system_information(systems, settables=False):
    """
    Utility function to obtain meta information from a system

    Imports a set of systems and imports these as matrix would do it.
    Depending on settables, a human readable description of the system (devices
    and parameters) is returned, or the number of settable columns.

    The function is used by matrix_script to verify the system still
    corresponds to the definition with which the script was created.
    Additionally, it is used to generate the help string.

    Parameters
    ----
    systems : list
      List of system (file)names that should be imported
    settables : boolean, optional
      controls whether to return the settable columns of the system (if True)
      or whether a human readble string with the system definition is returned.

    Returns
    ----
    system_descriptor : string
      Returns a string with the list of devices and a string with
      parameters that are available in the system (name + index)
      Alternatively, returns the settable columns of the system
    """
    sys = merge_systems(systems)
    if settables is True:
        # return only settables
        return get_settable_columns(sys)
    else:
        # generate string from devices, iterates over subsystems
        dev_list = []
        for dev, devtype in sys.devs.items():
            dev_list.append(f"{dev} <> {devtype}\n")
        dev_string = "device <> device type\n----------\n" + "".join(dev_list)
        # generate string from setable parameters
        par_list = []
        for index, param in enumerate(sys.parameters):
            if param.setter is not None:
                par_list.append(f"{index} <y> {param.name}\n")
            else:
                par_list.append(f"{index} <n> {param.name}\n")
        par_string = ("index <settable> parameter\n----------\n" +
                      "".join(par_list))
        return "----------\n".join((dev_string, par_string))


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
    script = "import matr1x.util as mu\n"
    script += "s = mu.merge_systems("
    script += "[\"{}\"])\n".format("\", \"".join(systems))
    # pass meta information
    script += "s.dcdata[\"Identifier\"] = self.sample\n"
    script += "s.dcdata[\"Creator\"] = self.user\n"
    # redefine set_value to limit user typing requirements
    script += "set_value = s.set_value\n"
    # script += "trigger_value = s.trigger_value\n"
    script += "read_value = s.read_value\n"
    # define wait function and connect to thread breakpoint
    script += "wait = self.breakpoint\n"
    script += "print = self.print\n"
    script += "s.set()\n"
    script += "devs = s.devs\n"
    # separate trigger system, I think this will not be required
    # script += "def trigger_system(util=mu,sys=s):\n"
    # script += " util.trigger_system(sys)\n"
    # wrap trigger_system into measure_system
    script += "def measure_system(fname,comment='',\n"
    script += "                   util=mu,sys=s, w=wait):\n"
    # wait(0) to have breakpoint even when user does not use it in script
    script += " w(0)\n"
    script += " util.trigger_system(sys)\n"
    script += " return util.measure_system(fname,sys,comment)\n\n"
    script += "# ==== begin user area ====\n"
    # merge user input into script
    script += user_script + "\n"
    script += "# ===== end user area =====\n"
    script += "s.reset()"
    return script


def matrix_script_process(filename, user="", sample=""):
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
    """
    # import required dependencies
    import re
    import traceback

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

        def __init__(self, script, sample="", user=""):
            """ initialize all variable """
            super().__init__()
            self.script = script
            self.sample = sample
            self.user = user
            self.pause_flag = False
            self.interrupt_flag = False

        def pause(self, state):
            """ pause the execution at the breakpoint """
            self.pause_flag = bool(state)
            if state is True:
                self.print("paused")

        def stop(self):
            """ set the interrupt flag, so that the execution is stopped at
                the breakpoint the execution at the breakpoint """
            self.interrupt_flag = True

        def breakpoint(self, sleep):
            """ breakpoint function that handles the interrupt as well
                as the waiting/sleep times """
            sleep_mod = sleep % 1
            sleep = int(sleep)
            for i in range(sleep):
                time.sleep(1)
            time.sleep(sleep_mod)
            while self.pause_flag is True and self.interrupt_flag is False:
                time.sleep(0.5)
            if self.interrupt_flag is True:
                raise KeyboardInterrupt

        def print(self, *args):
            """ reimplemented print that directly flushes the stdout """
            print(*args)
            sys.stdout.flush()

        def run(self):
            """ run the script and provide meaningful error information
                if the script exits with an error """
            try:
                try:
                    exec(self.script)
                except Exception:
                    self.print("script exited with error:")
                    # get traceback information and format accordingly
                    tbinfo = traceback.format_exception(*sys.exc_info())
                    tbstr = "".join(tbinfo[2:])
                    # get line information from traceback
                    ms = re.search(r"line (\d+)", tbstr)
                    line = int(ms.group(1))
                    # replace line number to match the user defined script
                    tbstr = re.sub(r"line (\d+)",
                                   "line " + str(int(ms.group(1))-18), tbstr)
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

    # initialize the thread and the paused flag
    thread = ExecThread(script, sample, user)
    paused = False

    # callback function that handles the input
    def handle_input(inp):
        nonlocal thread, paused
        if inp == "p":
            paused = not paused
            thread.pause(paused)
        elif inp == "q":
            thread.stop()
        elif inp == "k":
            thread.terminate()

    # start the thread that runs the script
    thread.start()

    # wait until the thread is finished while waiting for input on (piped) stdin
    while thread.is_alive():
        # this sleep prevents a deadlock scenario which otherwise heavily slows
        # down matrix_script execution
        time.sleep(0.1)
        nonblocking_getch(handle_input)


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
      List of booleans defining if the sweep is going both ways
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
    while(0 <= hCnt):
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


def get_settable_columns(system):
    """
    Function to obtain the settable columns for a given system. Used by matrix
    and matrix_script to verify that the input file/input script was generated
    with the same system as the one that is currently used.

    Parameters
    ----
    system : System
      System of which the settable columns should be returned

    Returns
    ----
    settables : list
      list of booleans describing whether a parameter is settable or not
    flattened_settable_names : list
      list of strings containing the names of the settable columns
    flattened_settable_units : list
      list of strings containing the units of the settable columns
    """
    settables = [(False if par.setter is None else True)
                 for par in system.parameters]
    flattened_settable_names = []
    flattened_settable_units = []
    for names, units, settable in zip(system.columns,
                                      system.units,
                                      settables):
        if settable is True:
            if isinstance(names, (list, tuple)):
                for name, unit in zip(names, units):
                    flattened_settable_names.append(name)
                    flattened_settable_units.append(unit)
            else:
                flattened_settable_names.append(names)
                flattened_settable_units.append(units)
    return (settables, flattened_settable_names, flattened_settable_units)


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


def take_measurement_point(output_filename, system):
    """
    takes one reading from all device specified in system
    """
    return_list = []
    if system.hdf5 is True:
        for i, col in enumerate(system.columns):
            return_value = system.read_value(i)
            with h5py.File(output_filename, "a") as data_file:
                if isinstance(col, (list, tuple)):
                    for j, column in enumerate(col):
                        dat = data_file["data/" + column]
                        csize = dat.chunks[0]
                        if csize > 1:
                            return_list.append(f"[{return_value[j][0]}, ...]")
                        else:
                            return_list.append(return_value[j])
                        dat.resize(dat.shape[0]+csize, axis=0)
                        dat[-csize:] = return_value[j]
                else:
                    dat = data_file["data/" + col]
                    csize = dat.chunks[0]
                    if csize > 1:
                        return_list.append(f"[{return_value[0]}, ...]")
                    else:
                        return_list.append(return_value)
                    dat.resize(dat.shape[0]+csize, axis=0)
                    dat[-csize:] = return_value
    else:
        for i in range(len(system.columns)):
            return_value = system.read_value(i)
            if isinstance(return_value, (np.ndarray, list, tuple)):
                # in case we get a list, (numpy array or) tuple cast
                # to list and append
                return_list += list(return_value)
            else:
                return_list.append(return_value)
        with open(output_filename, "a") as datafile:
            # write datapoint to file
            datafile.write(default_separator.join(str(v) for v in return_list))
            datafile.write("\n")

    # return device readout as list
    return return_list


def trigger_system(system):
    """
    triggers all devices in system by calling the trigger function with
    specified in the system
    """
    for i in range(len(system.columns)):
        system.trigger_value(i)


def measure_system(filename, system, comment=""):
    """
    takes one reading and takes care of initializing file in case it has to be
    newly initalized, script is not saved in the header!

    Design decision about whether or not to allow concurrent writes to file
    is still necessary, ideally one would copy matrix appraoch for file
    generation
    """
    # normalize filename to have correct ending
    if system.hdf5 is True:
        if ".h5" + output_extension not in filename:
            filename += ".h5" + output_extension
    else:
        if output_extension not in filename:
            filename += output_extension
    try:
        temp_file = open(filename, "r")
        temp_file.close()
    except IOError:
        # file is not yet initialized with header etc, needs to be done.
        # prepare parameters for handover
        if hasattr(system, "subsys"):
            sys_list = [subsys.__name__ for subsys in system.subsys]
        else:
            sys_list = [system.__name__]
        # write header to file
        print("running config query")
        query_dict = system.query()
        print("configuration acquired, initializing file")
        print("  ".join(list(flatten(system.columns))))
        print("  ".join(list(flatten(system.units))))
        system.dcdata["Description"] = comment
        write_matrix_header(filename, "w", "matrix script generated", sys_list,
                            system, query_dict)
    return_list = take_measurement_point(filename, system)
    return_str = [f"{str(retval):>10.10s}" for retval in return_list]
    return " ".join(return_str)


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


def write_matrix_header(output_filename, output_filemode, inputfile,
                        systemfile, system, query_dict):
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
    systemfile : str
      filename(s) of the system files that are used to generate the (merged)
      system which defines the measurement.
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
    if system.hdf5 is True:
        telemetry += [list(flatten(system.chunks))]
        with h5py.File(output_filename, 'w') as data_file:
            data_file["input_filename"] = inputfile
            data_file["system_filename"] = ",".join(systemfile)
            data_file["device_query"] = construct_query_string(query_dict)
            for dckey, dcvalue in system.dcdata.items():
                if dcvalue is None:
                    data_file[dckey] = "__None__"  # mark non-existing value
                else:
                    data_file[dckey] = dcvalue

            init_hdf5_skel(data_file, *telemetry)
    else:
        telemetry += [default_separator]
        with open(output_filename, 'w') as data_file:
            print(f"Creating new datafile: {output_filename}")
            for dckey, dcvalue in system.dcdata.items():
                if dcvalue is None:
                    data_file.write(f"# DC.{dckey} : None\n")
                else:
                    dcentry = dcvalue.replace("\n", "\n## ")
                    dcentry = dcentry.replace('"', '\"')
                    data_file.write(f"# DC.{dckey} : \"{dcentry}\"\n")
            data_file.write(f"# Input filename : \"{inputfile}\"\n")
            data_file.write("# System filename : ")
            data_file.write("\"" + ",".join(systemfile).strip() + "\"\n")
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
        data_grp.create_dataset(col, (0,), maxshape=(None,),
                                chunks=(chu,), dtype="f8")
        data_grp[col].attrs["unit"] = uni


def flatten(iterable):
    """
    Recursively flatten a list to have only one dimension left
    """
    for el in iterable:
        if ((isinstance(el, (tuple, list, np.ndarray)) and not
             isinstance(el, (str, bytes)))):
            yield from flatten(el)
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
