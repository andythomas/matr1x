# Sweep Generator

## Features

The sweepGenerator uses a system file to determine the input file format for the matrix program.
The sweep can then be generated, previewed and manipulated until it suits the requirements/wished
of the experimentator. Then it can be written to a file in a way compatible with the matrix
measurement program. It offers several possibilities to generate and customize a sweep used for
measurements.

1. Basic sweeps (e.g. 1 to 10 in 10 steps).
2. Multiple sweeps (e.g. 1 to 10 in 10 steps and 11 to 20 in 19 steps)
3. Up and down sweeps (e.g. 1 to 10 and 10 to 1 in 20 steps).
4. Repetition of generated patterns (e.g. 10 times from 1 to 10 in 10 steps).
5. Looping of a sweep over a sweep (e.g. for each element in column a sweep column b).
6. A combination of the above.

## Examples

### Simple Sweep

To generate a sweep from 1 to 10 in 10 steps in column a, set 'Start' of column a to 1, 'End' to 10
and 'Step count' to 10. Click on 'Append' and then 'Preview' or 'Output to file' after selecting a
filename.

### Multiple Sweeps

To generate a sweep from -2 to 2 with varying resolution, you need to create three simple sweeps
with the wanted regions and step counts and append each to the column.

Step by step this would look like this: -2 to -0.2 in 19 steps, append, -0.1 to 0.1 in 21 steps,
append, 0.2 to 2 in 19 steps, append.

### Up and Down Sweep

Follow the same procedure as above but tick 'Up- and down' (can include several sweeps).

If the simple sweep above is used, the sweep would go from 1 to 10 in 10 steps and then back from
10 to 1 in another 10 steps.

### Repetition of the Generated Pattern

Define the sweep you want to repeat (can include several sweeps and the up and down option). Set
the textedit 'Repeat' to the number of times you want to repeat the pattern (e.g. 2 results in 2
times the pattern, 5 in 5 times the pattern, etc. - default is 1).

Again with the simple sweep above and repeat = 2, the resulting sweep would go from 1 to 10 in 10
steps and then again from 1 to 10 in 10 steps

### Looping

Define the sweep as you want to have it (can include several sweeps, the up and down option and
repetitions). Define the sweep you want to loop over in another column. Now, select the column you
want to loop over in the other column and click on generate or preview the sweep.

### Parameters accepting multiple values

For each of the values the corresponding parameter accepts (e.g. magnetic field along x and y),
sweep generator will generate a column where the value can be set. Since the parameter always
requires two values to be set, the values in both columns need to be of equal length (i.e. we
always need to provide both, x and y component of the field).
