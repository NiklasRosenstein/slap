# slap &ndash; Update changelogs

  [Slap]: https://github.com/NiklasRosenstein/slap

This action updates changelog files managed by [Slap][] from a Pull Request to insert the URL of the PR into the newly added entries.

## Usage

```yaml
jobs:
  changelog-update:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v2
      - uses: NiklasRosenstein/slap@gha/changelog/update/v1
        with: { version: '1.3.0' }
```

If no `version` is specified, or the version is set to `*`, the newest version of Slap will be installed.
