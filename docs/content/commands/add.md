# `slap add`

> This command is venv aware.

This command adds one or more Python packages to the dependencies defined in `pyproject.toml`. If the packages
are not already installed, they will be installed into the current Python environment using Pip.

<details><summary>Synopsis</summary>
```
@shell slap add --help
```
</details>

## Usage example

The below example installs `httpx` using Pip and adds the dependency to `pyproject.toml`. If your project is using
Poetry as the build backend, it will add `httpx = "^0.22.0"` wheras if it is using Flit, the command will add instead
`'httpx (>=0.22.0,<0.23.0)'`.

    $ slap add httpx
    Installing httpx
    Adding httpx ^0.22.0

!!! note

    Slap uses `pkg_resources.get_distribution()` to retrieve the version of the package that got installed, or was
    already installed, and assumes that the package is available in the target Python environment.

## Support matrix

| Build system | Supported |
| ------------ | --------- |
| Flit | ✅ |
| Poetry | ✅ |
| Setuptools | ❌ (dependencies defined in `setup.cfg`) |
