# Slap

<img src="docs/content/img/logo.svg" style="height: 200px !important">

> *It slaps.*

  [PEP 517]: https://peps.python.org/pep-0517/

Slap is an extensive command-line tool to assist in the development of Python projects independent of the [PEP 517][]
build backend being used, capable of managing single- and multi-project repositories.

## Installation

We recommend installing Slap using Pipx.

    $ pipx install slap-cli

> __Note__: Currently Slap relies on an alpha version of `poetry-core` (`^1.1.0a6`). If you install it into
> the same environment as Poetry itself, you may also need to use an alpha version of Poetry (e.g. `1.2.0a2`).
>
> If you use Slap in GitHub Actions, try one of the actions provided by Slap directly:
>
> * [`NiklasRosenstein/slap@gha/install/v1`](https://niklasrosenstein.github.io/slap/guides/github/#install-slap)
> * [`NiklasRosenstein/slap@gha/changelog/update/v1`](https://niklasrosenstein.github.io/slap/guides/github/#update-changelogs)

## Documentation

You can find the documentation for Slap here: https://niklasrosenstein.github.io/slap/

## Feature Matrix

| Feature | Documentation |
| ------- | ------------- |
| Manage structured changelog entries | [slap changelog](https://niklasrosenstein.github.io/slap/commands/changelog/) |
| Show project details | [slap info](https://niklasrosenstein.github.io/slap/commands/info/) |
| Build and publish to PyPI using Twine | [slap publish](https://niklasrosenstein.github.io/slap/commands/publish/) |
| Create a new release (bump version numbersr)| [slap release](https://niklasrosenstein.github.io/slap/commands/release/) |
| Run a command configured in `pyproject.toml` | [slap run](https://niklasrosenstein.github.io/slap/commands/run/) |
| Run tests configured in `pyproject.toml` | [slap test](https://niklasrosenstein.github.io/slap/commands/test/) |
| Manage Python virtualenv's | [slap venv](https://niklasrosenstein.github.io/slap/commands/venv/) |

| Feature / Build backend | Flit  | Poetry  | Setuptools  | Documentation |
| ----------------------- | ----- | ------- | ----------- | --------- |
| Add dependency | ✅ | ✅ | ❌ | [slap add](https://niklasrosenstein.github.io/slap/commands/add/) |
| Sanity check project configuration | | ✅ | | [slap check](https://niklasrosenstein.github.io/slap/commands/check/) |
| Bootstrap project files | | ✅ | | [slap init](https://niklasrosenstein.github.io/slap/commands/init/) |
| Install projects using Pip | ✅ | ✅ | ✅ | [slap install](https://niklasrosenstein.github.io/slap/commands/install/) |
| Symlink projects (editable installs) | ✅ | ✅ | ✅ | [slap link](https://niklasrosenstein.github.io/slap/commands/link/) |
| Bump interdependencies in monorepository | ✅ (not tested regularly) | ✅ | ✅ (partial) | [slap release](https://niklasrosenstein.github.io/slap/commands/release/) |

> __Legend__: ✅ explicitly supported, ❌ explicitly not supported, (blank) not relevant or curerntly not supported

## FAQ

### Why "Slap"?

Finding a good, catchy name that also types easily in the terminal and is not already widely used isn't easy, ok?

### What makes this different to the Poetry CLI?

Poetry has it's own dependencies resolver and installer, but Slap just uses Pip. Slap also does not create or respect
lock files, so it may be more suitable to the development of reusable code than applications. Unlike Poetry, Slap
supports handling multiple Python projects under one repository (such as installing, symlinking, running tests,
publishing). While Poetry will create a virtual environment for you, Slap gives you an easy way to manage virtual
environments (backed by the `venv` stdlib module) and protects you from accidentally installing your project(s)
without a virtual environment enabled.
