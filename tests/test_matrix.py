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

"""Matrix test module.

This module contains tests for the matrix data acquisition software.
"""

import glob
import os
import subprocess
import sys
import tempfile

import matr1x.eval
import matr1x.util
import pyflakes.api
import pytest
from matr1x import output_extension

path = os.path.dirname(os.path.realpath(__file__))


@pytest.fixture(autouse=True)
def clean_data_files():
    """Clean up data files created during tests.

    This fixture runs automatically before and after each test to clean up any
    data files that were created. It tracks existing files before the test and
    removes any new files created during test execution.

    Yields
    ------
    None
    """
    existingfiles = glob.glob(os.path.join(path, f"*{output_extension}"))
    # run test
    yield
    files = glob.glob(os.path.join(path, f"*{output_extension}"))
    newfiles = set(files) - set(existingfiles)
    for f in newfiles:
        os.remove(f)


def test_matrix_dummy():
    """Test basic matrix functionality with dummy sweep data.

    Tests running matrix with a simple dummy sweep input file and verifies
    the output data file format and contents.

    Asserts
    -------
    return code is 0
    exactly one new file is created
    output has 6 data columns
    dataset has shape (9,)
    """
    inputfile = os.path.join(path, "sys_dummy_sweep_all.5t")
    basename = os.path.splitext(inputfile)[0]
    existingfiles = glob.glob(basename + "*")
    cmd = [matr1x.util.get_matrix_binary(), "-i", inputfile]
    print(subprocess.list2cmdline(cmd))
    ret = subprocess.run(cmd)
    assert ret.returncode == 0
    # find newly created datafile
    files = glob.glob(basename + "*")
    newfiles = set(files) - set(existingfiles)
    assert len(newfiles) == 1
    # check file contains data
    datafile = newfiles.pop()
    h, d = matr1x.eval.loadmatrix(datafile)
    assert len(h["columns"]) == 6  # check number of data columns
    # Note that one point is not recorded in the datafile
    assert d.shape == (9,)  # check shape of dataset


def test_matrix_dummy_merged():
    """Test matrix functionality with merged dummy data.

    Tests running matrix with merged dummy data input and verifies the
    output data file format and contents.

    Asserts
    -------
    return code is 0
    at least one output file exists
    output has 10 data columns
    dataset has shape (11,)
    """
    inputfile = os.path.join(path, "sys_dummy_merged.8t")
    outputfile = os.path.join(path, f"test_merged{output_extension}")
    cmd = [matr1x.util.get_matrix_binary(), "-i", inputfile, "-o",
           outputfile, "--plain"]
    print(subprocess.list2cmdline(cmd))
    ret = subprocess.run(cmd)
    assert ret.returncode == 0
    # open latest datafile and check data shape
    files = glob.glob(os.path.join(path, f"test_merged*{output_extension}"))
    files.sort(key=os.path.getmtime)
    assert len(files) >= 1
    h, d = matr1x.eval.loadmatrix(files[-1], structured=True)
    assert len(h["columns"]) == 10  # check number of data columns
    assert d.shape == (11, )  # check shape of dataset


def test_matrix_dummy_hdf5():
    """Test matrix functionality with HDF5 dummy data.

    Tests running matrix with HDF5 format dummy data input and verifies
    the output data file format and contents, including various dataset
    shapes.

    Asserts
    -------
    return code is 0
    at least one output file exists
    output has 8 data columns
    datasets have expected shapes for flat, 1D, 2D arrays
    """
    inputfile = os.path.join(path, "sys_dummy_hdf5_sweep.3t")
    outputfile = os.path.join(path, f"test_hdf5.h5{output_extension}")
    cmd = [matr1x.util.get_matrix_binary(), "-i", inputfile, "-o",
           outputfile, "--plain"]
    print(subprocess.list2cmdline(cmd))
    ret = subprocess.run(cmd)
    assert ret.returncode == 0
    # open latest datafile and check data shape
    files = glob.glob(os.path.join(path, f"test_hdf5*{output_extension}"))
    files.sort(key=os.path.getmtime)
    assert len(files) >= 1
    h, d = matr1x.eval.loadmatrix(files[-1])
    assert len(h["columns"]) == 8  # check number of data columns
    assert d["devhdfp4_flat"].shape == (10*4, )  # check shape of dataset
    assert d["devhdfp4_1d"].shape == (10, 4)  # check shape of dataset
    assert d["devhdfp4_2d"].shape == (10, 2, 2)  # check shape of dataset
    assert d["rand2d_1"].shape == (10, 4, 4)  # check shape of dataset
    assert d["rand2d_2"].shape == (10, 4, 4)  # check shape of dataset
    assert d["timeUTC"].shape == (10, )  # check shape of dataset


def test_matrix_script_pyflakes():
    """Test matrix script functionality with pyflakes.

    Tests running a matrix script through pyflakes for syntax checking.
    Prepares test environment with dummy functions and runs script validation.

    Asserts
    -------
    pyflakes returns 0 (no errors)
    """
    # prepares and runs a test script in the same fashion as done by
    # matrix_script, code is partially duplicated but should not require
    # changes except for bugfixes
    inputfile = os.path.join(path, "test.matrix")
    with open(inputfile, "r") as f:
        user_script = f.read()
    script = "_interrupt=lambda x:x; _print=lambda x:x; _input=lambda x:x; "
    script += "_report_line=lambda x:x;_report_path=lambda x:x;_meta_data={}; "
    script += "_scriptname=''; _script=''; _status=''\n"
    script += matr1x.util.generate_script(["system_dummy_feature",
                                           "system_dummy_meas"],
                                          user_script)
    print(script)
    ret = pyflakes.api.check(script, 'sc')
    assert ret == 0


def test_matrix_script_dummy_merged():
    """Test matrix script functionality with merged dummy data.

    Tests running a matrix script with merged dummy data. Generates script,
    processes it, and verifies output data format and contents.

    Asserts
    -------
    script process returns 0
    at least one output file exists
    output has 10 data columns
    dataset has shape (22, 10)
    """
    # prepares and runs a test script in the same fashion as done by
    # matrix_script, code is partially duplicated but should not require
    # changes except for bugfixes
    inputfile = os.path.join(path, "test.matrix")
    with open(inputfile, "r") as f:
        user_script = f.read()
    script = matr1x.util.generate_script(["system_dummy_feature",
                                          "system_dummy_meas"],
                                         user_script)
    with tempfile.NamedTemporaryFile(mode="w+b") as tf:
        for line in script:
            tf.write(line.encode())
        tf.flush()
        script = (
            "import matr1x.util as mu\n"
            + f"mu.matrix_script_process({repr(tf.name)}, {{}}, '')"
        )
        ret = subprocess.run([sys.executable, "-c", script], cwd=path)
        assert ret.returncode == 0
        files = glob.glob(os.path.join(path, f"epische_messdatei{output_extension}"))
        assert len(files) >= 1
        h, d = matr1x.eval.loadmatrix(files[-1], structured=None)
        assert len(h["columns"]) == 10
        assert d.shape == (22, 10)


def test_empty_script():
    """Test running an empty matrix script.

    Tests that an empty script can be processed without errors.

    Asserts
    -------
    script process returns 0
    """
    with tempfile.NamedTemporaryFile(mode="w+b") as tf:
        script = (
            "import matr1x.util as mu\n"
            + f"mu.matrix_script_process({repr(tf.name)}, {{}}, '')"
        )
        ret = subprocess.run([sys.executable, "-c", script], cwd=path)
        assert ret.returncode == 0
