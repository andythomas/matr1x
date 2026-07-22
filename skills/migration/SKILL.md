---
name: system-class-migration
description: Migrate matr1x Python system definition files from exporting a preconfigured System instance to exporting a System subclass. Use when converting existing matr1x system files to object-oriented setup, adding a new system file, or checking that a migration preserves legacy compatibility.
---

# System Class Migration

Define system setup on a `System` subclass and export the class through the module-level
`system` name. `System.from_file()` instantiates that class. Legacy files that export an
already-created `System` instance are still supported, so conversion is optional but recommended.

## Migration

1. Read the whole system file and identify module-level mutations of `system`: `add_dev`,
   `add_param`, `dcdata` assignments, `load_config`, and other instance setup.
2. Keep the existing `class MySystem(System)` or create one. Add `__init__`, call
   `super().__init__()` first, then move every instance mutation into it and change `system.` to
   `self.`.
3. Leave behavior methods such as `set`, `reset`, getters, and setters on the class. Do not open
   devices in `__init__`; only register descriptors with `self.add_dev`.
4. If the file uses the deprecated `sys` export name, rename it to `system` during the migration:
   replace `sys = MySystem()` with `system = MySystem` and change all adjacent `sys.` setup calls
   to `self.` inside `__init__`. A minimal file may use `system = System`.
5. Preserve comments as source: move each comment or section heading with the adjacent setup
   block into `__init__`. Keep its wording unless changing `system` to `self` is needed for
   accuracy; do not drop instructional comments merely because their code moves.
6. Preserve order: configuration and metadata must be initialized before any setup that relies on
   them, and device/parameter registrations should retain their former order.
7. Validate with `System.from_file(path)` and the relevant test suite. Confirm legacy instance
   files still load if compatibility is changed.

## Examples

Before (legacy, supported):

```python
from matr1x.devices.dummy import dummy
from matr1x.system import System

class Example(System):
    pass

system = Example()
system.dcdata["source"] = "example"
system.add_dev("device", dummy, args=("TCPIP::localhost::10007::SOCKET",))
system.add_param("voltage", "V", getter=["device", "voltage"])
```

After (recommended):

```python
from matr1x.devices.dummy import dummy
from matr1x.system import System

class Example(System):
    def __init__(self):
        super().__init__()
        self.dcdata["source"] = "example"
        self.add_dev("device", dummy, args=("TCPIP::localhost::10007::SOCKET",))
        self.add_param("voltage", "V", getter=["device", "voltage"])

system = Example
```

For a system with no specialization, this is sufficient:

```python
from matr1x.system import System

system = System
```

## Compatibility

Do not change the loader to reject `system = MySystem()` or `system = System()`.
Both are valid legacy forms. The preferred class export only changes where the instance is
created, not the public behavior of the resulting system.

`sys` remains supported only for backward compatibility and produces a deprecation warning.
When converting a system file, replace it with `system`; retain `sys` only when a task explicitly
requires leaving that legacy file untouched.

## Checks

Use a focused import check while developing:

```python
from pathlib import Path
from matr1x.error_handling import Success
from matr1x.system import System

result = System.from_file(Path("path/to/system_file.py"))
assert isinstance(result, Success)
```

Also run the system-import tests and any tests exercising the migrated system.
