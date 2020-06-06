# Welcome to the Shore documentation

Shore is an opinionated release management tool for pure Python packages and mono repositories
of such. Among it's features is the automatic generation of setuptools files, sanity checks,
version number bumping and release publishing as well as changelog management.

## Installation

Shore can be installed from PyPI:

    $ pip install nr.shore

## Typical Usage

Initialize a new Python package:

    $ shore new my.package .
    Write .gitignore
    Write package.yaml
    Write README.md
    Write src/my/__init__.py
    Write src/my/package/__init__.py
    Write src/test/my/__init__.py
    Write src/test/my/package/__init__.py
    Write src/test/my/package/test_some.py

Generate setuptools files:

    $ shore update
    ❌ 2 check(s) triggered
    WARNING (my.package): missing $.url
    WARNING (my.package): No LICENSE file found.
    ⚪ rendering 1 file(s)
    setup.py

Release the initial version:

    $ shore bump 0.0.1 --force --tag --push --publish pypi
    bumping 2 version reference(s)
      package.yaml: 0.0.1 → 0.0.1
      src/my/package/__init__.py: 0.0.1 → 0.0.1
    tagging 0.0.1
    [master f0dd374] (my.package) bump version to 0.0.1
    ...

Create a changelog entry:

    $ shore changelog --add feature --for cli -m 'Added some useful options.'

Release the next version:

    $ shore bump --minor --tag --push --publish pypi

Shore also makes it easy to publish from within CI jobs. For more information on this,
check out the [Publishing Guide][0].

  [0]: publishing-guide.md
