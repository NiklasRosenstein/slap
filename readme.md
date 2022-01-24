# shut

Shut is a command-line utility for developing Python applications. It works well with [Poetry][], but is using Poetry

is not required to make use of Shut.

__Features__

* Manage structured changelogs via the CLI
* Automate releases
* Sanity check `pyproject.toml` configuration
* Editable installs for Poetry managed packages

## Getting started

### Installation

It is recommended to install Shut via Pipx, but you can also install it with Pip directly.

    $ pipx install shut

### Managing changelogs

The `shut log` command can be used to manage changelog files which are usually stored in a `.changelog/` directory,
but the directory can be changed using the `tool.shut.changelog-dir` option. The CLI allows you to add new entries
as well as print them in a pretty format in the terminal or render the changelog as Markdown.

A changelog entry has a unique ID, one or more tags that categorize the type of change, one or more authors,
a short description, maybe a link to a pull request and links to issues that are fixed by the change.

```toml
$ shut log add -t fix,docs -m 'Fix the documentation' --fixes 231,234
# Added changelog entry to .changelog/_unreleased.toml
id = "d0092ba"
tags = [ "fix", "docs" ]
message = "Fix the documentation"
fixes = [
  "https://github.com/username/repo/issues/231",
  "https://github.com/username/repo/issues/234",
]
pr = null
```

The `pr` value can be set manually once a PR was created, or be updated automatically for example through a GitHub
action or other type of CI job (the `shut log inject-pr-url` command can help with that).

### Automating releases

The `shut release` command is a much improved version to the `poetry version` command in that is can bump multiple
references to the version number in the project. It can also be used to verify that the version number is consistent
and matching a particular value in CI checks using the `--verify` option.

Shut currently reads the configuration from `tool.poetry`, but support for [PEP 621][]
metadata is planned. It tries its best to detect the package source code roots, but if the automatic detection fails or
cannot be detected from other existing configurations, the `tool.shut.packages` and `tool.shut.source-directory`
options can be set explicitly.

The release process will also rename changelogs and insert the release date into changelogs created and managed with
`shut log`.

    $ shut release patch --tag --push
    bumping 2 version references:
      pyproject.toml: 0.1.0 → 0.1.1
      src/my_package/__init__.py: 0.1.0 → 0.1.1

    release staged changelog
      .changelog/_unreleased.toml → .changelog/0.1.0.toml

    tagging 0.1.1
      [develop] ec1e9b3] release 0.1.0
      3 files changed, 3 insertions(+), 4 deletions(-)
      rename .changelog/{_unreleased.yml => 0.1.0.yml} (78%)

    pushing develop, 0.1.1 to origin
      Enumerating objects: 24, done.
      Counting objects: 100% (24/24), done.
      Delta compression using up to 8 threads
      Compressing objects: 100% (17/17), done.
      Writing objects: 100% (24/24), 3.87 KiB | 566.00 KiB/s, done.
      Total 24 (delta 4), reused 0 (delta 0)
      To https://github.com/username/repo
      * [new branch]      develop -> develop
      * [new tag]         0.1.1 -> 0.1.1

Additional version references can be configured using the `tool.shut.version-references` option or by installing a
plugin that registers an entrypoint under `tool.shut.plugins.release`.

### Editable installs

This is particularly interesting when managing the package with [Poetry][] as it does not currently support editable
installs (as of Poetry 1.2.0a2 on 2022-01-14). This is a little helper command that will temporarily reorganize the
`pyproject.toml` to be compatible with [Flit] and make use if it's symlink installation feature (`flit install -s`).

    $ shut link
    # (TODO: Paste output here)


  [PEP 621]: https://www.python.org/dev/peps/pep-0621
  [Flit]: https://flit.readthedocs.io/en/latest/
  [Poetry]: https://python-poetry.org/


### Sanity checks

Using `shut check`, your project configuration will be checked an the results will be printed. Currently the checks include

* Can Shut determine your package source code (for example `src/my_package`)
* Can Shut detect the `__version__` in your package source code
* Is the `readme` in `tool.poetry` configured correctly (does the file exist? does the project use a non-standard
  readme filename that is not configured in Poetry?)
* Are the package URLs configured correctly?
* Is the `vcs-remote` option in `tool.shut` configured (recommended when using `shut log`)
* Are the `classifiers` in `tool.poetry` standard classifiers
* Is the `license` in `tool.poetry` a recommended SPDX Open Source License identifier
* Is the package homepage and documentation URL specified
* Are the changelog files in proper shape (i.e. can be decoded and are not missing required fields)

---

<p align="center">Copyright &copy; 2022 Niklas Rosenstein</p>
