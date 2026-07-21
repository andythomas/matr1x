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

5. The subclass should have a unique name, i.e. all files should use different names. `MeasSystem` is a too generic class name and has to be changed.
