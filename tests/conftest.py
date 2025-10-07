"""
Shared pytest fixtures and configuration for matr1x test suite.

Provides fixtures for managing Qt platform settings.
"""

import os
import sys

import pytest


@pytest.fixture(scope="session")
def qt_offscreen():
    """
    Set Qt platform to offscreen for headless testing.

    This fixture sets QT_QPA_PLATFORM to "offscreen". The environment
    variable is set at session scope and restored afterwards.

    Notes
    -----
    If the qapp fixture is used, the first Qt test in a testfile defines
    the Qt platform for all subsequent tests as well.
    """
    original_value = os.environ.get("QT_QPA_PLATFORM")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    yield
    if original_value is None:
        os.environ.pop("QT_QPA_PLATFORM", None)
    else:
        os.environ["QT_QPA_PLATFORM"] = original_value


@pytest.fixture(scope="session")
def qt_gui():
    """
    Set Qt platform to defined platform specific default.

    Sets QT_QPA_PLATFORM to "cocoa" for Mac, "windows" for windows and
    "offscreen" for other systems. The setting is restored afterwards.

    Notes
    -----
    If the qapp fixture is used, the first Qt test in a testfile defines
    the Qt platform for all subsequent tests as well.
    """
    original_value = os.environ.get("QT_QPA_PLATFORM")

    if sys.platform == "darwin":
        os.environ["QT_QPA_PLATFORM"] = "cocoa"
    elif sys.platform == "win32":
        os.environ["QT_QPA_PLATFORM"] = "windows"
    else:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    yield
    if original_value is None:
        os.environ.pop("QT_QPA_PLATFORM", None)
    else:
        os.environ["QT_QPA_PLATFORM"] = original_value
