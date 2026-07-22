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

A good name might be the filename of the module. If this name starts with `system_` strip this part from the class name. Generate a meaningful one-line docstring.

5. CLASS NAME UNIQUENESS CHECK (applies to all files, independent of steps 1-4):
   a. Search ALL .py files in this directory for any shared subclass name
      (especially `MeasSystem`).
   b. Every file must have a UNIQUE class name — no two files may use the same one.
   c. Rename all occurrences. Derive names from the filename (minus `system_` prefix)
      or from the hardware described in dcdata.
   d. Files already using unique names do NOT need changes.

## Control Command Migration

This skill migrates two kinds of legacy patterns in matr1x files:

1. **`cmds` dict entries** — raw lists or `Command.from_deprecated_list()` calls → `Command`, `Get`, or `Set` instantiation
2. **`add_param` calls** — positional setter/getter arguments → explicit keyword arguments

---

### Part 1 — `cmds` dict migration

#### Legacy formats to look for

**Raw list values** inside a `cmds` dict:
```python
cmds = {
    ":key": [dtype, setfunc, setargs, getfunc, getargs],              # length 5
    ":key": [dtype, setfunc, setargs, getfunc, getargs, polling_cmd], # length 6
}
```

**Explicit `from_deprecated_list` calls**:
```python
cmds = {
    ":key": Command.from_deprecated_list([dtype, setfunc, setargs, getfunc, getargs]),
}
```

#### Conversion rules

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

### Part 2 — `add_param` call migration

#### Legacy pattern to look for

`add_param` calls that pass `setter` and/or `getter` **positionally** (3rd and 4th args):

```python
system.add_param(name, unit, setter, getter)
system.add_param(name, unit, None, getter)    # setter is None
```

#### Conversion rules

- Convert positional `setter` / `getter` to explicit keyword arguments.
- If `setter` is `None` (getter-only parameter), drop the positional `None` and use `getter=` alone.
- If `getter` is `None` (setter-only parameter), drop the positional `None` and use `setter=` alone.
- Keep any other keyword arguments unchanged.

#### Before / After example

**Before:**
```python
system.add_param(["T_sample", "HR"], ["K", ""], "setLS", "getLS")
system.add_param("P_sample", "%", getter=["control", "lsht"])
system.add_param(["T_VTI", "NV"], ["K", "%"], "setVTI", "getVTI")
system.add_param("P_VTI", "%", getter=["control", "vtih"])
system.add_param("angle", "deg", None, "angle")
system.add_param("plane", "", None, "plane")
```

**After:**
```python
system.add_param(["T_sample", "HR"], ["K", ""], setter="setLS", getter="getLS")
system.add_param("P_sample", "%", getter=["control", "lsht"])
system.add_param(["T_VTI", "NV"], ["K", "%"], setter="setVTI", getter="getVTI")
system.add_param("P_VTI", "%", getter=["control", "vtih"])
system.add_param("angle", "deg", getter="angle")
system.add_param("plane", "", getter="plane")
```

Note: calls that already use keyword arguments (e.g. `getter=["control", "lsht"]`) require no change.

---

### Steps to perform the migration

1. **Identify files** — ask the user which file(s) to migrate, or scan for `.py` files containing `cmds = {` with list values, `from_deprecated_list`, or `add_param(` with positional setter/getter.

2. **Read each file** fully before making changes.

3. **Apply Part 1** conversions to every `cmds` dict entry that is still a list or a `from_deprecated_list` call.

4. **Apply Part 2** conversions to every `add_param` call that passes setter/getter positionally.

5. **Fix imports** — ensure the file imports exactly the classes it uses:
   - Add `Get` and/or `Set` to the import if they are now used.
   - Remove `Get`, `Set`, or `Command` from the import if they are no longer used.
   - The import comes from `matr1x.util`.
