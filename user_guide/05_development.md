# Development notes

## How to contribute

We welcome contributions! Report bugs, suggest features, or submit fixes via GitHub:

- [Raise an issue](https://github.com/andythomas/matr1x/issues)
- Submit a [pull request](https://github.com/andythomas/matr1x/pulls)

All changes require a pull request and are subject to unit tests, commit hooks, CI, and code
review. Direct commits to `main` are not possible.

We use [semantic versioning](https://semver.org/). Pull request titles must follow a
[specific pattern](https://www.conventionalcommits.org/en/v1.0.0/) for automatic versioning.

Titles must start with a prefix (`feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`,
`chore`, `revert`, `ci`), followed by a colon and a space. A quick introduction can be found
[here](https://gist.github.com/joshbuchea/6f47e86d2510bce28f8e7f42ae84c716).

[Commitizen](https://github.com/commitizen-tools/commitizen) can assist with message generation.

## Setting up a development environment

We recommend setting up your development environment using a `uv` virtual environment.

### Virtual environment with uv

Follow the installation instructions in the README. To obtain all dependencies, including optional
extras, use `uv sync --all-extras`.

## Testing the code locally

Run unit tests within your virtual environment using:

```bash
pytest
```

## Specific editor settings

### Zed editor settings

In case you use the Zed editor you may benefit from including these settings for this project and
install the `toml`, `ruff` and `ty` extensions. Note that you have to replace `<project-root>`
with the directory on your system.

```json
{
  "languages": {
    "Python": {
      "language_servers": ["ruff", "ty"]
    }
  },
  "lsp": {
    "ty": {
      "binary": {
        "path": "<project-root>/.venv/bin/ty",
        "arguments": ["server"]
      }
    },
    "ruff": {
      "binary": {
        "path": "<project-root>/.venv/bin/ruff",
        "arguments": ["server"]
      }
    }
  },
  "terminal": {
    "detect_venv": {
      "on": {
        "directories": [".venv"],
        "activate_script": "default"
      }
    }
  }
}
```

### Visual Studio Code settings

If you use Visual Studio Code, you can install the `Python`, `ruff` and `ty` extensions.
