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
"""Provide a stateless MCP server for matr1x."""

import base64
import io
import logging
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from mcp.server import MCPServer
from mcp.types import ImageContent, TextContent

from matr1x.core.eval import delta_polars, loadmatrix

logger = logging.getLogger(__name__)

mcp = MCPServer(
    "matr1x",
    description="Provide helpers when using the matr1x software package.",
)

_TEXTSIZE = 10
_TICKSIZE = 3
_FW = 300
_FH = 200
_LABELPAD = 4

_PLOT_STYLE: dict[str, Any] = {
    "figure.figsize": (_FW / 72, _FH / 72),
    "axes.titlesize": _TEXTSIZE,
    "axes.labelsize": _TEXTSIZE,
    "xtick.labelsize": _TEXTSIZE,
    "xtick.major.size": _TICKSIZE,
    "ytick.labelsize": _TEXTSIZE,
    "ytick.major.size": _TICKSIZE,
    "legend.fontsize": _TEXTSIZE,
    "font.size": _TEXTSIZE,
    "axes.ymargin": 0.1,
    "legend.handlelength": 1,
    "legend.columnspacing": 0.5,
    "legend.labelspacing": 0.25,
    "legend.handletextpad": 0.5,
    "legend.frameon": False,
    "lines.markersize": 4,
    "lines.linewidth": 1.5,
    "markers.fillstyle": "none",
    "lines.markeredgewidth": 0.75,
    "errorbar.capsize": 3,
    "axes.formatter.useoffset": False,
    "axes.linewidth": 1,
    "axes.labelpad": _LABELPAD,
    "axes.prop_cycle": plt.cycler(
        color=["#3f3f3f", "#9b193f", "#066682", "#70068a", "#d17f02", "#017d7d", "#d13102"],
    ),
    "figure.subplot.left": 45 / _FW,
    "figure.subplot.right": (_FW - 10) / _FW,
    "figure.subplot.bottom": 30 / _FH,
    "figure.subplot.top": (_FH - 10) / _FH,
    "ytick.right": False,
    "xtick.top": False,
    "ytick.direction": "out",
    "xtick.direction": "out",
    "savefig.format": "png",
    "savefig.dpi": 216,
}


def _load_frame(filename: Path) -> tuple[pl.DataFrame, dict[str, str]]:
    """
    Load a matr1x data file as a polars DataFrame.

    Parameters
    ----------
    filename : pathlib.Path
        Path to the .ma8 file (HDF5 or text based).

    Returns
    -------
    frame : polars.DataFrame
        The measurement data, one column per data field.
    units : dict
        Mapping of column name to unit string.
    """
    try:
        header, data = loadmatrix(filename, to_polars=True)
    except NotImplementedError:
        header, data = loadmatrix(filename)
    if isinstance(data, pl.DataFrame):
        frame = data
    elif isinstance(data, dict):
        frame = pl.DataFrame(data)
    else:
        names = data.dtype.names or ()
        frame = pl.DataFrame({name: data[name] for name in names})
    units = dict(zip(header["columns"], header["units"]))
    return frame, units


def _apply_math(frame: pl.DataFrame, column: str, math_mode: str | None, is_x: bool) -> pl.Series:
    """
    Resolve delta method data of a single column.

    Parameters
    ----------
    frame : polars.DataFrame
        Frame containing the column.
    column : str
        Name of the column to resolve.
    math_mode : str or None
        "delta-" or "delta+", or None to return the column unchanged.
    is_x : bool
        Whether the column is used on the x axis.

    Returns
    -------
    polars.Series
        The resolved column.
    """
    if math_mode is None:
        return frame.get_column(column)
    which = "pos" if is_x or math_mode == "delta+" else "neg"
    resolved = delta_polars(frame.select(column), column=column).select(which).collect()
    return resolved.to_series().alias(column)


def _label(column: str, units: dict[str, str]) -> str:
    """Return the axis label of a column, including its unit if known."""
    unit = units.get(column)
    return f"{column} ({unit})" if unit else column


def _error(message: str) -> list[TextContent | ImageContent]:
    """Build a tool result that carries an error message."""
    return [TextContent(type="text", text=f"Error: {message}")]


def _validate(
    path: str,
    x: str | None,
    y: str | None,
    z: str | None,
    math_mode: str | None,
) -> str | None:
    """Return an error message for invalid arguments, or None if they are valid."""
    if z is not None:
        return "3D plots (z) are not supported yet"
    if x is None and y is None:
        return "at least one of x or y is required"
    if math_mode not in (None, "delta-", "delta+"):
        return "math_mode must be 'delta-', 'delta+', or None"
    filename = Path(path).expanduser()
    if not filename.is_file():
        return f"file not found: {filename}"
    return None


@mcp.tool()
def plot_ma8(
    path: str,
    x: str | None = None,
    y: str | None = None,
    z: str | None = None,
    math_mode: str | None = None,
) -> list[TextContent | ImageContent]:
    """Render columns from a matr1x .ma8 data file as a PNG plot.

    Returns the plot as an inline image plus a short summary. Use it to
    visualize a measurement, inspect a column, or check a trend.

    Parameters
    ----------
    path : str
        Path to the .ma8 file (HDF5 or text based).
    x : str or None
        Name of the column to plot on the x axis.
    y : str or None
        Name of the column to plot on the y axis.
    z : str or None
        Name of the column for the z axis (3D plot). Not supported yet.
    math_mode : str or None
        Resolve delta method data, "delta-" or "delta+".
    """
    error = _validate(path, x, y, z, math_mode)
    if error is not None:
        return _error(error)
    filename = Path(path).expanduser()
    try:
        frame, units = _load_frame(filename)
    except (OSError, ValueError) as error:
        logger.warning("Could not load %s: %s", filename, error)
        return _error(f"could not load {filename}: {error}")
    columns = [column for column in (x, y) if column is not None]
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        return _error(f"unknown column(s) {missing}. Available: {list(frame.columns)}")
    frame = pl.concat(
        [_apply_math(frame, column, math_mode, column == x).to_frame() for column in columns],
        how="horizontal",
    )
    return _render(frame, units, x, y, filename)


def _render(
    frame: pl.DataFrame,
    units: dict[str, str],
    x: str | None,
    y: str | None,
    filename: Path,
) -> list[TextContent | ImageContent]:
    """Render the frame to a PNG and build the tool result."""
    plt.rcParams.update(_PLOT_STYLE)  # ty: ignore[no-matching-overload]
    value = y if y is not None else x
    if value is None:
        return _error("at least one of x or y is required")
    x_values = frame.get_column(x).to_numpy() if x is not None else np.arange(len(frame))
    y_values = frame.get_column(value).to_numpy()
    fig, ax = plt.subplots()
    ax.plot(x_values, y_values)
    ax.set_xlabel(_label(x, units) if x is not None else "index")
    ax.set_ylabel(_label(value, units))
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    plt.close(fig)
    columns = list(frame.columns)
    logger.info("Plotted %s from %s", columns, filename)
    summary = f"Plotted {columns} from {filename.name}, {len(frame)} points"
    return [
        TextContent(type="text", text=summary),
        ImageContent(
            type="image",
            data=base64.b64encode(buffer.getvalue()).decode(),
            mime_type="image/png",
        ),
    ]


def main() -> None:
    """Run the matr1x MCP server on stdio."""
    # logging must go to stderr, stdout carries the JSON-RPC messages
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
