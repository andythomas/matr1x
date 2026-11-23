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
"""Initialize a matr1x workspace from the command line."""

import argparse
import importlib.metadata
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

import tomli_w

DISTRIBUTION_NAME = "matr1x-measurements"
REPOSITORY_URL = "https://github.com/andythomas/matr1x"
RAW_REPOSITORY_URL = "https://raw.githubusercontent.com/andythomas/matr1x"
USER_GUIDE_URL = "https://andythomas.github.io/matr1x/"


class WorkspaceError(Exception):
    """Error while initializing a matr1x workspace."""


def _run(command: list[str], cwd: Path) -> None:
    """Run a command, streaming its output to the console."""
    # Drop VIRTUAL_ENV so that uv anchors to the workspace directory, not to
    # an environment that the caller may run in (e.g. `uv run` sets it).
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT")
    }
    result = subprocess.run(command, cwd=cwd, check=False, env=env)
    if result.returncode != 0:
        raise WorkspaceError(f"Command failed with code {result.returncode}: {' '.join(command)}")


def sanitize_name(name: str) -> str:
    """Derive a valid project and section name from a folder name."""
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-_.")
    return sanitized or "workspace"


def is_matr1x_checkout(path: Path) -> bool:
    """Check whether a folder is a matr1x source checkout."""
    project_file = path / "pyproject.toml"
    if not project_file.is_file():
        return False
    try:
        with project_file.open("rb") as file:
            data = tomllib.load(file)
    except tomllib.TOMLDecodeError:
        return False
    return data.get("project", {}).get("name") == DISTRIBUTION_NAME


def resolve_checkout(explicit: Path | None, workspace: Path) -> Path:
    """Determine the matr1x checkout for an editable install."""
    candidates = [explicit] if explicit is not None else [workspace.parent / "matr1x"]
    for candidate in candidates:
        if is_matr1x_checkout(candidate):
            return candidate.resolve()
    if explicit is not None:
        raise WorkspaceError(
            f"{explicit} is not a matr1x checkout (no pyproject.toml with "
            f"name '{DISTRIBUTION_NAME}')."
        )
    raise WorkspaceError(
        f"No matr1x checkout found at {workspace.parent / 'matr1x'}. "
        "Pass the path of a checkout with --matr1x."
    )


def pip_install_args(checkout: Path | None, extras: list[str]) -> list[str]:
    """Build the uv pip install arguments for the matr1x dependency."""
    if checkout is not None:
        target = str(checkout)
        args = ["-e"]
    else:
        target = DISTRIBUTION_NAME
        args = []
    if extras:
        target = f"{target}[{','.join(extras)}]"
    return args + [target]


def write_project_file(
    workspace: Path, name: str, checkout: Path | None, extras: list[str]
) -> None:
    """Write the pyproject.toml of a project-style workspace."""
    dependency = DISTRIBUTION_NAME
    if extras:
        dependency = f"{DISTRIBUTION_NAME}[{','.join(extras)}]"
    project: dict[str, object] = {
        "project": {
            "name": name,
            "version": "0.1.0",
            "requires-python": ">=3.10",
            "dependencies": [dependency],
        }
    }
    if checkout is not None:
        project["tool"] = {
            "uv": {"sources": {DISTRIBUTION_NAME: {"path": str(checkout), "editable": True}}}
        }
    with (workspace / "pyproject.toml").open("wb") as file:
        tomli_w.dump(project, file)


def seed_lock_file(workspace: Path, checkout: Path | None) -> None:
    """Copy the matr1x lock file to seed the workspace lock file.

    uv re-validates the copied file and re-locks whatever is stale, but
    keeps the copied versions for everything else, so the workspace
    environment stays close to the matr1x environment it came from.
    """
    destination = workspace / "uv.lock"
    if checkout is not None:
        source = checkout / "uv.lock"
        if not source.is_file():
            print(  # noqa: T201
                f"warning: no uv.lock in {checkout}; locking from scratch",
                file=sys.stderr,
            )
            return
        shutil.copyfile(source, destination)
        return
    version = importlib.metadata.version(DISTRIBUTION_NAME)
    if not _valid_version(version):
        print(  # noqa: T201
            f"warning: matr1x {version} is not a released version; locking from scratch",
            file=sys.stderr,
        )
        return
    url = f"{RAW_REPOSITORY_URL}/v{version}/uv.lock"
    try:
        with urllib.request.urlopen(url) as response:
            destination.write_bytes(response.read())
    except urllib.error.URLError as error:
        print(  # noqa: T201
            f"warning: could not download {url}: {error}; locking from scratch",
            file=sys.stderr,
        )


