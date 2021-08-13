# Welcome to Shut

Shut is an opinionated tool to simplify publishing pure Python packages. 

__What can Shut do for you?__

* Generate setup files (`setup.py`, `MANIFEST.in`, `LICENSE.txt`)
* Sanity check your package configuration
* Build and publish source/wheel distributions
* Execute unit tests and static type checks
* and more

## Installation

Shut requires Python 3.7+ and can be installed from PyPI:

    $ pip install shut

## Quickstart

Initialize a new Python package:

    $ shut pkg new --name my.package .
    write .gitignore
    write README.md
    write package.yml
    write src/my/package/__init__.py
    write src/my/__init__.py

Generate setuptools files:

    $ shut pkg update
    write setup.py
    write MANIFEST.in

Create a changelog entry and commit:

    $ shut changelog --add feature --for cli -cm 'Added some useful options.'

Sanity-check the package configuration:

```
shut pkg checks

  ✔️   classifiers
  ⚠️   license: not specified
  ✔️   namespace files
  ✔️   package-author
  ⚠️   package-url: missing
  ✔️   package-version
  ✔️   readme
  ✔️   up to date

ran 8 checks for package my.package in 0.003s
```

Commit the current status:

```
$ git add . && git commit -m 'bootstrapped package'
```

Release a new version:

```
$ shut pkg bump --tag --push

figuring bump mode from changelog
  1 feature → minor

bumping 3 version reference(s)
  package.yml: 0.0.0 → 0.1.0
  setup.py: 0.0.0 → 0.1.0
  src/my/package/__init__.py: 0.0.0 → 0.1.0

release staged changelog
  .changelog/_unreleased.yml → .changelog/0.1.0.yml

updating files
  write setup.py
  write MANIFEST.in

tagging 0.1.0
[master ec1e9b3] (my.package) bump version to 0.1.0
 4 files changed, 4 insertions(+), 4 deletions(-)
 rename .changelog/{_unreleased.yml => 0.1.0.yml} (78%)
Enumerating objects: 24, done.
Counting objects: 100% (24/24), done.
Delta compression using up to 8 threads
Compressing objects: 100% (17/17), done.
Writing objects: 100% (24/24), 3.87 KiB | 566.00 KiB/s, done.
Total 24 (delta 4), reused 0 (delta 0)
To https://github.com/me/my-package
 * [new branch]      master -> master
 * [new tag]         0.1.0 -> 0.1.0
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
