---
title: GitHub
---

# Using Slap in GitHub repositories

Most of Slap's functionality is independent of the repository hosting service that you use. However, Slap comes with
some built-in utities to make integration with GitHub easier.

__Table of Contents__

* [Install Slap](#install-slap)
* [Update Changelogs](#update-changelogs)
* [Assert Changelogs](#assert-changelogs)

## GitHub Actions

### Install Slap

  [0]: https://github.com/NiklasRosenstein/slap/tree/github-action/install/v1

The [`NiklasRosenstein/slap@gha/install/v2`][0] action installs Slap for you. It does this by setting up
Python 3.10 and installing Slap via Pipx.

!!! note

    Use this action _before_ you run your own step of `actions/setup-python@v2` as after this action the current
    Python version will be 3.10.

    The `version` option defaults to `*`, which installs the latest version of Slap. It is recommended that you
    pick an exact version for your configuration to avoid surprises.

```yaml title=".github/workflows/python.yml"
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: NiklasRosenstein/slap@gha/install/v2
        with: { version: '*' }
      - uses: actions/setup-python@v2
        with: { python-version: "3.x" }
      - run: slap install --no-venv-check
      - run: slap test
```

Instead of a `version`, you can also supply a Git ref with the `ref` input instead. This is useful when you want to
test unreleased changes to Slap.

### Update Changelogs

  [1]: https://github.com/NiklasRosenstein/slap/tree/gha/changelog/update/v2

The `slap changelog diff pr update` command updates the PR references of changelogs added between two Git revisions. In
addition, by passing `--use github-actions`, there is almost no need for any additional configuration inside of a
GitHub action run for a Pull Request event. The [`NiklasRosenstein/slap@gha/changelog/update/v3`][1] action
makes automatically updated changelogs a breeze:

```yaml title=".github/workflows/python.yml"
on: [ pull_request ]
jobs:
  changelog-update:
    name: "Insert the Pull Request URL into new changelog entries"
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request_target'
    steps:
      - uses: actions/checkout@v2
      - uses: NiklasRosenstein/slap@gha/changelog/update/v2
        with: { pr-id: '${{ github.event.pull_request.number }}' }
```

> The action takes additionally a `version`, `ref` and `token` input, but the defaults should be good enoguh in most
> cases.

Note that this workflow only works properly with the `pull_request_target` event. This is because the `pull_request`
event cannot post comments to the Pull Request.

!!! warning "Forks are not supported"

    The `GITHUB_TOKEN` does not have permissions to write back into the branch of a forked repository. If a pull
    request from a fork is recognized by Slap, it will instead post a comment to the Pull Request, asking the user
    to update the changelog entry manually.

## Assert Changelogs

  [2]: https://github.com/NiklasRosenstein/slap/tree/gha/changelog/assert-added/v2

The `slap changelog diff assert-added` command is similar to the `slap changelog diff pr update` command in that it
inspects the diff of changelogs between to Git versions, but it fails if no new changelog entry was added to the
unreleased changelog.

We recommend that you use the GitHub Action [`NiklasRosenstein/slap@gha/changelog/assert-added/v2`][2].

```yaml title=".github/workflows/python.yml"
on: [ pull_request ]
jobs:
  assert-new-changelog-entries:
    name: "Assert that new changelog entries have been added"
    runs-on: ubuntu-latest
    if: github.base_ref != '' && !contains(github.event.pull_request.labels.*.name, 'no changelog')
    steps:
      - uses: actions/checkout@v2
      - uses: NiklasRosenstein/slap@gha/changelog/assert-added/v2
        with: { version: '*' }
```
