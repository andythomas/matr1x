# Upgrade to v8.6

## Rename the `[matr1x.scripts]` TOML section to `[matr1x.apps]`

The configuration section names the applications. The section was renamed from
`[matr1x.scripts]` to `[matr1x.apps]`.

1. Check if there is a `~/.matr1x.toml` file.
2. If yes, check if there is a `[matr1x.scripts]` section.
3. If yes, rename that section to `[matr1x.apps]`.
4. Within that section, replace the `matrix-script` subsection name with
   `matrix_script` (underscored, to correspond 1:1 with the Python attribute).
5. Keep the `shortcuts` subsection and its keys as they are.
