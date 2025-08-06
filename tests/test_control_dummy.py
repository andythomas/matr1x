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
Module for testing the matr1x data acquisition system.

This module contains test fixtures and test functions to verify the
functionality of the matr1x data acquisition system, particularly
focusing on the control GUI and script execution capabilities.
"""

import glob
import os
import platform
import signal
import subprocess
import sys
import tempfile
import time
from importlib.metadata import entry_points

import matr1x.eval
import matr1x.util
import pytest
from matr1x import output_extension

path = os.path.dirname(os.path.realpath(__file__))

user_script = """
import numpy as np
fields = np.linspace(0, 200, 11)
init_datafile("epische_messdatei", comment="testcomment")
for field in fields:
    set_value(1, (field, field/fields.max()*100))
    system.devs["gui"].v2 = field  # test direct access and poll command
    measure_system()
    wait(until="+0.5s")
"""


@pytest.fixture(autouse=True)
def clean_data_files():
    """
    Clean up data files created during tests.

    This fixture runs automatically before and after each test. It keeps track
    of existing data files before the test and removes any new files created
    during the test execution.

    Yields
    ------
    None
        Control is yielded to the test function.
    """
    existingfiles = glob.glob(os.path.join(path, f"*{output_extension}"))
    # run test
    yield
    files = glob.glob(os.path.join(path, f"*{output_extension}"))
    newfiles = set(files) - set(existingfiles)
    for f in newfiles:
        os.remove(f)


@pytest.fixture
def start_control_dummy():
    """
    Start and manage the control-dummy GUI application.

    This session-scoped fixture starts the control-dummy GUI application in a
    subprocess before running tests and ensures proper cleanup afterward.

    Yields
    ------
    None
        Control is yielded to the test function while the GUI runs.

    Notes
    -----
    The GUI process is terminated gracefully after the tests complete.
    A warning is issued if the DISPLAY environment variable is not set.
    """
    # Start the control-dummy GUI app in a subprocess
    env = os.environ.copy()
    if platform.system() == "Linux" and "DISPLAY" not in env:
        print("Warning: DISPLAY is not set. GUI may not run.")

    # Find the 'control-dummy' GUI script entry point
    eps = entry_points()
    try:
        if sys.version_info >= (3, 10):
            ep = next(ep for ep in eps.select(group="gui_scripts") if ep.name == "control-dummy")
        else:
            ep = next(ep for ep in eps.get("gui_scripts", []) if ep.name == "control-dummy")
    except StopIteration:
        raise RuntimeError("Entry point 'control-dummy' not found in gui_scripts")

    # Split the entry point target: "module.submodule:func"
    module_path, func_name = ep.value.split(":")

    # Build the Python one-liner to run it
    command = f"import {module_path}; {module_path}.{func_name}()"

    # Start the GUI script as a subprocess
    print("Starting control-dummy GUI in pytest fixture ...")
    gui_proc = subprocess.Popen(
        [sys.executable, "-u", "-c", command],  # -u = unbuffered stdout/stderr
        stdout=None,
        stderr=None,
        env=env,
    )

    time.sleep(3)  # Give it time to start

    yield  # Run the test now

    # Cleanup: gracefully terminate the GUI
    try:
        gui_proc.send_signal(signal.SIGTERM)
        gui_proc.wait(timeout=5)
    except Exception:
        gui_proc.kill()


def test_matrix_script_control_dummy(start_control_dummy):
    """
    Test the matrix script execution with the control dummy GUI.

    This test function verifies that the matrix script can be properly executed
    using the control dummy GUI. It generates a test script, runs it, and
    validates the output data files and their contents.

    Returns
    -------
    None

    Raises
    ------
    AssertionError
        If any of the test validations fail.
    """
    # prepares and runs a test script in the same fashion as done by
    # matrix_script, code is partially duplicated but should not require
    # changes except for bugfixes

    script = matr1x.util.generate_script(["system_dummygui"], user_script)
    with tempfile.NamedTemporaryFile(mode="w+b") as tf:
        for line in script:
            tf.write(line.encode())
        tf.flush()
        script = (
            "import matr1x.util as mu\n" + f"mu.matrix_script_process({repr(tf.name)}, {{}}, '')"
        )
        ret = subprocess.run([sys.executable, "-c", script], cwd=path)
        assert ret.returncode == 0
        files = glob.glob(os.path.join(path, f"epische_messdatei{output_extension}"))
        assert len(files) >= 1
        h, d = matr1x.eval.loadmatrix(files[-1], structured=False)
        assert len(h["columns"]) == 6
        assert d.shape == (11, 6)
