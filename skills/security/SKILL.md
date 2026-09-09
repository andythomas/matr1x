---
name: security
description: >
  Address the security alerts.
license: GNU General Public License v3 or later (GPLv3+)
compatibility: Requires Python >=3.10.
---

# Security

Read security alerts and address them.

## Address alerts

1. Read the security alerts via `uv audit` for this repository.
2. There will be a recommendation for the version of the package to upgrade to.
3. Look into the local `pyproject.toml` file in the project's root directory.
4. If the affected package is listed there, upgrade it to the recommended version.
5. If the affected package is not listed there, add it to the `tool.uv` override-dependencies key in `pyproject.toml`.

## Example

```toml
[tool.uv]
override-dependencies = [
    "urllib3>=2.7.0", # CVE-2026-44432, CVE-2026-44431
    "idna>=3.15", # CVE-2026-45409
    "starlette>=1.0.1", # CVE-2026-48710
    "fastapi>=0.136.1", # forced by CVE-2026-48710
]
```

## Steps to perform the migration

1. **address alerts** - perform the steps outlined above.

2. **update repository** - run `uv sync --all-extras --all-groups` to update the repository and lock file.

3. **query user** - run all tests for the package
