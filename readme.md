# slap &ndash; Assert new changelog entries have been added

  [Slap]: https://github.com/NiklasRosenstein/slap

This action asserts that new changelog entries have been added to the unreleased changelog in a Pull Request.

## Usage

```yaml
on: [ pull_request ]
jobs:
  assert-new-changelog-entries:
    name: "Assert that new changelog entries have been added"
    runs-on: ubuntu-latest
    if: github.base_ref != '' && !contains(github.event.pull_request.labels.*.name, 'no changelog')
    steps:
      - uses: actions/checkout@v2
      - uses: NiklasRosenstein/slap@gha/changelog/assert-added/v2
```

If no `version` is specified, it defaults to `>=1.7.0` which is the minimum version of Slap that
this action works with.
