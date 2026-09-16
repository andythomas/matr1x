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
Tests for matr1x data loading functionality.

This module tests the loadmatrix functionality for various matr1x file
formats.
"""

from pathlib import Path

import numpy as np
import polars as pl
import pytest

import matr1x.core.eval

ma6_header_keys = {
    "columns",
    "units",
    "status",
    "system query",
    "input filename",
    "system filename",
    "comments",
    # text version still has "comment line", and "time stamp"
}

ma7_header_keys = {
    "columns",
    "units",
    "comments",
    "status",
    "system query",
    "input filename",
    "system filename",
    "device query",
    "dc.creator",
    "dc.date",
    "dc.identifier",
    "dc.description",
    "dc.source",
    "dc.type",
    "dc.publisher",
    "dc.format",
    "dc.language",
}

ma8_header_keys = {
    "columns",
    "units",
    "comments",
    "status",
    "system query",
    "input filename",
    "system filename",
    "dcterms:creator",
    "dcterms:date",
    "dcterms:identifier",
    "dcterms:relation",
    "dcterms:description",
    "dcterms:source",
    "dcterms:type",
    "dcterms:publisher",
    "dcterms:format",
    "dcterms:language",
}


def get_array_field_count(arr: np.ndarray) -> int:
    """Get the number of fields in a numpy array."""
    if arr.dtype.names is not None:
        # Structured array
        return len(arr.dtype.names)
    elif len(arr.shape) > 1:
        # Unstructured 2D array
        return arr.shape[1]
    else:
        # 1D array
        return 1


def test_loadmatrix_hdf5_ma8(data_dir: Path):
    """
    Test loading of HDF5 MA8 format files.

    Tests loading and validating contents of an HDF5 MA8 format data
    file. Checks header information, data columns, units, and specific
    data values.
    """
    datafile = data_dir / "random_test.h5.ma8"
    h, d = matr1x.core.eval.loadmatrix(datafile)
    assert ma8_header_keys == set(h.keys())
    assert h["dcterms:publisher"] == "matr1x measurement suite"
    assert h["dcterms:relation"] == ""
    assert h["dcterms:type"] == ""
    assert isinstance(d, np.ndarray), f"Expected np.ndarray, got {type(d)}"
    assert len(h["columns"]) == 6  # check number of data columns
    assert len(h["columns"]) == len(h["units"])  # check amount of specified units
    assert get_array_field_count(d) == len(h["columns"])
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
    assert pytest.approx(d["timeUTC"][1], 1e-9) == 1726870220.4  # check specific data value


def test_loadmatrix_ma8(data_dir: Path):
    """
    Test loading of MA8 format files.

    Tests loading and validating contents of an MA8 format data file.
    Checks header information, data columns, units, and specific data
    values.
    """
    datafile = data_dir / "random_test.ma8"
    h, d = matr1x.core.eval.loadmatrix(datafile, to_polars=True)
    assert ma8_header_keys == set(h.keys())
    assert isinstance(d, pl.DataFrame), f"Expected pl.DataFrame, got {type(d)}"
    assert h["dcterms:type"] == ""
    assert h["dcterms:identifier"] == "random numpy"
    assert d["timeUTC"].len() == 100  # check length of dataset
    assert len(h["columns"]) == 6  # check number of data columns
    assert len(h["columns"]) == len(h["units"])  # check amount of specified units
    assert len(d.columns) == len(h["columns"])
    assert h["columns"][3] == "dev1 p1"  # check specific column name
    assert h["units"][3] == "cnt"  # check specific unit entry
    assert h["status"] == "finished"
    assert isinstance(h["system query"], dict)
    assert len(h["system query"]) == 3
    assert h["system query"]["dev1"]["p4"] == [5.0, 3.0, 2.0, 1.0]
    assert len(h["system query"]["user script"]) == 381
    assert d["dev1 p3a"].len() == 100  # check length of dataset
    assert d["timeUTC"].len() == 100  # check length of dataset
    assert pytest.approx(d["dev1 p2"][3], 1e-5) == 0.393633  # check specific data value
    assert pytest.approx(d["timeUTC"][1], 1e-9) == 1726870139.20  # check specific data value


def test_loadmatrix_hdf5_ma7(data_dir: Path):
    """
    Test loading of HDF5 MA7 format files.

    Tests loading and validating contents of an HDF5 MA7 format data
    file. Checks header information, data columns, units, and specific
    data values.
    """
    datafile = data_dir / "magic_sample.h5.ma7"
    h, d = matr1x.core.eval.loadmatrix(datafile)
    assert ma7_header_keys <= set(h.keys())
    assert isinstance(d, np.ndarray), f"Expected np.ndarray, got {type(d)}"
    assert h["dc.publisher"] == "matr1x;University of Konstanz"  # ty:ignore[invalid-key]
    assert len(h["columns"]) == 11  # check number of data columns
    assert len(h["columns"]) == len(h["units"])  # check amount of specified units
    assert get_array_field_count(d) == len(h["columns"])  # check appropriate data column number
    assert h["columns"][4] == "HallProbe Temp"  # check specific column name
    assert h["units"][4] == "C"  # check specific unit entry
    assert len(h["device query"]) == 570  # ty:ignore[invalid-key]
    assert d["FSW8 f"].shape == (1, 2001)  # check shape of dataset
    assert d["timeUTC"].shape == (1,)  # check shape of dataset
    assert pytest.approx(d["FSW8 f"][0, 501], 1e-6) == 2.9555e9  # check specific data value
    assert pytest.approx(d["timeUTC"][0], 1e-9) == 1701194065  # check specific data value


def test_loadmatrix_ma7(data_dir: Path):
    """
    Test loading of MA7 format files.

    Tests loading and validating contents of an MA7 format data file.
    Checks header information, data columns, units, and specific data
    values.
    """
    datafile = data_dir / "mgk240213.ma7"
    h, d = matr1x.core.eval.loadmatrix(datafile, to_polars=True)
    assert ma7_header_keys <= set(h.keys())
    assert isinstance(d, pl.DataFrame), f"Expected pl.DataFrame, got {type(d)}"
    assert h["dc.type"] == "Transport data"  # ty:ignore[invalid-key]
    assert len(h["columns"]) == 7  # check number of data columns
    assert len(h["columns"]) == len(h["units"])  # check amount of specified units
    assert len(d.columns) == len(h["columns"])  # check appropriate data column number
    assert h["columns"][3] == "Ismu02"  # check specific column name
    assert h["units"][3] == "A"  # check specific unit entry
    assert len(h["device query"]) == 167  # ty:ignore[invalid-key]
    assert d["y field"].len() == 1460  # check length of dataset
    assert d["timeUTC"].len() == 1460  # check length of dataset
    assert (
        pytest.approx(d["y field"][17], 1e-6) == -0.6770565868263473
    )  # check specific data value
    assert pytest.approx(d["timeUTC"][0], 1e-10) == 1713015567.56  # check specific data value


def test_loadmatrix_hdf5_ma6(data_dir: Path):
    """
    Test loading of HDF5 MA6 format files.

    Tests loading and validating contents of an HDF5 MA6 format data
    file. Checks header information, data columns, units, and specific
    data values.
    """
    datafile = data_dir / "polybox.h5.ma6"
    h, d = matr1x.core.eval.loadmatrix(datafile)
    assert ma6_header_keys == set(h.keys())
    assert len(h["columns"]) == 6  # check number of data columns
    assert len(h["columns"]) == len(h["units"])  # check amount of specified units
    assert len(d) == len(h["columns"])  # check appropriate data column number
    assert h["columns"][2] == "k6621-v"  # check specific column name
    assert h["units"][2] == "V"  # check specific unit entry
    assert d["k6621-v"].shape == (5000,)  # check shape of dataset
    assert d["timeUTC"].shape == (50,)  # check shape of dataset
    assert pytest.approx(d["k6621-v"][2003], 1e-12) == 3.4997413e-06  # check specific data value
    assert pytest.approx(d["timeUTC"][45], 1e-9) == 1599555123.1  # check specific data value


def test_loadmatrix_ma6(data_dir: Path):
    """
    Test loading of MA6 format files.

    Tests loading and validating contents of an MA6 format data file.
    Checks header information, data columns, units, and specific data
    values.
    """
    datafile = data_dir / "ARMR.ma6"
    h, d = matr1x.core.eval.loadmatrix(datafile, to_polars=True)
    assert ma6_header_keys <= set(h.keys())
    assert isinstance(d, pl.DataFrame), f"Expected pl.DataFrame, got {type(d)}"
    assert (
        h["input filename"]
        == "/home/sisyphos/users/rs25/rs25180808a/ARMR_350Kto420K_10Ksteps_100uA_70mT_ip.4t"
    )
    assert len(h["columns"]) == 9  # check number of data columns
    assert len(h["columns"]) == len(h["units"])  # check amount of specified units
    assert len(d.columns) == len(h["columns"])  # check appropriate data column number
    assert h["columns"][3] == "timeUTC"  # check specific column name
    assert h["units"][3] == "s"  # check specific unit entry
    assert d["Vnvm07"].len() == 2196  # check length of dataset
    assert d["timeUTC"].len() == 2196  # check length of dataset
    assert pytest.approx(d["Vnvm07"][14], 1e-12) == 1.80986751e-06  # check specific data value
    assert pytest.approx(d["timeUTC"][-1], 1e-10) == 1557380107.327  # check specific data value


def test_loadmatrix_to_polars(data_dir: Path):
    """
    Test loading of text files with to_polars=True.

    Verifies that a native polars DataFrame is returned with the
    expected shape and columns.
    """
    datafile = data_dir / "random_test.ma8"
    h, d = matr1x.core.eval.loadmatrix(datafile, to_polars=True)
    assert isinstance(d, pl.DataFrame), f"Expected pl.DataFrame, got {type(d)}"
    assert d.shape == (100, 6)
    assert list(d.columns) == h["columns"]


def test_loadmatrix_numpy_deprecated(data_dir: Path):
    """
    Test that the legacy numpy return for text files is deprecated.

    Loading a text file without to_polars=True raises a FutureWarning.
    The returned structured array still holds the correct data until
    the numpy return is removed.
    """
    datafile = data_dir / "random_test.ma8"
    with pytest.warns(FutureWarning, match="to_polars=True"):
        h, d = matr1x.core.eval.loadmatrix(datafile)
    assert isinstance(d, np.ndarray), f"Expected np.ndarray, got {type(d)}"
    assert get_array_field_count(d) == len(h["columns"])
    assert d["timeUTC"].shape == (100,)
    assert pytest.approx(d["dev1 p2"][3], 1e-5) == 0.393633  # check specific data value


def test_loadmatrix_to_polars_hdf5(data_dir: Path):
    """Test that to_polars=True raises NotImplementedError for HDF5 files."""
    datafile = data_dir / "random_test.h5.ma8"
    with pytest.raises(NotImplementedError):
        matr1x.core.eval.loadmatrix(datafile, to_polars=True)


def test_loadmatrix_tristate_bool(tmp_path: Path):
    """
    Test that a bool column containing None becomes an object array.

    The object dtype is what the plot's categorical detection relies on
    to render the column as a tristate categorical axis.
    """
    datafile = tmp_path / "bool_none.ma7"
    datafile.write_text("a\tb\nV\tV\na\tb\nTrue\tTrue\nNone\tTrue\nFalse\tFalse\n")
    with pytest.warns(FutureWarning, match="to_polars=True"):
        h, d = matr1x.core.eval.loadmatrix(datafile)
    assert d["a"].dtype == np.dtype("O")
    assert list(d["a"]) == [True, None, False]
    # column without None stays a plain bool
    assert d["b"].dtype == np.dtype("bool")


def test_loadmatrix_pathlib_ma8(data_dir: Path):
    """
    Test loading of MA8 format files using pathlib.Path objects.

    Verifies that pathlib.Path objects work identically to string paths
    for MA8 format files.
    """
    # Test with pathlib.Path
    datafile_path = data_dir / "random_test.ma8"
    h_path, d_path = matr1x.core.eval.loadmatrix(datafile_path, to_polars=True)

    # Test with string (for comparison)
    datafile_str = str(datafile_path)
    h_str, d_str = matr1x.core.eval.loadmatrix(datafile_str, to_polars=True)

    assert isinstance(d_path, pl.DataFrame)
    assert isinstance(d_str, pl.DataFrame)

    # Results should be identical
    assert h_path["dcterms:identifier"] == h_str["dcterms:identifier"]
    assert h_path["columns"] == h_str["columns"]
    assert h_path["units"] == h_str["units"]
    assert len(d_path) == len(d_str)
    assert d_path["timeUTC"].len() == d_str["timeUTC"].len()
    assert pytest.approx(d_path["dev1 p2"][3], 1e-5) == pytest.approx(d_str["dev1 p2"][3], 1e-5)
