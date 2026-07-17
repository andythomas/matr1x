# System Specification

## Overview

A system file includes one and only one variable named `system` in the module-level namespace (1). This variable is an instance of the `System` class (or a subclass for more complex systems).

The system is configured through three mechanisms:
1. **Metadata** via the `dcdata` dictionary (2) — Dublin Core compliant
2. **Devices** added via `add_dev` (3)
3. **Parameters** added via `add_param` (4)

## Example

```python
from matr1x.devices.dummy import dummy
from matr1x.system import System

# (1) Create the system instance
system = System(name="my_experiment")

# (2) Override Dublin Core metadata defaults
system.dcdata["source"] = "dummy system for testing matr1x-matrix"
system.dcdata["creator"] = "Jane Doe"
system.dcdata["identifier"] = "sample_001"

# (3) Add devices (classes, not instances)
system.add_dev(
    "dev",                     # unique device name (dict key)
    dummy,                     # device class (not instanced)
    args=("TCPIP::localhost::10007::SOCKET",),
    # kwargs={"timeout": 100}  # optional keyword arguments for __init__
    # config_params={"key": "value"}  # optional custom device query config
)

# (4) Add parameters
system.add_param(
    "dev p2",                  # parameter name (unique)
    "cnt",                     # unit (used in data file headers)
    ["dev", "p2"],             # setter path → system.devs["dev"].p2
    ["dev", "p2"],             # getter path → system.devs["dev"].p2
    # default=None            # optional default value
    # dtype="float"           # optional data type
    # chunks=1                # optional chunk size for HDF5
)
```

## `dcdata` — Dublin Core Metadata

`system.dcdata` is a `DcDict` instance initialized with sensible defaults:

| Key           | Type   | Default | Description                |
|---------------|--------|---------|----------------------------|
| `creator`     | str    | `None`  | Measurement user           |
| `date`        | str    | ISO-like timestamp | Measurement date |
| `identifier`  | str    | `None`  | Sample name                |
| `relation`    | str    | `None`  | Parent sample              |
| `description` | str    | `None`  | Comment                    |
| `source`      | str    | `None`  | Measurement system         |
| `type`        | str    | `None`  | Measurement data type      |
| `publisher`   | str    | `None`  | Publishing institution     |
| `format`      | str    | `"text/plain; charset=UTF-8"` | Data format |
| `language`    | str    | `"en"`  | Language code              |

### Usage Notes

- **Read-only keys**: All keys above are pre-populated, so `system.dcdata["source"] = "something"` works directly (key already exists).
- **Appending mode**: Set `system.dcdata.append = True` to enable value appending (values are joined with `;@ap:`).
- **HDF5 detection**: Setting `system.hdf5 = True` automatically updates `dcdata["format"]` to `"application/x-hdf5"`.
- **Custom keys**: New keys can be added if a merged system context exists; otherwise only existing keys may be set.

## `add_dev` — Adding Devices

```python
def add_dev(self, name, descriptor, args=None, kwargs=None, config_params=None):
```

Registers a device class (not an instance) for lazy initialization. The device is opened/initialized later via `system.set()`.

### Parameters

| Name            | Type        | Required | Description                                      |
|-----------------|-------------|----------|--------------------------------------------------|
| `name`          | `str`       | Yes      | Unique device name; used as dictionary key in `system.devs` |
| `descriptor`    | `type`      | Yes      | The device **class** (e.g., `dummy`), not an instance |
| `args`          | `tuple`     | No       | Positional arguments passed to the device `__init__` |
| `kwargs`        | `dict`      | No       | Keyword arguments passed to the device `__init__` |
| `config_params` | `dict`      | No       | Custom query configuration for device introspection |

### Internal Storage

Devices are stored in `system.devs` as a list `[descriptor, args, kwargs]` (trimmed to present arguments). The same entry is mirrored in `system._devs_init` for re-opening.

### Device Path Convention

