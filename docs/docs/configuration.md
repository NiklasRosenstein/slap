# Configuration

The Slap configuration is read either from a `slap.toml` file or from the `[tool.slap]` section in `pyproject.toml`.

!!! note

    A `slap.toml` configuration file is usually only used at the project root in case of mono-repositories for multiple
    Python projects. The file is often used to
    
    * disable mono-repository level changelogs ([`slap changelog`](commands/changelog.md#configuration))
    * configure global tests or commands ([`slap run`](commands/run.md#configuration), [`slap test`](commands/test.md#configuration))
    * global version references ([`slap release`](commands/release.md#configuration))

In this section, we describe the global configuration options that affect Slap directly and are not specifically
tied to any single Slap command.

| Option | Type | Default | Description |
| ------ | ---- | ------- | ----------- |
| `typed` | `bool | None` | `None` | Whether the Python code uses type hints. If not set, Slap acts as if this is not known. |
| `disable` | `list[str]` | `[]` | A list of Slap application plugins to disable. |
| `enable-only` | `list[str]` | `[]` | A list of Slap application plugins to enable. |

## Plugin loading

All Slap commands are implemented as [`ApplicationPlugin`s][slap.plugins.ApplicationPlugin]. By default, Slap will load plugin
that is registered under the `slap.plugins.application` entrypoint, however plugins can be disabled using the `disable`
option or an explicit list of plugins to load and none other can be set with `enable-only`.

Restricting the plugins to load will impact the set of commands available at your disposal through the Slap CLI.
