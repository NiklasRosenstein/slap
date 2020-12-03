# shut

Shut is an opinionated tool that allows you to configure everything around the Python
packaging and release process from a single source of truth. It is intended to simplify
the process of publishing Python packages and prevent common pitfalls.

## At a glance

* Bootstrap Python packages: `shut pkg new --name my-package`
* Install and save dependencies: `shut pkg requirements add <package>`
* Document changes: ``shut changelog --add fix --commit --message "Fixed `TypeError` in `foo()`"``
* Bump the version according to changelog: `shut pkg bump --minor --tag --push`
* Publish on PyPI: `shut pkg publish warehouse:pypi`

## Configuration

**`package.yml`**

```yml
name: my-package
modulename: my_module
version: 0.1.0
license: MIT
description: My first every package built with Shut
author: Me <me@example.org>
requirements:
- python ^3.5
- requests ^2.22.0
entrypoints:
  console_scripts:
  - mycli = my_module.__main__:mycli
package-data:
  - include: data/*.txt
```

---

<p align="center">Copyright &copy; 2020, Niklas Rosenstein</p>
