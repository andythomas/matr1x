# Deprecation

Software packages evolve over time and our package is no exception.
There will be APIs, configuratons and other things that will be deprecated in the future.
In the next sections, we will explain the lifecycle.

## The Deprecation Lifecycle

When a feature is replaced, it progresses through three distinct phases across minor and major releases.

Assuming the current stable version is **`v8.4.0`**, the deprecation sequence works as follows:

| Version                          | Phase                |
| :------------------------------- | :------------------- |
| **`v8.5.0`** _(dev: `8.4.0dev`)_ | **Soft Deprecation** |
| **`v8.6.0`** _(dev: `8.5.0dev`)_ | **Loud Deprecation** |
| **`v9.0.0`**                     | **Hard Removal**     |

- **Soft Deprecation** The legacy item is marked as deprecated. **Quiet warnings** (such as log warnings) are emitted when the item is called. The replacement API is available.
- **Loud Deprecation** Warnings are escalated to **prominent messages** (e.g. log errors or even UI pop-ups) to alert holdouts.
- **Hard Removal** The old item is completely removed from the codebase. Calling it will result in an error.

## Upgrade Timeline

- **Release Cadence:** We target a minor release (`8.x.0`) every **2 to 3 months**.
- **Migration Window:** Users have a window of approximately **6 months** (spanning two minor versions) between the initial deprecation warning and hard removal in the next major version.
- **Automated Migration Assistance** To simplify upgrades, whenever possible we will release automated tools and migration scripts alongside deprecations to assist you in updating your codebase automatically.

## Deprecated items

| Item                  | Deprecation | Removal |
| :-------------------- | :---------: | :-----: |
| SR830 lock in driver  |    8.0.1    |  9.0.0  |
| `loadh5matrix`        |    8.1.0    |  9.0.0  |
| `sys` use in systems  |    8.0.1    |  9.0.0  |
| `function` in sweep   |    8.0.1    |  9.0.0  |
| initialized `system`  |    8.5.0    |  9.0.0  |
| `root_path` in config |    8.5.0    |  9.0.0  |

