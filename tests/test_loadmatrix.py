# This file is part of a software collection for data aquisition (matr1x).
# ---
# (c) 2024 matr1x developers. All rights reserved.
# ---
import os

import matr1x.eval
import pytest

path = os.path.dirname(os.path.realpath(__file__))


def test_loadmatrix_hdf5_ma7():
    datafile = os.path.join(path, "data", "magic_sample.h5.ma7")
    h, d = matr1x.eval.loadmatrix(datafile)
    assert h["DC.Publisher"] == "matr1x;University of Konstanz"
    assert len(h["columns"]) == 11  # check number of data columns
    assert len(h["columns"]) == len(h["units"])  # check amount of specified units
    assert len(d.dtype) == len(h["columns"])  # check appropriate data column number
    assert h["columns"][4] == "HallProbe Temp"  # check specific column name
    assert h["units"][4] == "C"  # check specific unit entry
    assert len(h["Device query"]) == 570
    assert d["FSW8 f"].shape == (1, 2001)  # check shape of dataset
    assert d["timeUTC"].shape == (1,)  # check shape of dataset
    assert (
        pytest.approx(d["FSW8 f"][0, 501], 1e-6) == 2.9555e9
    )  # check specific data value
    assert pytest.approx(d["timeUTC"][0], 1) == 1701194065  # check specific data value


def test_loadmatrix_ma7():
    datafile = os.path.join(path, "data", "mkg240213.ma7")
    h, d = matr1x.eval.loadmatrix(datafile)
    assert h["DC.Type"] == "Transport data"
    assert len(h["columns"]) == 7  # check number of data columns
    assert len(h["columns"]) == len(h["units"])  # check amount of specified units
    assert len(d.dtype) == len(h["columns"])  # check appropriate data column number
    assert h["columns"][3] == "Ismu02"  # check specific column name
    assert h["units"][3] == "A"  # check specific unit entry
    assert len(h["Device query"]) == 149
    assert d["y field"].shape == (1460,)  # check shape of dataset
    assert d["timeUTC"].shape == (1460,)  # check shape of dataset
    assert (
        pytest.approx(d["y field"][17], 1e-6) == -0.6770565868263473
    )  # check specific data value
    assert (
        pytest.approx(d["timeUTC"][0], 0.01) == 1713015567.56
    )  # check specific data value


def test_loadmatrix_hdf5_ma6():
    datafile = os.path.join(path, "data", "polybox.h5.ma6")
    h, d = matr1x.eval.loadmatrix(datafile)
    assert len(h["columns"]) == 6  # check number of data columns
    assert len(h["columns"]) == len(h["units"])  # check amount of specified units
    assert len(d) == len(h["columns"])  # check appropriate data column number
    assert h["columns"][2] == "k6621-v"  # check specific column name
    assert h["units"][2] == "V"  # check specific unit entry
    assert d["k6621-v"].shape == (5000,)  # check shape of dataset
    assert d["timeUTC"].shape == (50,)  # check shape of dataset
    assert (
        pytest.approx(d["k6621-v"][2003], 1e-12) == 3.4997413e-06
    )  # check specific data value
    assert (
        pytest.approx(d["timeUTC"][45], 1) == 1599555123.1
    )  # check specific data value


def test_loadmatrix_ma6():
    datafile = os.path.join(path, "data", "ARMR.ma6")
    h, d = matr1x.eval.loadmatrix(datafile)
    assert (
        h["Input filename"]
        == "/home/sisyphos/users/rs25/rs25180808a/ARMR_350Kto420K_10Ksteps_100uA_70mT_ip.4t"
    )
    assert len(h["columns"]) == 9  # check number of data columns
    assert len(h["columns"]) == len(h["units"])  # check amount of specified units
    assert len(d.dtype) == len(h["columns"])  # check appropriate data column number
    assert h["columns"][3] == "timeUTC"  # check specific column name
    assert h["units"][3] == "s"  # check specific unit entry
    assert d["Vnvm07"].shape == (2196,)  # check shape of dataset
    assert d["timeUTC"].shape == (2196,)  # check shape of dataset
    assert (
        pytest.approx(d["Vnvm07"][14], 1e-12) == 1.80986751e-06
    )  # check specific data value
    assert (
        pytest.approx(d["timeUTC"][-1], 0.01) == 1557380107.327
    )  # check specific data value
