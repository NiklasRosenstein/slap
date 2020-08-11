# shut

Shut is an opinionated tool that allows you to configure everything around the Python
packaging and release process from a single source of truth. It is intended to simplify
the process of publishing Python packages and prevent common pitfalls.



## Getting started

Use `shore pkg new --project-name my-package` to bootstrap a Python package directory.
Alternatively you can use the example configuration below.

**`package.yml`**

```yml
package:
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
```

Shut handles all the rest: `setup.py`, `MANIFEST.in`, `py.typed`, package data files, changelog
management, version number bumping, linter configuration, building and publishing to PyPI, etc.

__Todo__

* [ ] Automatic check for license headers in files / automatically insert license headers
* [ ] Conda recipe generator and conda-forge helper
* [ ] Package data / data files

---

<p align="center">Copyright &copy; 2020, Niklas Rosenstein</p>
