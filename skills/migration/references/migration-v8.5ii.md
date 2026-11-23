# Upgrade to v8.5

## Move from System Instance to System Class

Define system setup on exactly one local `System` subclass. `System.from_file` discovers and
instantiates that class, so no module-level `system` variable is required.
Initialized `system` and `sys` exports remain temporarily supported with a deprecation warning.

## Migration

1. Read the whole system file.
2. There must be exactly one class defined in the system file that is a subclass of `System`.
3. If there is no class and `System` or a subclass of it is only instantiated (e.g. `MySystem = System()`), create a subclass with an appropriate name. A good name could be the instance name (e.g. `MySystem`). This class is called "SystemClass" from here on.
4. If no `__init__` exists for the SystemClass, add one and call `super().__init__()` first. Please double-check that no `__init__` exists before adding one.
5. Now identify module-level mutations of `system`: `add_dev`, `add_param`, as well as `dcdata` assignments, and `load_config`. These instance mutation need to be moved into the SystemClass, which at least requires a change of `system.` to `self.`.
6. Preserve the imports, it is not required to add or remove imports.
7. Preserve comments as source: move each comment or section heading with the adjacent setup block into `__init__`. Keep its wording unless changing `system` to `self` is needed for accuracy; do not drop instructional comments merely because their code moves.
8. Preserve order: configuration and metadata must be initialized before any setup that relies on them, and device/parameter registrations should retain their former order.
9. Now, inspect the remaining items in the module for any items that need to be moved into the SystemClass. In particular, this includes functions that use the former `system` instance and need to become methods of SystemClass, which again at least requires a change of `system.` to `self.`.

## Examples

Before:

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

After:

```python
from matr1x.devices.dummy import dummy
from matr1x.system import System


class Example(System):
    def __init__(self):
        super().__init__()
        self.dcdata["source"] = "example"
        self.add_dev("device", dummy, args=("TCPIP::localhost::10007::SOCKET",))
        self.add_param("voltage", "V", getter=["device", "voltage"])
```

## Import check

Use a focused import check after the change for every file:

```python
from pathlib import Path
from matr1x.error_handling import Success
from matr1x.system import System

result = System.from_file(Path("path/to/system_file.py"))
assert isinstance(result, Success)
```

## Steps to Perform the Migration

1. **Identify files** — scan for files in the system subdirectories. Most likely the filenames have a `system_`-prefix.

2. **Read each file** fully before making changes.

3. **Apply changes** as described in the "Migration" step by step instructions.

4. **Validate changes** using the following two checks:
   - `ty check`: This should catch any remaining items that need to be moved in the SystemClass.
   - Import check (as described above): This should catch the additional errors.

5. **Perform additonal changes** as required by the previous step and repeat validation until all errors are resolved.