def create_environment(
    workspace: Path, project: bool, checkout: Path | None, extras: list[str]
) -> None:
    """Create the workspace environment and install matr1x into it."""
    if shutil.which("uv") is None:
        raise WorkspaceError("uv is required but was not found on the PATH.")
    if project:
        _run(["uv", "sync"], workspace)
    else:
        _run(["uv", "venv"], workspace)
        _run(["uv", "pip", "install", *pip_install_args(checkout, extras)], workspace)


def _valid_version(version: str) -> bool:
    """Check whether a version string has the shape of a released tag."""
    return bool(re.fullmatch(r"\d+\.\d+\.\d+", version))


def fetch_skills(version: str, destination: Path) -> None:
    """Download the skills of a released matr1x version from GitHub."""
    if not _valid_version(version):
        raise WorkspaceError(
            f"matr1x {version} does not look like a released version; "
            "no matching release archive to download skills from."
        )
    url = f"{REPOSITORY_URL}/archive/refs/tags/v{version}.tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "matr1x.tar.gz"
        try:
            with urllib.request.urlopen(url) as response, archive.open("wb") as file:
                shutil.copyfileobj(response, file)
        except urllib.error.URLError as error:
            raise WorkspaceError(f"Could not download {url}: {error}") from error
        with tarfile.open(archive) as tar:
            if sys.version_info >= (3, 12):
                tar.extractall(tmp, filter="data")
            else:
                tar.extractall(tmp)
        source = Path(tmp) / f"matr1x-{version}" / "skills"
        if not source.is_dir():
            raise WorkspaceError(f"No skills folder in the {version} release archive.")
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns(".*"))


def install_skills(workspace: Path, checkout: Path | None) -> None:
    """Copy the matr1x skills into the workspace."""
    destination = workspace / "skills"
    if checkout is not None:
        source = checkout / "skills"
        if not source.is_dir():
            raise WorkspaceError(f"No skills folder in the checkout: {source}")
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns(".*"))
    else:
        version = importlib.metadata.version(DISTRIBUTION_NAME)
        fetch_skills(version, destination)


def write_agents_md(
    workspace: Path,
    section: str,
    project: bool,
    checkout: Path | None,
    extras: list[str],
) -> None:
    """Write the AGENTS.md describing the workspace environment."""
    extras_suffix = f"[{','.join(extras)}]" if extras else ""
    if checkout is not None:
        if project:
            resync = "uv sync"
        else:
            resync = f"uv pip install -e {checkout}{extras_suffix}"
        source = (
            f"- matr1x is installed editable from `{checkout}`:\n"
            f"  - Coding conventions: `{checkout}/AGENTS.md`\n"
            "  - Task-specific procedures: the skills in `skills/` (this\n"
            "    folder); the source of truth is "
            f"`{checkout}/skills/` — re-copy\n"
            "    from there if it changed.\n"
            f"  - Update matr1x: `git -C {checkout} pull`, then re-sync this\n"
            f"    environment (`{resync}`)"
        )
    else:
        version = importlib.metadata.version(DISTRIBUTION_NAME)
        if project:
            update = "uv update matr1x-measurements"
        else:
            update = "uv pip install -U matr1x-measurements"
        source = (
            "- matr1x is installed from PyPI into this folder's `.venv`.\n"
            '  - User guide (incl. "Agentic coding"):\n'
            f"    {USER_GUIDE_URL}\n"
            "  - Task-specific procedures: the skills in `skills/` (this\n"
            f"    folder), copied from matr1x {version} at setup.\n"
            f"  - Update matr1x: `{update}`"
        )
    content = (
        "# matr1x workspace\n"
        "\n"
        "This folder contains my matr1x system files, control GUIs, and device\n"
        "drivers. It is registered in `~/.matr1x.toml` under the section\n"
        f"`[{section}]`.\n"
        "\n"
        "## Environment\n"
        "\n"
        "- Run Python from this folder: `uv run python <script>`\n"
        "  (uses this folder's `.venv`).\n"
        f"{source}\n"
    )
    (workspace / "AGENTS.md").write_text(content)


