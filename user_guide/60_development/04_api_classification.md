# API classification

The `matr1x` API uses a three-level classification. The levels describe what
kind of compatibility guarantee importers can expect:

::: {.api-classification}

| Level          | Meaning                                                                                                                                    | Guarantee                                                                                                                                     |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **Supported**  | The stable, documented interface of the package. Listed in the documentation's `reference` section.                                        | Behavior changes follow semantic versioning. Deprecation cycle as described in the documentation.                                             |
| **Unsupported**| Importable (in `__all__` or not underscored if it does not exist) and used outside of the defining module, but not listed in the `reference` section. | No stability guarantee. May change or be removed in any release without deprecation. External users are encouraged to migrate to the Supported API where possible. |
| **Internal**   | Internal implementation detail. Not meant to be imported at all.                                                                           | No guarantee at all. Free to change at any time; external code must not rely on it.                                                          |

:::

Consequences for the documentation:

- The *Devices* / *Device Drivers* and *Configuration* sections are the
  exception: they are listed in full, since device drivers and config schema
  (not added yet) are inherently part of the interface users build against.
- Anything not listed in the reference is either **Unsupported** (used
  externally but without a stability guarantee) or **Internal** (not meant to
  be imported at all). Both may change without notice; the only difference is
  intent, not stability.

## API stability test

The Supported API is pinned by a signature snapshot test
(`tests/test_public_api.py`, snapshot in `tests/data/public_api_snapshot.json`).
The test reads the `reference` section of `great-docs.yml`, resolves every
listed item, and compares its signature against the snapshot. Each parameter
is recorded with its name, its kind (positional-only via `/`,
positional-or-keyword, keyword-only via `*`, `*args`, `**kwargs`), its
default value and its annotation; classes are recorded with their constructor
and their own public members, enums with their member names, and constants
with their value.

- **Breaking changes fail the test:** removed items, parameters, members or
  enum members; renamed or reordered positional parameters; optional
  parameters becoming required; changed default values; restrictive parameter
  kind changes (e.g. making a parameter positional-only or keyword-only);
  removed `*args`/`**kwargs`; changed constant values.
- **Superset changes pass** but are reported: new optional parameters
  (keyword-only, or appended to the positional block), required parameters
  becoming optional, relaxed parameter kinds, added `*args`/`**kwargs`, new
  members, new reference items, annotation-only changes.

After an intended API change, regenerate the snapshot and commit the result:

```sh
MATR1X_UPDATE_API_SNAPSHOT=1 uv run pytest tests/test_public_api.py
```
