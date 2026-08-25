# This file is part of a software collection for data acquisition (matr1x).
# Copyright (C) 2006-2026 matr1x developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
"""Dublin Core metadata constants shared by matr1x applications."""

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
"""Valid Dublin Core metadata keys; false entries are auto-generated."""

APP_META_KEY = ["description"]
"""Dublin Core keys to which users may append."""
