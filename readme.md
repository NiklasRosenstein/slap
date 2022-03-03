# Install Slam

This action installs the [Slam](https://niklasrosenstein.github.io/slam/) program into your GitHub actions environment
using Python 3.10 and Pipx.

## Usage

```yaml
jobs:
  build:
    steps:
      - uses: NiklasRosenstein/slam@github-action/install/v1
        with:
          version: '1.1.2'
```

If no `version` is specified, or the version is set to `*`, the newest version will be installed.
