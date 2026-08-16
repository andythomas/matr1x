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

"""Perform desktop (un-)integration from the command line."""

import argparse
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)

# Configure console logging before importing matr1x, which initializes logging.
from matr1x.post_install import post_installation, remove_desktop_integration  # noqa: E402

parser = argparse.ArgumentParser(
    description="Perform or remove desktop integration of the matr1x applications.",
)

parser.add_argument(
    "-u",
    "--uninstall",
    action="store_true",
    help="Only remove desktop integration.",
)

options = parser.parse_args()


def main() -> None:
    """Perform the (un-)integration."""
    if options.uninstall:
        remove_desktop_integration()
    else:
        post_installation()


if __name__ == "__main__":
    main()
