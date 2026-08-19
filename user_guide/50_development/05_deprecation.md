# Deprecation

Software packages evolve over time and our package is no exception.
There will be APIs, configuratons and other things that will be deprecated in the future.
In the next sections, we will explain the lifecycle.

## The Deprecation Lifecycle

When a feature is replaced, it progresses through three distinct phases across releases.

Assuming the current stable version is **`v8.4.0`**, the deprecation sequence works as follows:

| Version                          | Phase                    |
| :------------------------------- | :----------------------- |
| **`v8.5.0`** _(dev: `8.4.0dev`)_ | **Soft Deprecation**     |
| **`v8.6.0`** _(dev: `8.5.0dev`)_ | **Explicit Deprecation** |
| **`>=v8.7.0`**                   | **Hard Removal**         |

- **Soft Deprecation** The legacy item is marked as deprecated. A **soft notification** (auto-dismissing after a few seconds) is shown when the item is called. The replacement API is available.
- **Explicit Deprecation** The notification is escalated to an **explicit alert** that must be manually dismissed to alert holdouts.
- **Hard Removal** The old item is completely removed from the codebase. Calling it will result in an error.

Please note that the notiications overwrite each other and inform the corresponding system programmer of any deprecated items as soon as possible.

## Upgrade Timeline

- **Release Cadence:** We target a minor release (`8.x.0`) every **2 to 3 months**.
- **Migration Window:** Users have a window of approximately **6 months** (spanning two minor versions) between the initial deprecation warning and hard removal at the third released version.
- **Automated Migration Assistance** To simplify upgrades, whenever possible we will release automated tools such as migration skills alongside deprecations to assist you in updating your codebase automatically.

## Deprecated items

| Item                                    | Deprecation | Removal |
| :-------------------------------------- | :---------: | :-----: |
| `duplicate_output_to_logfile` migration |    8.4.0    | >=8.6.0 |
| `print_to_comment` migration            |    8.4.0    | >=8.6.0 |
| initialized `system`                    |    8.5.0    | >=8.7.0 |
| `root_path` in config                   |    8.5.0    | >=8.7.0 |

## Removed in the current `development` version

| Item                 | Deprecation |           Remedy           |
| :------------------- | :---------: | :------------------------: |
| `function` in sweep  |    8.0.1    |    use `matrix_script`     |
| SR830 lock in driver |    8.0.1    | use `pymeasure` equivalent |
| `sys` use in systems |    8.0.1    |     rename to `system`     |
| `loadh5matrix`       |    8.1.0    |      use `loadmatrix`      |
