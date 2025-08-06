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
"""
Devices for matr1x measurements based on VisaDevice.

Please consider looking into pymeasure before using this device driver
as a template for new devices. We discourage the implementation of new
devices using the matr1x framework. Pull requests with new devices based
on VisaDevice will not be merged in the future.

Devices implemented here are kept for backward compatibility.
Instruments from pymeasure are fully compatible to be used within matr1x
systems.
"""

scpiPORTdrivers = 8888
