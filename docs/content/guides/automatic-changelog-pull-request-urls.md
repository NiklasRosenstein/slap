# Automate changelog Pull Request URLs

The `slam changelog update-pr` can be used in CI builds to automatically update the Pull Request URL in changelog
entries that have been added by that particular PR.

## GitHub Actions

Slam comes with a plugin if you are using GitHub actions to simplify your pipeline description.

```yaml
update-pr-numbers:
  if: github.event_name == 'pull_request'
  permissions:
    contents: write
  runs-on: ubuntu-latest
  steps:
  - uses: actions/checkout@v2
  - name: Set up Python ${{ matrix.python-version }}
    uses: actions/setup-python@v2
    with: { python-version: "3.10" }
  - name: Install Slam
    run: pip install -r slam-cli=={@shell slam --version | awk '{ print substr($3, 1, length($3)-1); \}' }
  - name: Update PR references in changelogs
    run: slam -vv changelog update-pr --use github-actions
```
