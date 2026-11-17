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
"""Tests for the matrix-workspace command line tool."""

import shutil
import sys
from pathlib import Path

import pytest

from matr1x.apps import workspace

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def run_workspace(monkeypatch: pytest.MonkeyPatch, *args: str) -> int:
    """Run matrix-workspace in-process and return its exit code."""
    monkeypatch.setattr(sys, "argv", ["matrix-workspace", *args])
    try:
        workspace.main()
    except SystemExit as error:
        return int(error.code or 0)
    return 0


@pytest.fixture
def fake_uv(monkeypatch: pytest.MonkeyPatch) -> list[tuple[list[str], Path]]:
    """Replace the uv subprocess calls with a recorder."""
    calls: list[tuple[list[str], Path]] = []

    def fake_run(command: list[str], cwd: Path) -> None:
        calls.append((command, cwd))

    monkeypatch.setattr(workspace, "_run", fake_run)
    return calls


@pytest.fixture
def fake_fetch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Replace the skills download with a local copy."""
    source = tmp_path / "skills-source"
    (source / "migration").mkdir(parents=True)
    (source / "migration" / "SKILL.md").write_text("downloaded skill")
    (source / ".DS_Store").write_text("junk")

    def fake_fetch(version: str, destination: Path) -> None:
        shutil.copytree(source, destination, ignore=shutil.ignore_patterns(".*"))

    monkeypatch.setattr(workspace, "fetch_skills", fake_fetch)


@pytest.fixture
def checkout(tmp_path: Path) -> Path:
    """Create a fake matr1x checkout with a skills folder."""
    path = tmp_path / "checkout"
    path.mkdir()
    (path / "pyproject.toml").write_text('[project]\nname = "matr1x-measurements"\n')
    (path / "AGENTS.md").write_text("# checkout conventions")
    (path / "skills" / "migration").mkdir(parents=True)
    (path / "skills" / "migration" / "SKILL.md").write_text("checkout skill")
    return path


@pytest.fixture
def home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the user configuration at a temporary home directory."""
    path = tmp_path / "home"
    path.mkdir()
    monkeypatch.setenv("HOME", str(path))
    return path


def test_sanitize_name() -> None:
    """Check the derivation of project and section names."""
    assert workspace.sanitize_name("my-lab") == "my-lab"
    assert workspace.sanitize_name("My Lab 42") == "My-Lab-42"
    assert workspace.sanitize_name("!!!") == "workspace"


