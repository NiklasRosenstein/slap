# Run

Run a command configured under the `run` section.

## Example

    $ slam run docs:dev

=== "pyproject.toml"

    ```toml
    [tool.slam.run]
    "docs:dev" = "cd docs && novella --serve"
    ```

=== "slam.toml"

    ```toml
    [run]
    "docs:dev" = "cd docs && novella --serve"
    ```
