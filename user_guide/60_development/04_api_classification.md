# API classification

The `matr1x` API uses a three-level classification. The levels describe what
kind of compatibility guarantee importers can expect:

::: {.api-classification}

| Level        | Meaning                                                                                                                                    | Guarantee                                                                                                                                     |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------- |
| **Public API** | The stable, documented interface of the package. Listed in the documentation's `reference` section.                                     | Behavior changes follow semantic versioning. Deprecation cycle as described in the documentation.                |
| **Public**     | In `__all__` (or not underscored if it does not exist), used outside of the defining module, but not listed in the `reference` section. | No stability guarantee. May change or be removed in any release without deprecation. External users are encouraged to migrate to the Public API where possible. |
| **Private**    | Internal implementation detail.                                                                                                            | No guarantee at all. Free to change at any time; external code must not rely on it.                                                          |

:::

Consequences for the documentation:

- The *Devices* / *Device Drivers* and *Configuration* sections are the
  exception: they are listed in full, since device drivers and config schema
  (not added yet) are inherently part of the interface users build against.
- Anything not listed in the reference is either **Public** (and used
  externally but unsupported) or **Private**, and may change without notice.
