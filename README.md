# Matr1x

Python tools for data recording, instrument control and visualization.

## Requirements

A Python installation with a version between 3.10 and 3.14 is
successfully tested to run the software.

## Installation (Windows, MacOS, Linux/Unix)

An overview of recommended options for the specific platforms is given in the following table.
In most cases we recommend an installation into a dedicated virtual environment. Most Mac and
Linux systems require the virtual environment, while Windows does not require it.

| Platform   | Python distribution | Virtual environment  | editable installation |
| ---------- | ------------------- | -------------------- | --------------------- |
| Windows    | uv recommended      | weakly recommended   | Yes                   |
| Linux/Unix | uv or system Python | strongly recommended | Yes                   |
| Mac OS     | uv                  | required             | Yes                   |

### <a name="basic-installation"> Basic installation

Please use [Github Desktop](https://desktop.github.com/download/) to clone the repository to avoid
missing submodules. In most cases, [installing uv](https://docs.astral.sh/uv/getting-started/installation/)
simplifies the installation tremendously. Two command are required for the installation:

- `uv sync`
- `source .venv/bin/activate` (Mac/ Linux) or `.venv\Scripts\activate.bat` (Windows)

If an optional feature is required for your setup use `uv sync --extra <FEATURE>` above.
Available extras can be found in the `[project.optional-dependencies]` sections of `pyproject.toml`
files.

After the installation, any application launch will perform the desktop integration, i.e.
provide application icons, start menu entries and such. For example, please launch:

- `matrix-preview`

A command line tool can also carry out the integration. Please start
`matrix-di` for integration and `matrix-di -u` for
removal. `matrix-script` might need a few minutes at the first start
to download the editor assets.

### Configuring matr1x installation

The install process of matr1x core parts can be in addition to the command line arguments
introduced above also configured by entries in the `~/.matr1x.toml` file. Some options are:

```toml
[matr1x.install]
# control wether users and log directory are created by the installer
create_directories = false
# enable/disable desktop integration
desktopintegration = true
# enable control-dummy desktop integration
controlguis = ["control-dummy"]
```

### Enabling control GUIs installation

In order to also perform desktop integration for the control GUIs (graphical frontends for
specific instruments) you have to include the following section in the `~/.matr1x.toml` file.

```toml
# list here control guis you want to use (see pyproject.toml for all the choices)
controlguis = ["control_ptarmigan", "control_chaos"]
```

After adding this or adjusting the settings rerun the desktop integration via the menu in any
of the applications or use the provided command line tool
(see [Basic installation](#basic-installation)).

### Windows

1. Download the Python installer from [uv](https://docs.astral.sh/uv/getting-started/installation/)
2. Execute [installation procedure](#basic-installation) in a command prompt or PowerShell window.

After launching any application, all applications are available via the Windows start menu.

### MacOS

The system Python version is quite old (3.9 in Sequoia) and cannot be used to install the
packages. Please use [uv](https://docs.astral.sh/uv/), use and perform the
[installation procedure](#basic-installation).

### <a name="linux-basic"> Linux/Unix

The package can be installed on Linux systems (well tested) and also on BSD systems (not tested
regularly) and likely other Posix compliant systems. We recommend using a virtual environment.
Before following the installation as described in [installation procedure](#basic-installation),
make sure you have the required system packages installed.

```bash
sudo apt install qt6-base-dev
```

## Use and configuration

[Configuration options](user_guide/configuration_options.md) can change the behavior of some
aspects of the software suite.

### Naming Conventions for Folders and Files:

1. Measurement data go into `~/users/xxxx/`
2. Logs go into ~/logs

## First measurement steps

It is recommended to utilize 'matrix-gui' for the first measurements. It uses
'sweep-generator' to build input files that describe the measurement. Please see this
[short introduction](user_guide/sweep_generator.md).

## Development

If you are interested in contributing to the project please see the
[development guide](user_guide/development.md).