def test_init_plain(
    tmp_path: Path, home: Path, fake_uv: list, fake_fetch: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Initialize a plain workspace with matr1x from PyPI."""
    workspace_dir = tmp_path / "mylab"
    assert run_workspace(monkeypatch, "init", str(workspace_dir)) == 0
    assert [command for command, _ in fake_uv] == [
        ["uv", "venv"],
        ["uv", "pip", "install", "matr1x-measurements"],
    ]
    assert all(cwd == workspace_dir for _, cwd in fake_uv)
    assert not (workspace_dir / "pyproject.toml").exists()
    agents = (workspace_dir / "AGENTS.md").read_text()
    assert "[mylab]" in agents
    assert "PyPI" in agents
    assert (workspace_dir / "skills" / "migration" / "SKILL.md").is_file()
    assert not (workspace_dir / "skills" / ".DS_Store").exists()
    config = tomllib.loads((home / ".matr1x.toml").read_text())
    assert config["mylab"]["systems_directory"] == str(workspace_dir.resolve())


def test_init_project(
    tmp_path: Path, home: Path, fake_uv: list, fake_fetch: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Initialize a project-style workspace with a pyproject.toml."""
    workspace_dir = tmp_path / "mylab"
    assert run_workspace(monkeypatch, "init", str(workspace_dir), "--project") == 0
    assert [command for command, _ in fake_uv] == [["uv", "sync"]]
    project = tomllib.loads((workspace_dir / "pyproject.toml").read_text())
    assert project["project"]["name"] == "mylab"
    assert project["project"]["dependencies"] == ["matr1x-measurements"]


def test_init_editable(
    tmp_path: Path, home: Path, fake_uv: list, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Initialize a plain workspace with an editable matr1x checkout."""
    workspace_dir = tmp_path / "mylab"
    assert (
        run_workspace(
            monkeypatch,
            "init",
            str(workspace_dir),
            "--editable",
            "--matr1x",
            str(checkout),
        )
        == 0
    )
    assert [command for command, _ in fake_uv] == [
        ["uv", "venv"],
        ["uv", "pip", "install", "-e", str(checkout)],
    ]
    agents = (workspace_dir / "AGENTS.md").read_text()
    assert str(checkout) in agents
    skill = workspace_dir / "skills" / "migration" / "SKILL.md"
    assert skill.read_text() == "checkout skill"


def test_init_editable_extras_resync(
    tmp_path: Path, home: Path, fake_uv: list, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep extras in the editable resync command of AGENTS.md."""
    workspace_dir = tmp_path / "mylab"
    assert (
        run_workspace(
            monkeypatch,
            "init",
            str(workspace_dir),
            "--editable",
            "--matr1x",
            str(checkout),
            "--extra",
            "elab",
        )
        == 0
    )
    agents = (workspace_dir / "AGENTS.md").read_text()
    assert f"uv pip install -e {checkout}[elab]" in agents


def test_valid_version() -> None:
    """Accept only released X.Y.Z version strings."""
    assert workspace._valid_version("8.5.1")
    assert not workspace._valid_version("8.5.1.dev0")
    assert not workspace._valid_version("8.5")


def test_fetch_skills_rejects_unreleased_version(tmp_path: Path) -> None:
    """Fail early when the version is not a released one."""
    with pytest.raises(workspace.WorkspaceError, match="does not look like a released"):
        workspace.fetch_skills("8.5.1.dev0", tmp_path / "skills")


def test_init_editable_default_checkout(
    tmp_path: Path, home: Path, fake_uv: list, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Find the matr1x checkout at ../matr1x without --matr1x."""
    labs = tmp_path / "labs"
    labs.mkdir()
    checkout = labs / "matr1x"
    checkout.mkdir()
    (checkout / "pyproject.toml").write_text('[project]\nname = "matr1x-measurements"\n')
    (checkout / "skills").mkdir()
    workspace_dir = labs / "mylab"
    assert run_workspace(monkeypatch, "init", str(workspace_dir), "--editable") == 0
    assert [command for command, _ in fake_uv] == [
        ["uv", "venv"],
        ["uv", "pip", "install", "-e", str(checkout.resolve())],
    ]


def test_editable_missing_checkout(
    tmp_path: Path,
    home: Path,
    fake_uv: list,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """Error with a hint when no editable checkout is found."""
    workspace_dir = tmp_path / "mylab"
    assert run_workspace(monkeypatch, "init", str(workspace_dir), "--editable") == 1
    assert "--matr1x" in capsys.readouterr().err
    assert not workspace_dir.exists()


def test_init_rerun_errors(
    tmp_path: Path, home: Path, fake_uv: list, fake_fetch: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuse to initialize a folder that is already a workspace."""
    workspace_dir = tmp_path / "mylab"
    assert run_workspace(monkeypatch, "init", str(workspace_dir)) == 0
    assert run_workspace(monkeypatch, "init", str(workspace_dir)) == 1


def test_existing_agents_md_errors(
    tmp_path: Path, home: Path, fake_uv: list, fake_fetch: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuse to overwrite an existing AGENTS.md."""
    workspace_dir = tmp_path / "mylab"
    workspace_dir.mkdir()
    (workspace_dir / "AGENTS.md").write_text("# other")
    assert run_workspace(monkeypatch, "init", str(workspace_dir)) == 1


def test_init_extras(
    tmp_path: Path, home: Path, fake_uv: list, fake_fetch: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pass repeatable --extra options to the install command."""
    workspace_dir = tmp_path / "mylab"
    assert (
        run_workspace(
            monkeypatch,
            "init",
            str(workspace_dir),
            "--extra",
            "elab",
            "--extra",
            "mcp",
        )
        == 0
    )
    assert [command for command, _ in fake_uv] == [
        ["uv", "venv"],
        ["uv", "pip", "install", "matr1x-measurements[elab,mcp]"],
    ]


def test_init_project_editable_extras(
    tmp_path: Path, home: Path, fake_uv: list, checkout: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Write an editable source override with extras to pyproject.toml."""
    workspace_dir = tmp_path / "mylab"
    assert (
        run_workspace(
            monkeypatch,
            "init",
            str(workspace_dir),
            "--project",
            "--editable",
            "--matr1x",
            str(checkout),
            "--extra",
            "elab",
        )
        == 0
    )
    project = tomllib.loads((workspace_dir / "pyproject.toml").read_text())
    assert project["project"]["dependencies"] == ["matr1x-measurements[elab]"]
    assert project["tool"]["uv"]["sources"]["matr1x-measurements"] == {
        "path": str(checkout),
        "editable": True,
    }


def test_init_existing_folder(
    tmp_path: Path, home: Path, fake_uv: list, fake_fetch: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Initialize a folder that already holds the user's files."""
    workspace_dir = tmp_path / "mylab"
    workspace_dir.mkdir()
    (workspace_dir / "system_my.py").write_text("# my system")
    assert run_workspace(monkeypatch, "init", str(workspace_dir)) == 0
    assert (workspace_dir / "system_my.py").is_file()
    assert (workspace_dir / "AGENTS.md").is_file()


def test_register_section_update(tmp_path: Path) -> None:
    """Update an existing section and keep the other sections."""
    config = tmp_path / ".matr1x.toml"
    config.write_text(
        '[other]\nsystems_directory = "/elsewhere"\n\n[mylab]\nsystems_directory = "/old"\n'
    )
    workspace.register_section(tmp_path / "new", "mylab", config)
    data = tomllib.loads(config.read_text())
    assert data["other"]["systems_directory"] == "/elsewhere"
    assert data["mylab"]["systems_directory"] == str(tmp_path / "new")


def test_register_section_noop(tmp_path: Path) -> None:
    """Leave the configuration untouched when the section is up to date."""
    config = tmp_path / ".matr1x.toml"
    workspace_dir = tmp_path / "mylab"
    config.write_text(f'[mylab]\nsystems_directory = "{workspace_dir}"\n')
    before = config.read_text()
    workspace.register_section(workspace_dir, "mylab", config)
    assert config.read_text() == before
