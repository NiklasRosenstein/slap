# `slap test`

> This command is venv aware.

Runs some or all of the tests from the Slap configuration. This is different from [`slap run`](run.md) in that by
default it runs multiple commands, prefixes the output them with the test name (similar to `docker-compose logs`),
works across multiple projects in a mono-repository and prints a summary of the results at the end.

If there is an active virtual environment and you are not already in a virtual environment, it will be activated
before the test commands are run.

<details><summary>Synopsis</summary>
```
@shell slap test --help
```
</details>

## Configuration

Option scope: `[tool.slap.run]` or `[run]`

| Option | Type | Default | Description |
| ------ | ---- | ------- | ----------- |
| `<name>` | `str` | n/a | A command as a string to run with the system shell. |

<details><summary>An example configuration</summary>

```toml title="pyproject.toml"
[tool.slap.test]
check = "slap check"
mypy = "mypy src/"
pytest = "pytest test/"
```

</details>

<details><summary>Example from the <a href="https://github.com/NiklasRosenstein/python-databind">databind</a> project</summary>

Databind is a mono-repository of three Python projects, two of which have tests set up. Running `slap test` in the
project root folder runs all tests of all projects.

```
$ slap test
databind.core:mypy| Success: no issues found in 8 source files
databind.core:pytest| ================== test session starts ==================
databind.core:pytest| platform linux -- Python 3.10.2, pytest-7.1.1, pluggy-1.0.0
databind.core:pytest| rootdir: /home/niklas/git/databind/databind.core
collected 17 items
databind.core:pytest|
databind.core:pytest| test/test_context.py .                            [  5%]
databind.core:pytest| test/test_schema.py ................              [100%]
databind.core:pytest|
databind.core:pytest| ================== 17 passed in 0.05s ===================
databind.json:mypy| Success: no issues found in 5 source files
databind.json:pytest| ================== test session starts ==================
databind.json:pytest| platform linux -- Python 3.10.2, pytest-7.1.1, pluggy-1.0.0
databind.json:pytest| rootdir: /home/niklas/git/databind/databind.json
collected 32 items
databind.json:pytest|
databind.json:pytest| test/test_converters.py ......................... [ 78%]
databind.json:pytest| .......                                           [100%]
databind.json:pytest|
databind.json:pytest| ================== 32 passed in 0.11s ===================

test summary:
  • databind.core:mypy (exit code: 0)
  • databind.core:pytest (exit code: 0)
  • databind.json:mypy (exit code: 0)
  • databind.json:pytest (exit code: 0)
```

</details>


## Test selection

* If no `test` positional argument is specified, all tests in the project or projects of the repository will be run. (`$ slap test`)
* To run the tests of only one project while in a mono-repository folder, pass the project name as the `test` argument. (`$ slap test databind.core`)
* To run tests of the same name across all projects, pass the test name prefixed with a colon as the `test` argument. (`$ slap test :mypy`)
* To run only one particular test from a given project, pass the project name and test name separated by a colon as the
  `test` argument. (`$ slap test databind.core:mypy`)
