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
"""Subprocess-based introspection of system definitions."""

import logging
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from matr1x.core.deprecation import deprecation_marker
from matr1x.core.error_handling import Error, Result, Success
from matr1x.core.models import (
    SystemCapability,
    SystemInfo,
    SystemReference,
)
from matr1x.core.util import SUBPROCESS_CREATION_FLAGS

logger = logging.getLogger(__name__)


def get_system_info(
    systems: Sequence[str | Path | SystemReference],
) -> Result[SystemInfo, str]:
    """Get system information using a subprocess."""
    try:
        tokens = [SystemReference.from_value(system).to_token() for system in systems]
    except ValidationError as error:
        return Error(str(error))
    script = (
        "import json\n"
        "import sys\n"
        "from matr1x.core.config import validation_errors\n"
        "from matr1x.core.error_handling import Error\n"
        "from matr1x.core.system import MergedSystem\n"
        "validation_error_count = len(validation_errors)\n"
        f"result = MergedSystem.from_references({tokens!r})\n"
        "if isinstance(result, Error):\n"
        "    print(result.error, file=sys.stderr)\n"
        "    raise SystemExit(1)\n"
        "info = result.value.grab_information()\n"
        "info['config_validation_errors'] = validation_errors[validation_error_count:]\n"
        "print(json.dumps(info))\n"
    )
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
            ],
            capture_output=True,
            timeout=30,
            creationflags=SUBPROCESS_CREATION_FLAGS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return Error(f"Could not run system info subprocess: {e}")

    if result.returncode != 0:
        stderr_output = result.stderr.decode()
        return Error(stderr_output)
    output_str = result.stdout.decode()
    error_output = result.stderr.decode().strip()
    if error_output != "":
        marker = deprecation_marker
        if marker in error_output:
            logger.error(error_output)
        else:
            logger.warning(error_output)
    # Find the last line that looks like JSON to avoid warnings/garbage
    json_str = ""
    for line in reversed(output_str.splitlines()):
        if line.strip().startswith("{") and line.strip().endswith("}"):
            json_str = line.strip()
            break

    if not json_str:
        return Error(f"Warning: No JSON found in subprocess output:\n{output_str}")

    try:
        validated_data = SystemInfo.model_validate_json(json_str)
        return Success(validated_data)
    except ValidationError as e:
        return Error(f"Warning: Could not parse JSON from subprocess output:\n{e}")


def get_system_capability(source: str) -> Result[SystemCapability, str]:
    """Inspect one system definition without constructing it."""
    script = (
        "import sys\n"
        "from matr1x.core.error_handling import Error\n"
        "from matr1x.core.system import System\n"
        f"result = System.inspect_file({source!r})\n"
        "if isinstance(result, Error):\n"
        "    print(result.error, file=sys.stderr)\n"
        "    raise SystemExit(1)\n"
        "print(result.value.model_dump_json())\n"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            timeout=30,
            creationflags=SUBPROCESS_CREATION_FLAGS,
            check=False,
        )
    except OSError as error:
        return Error(f"Could not inspect system in subprocess: {error}")
    if result.returncode != 0:
        return Error(result.stderr.decode())
    try:
        output = result.stdout.decode().splitlines()[-1]
        return Success(SystemCapability.model_validate_json(output))
    except (IndexError, ValidationError) as error:
        return Error(f"Could not parse system capability: {error}")
