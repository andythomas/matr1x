# Upgrade to v8.5

## Give Control GUI Systems Unique Names

Every `System` used by a `GuiDict` in the same `ControlWindow` must have a
unique name. The name is used to expose the system through the merged system,
for example as `window.S.temperature`.

The name must:

- be unique among all `GuiDict` systems in the `ControlWindow`; and
- be a valid Python identifier according to `str.isidentifier()`.

For example, `temperature`, `magnet_2`, and `cryostat` are valid names.
Names containing spaces, hyphens, or dots, such as `temperature control`,
`magnet-2`, or `lab.cryostat`, are not valid.

## Migration

1. Find the `GuiDict` classes used by each control GUI.
2. Check whether each class explicitly defines an `S` attribute.
3. If a `GuiDict` does not define `S`, no change is required. `GuiDict`
   automatically creates an empty system named after the `GuiDict` class.
4. If a `GuiDict` explicitly defines `S`, ensure that its `System` has a name
   that meets both requirements above.
5. Check all `GuiDict` systems passed to the same `ControlWindow` together and
   resolve any duplicate names.

Prefer supplying the name when the system is created:

```python
from matr1x.control import GuiDict
from matr1x.system import System


class TemperatureGui(GuiDict):
    S = System(name="temperature")
```

If a custom `System` subclass does not accept `name` as an initializer
argument, set the name explicitly after creating it:

```python
class TemperatureGui(GuiDict):
    S = TemperatureSystem()
    S.name = "temperature"
```

A separate `System` subclass is not required merely to give each control GUI
system a unique name.

## Validation

Start each migrated control GUI and verify that it opens without a missing,
invalid, or duplicate system-name error. If the merged system is accessed
directly, also verify that every subsystem is available under its configured
name, for example:

```python
control_window.S.temperature
```
