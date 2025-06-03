# This file is part of a software collection for data acquisition (matr1x).
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

"""Tests for matr1x data loading functionality.

This module tests the loadmatrix functionality for various matr1x file formats.
"""

import os

import matr1x.eval
import pytest

path = os.path.dirname(os.path.realpath(__file__))


def test_loadmatrix_hdf5_ma8():
    """Test loading of HDF5 MA8 format files.

    Tests loading and validating contents of an HDF5 MA8 format data file.
    Checks header information, data columns, units, and specific data values.
    """
    datafile = os.path.join(path, "data", "random_test.h5.ma8")
    h, d = matr1x.eval.loadmatrix(datafile)
    assert h["dcterms:publisher"] == "matr1x measurement suite"
    assert len(h["columns"]) == 6  # check number of data columns
    assert len(h["columns"]) == len(h["units"])  # check amount of specified units
    assert len(d.dtype) == len(h["columns"])  # check appropriate data column number
    assert h["columns"][2] == "dev1 p3a"  # check specific column name
    assert h["units"][2] == "cnta"  # check specific unit entry
    assert h["status"] == "aborted"
    assert isinstance(h["system query"], dict)
    assert len(h["system query"]) == 3
    assert list(h["system query"]["dev1"]["p4"] == [5.0, 3.0, 2.0, 1.0])
    assert len(h["system query"]["user script"]) == 411
    assert len(h["comments"]) == 6  # check number of comments
    assert d["timeUTC"].shape == (74,)  # check shape of dataset
    assert pytest.approx(d["dev1 p2"][3], 1e-5) == 0.392225  # check specific data value
    assert (
        pytest.approx(d["timeUTC"][1], 1e-9) == 1726870220.4
    )  # check specific data value


def test_loadmatrix_ma8():
    """Test loading of MA8 format files.

    Tests loading and validating contents of an MA8 format data file.
    Checks header information, data columns, units, and specific data values.
    """
    datafile = os.path.join(path, "data", "random_test.ma8")
    h, d = matr1x.eval.loadmatrix(datafile)
    assert h["dcterms:type"] is None
    assert h["dcterms:identifier"] == "random numpy"
    assert d["timeUTC"].shape == (100,)  # check shape of dataset
    assert len(h["columns"]) == 6  # check number of data columns
    assert len(h["columns"]) == len(h["units"])  # check amount of specified units
    assert len(d.dtype) == len(h["columns"])  # check appropriate data column number
    assert h["columns"][3] == "dev1 p1"  # check specific column name
    assert h["units"][3] == "cnt"  # check specific unit entry
    assert h["status"] == "finished"
    assert isinstance(h["system query"], dict)
    assert len(h["system query"]) == 3
    assert h["system query"]["dev1"]["p4"] == [5.0, 3.0, 2.0, 1.0]
    assert len(h["system query"]["user script"]) == 381
    assert d["dev1 p3a"].shape == (100,)  # check shape of dataset
    assert d["timeUTC"].shape == (100,)  # check shape of dataset
    assert pytest.approx(d["dev1 p2"][3], 1e-5) == 0.393633  # check specific data value
    assert (
        pytest.approx(d["timeUTC"][1], 1e-9) == 1726870139.20
    )  # check specific data value


def test_loadmatrix_hdf5_ma7():
    """Test loading of HDF5 MA7 format files.

    Tests loading and validating contents of an HDF5 MA7 format data file.
    Checks header information, data columns, units, and specific data values.
    """
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
    assert (
        pytest.approx(d["timeUTC"][0], 1e-9) == 1701194065
    )  # check specific data value


def test_loadmatrix_ma7():
    """Test loading of MA7 format files.

    Tests loading and validating contents of an MA7 format data file.
    Checks header information, data columns, units, and specific data values.
    """
    datafile = os.path.join(path, "data", "mgk240213.ma7")
    h, d = matr1x.eval.loadmatrix(datafile)
    assert h["DC.Type"] == "Transport data"
    assert len(h["columns"]) == 7  # check number of data columns
    assert len(h["columns"]) == len(h["units"])  # check amount of specified units
    assert len(d.dtype) == len(h["columns"])  # check appropriate data column number
    assert h["columns"][3] == "Ismu02"  # check specific column name
    assert h["units"][3] == "A"  # check specific unit entry
    assert len(h["Device query"]) == 167
    assert d["y field"].shape == (1460,)  # check shape of dataset
    assert d["timeUTC"].shape == (1460,)  # check shape of dataset
    assert (
        pytest.approx(d["y field"][17], 1e-6) == -0.6770565868263473
    )  # check specific data value
    assert (
        pytest.approx(d["timeUTC"][0], 1e-10) == 1713015567.56
    )  # check specific data value


def test_loadmatrix_hdf5_ma6():
    """Test loading of HDF5 MA6 format files.

    Tests loading and validating contents of an HDF5 MA6 format data file.
    Checks header information, data columns, units, and specific data values.
    """
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
        pytest.approx(d["timeUTC"][45], 1e-9) == 1599555123.1
    )  # check specific data value


def test_loadmatrix_ma6():
    """Test loading of MA6 format files.

    Tests loading and validating contents of an MA6 format data file.
    Checks header information, data columns, units, and specific data values.
    """
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
        pytest.approx(d["timeUTC"][-1], 1e-10) == 1557380107.327
    )  # check specific data value
