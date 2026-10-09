# This file is part of a software collection for data aquisition (matr1x).
# Copyright (C) 2006-2026 matr1x developers
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3.0, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""Tests for the pytest environment setup."""

import os


def test_environment_variable_is_set():
    """Check if the QT_QPA_PLATFORM environment variable is set to 'offscreen'."""
    assert os.getenv("QT_QPA_PLATFORM") == "offscreen"
    assert os.getenv("QT_QUICK_BACKEND") == "software"
