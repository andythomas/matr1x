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
Defines a system for demonstration of the HDF5 data file format option.

Note: The hdf5 data format is needed for multidimensional datasets but includes
a rather large overhead which is only compensated for if at each single data point
a large number of values is stored. For simple floating point values it is recommended
to stick to the ascii format.
In case you are interested in the overhead for chunked data storage in hdf5 see
https://davis.lbl.gov/Manuals/HDF5-1.8.7/Advanced/Chunking/index.html
"""

# ============================
# Custom import area
# ============================
import numpy

from matr1x.devices.dummy import dummy
from matr1x.system import System


# ============================
# This area contains the required MeasSystem definition and
# the optional reimplementation of the set and reset function
# ============================
class MeasSystem(System):
    """
    Measurement system with HDF5 support for testing matr1x-matrix.

    This class extends the base System class to provide a dummy system
    with HDF5 capabilities for testing purposes.
    """

    def __init__(self):
        """
        Initialize the MeasSystem.

        Sets up the system with a dummy source for HDF5 testing.
        """
        super().__init__()
        self.dcdata["source"] = "dummy system with HDF5 for testing matr1x-matrix"

    def get_p4(self, shape=-1):
        """
        Get and reshape the p4 parameter from the devhdf device.

        Parameters
        ----------
        shape : int or tuple, optional
            The shape to reshape the p4 array to. Default is -1 (flattened array).

        Returns
        -------
        numpy.ndarray
            The reshaped p4 parameter array.
        """
        return numpy.asarray(self.devs["devhdf"].p4).reshape(shape)


# ============================


# initialize system
system = MeasSystem()
# ========================================================================
# This is the main system area
# Device definition and configuration takes place here, but devices do
# not yet get opened!
#
# IMPORTANT:
#   The devices are not allowed to be opened here!
#   Otherwise the import would block any other use of the devices
#   Make sure to adhere to this or errors will occur!
# ========================================================================
system.add_dev("devhdf", dummy, args=("TCPIP::localhost::10010::SOCKET",))

# enforce HDF5 flag, will be set automatically if needed by any Parameter
# system.hdf5 = True

# define columns for measurement
system.add_param("devhdfp4_flat", "cnt", getter=["devhdf", "p4"], dtype="f8", chunks=4)
system.add_param("devhdfp4_1d", "cnt", getter=["devhdf", "p4"], chunks=(4,))
system.add_param(
    ["devhdf p3a", "devhdf p3b"],
    ["cnta", "cntb"],
    ["devhdf", "p3"],
    ["devhdf", "p3"],
    chunks=[1, 1],
    dtype=["i8", "i8"],
)
system.add_param(
    "devhdfp4_2d", "cnt", getter="get_p4", getter_kwargs={"shape": (2, 2)}, chunks=(2, 2)
)
system.add_param(
    ["rand2d_1", "rand2d_2"],
    ["cnt", "cnt"],
    getter=numpy.random.random,
    getter_args=[
        (2, 4, 4),
    ],
    chunks=[(4, 4), (4, 4)],
)
# ============================
