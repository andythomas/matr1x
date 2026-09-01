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
"""Re-export shim. The implementation lives in :mod:`matr1x.core.util`."""

from matr1x.core.execthread import matrix_script_process
from matr1x.core.util import (
    Command,
    Get,
    Set,
    StreamToLogger,
    construct_query_string,
    create_temp_dir_with_symlinks,
    default_separator,
    find_binary,
    flatten,
    generate_col_index,
    generate_script,
    generate_script_prefix_suffix,
    get_formatted_line,
    get_matrix_binary,
    get_package_path,
    get_pt100_temp,
    get_script_prefix_offset,
    get_user_script_line_range,
    init_ascii_header,
    init_hdf5_skel,
    log_multiline,
    module_from_path,
    normalize_cmds,
    resolve_config_path,
    resolve_pkgroot_path,
    run_python_cmdline,
    save_dict_to_hdf5,
)

__all__ = [
    "Command",
    "Get",
    "Set",
    "StreamToLogger",
    "construct_query_string",
    "create_temp_dir_with_symlinks",
    "default_separator",
    "find_binary",
    "flatten",
    "generate_col_index",
    "generate_script",
    "generate_script_prefix_suffix",
    "get_formatted_line",
    "get_matrix_binary",
    "get_package_path",
    "get_pt100_temp",
    "get_script_prefix_offset",
    "get_user_script_line_range",
    "init_ascii_header",
    "init_hdf5_skel",
    "log_multiline",
    "matrix_script_process",
    "module_from_path",
    "normalize_cmds",
    "resolve_config_path",
    "resolve_pkgroot_path",
    "run_python_cmdline",
    "save_dict_to_hdf5",
]
