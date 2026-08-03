---
name: dependabot
description: >
  Address the dependabot alerts.
license: GNU General Public License v3 or later (GPLv3+)
compatibility: Requires Python >=3.10.
---

# Dependabot

Take the dependabot alerts and address them.

## Address alerts

1. Read the [dependabot alerts](https://github.com/andythomas/IFW_software/security/dependabot) for this repository.
2. Follow the links to the affected packages one by one.
3. For every affected package, read the page.
4. On top of the page there will be a recommendation for the version of the package to upgrade to.
5. Look into the local `pyproject.toml` file in the project's root directory.
6. If the affected package is listed there, upgrade it to the recommended version.
7. If the affected package is not listed there, add it to the `tool.uv` override-dependencies key in `pyproject.toml`.

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

3. **query user** - Ask the user to perform the tests, do not perform the tests automatically.
