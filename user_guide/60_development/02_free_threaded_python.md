# Free-threaded Python

`matr1x` does not support free-threaded ("no-GIL") CPython builds
(`cp3XXt`, available since Python 3.13). Two dependencies cannot be
installed on such an interpreter:

- **PySide6** publishes no free-threaded wheels (as of 6.12.0).
- **polars** ships only stable-ABI (`abi3`) wheels, and uv refuses to
  install `abi3` wheels on free-threaded interpreters, because the
  stable ABI makes no free-threading guarantees.

uv selects the project interpreter from the Python installations
available on the system. To make sure a GIL-enabled build is used,
pin the variant in `.python-version`, for example:

```
3.15+gil
```

(equivalently: `uv python pin 3.15+gil`).

Once PySide6 publishes `cp3XXt` wheels, free-threaded Python will be
tested.
