# Update Slam changelogs

This action updates Slam changelogs from a Pull Request to insert the URL of the PR into the newly added entries.

## Usage

```yaml
jobs:
  changelog-update:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v2
      - uses: NiklasRosenstein/slam@github-action/changelog-update/v1
        with:
          version: '1.1.2'
```

If no `version` is specified, or the version is set to `*`, the newest version of Slam will be installed.
