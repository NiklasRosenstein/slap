# Configuration

The Slap configuration is read either from a `slap.toml` file or from the `[tool.slap]` section in `pyproject.toml`.

When a configuration value is described in the documentation, it is referenced without the `[tool.slap]` prefix that
is needed in the case where the configuration is loaded from `pyproject.toml`.

Check out the documentation for each command separately to understand how they can be configured.

## Application configuration

### `plugins.disable`

__Type__: `list[str] | None`  
__Default__: `None`

A list of plugins to disable, subtracting from the list of plugins that are loaded by default. By default, all builtin
plugins provided directly by Slap will be loaded. External plugins need to be enabled explicitly with `plugins.enable`.

### `plugins.enable`

__Type__: `list[str] | None`  
__Default__: `None`

A list of plugins to enable in addition to the list of plugins that are loaded by default (i.e. all the Slap builtin
plugins). External plugins need to be enabled explicitly with this option.

## `source-directory`

__Type__: `str | None`  
__Default__: `None`

The directory in which the Python source code resides. If not set, Slap will attempt to look into `./src/` first and
then `./`. This is used to detect the Python packages.

> __Todo__: If `[tool.poetry.packages]` is set, try and use that over manually detecting the packages.

## `typed`

__Type__: `bool`  
__Default__: `True`

Whether the project uses type hints.
