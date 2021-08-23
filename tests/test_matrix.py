import glob
import os
import subprocess
import sys
import tempfile

import matr1x.eval
import matr1x.util
import pytest

path = os.path.dirname(os.path.realpath(__file__))


@pytest.fixture(autouse=True)
def clean_ma7_files():
    existingfiles = glob.glob(os.path.join(path, "*.ma7"))
    # run test
    yield
    files = glob.glob(os.path.join(path, "*.ma7"))
    newfiles = set(files) - set(existingfiles)
    for f in newfiles:
        os.remove(f)


def test_matrix_dummy():
    inputfile = os.path.join(path, "sys_dummy_sweep_all.4t")
    basename = os.path.splitext(inputfile)[0]
    existingfiles = glob.glob(basename + "*")
    cmd = ["matrix", "-i", inputfile]
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
    assert len(h[0]) == 6  # check number of data columns
    assert d.shape == (9, 6)  # check shape of dataset


def test_matrix_dummy_merged():
    inputfile = os.path.join(path, "sys_dummy_merged.7t")
    outputfile = os.path.join(path, "test_merged.ma7")
    cmd = ["matrix", "-i", inputfile, "-o", outputfile, "--plain"]
    print(subprocess.list2cmdline(cmd))
    ret = subprocess.run(cmd)
    assert ret.returncode == 0
    # open latest datafile and check data shape
    files = glob.glob(os.path.join(path, "test_merged*.ma7"))
    files.sort(key=os.path.getmtime)
    assert len(files) >= 1
    h, d = matr1x.eval.loadmatrix(files[-1])
    assert len(h[0]) == 10  # check number of data columns
    assert d.shape == (11, 10)  # check shape of dataset


def test_matrix_dummy_hdf5():
    inputfile = os.path.join(path, "sys_dummy_hdf5_sweep.3t")
    outputfile = os.path.join(path, "test_hdf5.h5.ma7")
    cmd = ["matrix", "-i", inputfile, "-o", outputfile, "--plain"]
    print(subprocess.list2cmdline(cmd))
    ret = subprocess.run(cmd)
    assert ret.returncode == 0
    # open latest datafile and check data shape
    files = glob.glob(os.path.join(path, "test_hdf5*.ma7"))
    files.sort(key=os.path.getmtime)
    assert len(files) >= 1
    h, d = matr1x.eval.loadh5matrix(files[-1])
    assert len(h[0]) == 4  # check number of data columns
    assert d[0].shape == (10*4, )  # check shape of dataset
    assert d[-1].shape == (10, )  # check shape of dataset


def test_matrix_script_dummy_merged():
    # prepares and runs a test script in the same fashion as done by
    # matrix_script, code is partially duplicated but should not require
    # changes except for bugfixes
    inputfile = os.path.join(path, "test.matrix")
    user_script = ""
    with open(inputfile, "r") as f:
        for line in f:
            user_script += line
    script = matr1x.util.generate_script(["system_dummy_feature.py",
                                          "system_dummy_meas.py"],
                                         user_script)
    with tempfile.NamedTemporaryFile(mode="w+b") as tf:
        for line in script:
            tf.write(line.encode())
        tf.flush()
        script = ("import matr1x.util as mu\n" +
                  f"mu.matrix_script_process({repr(tf.name)}, '', '')")
        ret = subprocess.run([sys.executable, "-c", script], cwd=path)
        assert ret.returncode == 0
        files = glob.glob(os.path.join(path, "epische_messdatei.ma7"))
        assert len(files) >= 1
        h, d = matr1x.eval.loadmatrix(files[-1])
        assert len(h[0]) == 10
        assert d.shape == (22, 10)
