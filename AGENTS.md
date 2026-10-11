# Project Overview

Matr1x is a Python package for data acquisition and instrument control,
providing command line and GUI tools for measurements and data analysis.

## Folder Structure

- `matr1x`: Package source, organized in layers. Lower layers must not
  import from higher layers (enforced by import-linter contracts in
  `pyproject.toml`). Internal code imports the canonical `matr1x.core.*`
  / `matr1x.gui.*` paths, never the backwards-compatibility shims in the
  package root (`matr1x.util`, `matr1x.system`, `matr1x.models`, ...):
  - `matr1x/apps`: The `matrix`, `matrix-gui`, `matrix-script` and
    related entry points (top layer).
  - `matr1x/systems`: System definitions (measurement setups), e.g. the
    dummy systems used by the tests.
  - `matr1x/control`: The control-GUI framework (`ControlWindow`,
    `GuiDict`, widgets) used by device control panels.
  - `matr1x/gui`: Shared GUI building blocks (app, editor, plot,
    widgets). May use Qt.
  - `matr1x/devices`: Instrument drivers, one subpackage per vendor.
    Must not import each other (except the shared base modules) and must
    not use Qt (exception: `matr1x.devices.lakeshore.control`, see the
    import-linter contracts).
  - `matr1x/core`: The backend without GUI or entry points: config,
    system base classes, models, eval, execthread, SCPI server, VISA
    helpers. Must not import the `matr1x` root package or Qt.
- `tests`: Pytest tests mirroring the package layers. Inputs for the
  entry points live in `tests/input`, data under analysis in
  `tests/data`, shared path fixtures in `tests/conftest.py`. Tests write
  their outputs to pytest's `tmp_path` and must not create files in the
  repository tree.
- `user_guide`: The user guide, built into a website via great-docs.
  `great-docs/` is the generated output (do not edit), `media/` holds
  the documentation images, `skills/` holds agent skills, `templates/`
  the changelog template.

## Public API

- The supported public API is pinned in `great-docs.yml` (reference
  section) and verified by `tests/test_public_api.py` against
  `tests/data/public_api_snapshot.json`. It is subject to the
  deprecation lifecycle described in
  `user_guide/60_development/05_deprecation.md`.
- Anything **not** listed in the public API may be renamed or removed in
  any release **without** a compatibility layer. Do not add alias
  classes, re-export shims, or legacy names for non-public items.
- Exception: TOML configuration entries are part of the interface users
  build against and keep the documented migration and deprecation
  handling (see `matr1x/core/config_schema.py`).

## Libraries and Frameworks

PySide6 for the GUI, urwid for the TUI of `matrix`, the Monaco editor
via `monaco-assets` for matrix-script, and a Python 3.10+ backend
(pydantic, h5py, numpy, polars, pymeasure, pyvisa, ...). `uv` manages
the environment, lockfile and build (build backend: `uv_build`).

## Coding Standards

- Format with `ruff format`, lint with `ruff check`, typecheck with
  `ty check`, test with `pytest`. Code for Python 3.10+ and strongly
  type all newly added code.
- Docstrings: numpy style, max 72 characters, rendered as Markdown by
  great-docs (no RST/Sphinx markup; use plain text or single-backtick
  code spans). Keep them short: a one-line summary for internal code,
  full numpy sections (`Parameters`, `Returns`, `Raises`) only for
  public-API items. Document behavior, not implementation details.
  Start with a verb or the item's role, never a self-reference: write
  "Manage the input request workflow", not "This method manages the
  input request workflow" (also avoid "A class for ..." and
  "Contains the ...").
- Keep function complexity at or below 15 with `complexipy`
  (`uv run complexipy`; do not pass ad-hoc paths, that rewrites
  `complexipy-snapshot.json` for those paths only).
- Enforce the package layering and import rules with import-linter
  (`uv run lint-imports`); keep the contracts in `pyproject.toml` green.

## Guidelines

- Before starting a task, check `skills/` for an agent skill matching
  the task (e.g. `writeControl` for new control GUIs, `migration` for
  package migrations) and follow its `SKILL.md`.
- Only change the code parts required for the change; do not touch
  other parts of the code.
- Commit messages must fit on a single line of less than 50
  characters: use the semantic commit message format
  (`type(scope): summary`) and do not add a body or footer; put any
  further context in the pull request description.
- Always run `ruff` and `ty` and address all newly added issues.
- `uv run` keeps the environment up to date; on a fresh checkout (or
  when something is missing) run `uv sync --all-extras` once. Add
  `--all-groups` (Python 3.11+) to also build the user guide.
- Run the test suite with this exact command (it works on local
  machines, CI, and in sandboxes; the pseudo-terminal is required by
  the `matrix` CLI tests, the Chromium flag by the QtWebEngine-based
  editor tests, and both are harmless elsewhere):

  ```sh
  QTWEBENGINE_CHROMIUM_FLAGS=--no-sandbox uv run pytest tests
  ```

- GUI tests run offscreen (`QT_QPA_PLATFORM=offscreen` is set by pytest).
- The package version and `CHANGELOG.md` are managed by semantic-release;
  do not edit them manually.
- When searching with `rg`, use `rg -n` (line numbers); never `rg -rn`,
  where `-r` aliases `--replace` and rewrites every match to `n`,
  garbling the output (e.g. `skills/security` becomes `n/security`).
