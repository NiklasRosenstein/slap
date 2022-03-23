# Check

The `slap check` command performs sanity checks on your project.

## Configuration

### `check.plugins`

__Type__: `list[str]`  
__Default__: `["log", "poetry", "release", "slap"]`

A list of check plugins to use. Note that the Poetry plugin will only fire checks if your project appears to be using
Poetry, so there is no harm in leaving it enabled even if you don't use it.

Additional plugins can be registered via an `ApplicationPlugin` under the `CheckPlugin` group.

__Todo__: Error if a specified plugin does not exist.

## Built-in checks

### `log`

The `ChangelogConsistencyCheck` checks if the changelogs managed by Slap are in order.

#### Check `log:validate`

Checks if all structured changelog files managed by Slap can be loaded and are valid.

---

### `slap`

> The `ShutChecksPlugin` provides all Python specific checks.

#### Check `slap:packages`

Checks if Slap can detect at least one package.

#### Check `slap:typed`

Checks if the project is typed but does not contain a `py.typed` file or the other way round.
This currently relies on the `$.typed` configuration and does not inspect the code for type hints.

---

### `poetry`

> The `PoetryChecksPlugin` will perform some Poetry specific configuration checks.

#### Check `poetry:readme`

Checks if the project readme is configured correctly or if Poetry is able to automatically
pick up the readme file if it is not configured. This inspects te `[tool.poetry.readme]` or `[project.readme]`
settings in `pyproject.toml` and compares it with the readme file that was automatically identified by Slap
(which is a file called README, case-insensitive with one of the suffixes in the order of `.md`, `.rst`, `.txt`,
or if that does not match, any file beginning with `README.`).

#### Check `poetry:urls`

Checks if the project URLs are configured properly. For the homepage URL, it will check for `[tool.poetry.homepage]`
or the `Homepage` key in `[tool.poetry.urls]`. Not having the homepage configured will trigger a warning. If otherwise
at least one of `Documentation`, `Repository` or `Bug Tracker` are missing, the check shows a recommendation.

#### Check `poetry:classifiers`

Checks if `[tool.poetry] classifiers` are all valid trove classifiers per https://pypi.org/classifiers/.

#### Check `poetry:license`

Checks if the `[tool.poetry] license` is set and whether it is a valid SPDX license identifier.

__TODO__ Check if the license is a valid SPDX license identifier.

> __Todo__: More of those checks should also support looking into `[project]`.

---

### `release`

> The `ReleaseChecksPlugin` performs checks to validate that `slap release` can be used properly.

#### Check `release:version`

Checks if the `__version__` can be detected in the source code of all detected packages.

#### Check `release:remote`

__TODO__ Checks if the VCS remote is configured or can be detected automatically such that the
`slap release --create-release` option can be used.
