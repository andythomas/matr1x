# Upgrade to v8.5

## Validate system configuration defaults

`System.load_config()` continues to accept plain Pydantic `BaseModel` classes, but it does not
enable validation of their default values. Use `SystemConfigModel` for system configuration so
both configured values and defaults are validated.

1. Find every Pydantic model passed to `load_config(...)` in a system file.
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
