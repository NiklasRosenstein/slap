# `slap release`

This command updates the version numbers in your project(s).

<details><summary>Synopsis</summary>
```
@shell slap release --help
```
</details>

## Tool comparison

| Feature | `poetry bump` | `slap release` |
| ------- | ------ | ---- |
| Check for consistent version numbers across files in your repository | ❌ | ✅ |
| Update version number in `pyproject.toml` | ✅ | ✅ |
| Update dependencies of another project within the same mono-repository (interdependencies) | | ✅ |
| Update `__version__` in source code | ❌ | ✅ |
| Update and rename Slap structure changelog files | | ✅ |
| Commit changes, create a tag and push to Git remote | ❌ | ✅ |
| Create GitHub releases | ❌ | ❌ (planned in [#29](https://github.com/NiklasRosenstein/slap/issues/29)) |

> __Legend__: ✅ supported, ❌ not supported, (blank) conceptually irrelevant

## Configuration

Option scope: `[tool.slap.release]` or `[release]`

| Option | Type | Default | Description |
| ------ | ---- | ------- | ----------- |
| `branch` | `str` | `"develop"` | The branch on which releases are created. Unless `--no-branch-check` is passed to `slap release`, the command will refuse to continue if the current branch name does not match this value. |
| `commit-message` | `str` | `release {version}` | The commit message to use when using the `--tag, -t` option. The string `{version}` will be replaced with the new version number. |
| `tag-name` | `str` | `{version}` | The tag name to use when using the `--tag, -t` option. The string `{version}` will be replaced with the new version number. |
| `references` | `list[VersionRefConfig]` | `[]` | A list of version references that should be considered in addition to the version references that are automatically detected by Slap when updating version numbers across the project with the `slap release` command. A `VersionRefConfig` contains the fields `file: str` and `pattern: str`. The `file` is considered relative to the project directory (which is the directory where the `slap.toml` or `pyproject.toml` configuration file resides). |

<details><summary><code>ReleaseConfig</code></summary>

::: slap.ext.application.release.ReleaseConfig

</details>

<details><summary><code>VersionRefConfig</code></summary>

::: slap.ext.application.release.VersionRefConfig

</details>

## Usage example

```
$ slap release patch --tag --push
bumping 2 version references:
  pyproject.toml: 0.1.0 → 0.1.1
  src/my_package/__init__.py: 0.1.0 → 0.1.1

release staged changelog
  .changelog/_unreleased.toml → .changelog/0.1.1.toml

tagging 0.1.1

pushing develop, 0.1.1 to origin
```
