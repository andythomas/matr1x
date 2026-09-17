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
INTERNAL TEMPLATE FILE - DO NOT RUN OR IMPORT DIRECTLY.

This file is a template used by matr1x.core.util.generate_script() to
create executable scripts for matrix-script. It contains placeholder
variables and markers that must be replaced before execution.

The template is executed via `exec` with an injected namespace (see
`ExecThread.run`). It installs the script API (the functions available
in user scripts, see `matr1x.core.script_api`) and imports it into
the script namespace.
"""

import os as _os
import re as _re
import sys as _sys
import textwrap as _textwrap
import time as _time
import traceback as _traceback
import types as _types
import typing as _typing
from pathlib import Path as _Path

import wrapt as _wrapt

import matr1x as _matr1x
import matr1x.core.util as _matrix_util
from matr1x.core import script_api as _script_api
from matr1x.core.models import Message as _Message
from matr1x.core.script_api import (
    end_script,
    init_datafile,
    input,  # noqa: A004
    input_bool,
    input_numerical,
    measure_system,
    print,  # noqa: A004
    read_value,
    set_value,
    trigger_value,
    wait,
)
from matr1x.core.system import MergedSystem as _MergedSystem

if _typing.TYPE_CHECKING:
    from matr1x.core.execthread import ExecThread

    class _ThreadAPI:
        def __init__(self, exec_thread: ExecThread):
            self._exec_thread = exec_thread

    _thread_api = _ThreadAPI(ExecThread("", {}, "", None, []))

    # This has to match _vars in the run method of ExecThread
    _interrupt = _thread_api._exec_thread.interrupt
    _status = _thread_api._exec_thread.stop_status
    _report = _thread_api._exec_thread.report
    _input = _thread_api._exec_thread.input
    _meta_data = _thread_api._exec_thread.meta_data
    _scriptname = _thread_api._exec_thread.scriptname
    _script = _thread_api._exec_thread.script
    _system = _thread_api._exec_thread.system

_validated_config = _matr1x.config.matr1x.scripts.matrix_script

for _key, _value in _meta_data.items():
    if _matr1x.VALID_META_KEYS.get(_key):
        _system.dcdata[_key] = _value
_reset_kwargs = {}

_script_api.install(_system, _report, _interrupt, _input, _status, _script, _scriptname)


def _configure_execution_path(scriptname: str | _Path) -> None:
    """Change execution path if requested in config."""
    script_path = _Path(scriptname)
    if _validated_config.script_path is None:
        if script_path.parent != _Path.cwd():
            _os.chdir(script_path.parent)
    else:
        config_path = _Path(_validated_config.script_path)
        if config_path.exists():
            _os.chdir(config_path)


def _configure_script_storing(system: _MergedSystem, script: str) -> None:
    """Store user script if requested in config."""
    if _validated_config.store_script_in_datafile:
        _, suffix = _matrix_util.generate_script_prefix_suffix()
        npref, nsuff = _matrix_util.get_script_prefix_offset(), len(suffix.splitlines())
        # strip prefix and suffix lines from script for storing
        user_script = _textwrap.dedent("\\n".join(script.splitlines()[npref:-nsuff]))
        if "user script" not in system.system_config_params:
            system.system_config_params["user script"] = user_script
        else:
            _report(
                _Message(
                    "'user script' key already present in system, not overwriting!",
                    to_comment=False,
                )
            )


@_wrapt.decorator
def _lineno_decorator(wrapped, instance, args, kwargs):
    """Report the executing line number back to the GUI."""
    _ = instance  # suppress ty warning
    _script_api.show_lineno()
    return wrapped(*args, **kwargs)


@_wrapt.decorator
def _breakpoint(wrapped, instance, args, kwargs):
    """Add a breakpoint check."""
    # avoid recursive loop (a decorated function calling another)
    # If the wrapped object is a method, attach _calling to the instance
    if instance is not None:
        if not hasattr(instance, "_calling"):
            instance._calling = False

        if instance._calling:
            # do not call decoration recursively
            return wrapped(*args, **kwargs)

        instance._calling = True
        try:
            _script_api.checkpoint()
            result = wrapped(*args, **kwargs)
        finally:
            instance._calling = False
    else:
        # If the wrapped object is a function,
        # attach _calling to the function itself
        if not hasattr(wrapped, "_calling"):
            wrapped._calling = False

        if wrapped._calling:
            # do not call decoration recursively
            return wrapped(*args, **kwargs)

        wrapped._calling = True
        try:
            _script_api.checkpoint()
            result = wrapped(*args, **kwargs)
        finally:
            wrapped._calling = False
    return result


def _inject_decorator(instance, decorator) -> None:
    """Inject decorator into instance methods."""
    for attr_name in dir(instance):
        if attr_name in ["add_comment", "report"]:
            # exclude this methods from decoration since they are
            # potentially called from inside the decorator. anything
            # called inside the _interrupt function should be added
            # here/not decorated.
            continue
        attr = getattr(instance, attr_name)
        if isinstance(attr, _types.MethodType):
            decorated_attr = decorator(attr)
            setattr(instance, attr_name, decorated_attr)


_time.sleep = _lineno_decorator(_time.sleep)  # ty: ignore[invalid-assignment]
_inject_decorator(_system, _breakpoint)  # inject system methods

for subsys in _system.subsys:
    _inject_decorator(subsys, _breakpoint)
    _inject_decorator(subsys, _lineno_decorator)
# bring meta_data and system into namespace
meta_data = _system.dcdata
system = _system

# load execution path of scripts and change to this directory
_configure_execution_path(_scriptname)
# optionally set user script to be stored in data file
_configure_script_storing(_system, _script)
# initialize system and put devs into namespace
_report(_Message("setting system", to_comment=False))
# system.set is called before the filename is set. So, we have no
# arguments here -> this is a difference to matrix
_system.set()
devs = _system.devs

# switch meta data to append state
_system.dcdata.append = True
_script_api.capture_initial_meta_data()

try:
    pass  # handle empty scripts
    # ==== BEGIN USER SCRIPT AREA ====
    # USER_SCRIPT_INSERTION_POINT
# ==== END USER SCRIPT AREA ====
except KeyboardInterrupt:
    _report(_Message("\nscript has been aborted by user."))
    if _status.finished:
        _reset_kwargs["status"] = "finished"
    elif _status.finished is False:
        _reset_kwargs["status"] = "aborted"
except Exception as e:
    _report(_Message("script exited with error:", to_comment=False))
    exc_type, exc_value, exc_traceback = _sys.exc_info()

    tbinfo = _traceback.format_exception(exc_type, exc_value, exc_traceback)

    # Don't skip the traceback lines - we need them for line number
    # extraction
    tbstr = "".join(tbinfo[1:])  # Skip only the first line (Traceback header)
    tbstr = tbstr.replace("<module>", "script")

    # get line information from traceback
    ms = _re.search(r"line (\d+)", tbstr)

    if ms:
        line = int(ms.group(1))
        n_pref = _matrix_util.get_script_prefix_offset()
        adjusted_line = line - n_pref
        tbstr = _re.sub(r"line (\d+)", "line " + str(adjusted_line), tbstr)

        # Fix file replacement - get the actual script content
        # Since we're executing from a string, we need to get the script
        # content differently
        try:
            # Get the current script content from the _script variable
            # that was injected
            script_lines = _script.splitlines()
            if 1 <= line <= len(script_lines):
                actual_line = script_lines[line - 1].strip()
                tbstr = tbstr.replace('File "<string>"', f'"{actual_line}"')
            else:
                tbstr = tbstr.replace('File "<string>"', '"<unknown line>"')
        except Exception:
            tbstr = tbstr.replace('File "<string>"', '"<script>"')

        _report(_Message(tbstr, to_comment=False))

        # Check adjusted line instead of original line
        if adjusted_line < 1:
            _report(_Message(" error during device initialization", to_comment=False))
    else:
        # No line number found in traceback
        tbstr = tbstr.replace('File "<string>"', '"<script>"')
        _report(_Message(tbstr, to_comment=False))
        _report(_Message(" error during device initialization", to_comment=False))

    _reset_kwargs["status"] = "errored"
    if exc_type is None:
        _system.add_comment(f"Script errored: {e}")
    else:
        _system.add_comment(f"Script errored: {exc_type.__name__}: {e}")
# mark last open file as finished, if not labeled elsewhere
if "status" not in _reset_kwargs:
    _reset_kwargs["status"] = "finished"
_report(_Message("resetting system"))
_system.reset(**_reset_kwargs)
