# This file is part of a software collection for data aquisition (matr1x).
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
"""Shared pytest fixtures for matr1x tests."""

import sys

import pytest
from PySide6.QtCore import QByteArray
from PySide6.QtWebEngineCore import QWebEngineUrlScheme

from matr1x.gui_util import MApplication


def pytest_configure(config):
    """Register the monaco:// URL scheme before QWebEngine is initialized."""
    scheme = QWebEngineUrlScheme(QByteArray(b"monaco"))
    scheme.setFlags(
        QWebEngineUrlScheme.Flag.CorsEnabled
        | QWebEngineUrlScheme.Flag.LocalAccessAllowed
        | QWebEngineUrlScheme.Flag.SecureScheme
        | QWebEngineUrlScheme.Flag.FetchApiAllowed
    )
    QWebEngineUrlScheme.registerScheme(scheme)


@pytest.fixture(scope="session")
def qapp():
    """Create and later exit an MApplication instance."""
    argv = sys.argv or ["pytest"]
    app = MApplication(argv)
    yield app
