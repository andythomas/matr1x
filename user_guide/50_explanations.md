# Explanations

This section places key terms into a broader context, expanding on the simple definitions provided in the [glossary](glossary.md).

## Target Audiences & Roles

### GUI User

**GUI Users** require general familiarity with their operating system and basic computer navigation.
They must know how to navigate the local file system to locate required input files and retrieve generated output files.
Additionally, they must understand standard graphical user interface concepts, such as menus and toolbars.

### Script User

**Script Users** write small Python scripts and therefore require a basic understanding of Python syntax.
They must grasp fundamental programming concepts like variable assignment (`a = 2`), function calling (`add(a, b)`), selection (`if a == 1:`), and iteration (`for i in range(10):`).
They also need to know how to look up information regarding custom functions added via `matrix-script` (e.g. `measure_system()`).

### System Programmer

**System Programmers** operate within a pre-installed environment to write and maintain system configuration files or control GUIs.
They must know how to activate logging, interpret log files, and launch applications via the command line to debug full error traces.
Additionally, they are responsible for tracking release notes on [GitHub](https://github.com/andythomas/matr1x) and updating system files to accommodate API or configuration changes.

### Primary Programmer

**Primary Programmers** handle the initial software package installation, a process that may or may not require local administrator rights.
They must install Python (e.g. via `uv`) and understand environment management concepts like virtual environments and editable installations.
Furthermore, they need a general familiarity with the software's API to develop system files and control GUIs.

### Package Programmer

**Package Programmers** actively develop, modify, and maintain the core codebase of the software package itself.

## Major GUI Components

### Device Config

Use the configuration editor to modify the operational settings of attached instruments and devices.
The editor automatically validates all entered values against the specifications (defined as a `pydantic` model) established in the system file.
Because the system reads this configuration strictly at the start of a measurement, these settings only modify the predefined behavior of the devices (such as the maximum voltage applied by a current source).
They cannot alter the internal structural behavior of the system, such as the number of input and output columns.

### Measurement Queue

The measurement queue serves as the primary interface element within `matrix-gui`.
It allows users to build a list of multiple sweep files and execute them sequentially in a defined order.
Each individual entry within the queue independently stores its own specific device configuration and metadata.

### Metadata

The metadata panel enables users to attach descriptive information, such as sample identifiers and user names, directly to the headers of measurement files.
It structures these fields using a subset of the [Dublin Core vocabulary](https://en.wikipedia.org/wiki/Dublin_Core).
While this metadata provides context for identifying files later (and can be easily inspected using `matrix-preview`), it does not alter the execution or flow of the measurement in any way.
The system registers all metadata at the start of the measurement process.

### Parameter Editor

The parameter editor serves as the primary interface for `sweep-generator`.
It allows users to define measurement variables by specifying parameter triples, a start value, an end value, and a point count, similar to the `numpy.linspace` function.
Users can further modify these parameters by applying operations such as sequence repetition.
Ultimately, this tool generates a standardized measurement sweep file that `matrix-gui` consumes to execute a physical measurement.
To ensure these sweep files remain reusable across different experiments, they intentionally exclude metadata and device configurations.

### Script Editor

The script editor serves as the core interface for `matrix-script`.
Built on the [Monaco editor](https://microsoft.github.io/monaco-editor/), it provides essential convenience features such as syntax highlighting, hover help, and error detection via an LSP.
Here, users combine standard Python language constructs with custom function calls and properties provided by the package to write tailored instrument-control code.
Upon execution, the software integrates this custom script with the active metadata and device configuration to drive the measurement process, ultimately generating the physical output and saving the collected data into a structured output file.
