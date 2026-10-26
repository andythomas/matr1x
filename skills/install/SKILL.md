---
name: matr1x-install
description: >
  Use to install and setup the matr1x package.
license: GNU General Public License v3 or later (GPLv3+)
compatibility: Requires Python >=3.10.
---

# Matr1x

Python tools for data recording, instrument control and visualization.

## Installation

1. On a Linux system, install the required qt6 library via `sudo apt install qt6-base-dev`
2. Follow the [uv installation](https://docs.astral.sh/uv/getting-started/installation/) procedure if `uv` is not already installed.
3. Clone the gitub repository `git clone https://github.com/andythomas/matr1x.git` in the desired location (called pkg-root from now on).
4. Execute `uv sync` in pkg-root.
5. Activate the virtual environment in pkg-root according to the OS, i.e. `source .venv/bin/activate` on Linux/MacOS, `.\.venv\Scripts\activate.bat` on Windows.
6. Ensure that `~/.matr1x.toml` exists and includes the following content. If the file does not exist, create it with this content. If it exists, add this content only if it is not already present:

```toml
[matr1x.install]
controlguis = ["control-dummy"]
```

7. If not, either add the content to the existing file or generate the file with the content.
8. Run the disktop integration in the pkg-root folder via `matrix-di` 
9. Launch `matrix-script` in the pkg-root folder. This will take a minute or two, because the editor-assets will be downloaded.

In case there are any errors in the last two steps, please inspect the newest files in `~/logs/` for the underlying cause, attempt to fix the issue, and repeat the failed step.

## Workspace

If the user has a folder with their own system files, control GUIs, and
device drivers (or wants to create one), set it up as a matr1x
workspace with the `matrix-workspace` command, which is installed in
the pkg-root environment:

    uv run matrix-workspace init <folder> --editable --matr1x <pkg-root>

The command creates the virtual environment, the `AGENTS.md` file, and
the `skills/` folder in the workspace, and registers the folder in
`~/.matr1x.toml`.
Use `--project` if the user wants the workspace to be a uv project
with a lock file, and a repeatable `--extra <name>` for additional
extras.
If the user does not want an editable install, omit `--editable`;
matr1x is then installed from PyPI into the workspace.
Running `init` again in an initialized folder is refused.
