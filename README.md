# Shut

Shut is an opinionated tool that allows you to configure everything around the Python
packaging and release process with a single YAML configuration file.

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

---

<p align="center">Copyright &copy; 2020, Niklas Rosenstein</p>
