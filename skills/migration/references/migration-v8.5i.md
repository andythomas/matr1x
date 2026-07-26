# Upgrade to v8.5

## Enforce unique systems classes

1. Please inspect the files in the `systems` subdirectory of the repository.
2. In every file there should be an import of the `System` class.
3. In every file there should be one and only one `system =` line in scope of the module.
4. The right side of this assignment should be a subclass of the imported `System` class. If it only instantiates `System`, e.g. `system = System()`, subclass `System` as in the following example.

```python
class MeasSystem(System):
    """Measurement system for dummy feature demonstration."""
```

A good name might be the filename of the module. 
If this name starts with `system_` strip this part from the class name. 

5. CLASS NAME UNIQUENESS CHECK (applies to all files, independent of steps 1-4):
   a. Search ALL .py files in this directory for any shared subclass name
      (especially `MeasSystem`).
   b. Every file must have a UNIQUE class name — no two files may use the same one.
   c. Rename all occurrences. Derive names from the filename (minus `system_` prefix)
      or from the hardware described in dcdata.
   d. Files already using unique names do NOT need changes.

6. Make sure you did not touch the comments or docstrings. The only exception is the replacement of an referral of an old name to the new name of the class.

## System configuration model migration

1. Find every Pydantic model passed to `System.load_config(...)` in a system file.
   Do not change unrelated `BaseModel` classes.
2. Replace `BaseModel` with `SystemConfigModel` for each system configuration model:

```python
# Before
from pydantic import BaseModel, Field


class DeviceConfig(BaseModel):
    mode: Literal["CURR", "VOLT"] = Field("VOLT")
```

```python
# After
from pydantic import Field

from matr1x.models import SystemConfigModel


class DeviceConfig(SystemConfigModel):
    mode: Literal["CURR", "VOLT"] = Field("VOLT")
```

3. Preserve other Pydantic model configuration options. Pydantic merges them with the
   inherited `validate_default=True` setting:

```python
class DeviceConfig(SystemConfigModel):
    model_config = ConfigDict(extra="forbid")
```

4. Validate the model after migration. Instantiate it without arguments when it has no
   required fields; otherwise supply representative values for the required fields. Defaults
   must satisfy the same `Literal`, numeric, string, and custom constraints as configured
   values. Fix an invalid default or make that field required with `Field(...)`; do not
   disable default validation.
5. If a configuration model already uses a custom Pydantic base class, do not replace it
   blindly. Make that base inherit `SystemConfigModel`, or add
   `ConfigDict(validate_default=True)` while preserving its existing behavior.

## Control Command Migration

This skill migrates legacy patterns in matr1x files:

**`cmds` dict entries** — raw lists or `Command.from_deprecated_list()` calls → `Command`, `Get`, or `Set` instantiation

### Legacy formats to look for

**Raw list values** inside a dict:
```python
cmds = {
    ":key": [dtype, setfunc, setargs, getfunc, getargs],              # length 5
    ":key": [dtype, setfunc, setargs, getfunc, getargs, polling_cmd], # length 6
}
```

### Conversion rules

Apply these rules to each entry (prefer `Get`/`Set` over `Command` when possible):

| setfunc | getfunc | Use |
|---------|---------|-----|
| not `None` | not `None` | `Command(dtype, setfunc, getfunc, ...)` |
| `None` | not `None` | `Get(dtype, getfunc, ...)` |
| not `None` | `None` | `Set(dtype, setfunc, ...)` |

Optional keyword arguments — **only include if non-empty / not `None`**:
- `setargs` — omit if `None`, `()`, or `[]`
- `getargs` — omit if `None`, `()`, or `[]`
- `polling_cmd` — omit if `None`

#### Before / After example

**Before:**
```python
from matr1x.util import Command

cmds = {
    ":temp":   [float, "setTemp", (), "getTemp", ()],
    ":field":  [float, None, (), "getField", ()],
    ":press":  [float, "setPress", (1,), None, (), ":pressrd"],
    ":v2":     [float, ("dummy", "p2"), None, "V2", None, ":v2rd"],
    ":info":   Command.from_deprecated_list([str, None, None, "getInfo", None]),
}
```

**After:**
```python
from matr1x.util import Command, Get, Set

cmds = {
    ":temp":   Command(float, "setTemp", "getTemp"),
    ":field":  Get(float, "getField"),
    ":press":  Set(float, "setPress", setargs=(1,), polling_cmd=":pressrd"),
    ":v2":     Command(float, ("dummy", "p2"), "V2", polling_cmd=":v2rd"),
    ":info":   Get(str, "getInfo"),
}
```

---

### Steps to perform the migration

1. **Identify files** — scan for files in the control subdirectories containing `cmds = {`,`common_commands = {`, `cmd_list = {` or similar patterns with list values.

2. **Read each file** fully before making changes.

3. **Apply changes** convert the dict entries that are still a list 

4. **Fix imports** — ensure the file imports exactly the classes it uses:
   - Add `Get` and/or `Set` and/or `Command` to the import if they are now used.
   - Remove `Get`, `Set`, or `Command` from the import if they are no longer used.
   - The import comes from `matr1x.util`.
