# Getting Started

## Naming Conventions for Folders and Files:

1. Measurement data go into `~/users/xxxx/`
2. Logs go into ~/logs

## First measurement steps

It is recommended to utilize 'matrix-gui' for the first measurements. It uses
'sweep-generator' to build input files that describe the measurement. Please see this
[short introduction](sweep_generator.md).

## Enabling control GUIs installation

In order to also perform desktop integration for the control GUIs (graphical frontends for
specific instruments) you have to include the following section in the `~/.matr1x.toml` file.

```toml
# list here control guis you want to use (see pyproject.toml for all the choices)
[matr1x.install]
controlguis = ["control-dummy"]
```
