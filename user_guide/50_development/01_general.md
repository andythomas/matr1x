# Development notes

{{< include "../../../.github/CONTRIBUTING.md" >}}

## Conventional Commits

Please note that [Commitizen](https://github.com/commitizen-tools/commitizen) can assist with message generation.

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
