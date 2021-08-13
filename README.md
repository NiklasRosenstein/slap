# shut

Shut is an opinionated tool that allows you to configure everything around the Python
packaging and release process from a single source of truth. It is intended to simplify
publishing Python packages and prevent common pitfalls.

## Installation

Shut requires Python 3.7+ and can be installed from PyPI:

    $ pip install shut

## Quickstart

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

(Todo: run `shut pkg checks`)

Release a new version:

```
$ shut pkg bump --minor --tag --push --dry
bumping 3 version reference(s)
package.yaml: 0.0.0 → 0.1.0
setup.py: 0.0.0 → 0.1.0
src/my/package/__init__.py: 0.0.0 → 0.1.0

updating files
write setup.py
write MANIFEST.in

tagging 0.2.0
```

Publish the release to PyPI:

```
$ shut pkg publish warehouse:pypi

building setuptools:sdist
  :: build/my.package-0.1.0.tar.gz

building setuptools:wheel
  :: build/my.package-0.1.0-py3-none-any.whl

publishing warehouse:pypi
  :: build/my.package-0.1.0.tar.gz
  :: build/my.package-0.1.0-py3-none-any.whl
```

Shut also makes it easy to publish from within CI jobs. For more information on this,
check out the [Publishing Guide][0].

  [0]: publishing-guide.md

---

<p align="center">Copyright &copy; 2021 Niklas Rosenstein</p>
