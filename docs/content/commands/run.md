# `slap run`

> This command is venv aware.

Runs a command, using the commands configured under the `[tool.slap.run]` section as a source for aliases.

If there is an active virtual environment and you are not already in a virtual environment, it will be activated
before the command is run.

<details><summary>Synopsis</summary>
```
@shell slap run --help
```
</details>

## Configuration

Option scope: `[tool.slap.run]` or `[run]`

| Option | Type | Default | Description |
| ------ | ---- | ------- | ----------- |
| `<name>` | `str` | n/a | A command as a string to run with the system shell. |

__Example configuration__

=== "pyproject.toml"

    ```toml
    [tool.slap.run]
    "docs:build" = "cd docs && novella --base-url slap/"
    "docs:dev" = "cd docs && novella --serve"
    ```

=== "slap.toml"

    ```toml
    [run]
    "docs:build" = "cd docs && novella --base-url slap/"
    "docs:dev" = "cd docs && novella --serve"
    ```

```
$ slap run docs:dev
...
```
