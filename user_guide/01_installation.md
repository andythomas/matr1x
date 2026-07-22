# Installation

## Agentic Installation

An agent can be utilized to perform all the required and recommended steps as indicated on this page automatically.
Please install the package skills using the agent framework of your choice.
Create an empty directory, point you agent to this directory and prompt for example:

```markdown
Please install matr1x as described in the matr1x-install skill.
```

If you have problems installing the skills, please point the agent to

```markdown
https://andythomas.github.io/matr1x/.well-known/agent-skills/matr1x-install/SKILL.md
```

## Basic Installation

Please use [Github Desktop](https://desktop.github.com/download/) to clone the repository.
We recommend to install uv, because it simplifies the installation and downloads the package versions we utilize for testing.
Then, two more steps are required for the installation:

1. Sychronize uv in the cloned directory
2. Activate the virtual environment

::: {.panel-tabset}

## Windows

1. Follow the [uv installation](https://docs.astral.sh/uv/getting-started/installation/) procedure.
2. Execute `uv sync`
3. Execute `.venv\Scripts\activate.bat` in a command prompt or PowerShell window.

## MacOS

The system Python version is quite old (3.9 in Sequoia) and cannot be used to install the packages.

1.  Follow the [uv installation](https://docs.astral.sh/uv/getting-started/installation/) procedure.
2.  Execute `uv sync`
3.  Execute `source .venv/bin/activate`

## Linux/Unix

The package can be installed on Linux systems (well tested) and also on BSD systems (not tested regularly) and likely other Posix compliant systems.
We recommend using a virtual environment.
First, make sure you have the required system packages installed.

```bash
sudo apt install qt6-base-dev
```

Then, continue the basic installation:

1. Follow the [uv installation](https://docs.astral.sh/uv/getting-started/installation/) procedure.
2. Execute `uv sync`
3. Execute `source .venv/bin/activate`

:::

If an optional feature is required for your setup use `uv sync --extra <FEATURE>` instead.

## Desktop Integration

After the installation, any application launch will perform the desktop integration, i.e. provide application icons, start menu entries and such. For example, please execute

- `matrix-preview`

A command line tool can carry out the integration as well:
Please start `matrix-di` for integration and `matrix-di -u` for removal.

`matrix-script` might need a few minutes at the first start to download the editor assets.

## Overview of Recommended Options

An overview of recommended options for the specific platforms is given in the following table.
In most cases we recommend an installation into a dedicated virtual environment. Most Mac and
Linux systems require the virtual environment, while Windows does not require it.

| Platform   | Python distribution | Virtual environment  | editable installation |
| ---------- | ------------------- | -------------------- | --------------------- |
| Windows    | uv recommended      | weakly recommended   | Yes                   |
| Linux/Unix | uv or system Python | strongly recommended | Yes                   |
| Mac OS     | uv                  | required             | Yes                   |
