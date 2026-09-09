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
Matrix test module.

This module contains tests for the matrix data acquisition software.
"""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pytest

import matr1x.eval
import matr1x.util
from matr1x import output_extension
from matr1x.execthread import ExecThread
from matr1x.models import LineNumber, MeasurementData
from matr1x.util import matrix_cmdline

path = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def clean_data_files():
    """
    Clean up data files created during tests.

    This fixture runs automatically before and after each test to clean up any
    data files that were created. It tracks existing files before the test and
    removes any new files created during test execution.

    Yields
    ------
    None
    """
    existingfiles = set(path.glob(f"*{output_extension}"))
    # run test
    yield
    files = set(path.glob(f"*{output_extension}"))
    newfiles = files - existingfiles
    for f in newfiles:
        f.unlink()


def test_matrix_dummy():
    """
    Test basic matrix functionality with dummy sweep data.

    Tests running matrix with a simple dummy sweep input file and verifies
    the output data file format and contents.

    Asserts
    -------
    return code is 0
    exactly one new file is created
    output has 6 data columns
    dataset has shape (9,)
    """
    inputfile = path / "sys_dummy_sweep_all.5t"
    basename_path = inputfile.with_suffix("")
    existingfiles = set(basename_path.parent.glob(basename_path.name + "*"))
    cmd = matrix_cmdline("-i", str(inputfile))
    print(subprocess.list2cmdline(cmd))
    ret = subprocess.run(cmd)
    assert ret.returncode == 0
    # find newly created datafile
    files = set(basename_path.parent.glob(basename_path.name + "*"))
    newfiles = files - existingfiles
    assert len(newfiles) == 1
    # check file contains data
    datafile = newfiles.pop()
    h, d = matr1x.eval.loadmatrix(datafile)
    assert len(h["columns"]) == 6  # check number of data columns
    # Note that one point is not recorded in the datafile
    assert isinstance(d, np.ndarray), f"Expected np.ndarray, got {type(d)}"
    assert d.shape == (9,)  # check shape of dataset


def test_matrix_dummy_merged():
    """
    Test matrix functionality with merged dummy data.

    Tests running matrix with merged dummy data input and verifies the
    output data file format and contents.

    Asserts
    -------
    return code is 0
    at least one output file exists
    output has 10 data columns
    dataset has shape (11,)
    """
    inputfile = path / "sys_dummy_merged.8t"
    outputfile = path / f"test_merged{output_extension}"
    cmd = matrix_cmdline("-i", str(inputfile), "-o", str(outputfile), "--plain")
    print(subprocess.list2cmdline(cmd))
    ret = subprocess.run(cmd)
    assert ret.returncode == 0
    # open latest datafile and check data shape
    files = sorted(path.glob(f"test_merged*{output_extension}"), key=lambda p: p.stat().st_mtime)
    assert len(files) >= 1
    h, d = matr1x.eval.loadmatrix(files[-1], structured=True)
    assert len(h["columns"]) == 10  # check number of data columns
    assert isinstance(d, np.ndarray), f"Expected np.ndarray, got {type(d)}"
    assert d.shape == (11,)  # check shape of dataset


def test_matrix_dummy_hdf5():
    """
    Test matrix functionality with HDF5 dummy data.

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
    inputfile = path / "sys_dummy_hdf5_sweep.3t"
    outputfile = path / f"test_hdf5.h5{output_extension}"
    cmd = matrix_cmdline("-i", str(inputfile), "-o", str(outputfile), "--plain")
    print(subprocess.list2cmdline(cmd))
    ret = subprocess.run(cmd)
    assert ret.returncode == 0
    # open latest datafile and check data shape
    files = sorted(path.glob(f"test_hdf5*{output_extension}"), key=lambda p: p.stat().st_mtime)
    assert len(files) >= 1
    h, d = matr1x.eval.loadmatrix(files[-1])
    assert len(h["columns"]) == 8  # check number of data columns
    assert d["devhdfp4_flat"].shape == (10 * 4,)  # check shape of dataset
    assert d["devhdfp4_1d"].shape == (10, 4)  # check shape of dataset
    assert d["devhdfp4_2d"].shape == (10, 2, 2)  # check shape of dataset
    assert d["rand2d_1"].shape == (10, 4, 4)  # check shape of dataset
    assert d["rand2d_2"].shape == (10, 4, 4)  # check shape of dataset
    assert d["timeUTC"].shape == (10,)  # check shape of dataset


def test_matrix_script_dummy_merged():
    """
    Test matrix script functionality with merged dummy data.

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
    inputfile = path / "test.matrix"
    with inputfile.open() as f:
        user_script = f.read()
    script = matr1x.util.generate_script(user_script)
    with tempfile.NamedTemporaryFile(mode="w+b") as tf:
        for line in script:
            tf.write(line.encode())
        tf.flush()
        script = (
            "import matr1x.util as mu\n"
            "mu.matrix_script_process(\n"
            f"{repr(tf.name)}, {{}}, '', None, ['system_dummy_feature', 'system_dummy_meas']\n"
            ")"
        )
        ret = subprocess.run([sys.executable, "-c", script], cwd=path)
        assert ret.returncode == 0
        files = list(path.glob(f"epische_messdatei*{output_extension}"))
        assert len(files) >= 1
        h, d = matr1x.eval.loadmatrix(files[-1], structured=False)
        assert len(h["columns"]) == 10
        assert isinstance(d, np.ndarray), f"Expected np.ndarray, got {type(d)}"
        assert d.shape == (22, 10)


def test_empty_script():
    """
    Test running an empty matrix script.

    Tests that an empty script can be processed without errors.

    Asserts
    -------
    script process returns 0
    """
    with tempfile.NamedTemporaryFile(mode="w+b") as tf:
        script = (
            "import matr1x.util as mu\n"
            f"mu.matrix_script_process({repr(tf.name)}, {{}}, '', None, [])"
        )
        ret = subprocess.run([sys.executable, "-c", script], cwd=path)
        assert ret.returncode == 0


@pytest.mark.parametrize(
    ("user_script", "expected_lines"),
    [
        (
            'for i in range(2):\n    set_value("timeUTC", 0.001)\n    wait(0.001)\n',
            [2, 3, 2, 3],
        ),
        (
            'def set_time():\n    set_value("timeUTC", 0.001)\n\nset_time()\n',
            [2],
        ),
    ],
)
def test_matrix_script_reports_only_user_line_numbers(user_script, expected_lines, monkeypatch):
    """Line reporting keeps the nearest user line highlighted during external work."""
    script = matr1x.util.generate_script(user_script)
    thread = ExecThread(script, {}, "", None, [])
    generated_lines: list[int] = []

    def collect_line_numbers(data: MeasurementData) -> None:
        if isinstance(data, LineNumber):
            generated_lines.append(data.line)

    with monkeypatch.context() as patch:
        patch.setattr(thread, "report", collect_line_numbers)
        # Record the original process-wide function so the context restores it
        # after the generated script decorates time.sleep.
        patch.setattr(time, "sleep", time.sleep)
        thread.run()

    offset = matr1x.util.get_script_prefix_offset()
    reported_lines = [line - offset for line in generated_lines]
    distinct_lines = [
        line
        for index, line in enumerate(reported_lines)
        if index == 0 or line != reported_lines[index - 1]
    ]

    assert distinct_lines == expected_lines
    assert all(1 <= line <= len(user_script.splitlines()) for line in reported_lines)
