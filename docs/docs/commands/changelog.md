# `slap changelog`

This command provides four sub-commands that allow you to interact with Slap's structured changelog format: `add`,
`convert`, `format` and `update-pr`.

## Configuration

Option scope: `[tool.slap.changelog]` or `[changelog]`

| Option | Type | Default | Description |
| ------ | ---- | ------- | ----------- |
| `enabled` | `bool` | `True` | Whether the changelog feature is enabled for the directory in which the option is configured. This is useful to disable on the root of a mono-repository that contains multiple Python projects if one wants to prevent accidentally add changelog entries to the root directory. |
| `directory` | `str` | `.changelog/` | The directory in which the changelogs are stored. |
| `valid-types` | `list[str]` | `["breaking change", "docs", "feature", "fix", "hygiene", "improvement", "tests"]` | A list of strings that are accepted in changelog entries as types. |

<details><summary><code>ChangelogConfig</code> documentation</code></summary>

::: slap.ext.application.changelog.ChangelogConfig

</details>

---

## Subcommands

### `slap changelog add`

Add an entry to the unreleased changelog. Given the `-c,--commit` option, it will also create a Git commit with
the same message as the entry description, prefixed by the changelog type. If used in a sub-directory of a project,
the commit message is prefixed by the sub-directory.

__Example__

```toml
$ slap changelog add -t fix -d 'Fix the documentation' --issue 231 --issue 234
# Added changelog entry to .changelog/_unreleased.toml
id = "e0ee08af-ff2e-4aee-b795-e6c37e4c16de"
type = "fix"
description = "Fix the documentation"
author = "@NiklasRosenstein"
issues = [
  "https://github.com/username/repo/issues/231",
  "https://github.com/username/repo/issues/234",
]
```

<details><summary>Default changelog types</summary>
```py
DEFAULT_VALID_TYPES = [
  'breaking change',
  'deprecation',
  'docs',
  'feature',
  'fix',
  'hygiene',
  'improvement',
  'refactor',
  'tests'
]
```
<!--
::: slap.ext.application.changelog.DEFAULT_VALID_TYPES :with { render_title = false, render_signature = true }
-->
</details>

<details><summary>Synopsis</summary>
```
@shell slap changelog add --help
```
</details>

---

### `slap changelog convert`

This command converts changelogs from the previous YAML-based format used by Shut (a predecessor to Slap) to the
TOML format.

<details><summary>Synopsis</summary>
```
@shell slap changelog convert --help
```
</details>

---

### `slap changelog format`

  [Novella]: https://niklasrosenstein.github.io/novella/

Pretty print a changelog for the terminal or formatted as Markdown. Use the `-a,--all` option to format all changelogs.
This command is particularly useful to embed the changelog contents into generated documentation. For example, if you
use [Novella][], you can use the below bit in your documentation:

    @shell cd .. && slap changelog format --as-markdown --all

This is actually used in this very documentation: Check out the [Changelog](../changelog.md) page.

<details><summary>Synopsis</summary>
```
@shell slap changelog format --help
```
</details>

---

### `slap changelog diff pr update`

Updates the `pr` field of entries in the unreleased changelog. This is useful to run from continuous integration
jobs to avoid having to manually inject the pull request URL into changelog entries. If you are using GitHub, try
using the [`NiklasRosenstein/slap@gha/changelog/update/v2`](../guides/github.md#update-changelogs) action.

<details><summary>Synopsis</summary>
```
@shell slap changelog diff pr update --help
```
</details>

---

### `slap changelog diff assert-added`

This is a useful command to run in CI on Pull Requests to ensure that a new changelog entry was added by the PR.
If you are using GitHub, try using the [`NiklasRosenstein/slap@gha/changelog/assert-added/v2`](../guides/github.md#assert-changelogs) action.

<details><summary>Synopsis</summary>
```
@shell slap changelog diff assert-added --help
```
</details>
