# slap &ndash; Update changelogs

  [Slap]: https://github.com/NiklasRosenstein/slap

This action updates changelog files managed by [Slap][] from a Pull Request to insert the
URL of the PR into the newly added entries.

## Usage

```yaml
on: [ pull_request ]
jobs:
  changelog-update:
    name: "Insert the Pull Request URL into new changelog entries"
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: NiklasRosenstein/slap@gha/changelog/update/v2
```

If no `version` is specified, the version will default to `>=1.7.0` (which is the minimum version
of Slap required for this action to work).
