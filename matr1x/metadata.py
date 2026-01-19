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
Metadata constants and definitions for the matr1x data acquisition software.

This module centralizes all metadata-related constants to avoid circular imports
between the main package modules. It defines Dublin Core metadata keys,
their editability status, and appendability settings.
"""

# Define allowed Dublin Core metadata keys and their properties
# The dictionary values indicate whether the key is editable in the GUI
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

# Metadata keys that support value appending (instead of overwriting)
# These keys can have multiple values separated by special delimiters
APP_META_KEY = ["description"]
