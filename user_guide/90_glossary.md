# Glossary

This glossary defines key terms and roles used throughout the repository and the user guide.

## Target Audiences & Roles

### GUI User

**GUI Users** operate the software package to perform measurements exclusively through graphical interfaces, such as `sweep-generator` and `matrix-gui`.

### Script User

**Script Users** utilize the software package to execute measurements programmatically via `matrix-script`.

### System Programmer

**System Programmers** maintain and configure specific hardware environments or experimental setups.

### Primary Programmer

**Primary Programmers** install the software package on the host computer and develop the initial system code.

### Package Programmer

**Package Programmers** develop, modify, and maintain the core codebase of the software package itself.

## Major GUI Components

### Device Config

An editor used to modify the operational settings of attached instruments prior to a measurement.

### Measurement Queue

The primary `matrix-gui` interface for sequentially executing a list of measurement sweep files.

### Metadata

A panel for attaching descriptive context to measurement file headers.

### Parameter Editor

The main interface within `sweep-generator` used to define measurement variables and generate sweep files for execution.

### Script Editor

The core interface of `matrix-script` where users write tailored Python code to control instruments and drive the measurement process.
