# Slam

Slam is a CLI that provides utilities for developing on Python projects. It works well with
[Poetry][] projects in particular, but you're not required to use it.

<!-- Available Commands -->
```
Available commands:
  check          Run sanity checks on your Python project.
  help           Displays help for a command.
  link           Symlink your Python package with the help of Flit.
  release        Create a new release of your Python package.
  test           Execute commands configured in [tool.slam.test].

 log
  log add        Add an entry to the unreleased changelog via the CLI.
  log convert    Convert Shut's old YAML based changelogs to Slam's TOML changelogs.
  log format     Format the changelog in the terminal or in Markdown format.
  log pr update  Update the pr field of changelog entries in a commit range.
```
<!-- /Available Commands -->

### Installation

It is recommended to install Slam via Pipx, but you can also install it with Pip directly.

    $ pipx install slam-cli

> __Note__: Currently, Slam relies on an alpha version of `poetry-core` (`^1.1.0a6`). If you install it into
> the same environment as Poetry itself, you may also need to use an alpha version of Poetry (e.g. `1.2.0a2`).

---

<p align="center">Copyright &copy; 2022 Niklas Rosenstein</p>
