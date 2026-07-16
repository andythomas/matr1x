# Configuration options

In the `~/.matr1x.toml` configuration file which follows a [TOML file format](https://toml.io)
some options can be configured. These are typically only needed if some behavior of the
programs needs to be changed and for most users the default options will be just fine.
In addition to a config file in the users home directory one can also use a custom config
file `matr1x.toml` in the directory where any matrix-program is started.

While here the available global options are discussed you can find install specific options in the
Installation section of the [README](../../README.md#installation-windows-macos-linuxunix).

````toml
[matr1x]
# customize datetime format in log files: follow https://docs.python.org/3/library/time.html#time.strftime
datetime_format = "%Y-%m-%dT%H:%M:%S"
# default directory to store files
users_directory = "~/users"
# default directory for sweep-generator/matrix-script to find system files
systems_directory = "<pkgroot>/systems"
# folder to store log files
logging_directory = "~/logs"
# Determines if matrix-script output should be saved to a log file in addition to displaying in the GUI
duplicate_output_to_logfile = false
# Enables automatic conversion of print statements to data file comments
# Note: Measurement point outputs are excluded. This feature helps link script output with the data file.
print_to_comment = false

[matr1x.scripts.matrix-script]
# location where matrix-script scripts are executed (files from this folder can be imported in scripts)
# by default ("") this is the folder were matrix-script is started. The special value "<script-location>"
# can be used to change to the script file location.
script_path= ""
# Controls whether executed script code is stored in the data file header
store_script_in_datafile = false

[matr1x.scripts.matrix-script.shortcuts]
# The shortcut that is displayed for the toggle line comment menu item.
line_comment_display = "Ctrl+/"
# The shortcut that is used for the toggle line comment menu item.
line_comment_shortcut = "Ctrl+/"

[matr1x.devices.visadevice]
# some devices support rate limiting of transmissions to the hardware. the property 'commands per second'
# can be used to the set the global default value use for the rate limiting
cmdpers = 30
# enable printing to screen for hardware communication
pts = false
# enable Visa debug output
visadebug = false

Systems in the last given `systems_directory` path will be shown initially where system files can
be loaded. Some systems also define optional parameters which can be configured via the same
`~/.matr1x.toml`. An example is found in `system_dummy_feature.py` which adds four options.

```toml
[matr1x.systems.system_dummy_feature]
setting1 = "CURR"
setting2 = false
setting3 = 36.232
setting4 = "~/.matr1x.toml"
```

### Configuring systems via Pydantic models

The recommended way to define and access configuration options is using Pydantic models. This
provides automatic validation, type safety, and direct attribute access. The GUI config editor also
uses the metadata from the model (like descriptions and types) to allow for a better editing
experience.

The definition of default values for the options and the access to them is performed as shown in
the following example from `system_dummy_feature.py`.

```python
from typing import Literal
from pydantic import BaseModel, Field

from matr1x.models import FilePath, GuiField, SciFloat
from matr1x.system import System

class DummyConfig(BaseModel):
    """Configuration for dummy feature."""
    # 1. Dropdown menu (using Literal)
    setting1: Literal["CURR", "VOLT"] = Field("VOLT", description="Measurement mode")

    # 2. Checkbox (using bool)
    setting2: bool = Field(True, description="Enable feature")

    # 3. Spinbox with limits (using ge/le/multiple_of)
    # Use GuiField to set display decimals easily
    setting3: float = GuiField(
        3.3215,
        ge=-1e9,
        le=99,
        description="Reference value",
        decimals=4
    )

    # 4. Path selector (File/Folder dialog)
    # Use FilePath or FolderPath types to trigger a browser button
    setting4: FilePath = Field(
        "~/.matr1x.toml",
        description="Config file path"
    )

    # 5. Scientific notation (scifloat)
    # Use SciFloat type to enable scientific notation
    setting5: SciFloat = Field(
        1.23e-6,
        description="A small value"
    )

class MeasSystem(System):
    """Measurement system for dummy feature demonstration."""

    def __init__(self):
        """Initialize the MeasSystem."""
        super().__init__()
        # Load and validate configuration using the model
        self.load_config(DummyConfig, "matr1x.systems.system_dummy_feature")

    def set(self, *args, **kwargs):
        """Initialize and configure the measurement."""
        # wrap base system function for safe handling of opening
        super().set(*args, **kwargs)
        # configure devices upon initialization using attribute access
        self.devs["dev1"].p2 = 10
        self.devs["dev2"].configure(
            setting1=self.config.setting1,
            setting2=self.config.setting2
        )
```

Descriptions provided in `Field(description="...")` are automatically shown as **tooltips** in the GUI configuration editor.

#### Supported GUI Hints and Types:

The basic use is to provide a type hint and a Field definition. To simplify configuration definitions, `matr1x.models` provides several helper types and a `GuiField` wrapper:

| Hint/Type               | Description                                                    | Editor element                                       |
| ----------------------- | -------------------------------------------------------------- | ---------------------------------------------------- |
| `Literal`=`Field`       | Restrict the values to a fixed set of options.                 | ComboBox                                             |
| `bool`=`Field`          | A boolean value.                                               | CheckBox                                             |
| `int`=`Field`           | An integer value.                                              | SpinBox                                              |
| `float`=`Field`         | A floating-point value.                                        | DoubleSpinBox                                        |
| `float`=`GuiField(...)` | A wrapper around `Field` that adds a `decimals` parameter.     | DoubleSpinBox                                        |
| `SciFloat`=`Field`      | Alias for `float` with scientific notation enabled in the GUI. | LineEdit                                             |
| `FilePath`=`Field`      | Alias for `str` that triggers a file selection dialog.         | Read-only LineEdit + Button with file dialog popup   |
| `FolderPath`=`Field`    | Alias for `str` that triggers a folder selection dialog.       | Read-only LineEdit + Button with folder dialog popup |

If a config setting contains sensitive information (e.g., a password or API key) that should not be stored in measurement data files, it should be specified in the `sensitive_keys` argument of `load_config`. This automatically moves these keys to `self.sensitive_config` and excludes them from metadata.

```python
        self.load_config(
            MyConfig,
            "matr1x.systems.my_system",
            sensitive_keys=["password", "api_key"]
        )
```

An implementation example for this can be found in the `system_elabftw.py` system.

## ElabFTW specific config options

The `system_elabftw.py` system allows to automatically create electronic labbook entries in an
[ElabFTW](https://www.elabftw.net/) instance. The `host` and `api_key` options are required when
elabFTW integration is enabled; all other options can be changed from their defaults as needed.

```toml
[matr1x.systems.system_elabftw]
# Mandatory settings for server connection
# Use the server base URL. The /api/v2 suffix is added automatically.
host = "https://elab.example.com"
api_key = "your-secure-api-key"
# Team ID used for category and status lookup. The default team is 0.
teamid = 0

# Enable elabFTW integration. If false, no entry is created.
enable_elab = true
# Enable debug output from the elabFTW API client.
debug = false
# Boolean to decide if server connection is required.
# If true, the server connection is required for a running a measurement.
require_server = false
# Boolean or maximal file size in MB for data file uploads
upload_datafile = false
# Category for newly generated experiment entries.
# This category must exist in ElabFTW.
category = ""
# If a sample cannot be found as an ElabFTW resource, create one.
create_resource = false
# Category for newly generated resources. This category must exist in ElabFTW.
resource_category = "Transport device"

# Template for generating titles for the ElabFTW entry.
# Uses Jinja2 syntax to construct a title from the metadata and filename
title_template = """
    {%- set title_parts = [] %}
    {%- if dcdata['identifier'] %}
        {%- set _ = title_parts.append(dcdata['identifier']) %}
    {%- endif %}
    {%- set _ = title_parts.append(base_filename) %}
    {{- title_parts | join(' - ') -}}
"""

# Template for generating body content of the ElabFTW entry.
# Uses Jinja2 syntax to format measurement data into HTML
body_template = """
    <h1>Measurement Report</h1>
    <p><strong>{{ dcdata['source'] }}</strong></p>
    <hr>
    <p><strong>Filename:</strong> {{ filename }}</p>
    <p><strong>Sample:</strong> {{ dcdata['identifier'] }}</p>
    <p><strong>Creator:</strong> {{ dcdata['creator'] }}</p>
    <h2>Description:</h2>
    <p>{{ dcdata['description'] | replace('\n', '<br>') }}</p>
    <h2>Additional Data:</h2>
    <table>
        <tr>
            <th>Parameter</th>
            <th>Value</th>
        </tr>
        {%- for key, value in dcdata.items() %}
        {%- if key not in ['identifier', 'creator', 'description', 'source'] %}
        <tr>
            <td>{{ key }}</td>
            <td>{{ value }}</td>
        </tr>
        {%- endif %}
        {%- endfor %}
    </table>
"""
```

## Setting up sending email notifications

Some control GUIs or measurement scripts can send email notifications.
In the control GUI this typically notifies about a special situation which needs attention (e.g.
low liquid Helium levels, or too high vacuum pressure). For the programs to be able to send emails
an SMTP server needs to be configured. On all platforms this can be done via `~/.matr1x.toml`. The
relevent options are

```toml
[matr1x.email]
# smtp server address
smtp_server = "smtp.gmail.com"
smtp_user = "<username>"
password = "<password>"
# sending email address compatible with the username above
fromemail = "<email_address>"
```

Once you added these settings in the configuration you will want to disable generation of the
default config during installation since this would overwrite your changes.

On posix platforms (Linux/Mac OS) the sending of emails falls back to using `sendmail` which needs
to be configured accordingly. This is only attempting in case of incomplete configuration and the
`sendmail` command needs to be accessible via `PATH`.
````
