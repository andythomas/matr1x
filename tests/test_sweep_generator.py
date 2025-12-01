# This file is part of a software collection for data aquisition (matr1x).
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
"""Test internal functions of sweep generator."""

from matr1x.error_handling import Error
from matr1x.scripts.sweep_generator import calculate_sweep, check_depth


def test_check_depth():
    """Test check_depth function using several examples."""
    result = check_depth(0, [-1, -1, 1, 2])
    assert not isinstance(result, Error)
    assert result.value == 0

    result = check_depth(1, [-1, -1, 1, 2])
    assert not isinstance(result, Error)
    assert result.value == 2

    result = check_depth(2, [-1, -1, 1, 2])
    assert not isinstance(result, Error)
    assert result.value == 1

    result = check_depth(3, [-1, -1, 1, 2])
    assert not isinstance(result, Error)
    assert result.value == 0


def test_calculate_sweep():
    """Test calculate_sweep function with one example."""
    sweep_parms = [[[1, 2, 2], [3, 4, 2]], [], [[-1, 1, 2]]]
    loop_over = [-1, -1, 0]
    up_down = [True, False, False]
    repeat = [1, 1, 1]
    expected_result = [
        [1.0, 2.0, 3.0, 4.0, 4.0, 3.0, 2.0, 1.0],
        [],
        [-1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0],
    ]
    result = calculate_sweep(sweep_parms, loop_over, up_down, repeat)
    assert not isinstance(result, Error)
    assert result.value == expected_result
