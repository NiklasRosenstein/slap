# shut

Shut is a CLI that provides utilities for developing on Python projects. It works well with
[Poetry][] projects in particular, but you're not required to use it.

<!-- Available Commands -->
```
Available commands:
  check          Run sanity checks on your Python project.
  help           Displays help for a command.
  link           Symlink your Python package with the help of Flit.
  release        Create a new release of your Python package.
  test           Execute commands configured in [tool.shut.test].

 log
  log add        Add an entry to the unreleased changelog via the CLI.
  log convert    Convert Shut's old YAML based changelogs to new style TOML changelogs.
  log format     Format the changelog in the terminal or in Markdown format.
  log pr update  Update the pr field of changelog entries in a commit range.
```
<!-- /Available Commands -->

### Installation

It is recommended to install Shut via Pipx, but you can also install it with Pip directly.

    $ pipx install shut

---

<p align="center">Copyright &copy; 2022 Niklas Rosenstein</p>
