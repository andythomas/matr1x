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
"""Dublin core metadata constants for matr1x.

These constants are shared between the configuration system and the
generated script template. They live in a leaf module so that both the
``matr1x`` package root and ``matr1x.system`` can re-export them without
creating an import cycle.
"""

VALID_META_KEYS = {
    "creator": True,
    "date": False,
    "identifier": True,
    "relation": True,
    "description": True,
    "source": True,
    "type": True,
    "publisher": True,
    "format": False,
    "language": False,
}
"""
Valid metadata keys for the dublin core metadata.

The 'false' keys are auto-generated and cannot be set.
"""

APP_META_KEY = ["description"]
"""
The user can append to these dublin core keys.
"""
