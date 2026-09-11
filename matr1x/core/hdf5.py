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
HDF5 data file handling.

This module implements reading and writing of the matr1x HDF5 file
format. It is the only module that imports h5py; other modules import
it lazily so that h5py is only loaded when HDF5 files are used.
"""

from pathlib import Path

import h5py
import numpy as np

from matr1x.core.models import HeaderDict, create_empty_header

__all__ = [
    "init_hdf5_skel",
    "load_hdf5_file",
    "save_dict_to_hdf5",
]


def save_dict_to_hdf5(data_dict: dict, hdf5_file: h5py.File, root_group: str) -> None:
    """
    Save a dictionary to an HDF5 file in a hierachical data group.

    Parameters
    ----------
    data_dict : dict
        The dictionary to be saved.
    hdf5_file : h5py.File
        File handle of the HDF5 file to save the data to.
    root_group : str
        The name of the root group in the HDF5 file.

    Notes
    -----
    This function recursively writes nested dictionaries to HDF5 groups and
    datasets. Lists are converted to datasets, and scalar values are saved as
    attributes.
    """

    def write_dict(group: h5py.Group, d: dict) -> None:
        """Recursively write a dictionary to an HDF5 group."""
        for key, value in d.items():
            if isinstance(value, dict):
                # Create a subgroup for nested dictionaries
                subgroup = group.create_group(key)
                write_dict(subgroup, value)
            elif isinstance(value, list):
                # Convert lists to datasets
                group.create_dataset(key, data=value)
            else:
                # Save scalar values
                group.attrs[key] = value

    # Create or get the specified root group
    group = hdf5_file.require_group(root_group)

    write_dict(group, data_dict)


def init_hdf5_skel(
    file_handle, columns: list[str], units: list[str], dtypes, chunks: list[int]
) -> None:
    """
    Initialize a HDF5 file skeleton for a measurement file.

    Parameters
    ----------
    file_handle : h5py.File
        Opened HDF5 file that the header should be written to.
    columns : list
        Column names written into the header.
    units : list
        Column units to be written into the header.
    chunks : list
        List of ints that define the chunk length of the individual datasets.
    dtypes : list
        List of strings specifying the dtype of the individual datasets.
    """
    data_grp = file_handle.create_group("data")
    dt = np.dtype(
        [
            ("message", h5py.string_dtype(encoding="utf-8")),
            ("timestamp", h5py.string_dtype(encoding="utf-8")),
        ]
    )
    # Create an empty dataset for comments
    file_handle.create_dataset("comments", shape=(0,), maxshape=(None,), dtype=dt)
    for col, uni, chu, dtype in zip(columns, units, chunks, dtypes):
        if isinstance(chu, tuple):
            data_grp.create_dataset(
                col,
                (0, *chu),
                maxshape=(None, *chu),
                chunks=(1, *chu),
                dtype=dtype,
                compression=True,
            )
        else:
            data_grp.create_dataset(
                col,
                (0,),
                maxshape=(None,),
                chunks=(chu,),
                dtype=dtype,
                compression=True,
            )
        data_grp[col].attrs["unit"] = uni


def _load_dict_from_hdf5(hdf5_file: h5py.File, root_group: str) -> dict:
    """
    Load a dictionary from an HDF5 file.

    This function reads data from an HDF5 file and returns it as a
    nested dictionary. It recursively traverses the HDF5 file structure,
    converting groups to subdictionaries and datasets to array-like
    objects.

    Parameters
    ----------
    hdf5_file : h5py.File
        An open HDF5 file object.
    root_group : str
        The name of the root group to start reading from.

    Returns
    -------
    dict
        A nested dictionary representing the structure and data of the
        HDF5 file.

    Notes
    -----
    This function assumes that the HDF5 file is already open when passed
    as an argument. It's the caller's responsibility to close the file
    after use.
    """

    def read_group(group: h5py.Group):
        """
        Recursively read an HDF5 group into a dictionary.

        This includes the attributes.
        """
        d = {}

        # Read attributes from the group
        for key, value in group.attrs.items():
            d[key] = value

        # Read subgroups and datasets
        for key, item in group.items():
            if isinstance(item, h5py.Group):
                # Recursively read subgroups
                d[key] = read_group(item)
            elif isinstance(item, h5py.Dataset):
                # Read dataset as list
                d[key] = item[:]

        return d

    # Get the specified root group
    if root_group in hdf5_file:
        group = hdf5_file[root_group]
    else:
        raise KeyError(f"Group '{root_group}' not found in the HDF5 file.")
    if not isinstance(group, h5py.Group):
        raise TypeError(f"Expected group '{root_group}' to be a group, got {type(group)}")

    return read_group(group)


def _parse_comments(h5f: h5py.File, header: HeaderDict) -> None:
    """
    Parse the comments dataset of an HDF5 file into the header.

    Parameters
    ----------
    h5f : h5py.File
        File handle of the HDF5 file to read the comments from.
    header : HeaderDict
        Header dictionary to append the comments to.
    """
    if (h5com := h5f.get("comments")) and isinstance(h5com, h5py.Dataset):
        for entry in h5com:
            message = entry[0].decode("utf-8")
            timestamp = entry[1].decode("utf-8")
            header["comments"].append(f"{timestamp}: {message}")


def _read_data(h5g: h5py.Group) -> np.ndarray | dict[str, np.ndarray]:
    """
    Read the datasets of a data group into a structured array.

    Parameters
    ----------
    h5g : h5py.Group
        The data group to read the datasets from.

    Returns
    -------
    np.ndarray | dict[str, np.ndarray]
        The data as a structured array, or a dictionary of arrays if the
        datasets have unequal lengths.
    """
    dtypeslist = []
    # the following line relies on the fact that the first item has
    # the correct length, the code fails later if there are unequal
    # length
    npoints = len(next(iter(h5g.values())))
    for name, v in h5g.items():
        if len(v.shape) == 1:
            dtypeslist.append((name, v.dtype))
        else:
            dtypeslist.append((name, v.dtype, v.shape[1:]))
    try:
        data = np.empty(npoints, dtype=np.dtype(dtypeslist))
        for name, v in h5g.items():
            data[name] = v[...]
    except ValueError:  # occurs for unequal data length in 1D arrays
        data = {name: v[...] for name, v in h5g.items()}
    return data


def load_hdf5_file(
    filename: Path, structured: bool
) -> tuple[HeaderDict, np.ndarray | dict[str, np.ndarray]]:
    """
    Load data from HDF5 file format.

    Parameters
    ----------
    filename : Path
        Path to the HDF5 file
    structured : bool
        Whether to return structured array

    Returns
    -------
    tuple[HeaderDict, np.ndarray | dict[str, np.ndarray]]
        Header information and data
    """
    header = create_empty_header()

    # use swmr read mode, to avoid corrupting the data during the
    # measurement (where it is written to by the matrix process)
    with h5py.File(filename, "r", swmr=True, libver="latest", locking=False) as h5f:
        h5g = h5f["data"]

        if not isinstance(h5g, h5py.Group):
            raise TypeError(f"Expected 'data' to be a Group, got {type(h5g).__name__}")

        # populate header fields from HDF5
        header["columns"] = list(h5g.keys())
        header["units"] = [it.attrs["unit"] for it in h5g.values()]

        # check whether comments exist in file
        _parse_comments(h5f, header)

        # parse additional attributes
        for key, val in h5f.attrs.items():
            header[key.lower()] = "" if val == "__None__" else val

        # parse System query entry into hierarchical dictionary
        if filename.suffix == ".ma8":
            header["system query"] = _load_dict_from_hdf5(h5f, "system query")

        # generate data object as structured array
        data = _read_data(h5g)

    return header, data
