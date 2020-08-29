# Welcome to the Shut documentation

Shut is an opinionated release management tool for pure Python packages and mono repositories.
Among it's features is the automatic generation of setuptools files, sanity checks, version number
bumping and release publishing as well as changelog management.

## Installation

Shut can be installed from PyPI:

    $ pip install shut

## Typical Usage

Initialize a new Python package:

    $ shut pkg new --name my.package .
    write .gitignore
    write package.yml
    write README.md
    write src/my/__init__.py
    write src/my/package/__init__.py

Generate setuptools files:

    $ shut pkg update
    write setup.py
    write MANIFEST.in

Create a changelog entry and commit:

    $ shut changelog --add feature --for cli -cm 'Added some useful options.'

Release a new version:

    $ shut pkg bump --minor --tag --push --dry

    ✔️ classifiers
    ✔️ consistent-author
    ✔️ consistent-version
    ✔️ license
    ✔️ readme
    ✔️ unknown-config
    ✔️ url

    ran 7 checks for package my.package in 0.001s

    bumping 3 version reference(s)
    package.yaml: 0.0.0 → 0.1.0
    setup.py: 0.0.0 → 0.1.0
    src/my/package/__init__.py: 0.0.0 → 0.1.0

    updating files
    write setup.py
    write MANIFEST.in

    tagging 0.2.0

    $ shut pkg publish warehouse:pypi

    # ... todo

Shut also makes it easy to publish from within CI jobs. For more information on this,
check out the [Publishing Guide][0].

  [0]: publishing-guide.md
