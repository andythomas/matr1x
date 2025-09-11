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
communication operations can interfere with each other, causing errors like:
"Wrong reply received when there should be an acknowledge."

The fix patches all pymeasure.Instrument communication methods at the class level,
making them thread-safe by default. This protects:
- Direct method calls: write(), read(), ask(), values(), binary_values(), etc.
- Property access: Properties created by control(), setting(), measurement() are
  made atomic to prevent race conditions between their internal method calls
- Error checking methods: check_get_errors(), check_set_errors()

Implementation details:
- Uses RLock-based synchronization for reentrant safety
- Class-level patching ensures all instrument instances are protected
- Per-instance locks prevent different instruments from blocking each other
- No performance overhead for single-threaded usage

This can be removed when PyMeasure upstream implements proper thread safety
(pymeasure/pymeasure#506, pymeasure/pymeasure#952)

Usage is automatic - all pymeasure instruments become thread-safe when matr1x
is imported.
"""

import threading
from collections.abc import Callable
from functools import wraps
from typing import Any

from pymeasure.instruments import Instrument

# Methods that need thread-safe protection for communication
# These methods perform actual I/O operations that can interfere with each other
_COMMUNICATION_METHODS = {
    "write",
    "read",
    "ask",
    "values",
    "binary_values",
    "check_get_errors",
    "check_set_errors",
    "wait_for_srq",
}


def _create_thread_safe_property_accessor(
    original_accessor: Callable[..., Any], accessor_type: str
) -> Callable[..., Any]:
    """
    Create a thread-safe wrapper for property getter or setter.

    Property accessors may make multiple communication method calls in sequence
    (e.g., write() then check_set_errors(), or values() then check_get_errors()).
    This wrapper ensures the entire property operation is atomic.

    Parameters
    ----------
    original_accessor : callable
        The original property getter or setter function
    accessor_type : str
        Type of accessor ('getter' or 'setter') for debugging

    Returns
    -------
    callable
        Thread-safe wrapper that acquires the communication lock for the
        entire operation
    """

    @wraps(original_accessor)
    def thread_safe_accessor(self: Instrument, *args: Any, **kwargs: Any) -> Any:
        # Ensure instance has a communication lock
        _ensure_comm_lock(self)
        # Execute the entire property operation atomically
        with self._comm_lock:
            return original_accessor(self, *args, **kwargs)

    # Preserve debugging information
    thread_safe_accessor.__name__ = f"thread_safe_{accessor_type}"
    return thread_safe_accessor


def _ensure_comm_lock(instance: Instrument) -> None:
    """
    Ensure an instrument instance has a communication lock.

    Parameters
    ----------
    instance : pymeasure.instruments.Instrument
        The instrument instance that needs a communication lock
    """
    if not hasattr(instance, "_comm_lock"):
        instance._comm_lock = threading.RLock()


def _add_atomic_operation_method(instrument: Instrument) -> None:
    """
    Add atomic_operation context manager method to instrument instance.

    This provides a clean API for users who need to perform custom
    atomic operations beyond what the built-in properties provide.
    """
    from contextlib import contextmanager

    @contextmanager
    def atomic_operation():
        """
        Context manager for atomic instrument operations.

        Use this when you need to perform multiple instrument operations
        atomically without interference from other threads.

        Examples
        --------
        >>> with instrument.atomic_operation():
        ...     instrument.write("CONFIG:MODE ADVANCED")
        ...     instrument.write("PARAM:VOLTAGE 5.0")
        ...     result = instrument.ask("MEASURE:DATA?")

        Returns
        -------
        context manager
            Context manager that acquires the communication lock
        """
        instrument._comm_lock.acquire()
        try:
            yield
        finally:
            instrument._comm_lock.release()

    # Add the method to the instance
    instrument.atomic_operation = atomic_operation


def _patch_pymeasure_instrument_methods():
    """
    Apply class-level patches to pymeasure.Instrument communication methods.

    This patches communication methods at the class level to ensure all instances
    use thread-safe communication by default. Each method is wrapped with proper
    locking to prevent race conditions during concurrent access.

    The key insight is that PyMeasure properties internally call these methods
    (especially 'values' and 'ask'), so by making these methods thread-safe,
    we automatically make property access thread-safe as well.

    Methods patched: write, read, ask, values, binary_values, check_get_errors,
    check_set_errors, wait_for_srq
    """
    for method_name in _COMMUNICATION_METHODS:
        if hasattr(Instrument, method_name):
            original_method = getattr(Instrument, method_name)
            if callable(original_method):
                # Create a thread-safe wrapper with proper closure handling
                def create_synchronized_method(
                    orig_method: Callable[..., Any], name: str
                ) -> Callable[..., Any]:
                    @wraps(orig_method)
                    def synchronized_method(self: Instrument, *args: Any, **kwargs: Any) -> Any:
                        # Ensure instance has a communication lock
                        _ensure_comm_lock(self)
                        # Use the lock for synchronization
                        with self._comm_lock:
                            return orig_method(self, *args, **kwargs)

                    # Preserve method name for debugging
                    synchronized_method.__name__ = f"synchronized_{name}"
                    return synchronized_method

                # Replace the method with the synchronized version
                synchronized_method = create_synchronized_method(original_method, method_name)
                setattr(Instrument, method_name, synchronized_method)


def _create_thread_safe_property_creator(original_method, method_name):
    """
    Create a thread-safe wrapper for property creation methods.

    This wraps property creation methods like control(), setting(), and measurement()
    to ensure the properties they create have thread-safe accessors.
    """

    @staticmethod
    def thread_safe_property_creator(*args, **kwargs):
        """Thread-safe wrapper for property creation methods."""
        # Create the property using the original method
        prop = original_method(*args, **kwargs)

        # Wrap the property getter and setter with thread safety
        thread_safe_getter = None
        thread_safe_setter = None

        if prop.fget is not None:
            thread_safe_getter = _create_thread_safe_property_accessor(prop.fget, "getter")

        if prop.fset is not None:
            thread_safe_setter = _create_thread_safe_property_accessor(prop.fset, "setter")

        # Return a new property with thread-safe accessors
        return property(
            fget=thread_safe_getter, fset=thread_safe_setter, fdel=prop.fdel, doc=prop.__doc__
        )

    # Mark as patched
    thread_safe_property_creator._threading_patched: bool = True
    thread_safe_property_creator.__name__ = f"thread_safe_{method_name}"

    return thread_safe_property_creator


def _patch_pymeasure_property_creators():
    """
    Patch all PyMeasure property creation methods for thread safety.

    PyMeasure has multiple methods that create properties with potential race conditions:
    - Instrument.control: Creates read/write properties
    - Instrument.setting: Creates write-only properties
    - Instrument.measurement: Creates read-only properties

    All of these can make multiple communication method calls in sequence and
    need to be atomic to prevent race conditions.
    """
    # List of property creation methods that need patching
    property_methods = ["control", "setting", "measurement"]

    for method_name in property_methods:
        if hasattr(Instrument, method_name):
            original_method = getattr(Instrument, method_name)

            # Check if already patched to avoid recursion
            if hasattr(original_method, "_threading_patched") or getattr(
                original_method, "__name__", ""
            ).startswith("thread_safe_"):
                continue

            # Create and apply the thread-safe wrapper
            thread_safe_method = _create_thread_safe_property_creator(original_method, method_name)
            setattr(Instrument, method_name, thread_safe_method)


def _patch_pymeasure_instrument_init():
    """
    Apply monkey patch to pymeasure.Instrument.__init__.

    This function modifies the pymeasure Instrument class so that all new
    instances automatically receive thread safety patches. The original
    __init__ method is preserved and called normally, with thread safety
    applied afterward.

    This is called automatically when this module is imported.
    """
    # Check if already patched to avoid recursion
    if hasattr(Instrument.__init__, "_threading_patched"):
        return

    # Store reference to original __init__ method
    original_init = Instrument.__init__

    def thread_safe_init(self: Instrument, *args: Any, **kwargs: Any) -> Any:
        """Thread-safe wrapper for Instrument.__init__."""
        # Call original initialization
        result = original_init(self, *args, **kwargs)

        # Ensure this instance has a communication lock
        _ensure_comm_lock(self)

        # Add atomic operation context manager method
        _add_atomic_operation_method(self)

        return result

    # Mark as patched and replace the class method
    thread_safe_init._threading_patched: bool = True
    setattr(Instrument, "__init__", thread_safe_init)


# Apply the monkey patches automatically when this module is imported
# This ensures all pymeasure instruments are thread-safe by default

# First, patch the communication methods at class level
# This provides basic thread safety for individual method calls
_patch_pymeasure_instrument_methods()

# Then, patch all property creation methods (control, setting, measurement)
# This ensures property getters/setters that make multiple method calls
# are executed atomically without interference from other threads
_patch_pymeasure_property_creators()

# Finally, patch the __init__ method to ensure proper setup
_patch_pymeasure_instrument_init()
