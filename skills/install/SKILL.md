---
name: install
description: >
  Python tools for data recording, instrument control and visualization. Use to install and setup the matr1x package.
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
6. Check if there is a `~/.matr1x.toml` file and the following content is included

```toml
[matr1x.install]
controlguis = ["control-dummy"]
```

7. If not, either add the content to the existing file or generate the file with the content.
8. Run the disktop integration in the pkg-root folder via `matrix-di` 
9. Launch `matrix-script` in the pkg-root folder. This will take a minute or two, because the editor-assets will be downloaded.

In case there are any errors in the last two steps, please inspect the newest files in `~/logs/` for the underlying cause.
