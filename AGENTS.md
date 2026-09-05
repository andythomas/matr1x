# Project Overview

Matr1x is a Python package for data acquisition and instrument control.
It provides command line and GUI tools for measurements and data analysis.
Most parts are written in Python and the editor uses some JavaScript.

## Folder Structure

- `matr1x`: The source code of the package, organized in layers.
  Lower layers must not import from higher layers (enforced by
  import-linter contracts in `pyproject.toml`):
  - `matr1x/scripts`: The `matrix`, `matrix-gui`, `matrix-script` and
    related entry points (top layer).
  - `matr1x/systems`: System definitions (measurement setups), e.g. the
    dummy systems used by the tests.
  - `matr1x/control`: The control-GUI framework (`ControlWindow`,
    `GuiDict`, widgets) used by device control panels.
  - `matr1x/gui`: Shared GUI building blocks (app, editor, plot, widgets,
    shared classes). May use Qt.
  - `matr1x/devices`: Instrument drivers, one subpackage per vendor.
    Device packages must not import each other (except the shared base
    modules) and must not use Qt.
  - `matr1x/core`: The backend without GUI or entry points: config,
    system base classes, models, eval, execthread, SCPI server, VISA
    helpers. Must not import the `matr1x` root package or Qt.
  - Package root: `__init__.py` (public config re-exports) plus thin
    backwards-compatibility shims for the historical module layout
    (`matr1x.util`, `matr1x.system`, `matr1x.models`, ...). Internal code
    must import the canonical `matr1x.core.*` / `matr1x.gui.*` paths,
    not the shims.
- `tests`: Pytest tests, mirroring the package layers (`tests/core`,
  `tests/control`, `tests/scripts`). `tests/input` holds input files for
  the entry points, `tests/data` holds data files under analysis. Shared
  path fixtures live in `tests/conftest.py`; tests write their outputs to
  pytest's `tmp_path` and must not create files in the repository tree.
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
- We enforce the package layering and import rules with import-linter
  (`uv run lint-imports`); keep the contracts in `pyproject.toml` green.

## Guidelines

- Please only change the code parts required for the code change and do
  not touch other parts of the code.
- Always run `ruff` and `ty` and address all newly added issues.
- `uv run` keeps the environment up to date automatically; no explicit
  sync is needed for day-to-day work.
- On a fresh checkout or is something is missing run `uv sync --all-extras` once.
- To build the user guide as well, sync with
  `uv sync --all-extras --all-groups` (adds the `docs` group, Python 3.11+).
- Run the test suite with `uv run pytest tests`. The `matrix` CLI tests
  need a terminal: in headless environments (CI, sandboxes) wrap the run
  in a pseudo-terminal, e.g. `script -q /dev/null sh -c 'uv run pytest tests'`.
- GUI tests run offscreen (`QT_QPA_PLATFORM=offscreen` is set by pytest).
- The `matrix-script`/`CodeEditor` tests need a working QtWebEngine
  renderer. Inside restrictive sandboxes set
  `QTWEBENGINE_CHROMIUM_FLAGS=--no-sandbox`, because the renderer cannot
  apply its own sandbox there.
- The package version and `CHANGELOG.md` are managed by semantic-release;
  do not edit them manually.
