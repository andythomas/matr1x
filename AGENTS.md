# Project Overview

Matr1x is a Python package for data acquisition and instrument control.
It provides command line and GUI tools for measurements and data analysis.
Most parts are written in Python and the editor uses some JavaScript.

## Folder Structure

- `matr1x`: The source code of the package.
- `matr1x/devices`: Instrument drivers
- `matr1x/scripts`: The `matrix`, `matrix-gui`, `matrix-script` and related entry points.
- `tests`: Pytest tests.
- `user_guide`: The user guide, built into a website via great-docs.
- `great-docs`: Output folder of the documentation build (generated, do not edit).
- `media`: Images and other media used by the documentation.
- `skills`: Agent skills (e.g. the required steps for a matr1x package migration).
- `templates`: Contains the changelog template.

## Libraries and Frameworks

- PySide6 for the GUI frontend.
- Python 3.10+ and many libraries for the backend (pydantic, h5py, numpy, pandas, pymeasure, pyvisa, ...).
- urwid for the terminal user interface of the `matrix` script.
- The VS-code core (Monaco editor) via `monaco-assets` for matrix-script.
- `uv` for environment management, locking and building (build backend: `uv_build`).

## Coding Standards

- We format our code with `ruff format`.
- We lint our code with `ruff check`.
- We typecheck our code with `ty check`.
- We test our code via `pytest`.
- We code for Python 3.10 and above.
- We strongly type all newly added code.
- We use numpy docstring style with a maximum of 72 characters line length.
- We keep function complexity in check with `complexipy` (max complexity 15, see `pyproject.toml`).

## Guidelines

- Please only change the code parts required for the code change and do
  not touch other parts of the code.
- Always run `ruff` and `ty` and address all newly added issues.
- `uv run` keeps the environment up to date automatically; no explicit
  sync is needed for day-to-day work.
- On a fresh checkout or is something is missing run `uv sync --all-extras` once.
- To build the user guide as well, sync with
  `uv sync --all-extras --all-groups` (adds the `docs` group, Python 3.11+).
- Run the test suite with this single command (it works on local
  machines, CI, and inside sandboxes):

  ```sh
  QTWEBENGINE_CHROMIUM_FLAGS=--no-sandbox script -q /dev/null sh -c 'uv run pytest tests'
  ```

  The pseudo-terminal (`script`) is needed because the `matrix` CLI tests
  require a terminal, and `QTWEBENGINE_CHROMIUM_FLAGS=--no-sandbox` is
  needed because the QtWebEngine renderer used by the
  `matrix-script`/`CodeEditor` tests cannot apply its own sandbox in
  restricted environments. Both are harmless outside sandboxes, so always
  use the command as-is instead of plain `uv run pytest tests`.
- GUI tests run offscreen (`QT_QPA_PLATFORM=offscreen` is set by pytest).
- The package version and `CHANGELOG.md` are managed by semantic-release;
  do not edit them manually.
