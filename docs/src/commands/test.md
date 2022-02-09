# shut test

Configure the commands to run with `shut test` under the `tool.shut.test` table:

```toml
[tool.shut.test]
pytest = "pytest --cov=shut"
mypy = "mypy"
pylint = "pylint --fail-under=8.0"
```