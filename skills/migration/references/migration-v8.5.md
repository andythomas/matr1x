# Matr1x

## Upgrade to v8.5

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
