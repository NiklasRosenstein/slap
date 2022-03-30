# `slap run`

Runs one of the commands from the Slap configuration. This is similar to `npm run` and `yarn run` for JavaScript projects.

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
