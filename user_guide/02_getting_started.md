# Getting Started

## Installation

Please install the Matrix software package as described in the [installation guide](installation.md).
Now, the available applications are listed below.

- `matrix-gui`: A desktop application that provides a graphical user interface for the measurements.
- `matrix-preview`: A desktop application that displays the measurement results.
- `matrix-script`: An integrated environment to edit and run measurement scripts.
- `matrix`: A command line interface to perform measurements.
- `sweep-generator`: A tool to build input files for `matrix-gui` and `matrix`.
- `matrix-di`: A command line tool to perform the desktop integration.

## Desktop Integration

Please start any application other than `matrix` from the command line to initiate the desktop integration.
Afterwards, the applications are integrated into your desktop environment, e.g. startmenu, taskbar, etc.
Please note that `matrix-script` will need a longer startup time (>1min) than the other applications, because the editor assets are automatically downloaded as well. 

## Logging

Log files are stored in `~/logs`. 
Please look into the newest files in this folder for debugging information if something does not work as expected.

## Enabling control GUI installation

In order to also perform desktop integration for the example control GUI (graphical frontend for
specific instruments) you have to generate a `~/.matr1x.toml` file with the following content:

```toml
[matr1x.install]
controlguis = ["control-dummy"]
```

Afterwards, rerun the desktop integration to register these changes.
The "help" menu of all GUI applications will have the option to "Remove" and "Install" the desktop integration.
Now, another application named `control-dummy` is available.
For other configuration options, please see the [configuration guide](configuration_options.md).

## First measurement steps

It is recommended to utilize `matrix-gui` for the first measurements. It uses
`sweep-generator` to build input files that describe the measurement. Please see this
[short introduction](sweep_generator.md).
