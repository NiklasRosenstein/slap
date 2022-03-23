# Run

Run a command configured under the `run` section.

## Example

    $ slap run docs:dev

=== "pyproject.toml"

    ```toml
    [tool.slap.run]
    "docs:dev" = "cd docs && novella --serve"
    ```

=== "slap.toml"

    ```toml
    [run]
    "docs:dev" = "cd docs && novella --serve"
    ```
