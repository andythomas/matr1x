---
name: Migration8.4.0
description: >
  Use this to update the configuration file if the previous installation if the matr1x package is <8.4.0.
license: GNU General Public License v3 or later (GPLv3+)
compatibility: Requires Python >=3.10.
---

# Matr1x

## Upgrade to v8.4

1. Check if there is a `~/.matr1x.toml` file 
2. If yes, check if the is a `[matr1x.scripts.matrix-script]` section.
3. If yes, check if there are entries for the `duplicate_output_to_logfile` and/or `print_to_comment` keys
4. Move the existing entries to the `[matr1x]` section of the file. If that section does not exist, create it.
