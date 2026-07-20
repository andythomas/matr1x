---
name: matr1x
description: >
  Use this to update the configuration file if the previous installation if the matr1x package is <8.3.0.
license: GNU General Public License v3 or later (GPLv3+)
compatibility: Requires Python >=3.10.
---

# Matr1x

## Upgrade to v8.3

1. Check if there is a `~/.matr1x.toml` file 
2. If yes, check if the is a `[matr1x.install]` section.
3. If yes, delete the `options` and `pipoptions` keys (if present).
