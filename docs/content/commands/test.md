# Test

Configure the commands to run with `slap test` under the `tool.slap.test` table:

```toml
[tool.slap.test]
check = "slap check"
mypy = "mypy src/"
pytest = "pytest test/"
```