# Link

This is particularly interesting when managing the package with [Poetry][] as it does not currently support editable
installs (as of Poetry 1.2.0a2 on 2022-01-14). This is a little helper command that will temporarily reorganize the
`pyproject.toml` to be compatible with [Flit] and make use if it's symlink installation feature (`flit install -s`).

    $ slam link
    Extras to install for deps 'all': {'.none'}
    Symlinking src/my_package -> /home/niklas/.local/venvs/craftr/lib/python3.10/site-packages/my_package

  [PEP 621]: https://www.python.org/dev/peps/pep-0621
  [Flit]: https://flit.readthedocs.io/en/latest/
  [Poetry]: https://python-poetry.org/
