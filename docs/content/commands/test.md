# Test

Configure the commands to run with `slam test` under the `tool.slam.test` table:

```toml
[tool.slam.test]
check = "slam check"
mypy = "mypy src/"
pytest = "pytest test/"
```