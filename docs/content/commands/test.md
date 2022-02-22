# slam test

Configure the commands to run with `slam test` under the `tool.slam.test` table:

```toml
[tool.slam.test]
pytest = "pytest --cov=slam"
mypy = "mypy"
pylint = "pylint --fail-under=8.0"
```