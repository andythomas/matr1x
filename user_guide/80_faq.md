# FAQ

## Should I use `--system-site-packages` during the installation?

Generally, we recommend not using that flag.
An installation from scratch via `uv` into a dedicated virtual environment is recommended.
Then, all packages will be installed as indicated in the `uv.lock` file, which corresponds to the tested versions in the GitHub workflows.
However, if a (e.g., proprietary) package is only available globally on your system, you have to use `--system-site-packages`.

## Can the measurements run any faster?

On a reasonably new computer (e.g., 2023), the software can collect a datapoint every 600µs, assuming that the datapoint itself requires no acquisition time.
Profiling a run in `matrix-script` yielded the following result:
The time to allow the visualization of the currently executed line amounts to approximately 200µs.
The time to open the datafile, add the datapoint and close it again also takes approximately 200µs.
Everything else takes the remaining 200µs and was not further investigated.

If a 3× speed increase would be beneficial in your use case, please open an [issue](https://github.com/andythomas/matr1x/issues) on the GitHub repository.

## What is the relation between `matrix-script` and `matrix-gui`?

`matrix-gui` provides a zero-programming interface to measurements, which might be preferable to some users, while `matrix-script` requires short Python scripts to define the measurements.
This should mostly be a matter of preference, and the capabilities of `matrix-gui` should not be limited _by design_.
However, the possibility to run arbitrary Python code in `matrix-script` will to some extent allow lower-level control.
