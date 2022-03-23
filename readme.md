# slap

Slap is a command-line tool for developing Python projects that provides a common interface for many tasks independent
of the build system you use (currently supporting Setuptools via Pyproject, Poetry and Flit). It makes it easier to
manage monorepositories of multiple projects which may even have inter-dependencies.

> Developer's note: I personally use Poetry as the build system for some of its features, in particular because of
> its support for semantic version selectors which are not supported by Setuptools or Flit; but never actually
> use the Poetry CLI because I too often run into issues with it's dependency resolution and installation mechanism
> as well as its implicitly created virtual environments.

Slap provides a variety of features, including but not limited to

* Sanity check your project configuration
* Install your project and it's dependencies via Pip (in the right order in case of a monorepository)
* Symlink your project (using Flit's symlinking function internally, independent of your actual build system; Poetry
  does not support editable installs so this is really convenient)
* Build and publish your project (and all its individual packages in case of a monorepository) to Pypi using Twine
* Release new versions (automatically update version numbers in code, create a Git tag and push)
* Run tests configured in your Pyproject config under `[tool.slap.test]`
* Manage local (`~/.venvs`) and global (`~/.local/venvs`) virtual environments (backed by Python's `venv` module)
* Manage structured changelogs (TOML) via the CLI; easily inject PR URLs into changelog entries in pull requests via CI

## Installation

It is recommended to install Slap via Pipx, but you can also install it with Pip directly.

    $ pipx install slap-cli

> __Note__: Currently, Slap relies on an alpha version of `poetry-core` (`^1.1.0a6`). If you install it into
> the same environment as Poetry itself, you may also need to use an alpha version of Poetry (e.g. `1.2.0a2`).

## Usage examples

Bootstrap a (opinionated) Poetry project using Slap.

    $ slap init --name my.pkg
    write my-pkg/pyproject.toml
    write my-pkg/LICENSE
    write my-pkg/readme.md
    write my-pkg/.gitignore
    write my-pkg/src/my/pkg/__init__.py
    write my-pkg/test/test_import.py
    write my-pkg/src/my/pkg/py.typed

Sanity check your project configuration

    $ slap check
    Checks for project slap-cli

      changelog:validate           OK             — All 74 changelogs are valid.
      general:packages             OK             — Detected /home/niklas/git/slap/src/slap
      general:typed                OK             — py.typed exists as expected
      poetry:classifiers           OK             — All classifiers are valid.
      poetry:license               OK             — License "MIT" is a valid SPDX identifier.
      poetry:readme                OK             — Poetry readme is configured correctly (path: readme.md)
      poetry:urls                  RECOMMENDATION — Please configure the following URLs: "Bug Tracker"
      release:source-code-version  OK             — Found __version__ in slap

Install and link your project (by default, the command protects you from accidentally installing the project; you can pass `--no-venv-check` to skip this safeguard).

    $ slap install --link

Validate the version numbers in your project and release a new version.

    $ slap release --validate
    versions are ok
      pyproject.toml:          1.2.4 # version = "1.2.4"
      src/slap/__init__.py:    1.2.4 # __version__ = '1.2.4'
    $ slap release --tag --push minor
    bumping 3 version references to 1.3.0
      pyproject.toml:          1.2.4 → 1.3.0 # version = "1.2.4"
      src/slap/__init__.py:    1.2.4 → 1.3.0 # __version__ = '1.2.4'

    releasing changelog
      .changelog/_unreleased.toml → .changelog/1.3.0.toml

    tagging 1.3.0

    pushing develop, 1.3.0 to origin
