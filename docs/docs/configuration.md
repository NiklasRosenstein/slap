# Configuration

## Python Packages

Python packages are configured with a `package.yml` file. Most of the information will be
rendered into the `setup.py` file when running the `shore pkg update` command.

```yaml
name: my-package
version: 0.1.0
description: This is my package.
license: MIT
author: Me <me@me.org>
requirements:
  - python ^2.7|^3.4  # Indicates that the package is universal
  - click ~7.1.1
entrypoints:
  console_scripts:
    - my-cli = my_package.__main__:cli
```

## Mono Repositories

Monorepositories are configured with a `monorepo.yml` file. Packages in the repository must be
in folder directly next to the configuration file. The `shut mono update` command recursively
runs the update for all packages.

```yaml
name: my-monorepo
version: null  # Only needed for mono-versioning
release: false
```
