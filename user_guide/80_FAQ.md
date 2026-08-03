# FAQ

### Should I use `--system-site-packages` during the installation?

Generally, we recommend not using that flag.
An installation from scratch via `uv` into a dedicated virtual environment is recommended.
Then, all packages will be installed as indicated in the `uv.lock` file, which corresponds to the tested versions in the GitHub workflows.
However, if a (e.g., proprietary) package is only available globally on your system, you have to use `--system-site-packages`.

### Can the measurements run any faster?

On a reasonably new computer (e.g., 2023), the software can collect a datapoint every 600µs, assuming that the datapoint itself requires no acquisition time.
Profiling a run in `matrix-script` yielded the following result:
The time to allow the visualization of the currently executed line amounts to approximately 200µs.
The time to open the datafile, add the datapoint and close it again also takes approximately 200µs.
Everything else takes the remaining 200µs and was not further investigated.

If a 3× speed increase would be beneficial in your use case, please open an [issue](https://github.com/andythomas/matr1x/issues) on the GitHub repository.

### What is the relation between `matrix-script` and `matrix-gui`?

`matrix-gui` provides a zero-programming interface to measurements, which might be preferable to some users, while `matrix-script` requires short Python scripts to define the measurements.
This should mostly be a matter of preference, and the capabilities of `matrix-gui` should not be limited _by design_.
However, the possibility to run arbitrary Python code in `matrix-script` will to some extent allow lower-level control.

### Is there a Dark mode?

Yes, Dark mode is provided for all matr1x graphical user interfaces.
In previous discussions, this feature was considered essential by some users.
This includes dynamic, automatic switching between light and dark mode based on the system settings.
Consequently, this extends to the user guide as well, where all images are provided in two variants.

### Why is type-checking used in the code base? Python is and should be a dynamic language!

Let us consider a [quote](https://thenewstack.io/guido-van-rossum-on-types-speed-and-the-future-of-python/) from van Rossum first: "My assumption is that many, many people developing Python software professionally, for some kind of production situation, are using a static type checker. Especially anybody who has a continuous integration cycle — probably, one of the steps in their testing routine that happens for basically every commit is 'Run a static type checker'"

Scientific data acquisition and instrument control are certainly similar to a production situation, and we do use continuous integration.
So, why do so many people in that situation use it?
The answer is simple: it catches bugs early.
W. Xu et al. [reported](https://doi.org/10.1109/ICPC58990.2023.00039) 29 out of 40 bugs caught with and 14/40 without type checking and the experience with our own code base is very similar.
Furthermore, type checking enables refactoring of lower code quality, which would otherwise inherently increase the number of bugs.

Please note that we will assist with adding type hints to pull requests for new features or bug fixes.

### Do you accept patches for upstream bugs?

Unfortunately, it is not possible for us to accept patches for upstream bugs.
This was attempted in the past and only led to increased complexity, a higher maintenance burden, and potential regressions.
In very rare cases where our software does not work properly at all and an upstream fix is not (and will not be) available, we will consider patches.
