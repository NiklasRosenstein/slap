# `slap link`

  [Flit]: https://flit.readthedocs.io/en/latest/
  [Poetry]: https://python-poetry.org/

> This command is venv aware.

Symlink your project or all projects in a mono-repository into the current Python environment. This works for [Poetry][]
projects as well.

!!! warning

    Independent from the Python build system you are using, Slap reuses [Flit][]'s symlinking feature to perform
    this action. This actually symbolically links your source code into the Python site-packages. Be aware that this
    _can_ cause your code to be overwritten for example by Pip if you end up overwriting the symlinked installation
    of your package by installing another version of it into the same environment.

<details><summary>Synopsis</summary>
```
@shell slap link --help
```
</details>
