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
"""GUI subpackage of matr1x.

Contains the Qt-based user interface. This is the top layer of the
architecture: it may depend on :mod:`matr1x.core` and other lower layers,
but the reverse is not allowed. Keeping the Qt imports here (rather than in
the Qt-free :mod:`matr1x.core`) is what lets the core stay GUI-agnostic.
"""
