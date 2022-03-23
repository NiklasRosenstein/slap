# Run

Run a command configured under the `run` section.

## Example

    $ clap run docs:dev

=== "pyproject.toml"

    ```toml
    [tool.clap.run]
    "docs:dev" = "cd docs && novella --serve"
    ```

=== "clap.toml"

    ```toml
    [run]
    "docs:dev" = "cd docs && novella --serve"
    ```
