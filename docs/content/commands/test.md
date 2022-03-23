# Test

Configure the commands to run with `clap test` under the `tool.clap.test` table:

```toml
[tool.clap.test]
check = "clap check"
mypy = "mypy src/"
pytest = "pytest test/"
```