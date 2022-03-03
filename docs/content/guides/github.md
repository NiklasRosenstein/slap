---
title: GitHub
---

# Using Slam in GitHub repositories

Most of Slam's functionality is independent of the repository hosting service that you use. However, Slam comes with
some built-in utities to make integration with GitHub easier.

## GitHub Actions

### Install Slam

The `NiklasRosenstein/slam@github-action/install/v1` action installs Slam for you. It does this by setting up
Python 3.10 and installing Slam via Pipx.

!!! note

    Use this action _before_ you run your own step of `actions/setup-python@v2` as after this action the current
    Python version will be 3.10.

    The `version` option defaults to `*`, which installs the latest version of Slam. It is recommended that you
    pick an exact version for your configuration to avoid surprises.

```yaml title=".github/workflows/python.yml"
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: NiklasRosenstein/slam@github-action/install/v1
        with: { version: '*' }
      - uses: actions/setup-python@v2
        with: { python-version: "3.x" }
      - run: slam install --no-venv-check
      - run: slam test
```

### Update Changelogs

The `slam changelog update-pr` command updates the PR references of changelogs added between two Git revisions. In
addition, by passing `--use github-actions`, there is almost no need for any additional configuration inside of a
GitHub action run for a Pull Request event. The `NiklasRosenstein/slam@github-action/changelog-update/v1` action
makes automatically updated changelogs a breeze:

```yaml title=".github/workflows/python.yml"
on: [ pull_request ]
jobs:
  changelog-update:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v2
      - uses: NiklasRosenstein/slam@github-action/changelog-update/v1
        with: { version: '*' }
```
