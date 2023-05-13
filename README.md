# slap &ndash; Install

  [Slap]: https://github.com/NiklasRosenstein/slap

This action installs the [Slap][] tool into your GitHub actions environment using Python 3.10 and Pipx.

## Usage

```yaml
jobs:
  build:
    steps:
      - uses: NiklasRosenstein/slam@gha/install/v1
        with: { version: '1.3.0' }
```

If no `version` is specified, or the version is set to `*`, the newest version will be installed. A constraint like
`>=1.7.0` can also be specified for the version.

## Changelog

### `v1` -> `v2`

* Now supports a `ref` input which is taken into account over the `version` input if specified. It can point to
  a Git ref in the [NiklasRosenstein/slap][Slap] repository to install from.
