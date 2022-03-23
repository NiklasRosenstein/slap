# Usage examples

Slap provides a variety of features to increase productivity for Python developers. It supports dealing with
multiple Python projects managed from a monorepository, in which case most operations are homogenously applied
across all projects.

All features are implemented as {@pylink slap.plugins.ApplicationPlugin} and most features provide additional
interfaces to plug into their functionality (such as additional plugins for the `slap check` and `slap release`
command).

## Inspect Slap's understanding of your project

Using the `slap info` command, you can get an overview of the project details that Slap understands of your project.

``` title="$ slap info"
@shell cd .. && slap info
```

> [More details](commands/info.md)

## Install your project and its dependencies

  [Poetry]: https://python-poetry.org/
  [Flit]: https://flit.readthedocs.io/en/latest/

Using the `slap install` command, you can install your project using Pip. This is useful for example if you want
to use Pip even if your project uses [Poetry][] as a build system. Passing the `--link` option will make use of
[Flit's][Flit] symlinking installation method, independent of the project build system (so also good if you use
Poetry because it does not support editable installs).

You can also use the `--only-extras` option to pick only a set of extras to install from the `pyproject.toml`
and not install the project itself (this often comes in handy in CI checks).

    $ slap install --link

!!! note

    The command will check if you are in a virtual environment before continuing to instal your project(s). If you
    want to deliberately install into a global Python environment, pass the `--no-venv-check` flag.

> [More details](commands/install.md)

## Check your project configuration

The `slap check` command provides some feedback on the sanity of your project configuration.

``` title="$ slap check"
@shell cd .. && slap check
```

> [More details](commands/check.md)

## Test your project

The `slap test` command simply runs commands configured in your `pyproject.toml` configuration intended to test
your project. It is quite common to add `slap check` as one of the tests, as well as static type checking and
unit tests.

```toml title="Example pyproject.toml"
[tool.slap.test]
check = "slap check"
mypy = "mypy src/"
pytest = "pytest test/"
```

> [More details](commands/test.md)

## Manage version references and create releases

The `slap release` command updates version numbers in your code base and can create a Git commit and tag, and push
it to the `origin` remote. It can also be used to validate if all version references that can be found match. Without
further configuration, the command will find the version in your `pyproject.toml` as well as the version numbers of
dependencies to projects in the same monorepository (if applicable) and the `__version__` in your source code.

``` title="$ slap release --validate"
@shell cd .. && slap release --validate
```

To create a new release, pass the version number of a version bump rule instead.

``` title="$ slap release --tag --push patch --dry"
@shell cd .. && slap release --dry --tag --push patch --no-branch-check --no-worktree-check
```

> [More details](commands/release.md)
