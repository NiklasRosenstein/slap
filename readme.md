# Slap

<img src="docs/content/img/logo.svg" style="height: 200px !important">

  [PEP 517]: https://peps.python.org/pep-0517/

Slap is a command-line tool to simplify common workflows in the development of Python projects
independent of the [PEP 517][] build backend being used, capable of managing single- and multi-project
repositories.

## Installation

I recommend installing Slap using Pipx. (Requires Python 3.10 or higher)

    $ pipx install slap-cli

> __Note__: Currently Slap relies on an alpha version of `poetry-core` (`^1.1.0a6`). If you install it into
> the same environment as Poetry itself, you may also need to use an alpha version of Poetry (e.g. `1.2.0a2`).
>
> If you use Slap in GitHub Actions, try one of the actions provided by Slap directly:
>
> * [`NiklasRosenstein/slap@gha/install/v1`](https://python-slap.github.io/slap-cli/guides/github/#install-slap)
> * [`NiklasRosenstein/slap@gha/changelog/update/v1`](https://python-slap.github.io/slap-cli/guides/github/#update-changelogs)

## Documentation

You can find the documentation for Slap here: <https://niklasrosenstein.github.io/slap/>

Check out the [Getting started](https://python-slap.github.io/slap-cli/getting-started/) guide.

## Feature Matrix

| Feature | Poetry | Documentation |
| ------- | ------ | ------------- |
| Manage structured changelog entries | ❌ | [slap changelog](https://python-slap.github.io/slap-cli/commands/changelog/) |
| Show project details | ❌ | [slap info](https://python-slap.github.io/slap-cli/commands/info/) |
| Build and publish to PyPI using Twine | ✅ (single project only) | [slap publish](https://python-slap.github.io/slap-cli/commands/publish/) |
| Create a new release (bump version numbersr)| ❌ (sub-par support) | [slap release](https://python-slap.github.io/slap-cli/commands/release/) |
| Run a command configured in `pyproject.toml` | ❌ | [slap run](https://python-slap.github.io/slap-cli/commands/run/) |
| Run tests configured in `pyproject.toml` | ❌ | [slap test](https://python-slap.github.io/slap-cli/commands/test/) |
| Manage Python virtualenv's | ✅ (but out-of-worktree) | [slap venv](https://python-slap.github.io/slap-cli/commands/venv/) |
| Generate a dependencies report | ❌ | [slap report dependencies](https://python-slap.github.io/slap-cli/commands/report/) |
| Project dependencies lock file | ✅ | ❌ |

| Feature / Build backend | Flit  | Poetry  | Setuptools  | Documentation |
| ----------------------- | ----- | ------- | ----------- | --------- |
| Add dependency | ✅ | ✅ | ❌ | [slap add](https://python-slap.github.io/slap-cli/commands/add/) |
| Sanity check project configuration | | ✅ | | [slap check](https://python-slap.github.io/slap-cli/commands/check/) |
| Bootstrap project files | | ✅ | | [slap init](https://python-slap.github.io/slap-cli/commands/init/) |
| Install projects using Pip | ✅ | ✅ | ✅ | [slap install](https://python-slap.github.io/slap-cli/commands/install/) |
| Symlink projects (editable installs) | ✅ | ✅ | ✅ | [slap link](https://python-slap.github.io/slap-cli/commands/link/) |
| Bump interdependencies in mono-repository | ✅ (not tested regularly) | ✅ | ✅ (partial) | [slap release](https://python-slap.github.io/slap-cli/commands/release/) |

> __Legend__: ✅ explicitly supported, ❌ explicitly not supported, (blank) not relevant or currently not supported

## Issues / Suggestions / Contributions

  [GitHub Issues]: https://github.com/NiklasRosenstein/slap/issues
  [GitHub Discussions]: https://github.com/NiklasRosenstein/slap/discussions
  [GitHub Repository]: https://github.com/NiklasRosenstein/slap

Slap is currently very opinionated by the fact that I built it as my personal workflow tool, but I welcome
suggestions and contributions, and I am hopeful it will be useful to a wider audience than myself.

Please report any issues you encounter via [GitHub Issues][]. Feel free to use the [GitHub Discussions][] forum
to ask questions or make suggestions on new features (e.g. if you would like a new build backend to be supported?).
Lastly, feel free to submit pull requests to the [GitHub Repository][].

## FAQ

### Why "Slap"?

Finding a good, catchy name that also types easily in the terminal and is not already widely used isn't easy, ok?

### What makes this different to the Poetry CLI?

Some people might find this similar to tools like Poetry, and while there is some overlap in functionality, Slap is
**not a build backend** and is more targeted towards library development. In fact, most of my projects use Poetry as
the build backend but I never even once interact with the Poetry CLI throughout the lifetime of the project.

The most notable differences to Poetry are

* Supports mono-repositories (i.e. multiple related Python projects in the same repository), to the extent that it
  bumps version numbers of project inter-dependencies and installs your projects in topological order
* Supports development installs independent of the build backend (yes; this means you can install Poetry packages
  in editable mode even though the Poetry backend right now does not support editable installs)
* Slap's version bump command (`slap release`) updates the version not just in your `pyproject.toml` but also the
  `__version__` in your source code as well as in related projects (see mono-repositories above) and any additional
  references you can configure via Regex patterns
* Does not automagically create a virtual environment for you when instal your project(s); instead, it errors when
  you try to install into a non-virtual Python environment and gives you an easy-to-use tool to create and activate
  virtual environments (and allowing multiple environments per project as well as global environments)
* Uses Pip to install your project(s), unlike Poetry which comes with its own dependency resolver and package
  installer (which I personally have been having a lot of issues with in the past).
* Does not have a concept of lock files