Devices are accessed via `system.devs["dev_name"]`. Parameter paths in `add_param` reference devices as `["dev_name", "attr_name"]` → `system.devs["dev_name"].attr_name`.

## `add_param` — Adding Parameters

```python
def add_param(
    self,
    name: str | list[str],
    unit: str | list[str],
    setter=None,
    getter=None,
    default: float | list[float] | None = None,
    dtype: str | list[str] | None = None,
    chunks=None,
    trigger=None,
    setter_args: tuple | list | None = None,
    setter_kwargs: dict | None = None,
    getter_args: tuple | list | None = None,
    getter_kwargs: dict | None = None,
    trigger_args: tuple | list | None = None,
    trigger_kwargs: dict | None = None,
):
```

Registers a measurement parameter. Each parameter defines how to set, trigger, and read a value from one or more devices.

### Parameters

| Name             | Type                           | Default  | Description                                    |
|------------------|--------------------------------|----------|------------------------------------------------|
| `name`           | `str \| list[str]`             | Required | Human-readable parameter name                  |
| `unit`           | `str \| list[str]`             | Required | Unit string for data file headers              |
| `setter`         | `list \| str`                  | Required | Path to setter (see below)                     |
| `getter`         | `list \| str`                  | Required | Path to getter (see below)                     |
| `default`        | `float \| list[float] \| None` | `None`   | Default/initial value                          |
| `dtype`          | `str \| list[str] \| None`     | `None`   | Data type (e.g., `"float"`, `"int"`)           |
| `chunks`         | `int \| list \| tuple`         | `1`      | Chunk size for HDF5 data storage               |
| `trigger`        | `list \| str \| None`          | `None`   | Path to a trigger function                     |
| `setter_args`    | `tuple \| list \| None`        | `None`   | Extra args for setter                          |
| `setter_kwargs`  | `dict \| None`                 | `None`   | Kwargs for setter                              |
| `getter_args`    | `tuple \| list \| None`        | `None`   | Extra args for getter                          |
| `getter_kwargs`  | `dict \| None`                 | `None`   | Kwargs for getter                              |
| `trigger_args`   | `tuple \| list \| None`        | `None`   | Extra args for trigger                         |
| `trigger_kwargs` | `dict \| None`                 | `None`   | Kwargs for trigger                             |

### Setter/Getter Path Formats

Paths define how to access device attributes or methods:

| Format                     | Resolution                                        |
|----------------------------|---------------------------------------------------|
| `["dev", "attr"]`          | `system.devs["dev"].attr` (attribute access)      |
| `["dev", "method", "attr"]`| `system.devs["dev"].method().attr` (method call)   |
| `"dev.attr"`               | Shortcut for `["dev", "attr"]`                    |

## Key Attributes

| Attribute              | Type           | Description                                  |
|------------------------|----------------|----------------------------------------------|
| `system.parameters`    | `list[Param]`  | All registered parameters                    |
| `system.devs`          | `dict`         | Device registry: `{name: [class, args, kwargs]}` |
| `system.dcdata`        | `DcDict`       | Dublin Core metadata                         |
| `system.opened`        | `bool`         | Whether devices have been initialized        |
| `system.config`        | `Any`          | System-specific configuration (loaded from TOML) |
| `system.sensitive_config` | `UntypedConfigModel` | Sensitive config (not written to files) |
| `system.system_config_params` | `dict` | Custom query config per device               |
| `system.hdf5`          | `bool`         | Whether HDF5 format is used                  |
| `system.filename`      | `Path \| None` | Current data file path                       |

## Lifecycle

1. **Define**: Create `system = System()`, add devices and parameters
2. **Set**: `system.set()` — opens/initializes all devices
3. **Query**: `system.query()` — reads device configuration/status
4. **Measure**: `system.set()` → `system.trigger()` → `system.read()` → `system.take_measurement_point()`
5. **Reset**: `system.reset()` — returns system to defined state
6. **Close**: `system.close()` — closes all devices
