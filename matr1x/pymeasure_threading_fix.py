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
Thread Safety Monkey Patch for PyMeasure Instruments.

This module fixes thread safety issues in the pymeasure library where concurrent
write/read operations can interfere with each other, causing errors like:
"Wrong reply received when there should be an acknowledge."

The fix automatically patches all pymeasure.Instrument instances to use thread-safe
communication locks, preventing race conditions during concurrent access.

This can be removed when PyMeasure upstream implements proper thread safety
(pymeasure/pymeasure#506)

Usage is automatic - all pymeasure instruments become thread-safe when matr1x
is imported.
"""

import threading
import weakref

from pymeasure.instruments import Instrument

# Global registry to track instruments that have been patched with thread safety
# Using WeakSet to avoid memory leaks when instruments are garbage collected
_patched_instruments = weakref.WeakSet()


def _make_thread_safe_method(original_method, instance):
    """
    Create a thread-safe wrapper for an instrument communication method.

    This function wraps an instrument's communication method (write, read, ask)
    with a thread lock to prevent race conditions during concurrent access.

    Parameters
    ----------
    original_method : callable
        The original instrument method to wrap
    instance : pymeasure.instruments.Instrument
        The instrument instance that owns the method

    Returns
    -------
    callable
        Thread-safe wrapper function that acquires a lock before calling
        the original method
    """

    def thread_safe_wrapper(*args, **kwargs):
        # Ensure the instance has a communication lock
        if not hasattr(instance, "_comm_lock"):
            instance._comm_lock = threading.RLock()

        # Execute the original method within the lock
        with instance._comm_lock:
            return original_method(*args, **kwargs)

    # Preserve original method attributes for introspection
    thread_safe_wrapper.__name__ = getattr(original_method, "__name__", "thread_safe_wrapper")
    thread_safe_wrapper.__doc__ = getattr(original_method, "__doc__", None)

    return thread_safe_wrapper


def patch_instrument_for_thread_safety(instrument: Instrument) -> Instrument:
    """
    Apply thread safety patch to a pymeasure Instrument instance.

    This function modifies an existing pymeasure Instrument instance to use
    thread-safe communication methods. It's safe to call multiple times on
    the same instrument (subsequent calls are no-ops).

    Parameters
    ----------
    instrument : pymeasure.instruments.Instrument
        The instrument instance to make thread-safe

    Returns
    -------
    pymeasure.instruments.Instrument
        The same instrument instance, now with thread-safe communication

    Examples
    --------
    >>> from pymeasure.instruments import Instrument
    >>> instrument = Instrument(adapter)
    >>> safe_instrument = patch_instrument_for_thread_safety(instrument)
    >>> # Now instrument.write(), .read(), .ask() are thread-safe
    """
    # Skip if already patched to avoid double-wrapping
    if instrument in _patched_instruments:
        return instrument

    # Add communication lock to the instance
    instrument._comm_lock = threading.RLock()

    # Store references to original methods
    original_write = instrument.write
    original_read = instrument.read
    original_ask = instrument.ask

    # Replace methods with thread-safe versions
    instrument.write = _make_thread_safe_method(original_write, instrument)
    instrument.read = _make_thread_safe_method(original_read, instrument)
    instrument.ask = _make_thread_safe_method(original_ask, instrument)

    # Track this instrument as patched
    _patched_instruments.add(instrument)

    return instrument


def _patch_pymeasure_instrument_init():
    """
    Apply monkey patch to pymeasure.Instrument.__init__.

    This function modifies the pymeasure Instrument class so that all new
    instances automatically receive thread safety patches. The original
    __init__ method is preserved and called normally, with thread safety
    applied afterward.

    This is called automatically when this module is imported.
    """
    # Store reference to original __init__ method
    original_init = Instrument.__init__

    def thread_safe_init(self, *args, **kwargs):
        """Thread-safe wrapper for Instrument.__init__."""
        # Call original initialization
        result = original_init(self, *args, **kwargs)

        # Apply thread safety patch to the new instance
        patch_instrument_for_thread_safety(self)

        return result

    # Replace the class method with our wrapper
    Instrument.__init__ = thread_safe_init


# Apply the monkey patch automatically when this module is imported
# This ensures all pymeasure instruments are thread-safe by default
_patch_pymeasure_instrument_init()