def register_section(workspace: Path, section: str, config_path: Path | None = None) -> None:
    """Register the workspace folder in the user configuration."""
    if config_path is None:
        config_path = Path("~/.matr1x.toml").expanduser()
    systems_directory = str(workspace)
    try:
        if config_path.is_file():
            text = config_path.read_text(encoding="utf-8")
            config = tomllib.loads(text)
            existing = config.get(section)
            if isinstance(existing, dict) and existing.get("systems_directory") == (
                systems_directory
            ):
                return
            if section in config:
                config[section] = {"systems_directory": systems_directory}
                config_path.write_text(tomli_w.dumps(config), encoding="utf-8")
                return
            if not text.endswith("\n"):
                text += "\n"
        else:
            text = ""
        entry = tomli_w.dumps({section: {"systems_directory": systems_directory}})
        config_path.write_text(text + ("\n" + entry if text else entry), encoding="utf-8")
    except OSError as error:
        raise WorkspaceError(f"Could not access {config_path}: {error}") from error


def init_workspace(
    directory: Path,
    project: bool = False,
    editable: bool = False,
    matr1x_path: Path | None = None,
    extras: list[str] | None = None,
) -> None:
    """Create a new matr1x workspace in a folder."""
    extras = extras or []
    workspace = directory.expanduser().resolve()
    if workspace.exists():
        for marker in (".venv", "pyproject.toml", "AGENTS.md"):
            if (workspace / marker).exists():
                raise WorkspaceError(
                    f"{workspace} already looks like a matr1x workspace "
                    f"(found {marker}). Choose another folder."
                )
    checkout = resolve_checkout(matr1x_path, workspace) if editable else None
    workspace.mkdir(exist_ok=True)
    section = sanitize_name(workspace.name)
    if project:
        write_project_file(workspace, section, checkout, extras)
        seed_lock_file(workspace, checkout)
    create_environment(workspace, project, checkout, extras)
    install_skills(workspace, checkout)
    write_agents_md(workspace, section, project, checkout, extras)
    register_section(workspace, section)
    print(f"Initialized matr1x workspace at {workspace}")  # noqa: T201
    print(  # noqa: T201
        f"Registered section [{section}] in {Path('~/.matr1x.toml').expanduser()}"
    )


def main() -> None:
    """Run the matrix-workspace command line interface."""
    parser = argparse.ArgumentParser(
        prog="matrix-workspace",
        description=(
            "Initialize a matr1x workspace: a folder with your own system "
            "files, control GUIs, and device drivers, prepared for matr1x "
            "and coding agents."
        ),
        epilog=(
            "In a folder without matr1x installed yet, bootstrap with: "
            "uv run --with 'matr1x-measurements' matrix-workspace init"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a new workspace.",
        description=(
            "Create the environment, AGENTS.md, and skills folder of a new "
            "matr1x workspace and register it in ~/.matr1x.toml."
        ),
    )
    init_parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path("."),
        help="Workspace folder (created if it does not exist).",
    )
    init_parser.add_argument(
        "--project",
        action="store_true",
        help="Make the workspace a uv project with pyproject.toml and lock file.",
    )
    init_parser.add_argument(
        "--editable",
        action="store_true",
        help="Install matr1x editable from a local checkout instead of PyPI.",
    )
    init_parser.add_argument(
        "--matr1x",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to the matr1x checkout (default: ../matr1x next to the workspace).",
    )
    init_parser.add_argument(
        "--extra",
        action="append",
        default=[],
        metavar="NAME",
        help="Install an extra of matr1x-measurements (repeatable).",
    )
    args = parser.parse_args()
    try:
        init_workspace(args.directory, args.project, args.editable, args.matr1x, args.extra)
    except WorkspaceError as error:
        print(f"error: {error}", file=sys.stderr)  # noqa: T201
        sys.exit(1)


if __name__ == "__main__":
    main()
