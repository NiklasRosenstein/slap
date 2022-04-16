# Getting started

@cat ../../readme.md :with { markdown_section = "Installation", rename_section_to = "1. Installation" }

## 2. Bootstrapping a new project

Slap has an `init` command that bootstraps project files for you. You can preview what the
generated files look like by checking out the [init command's documentation](commands/init.md).


> Using this command to start a project from scratch is entirely optional and you may use `poetry new` or
> `flit init` instead, or just write everything from scratch.

Currently, it provides only a template for projects using Poetry as the build-backend and the template is rather
opinionated (i.e. it tells Slap that the project uses typing and the default test commands use Mypy and Pytest).

    $ mkdir my_package; cd my_package
    $ slap init --name my_package
    write /home/niklas/git/my_package/pyproject.toml
    write /home/niklas/git/my_package/LICENSE
    write /home/niklas/git/my_package/readme.md
    write /home/niklas/git/my_package/.gitignore
    write /home/niklas/git/my_package/src/my_package/__init__.py
    write /home/niklas/git/my_package/test/test_import.py
    write /home/niklas/git/my_package/src/my_package/py.typed

!!! note

    You can include dots (`.`) in the `--name` argument value to bootstrap for a [PEP 420][] implicit namespace
    package, such as `$ slap init --name databind.core`.

  [PEP 420]: https://peps.python.org/pep-0420/

## 3. Creating a virtual environment

Slap's `venv` command is a small but convenient tool to create, activate and delete Python virtual environments
with the same-named standard library module.

> In order to use it's activate feature, you need to set up a shell function that shadow's the `slap` command. For
> details on how to do this, follow the instructions in the [venv command's documentation](commands/venv.md).

    $ slap venv -ac 3.10
    creating local environment "3.10" (using python3.10)
    activating local environment "3.10"
    (3.10) $

!!! note

    Combining the `-a,--activate` and `-c,--create` options will create and subsequently activate the environment.

    Without a `-p,--python` argument, the Python version is derived from the environment name as `"python" + name`.

## 4. Install your package into the environment

Whether you only just bootstrapped your project files or you cloned an existing Python project, before you can
use or test it locally, you need to install it into the virtual environment created in the previous step. The `install`
command will use Pip to install your package and all of its dependencies.

> You are not required to use Slap's `venv` command for this step, you can be in any kind of Python virtual environment.

!!! note

    Using the `--link` option will symlink your package into the Python environment instead of installing it with
    Pip, allowing you to make edits to your source code without needing to re-install it after every change. If all
    your dependencies are already installed, you can also use the [`slap link`](commands/link.md) command to only do
    the linking step (this is also convenient if only your project's entry points have changed).

```
(3.10) $ slap install --link
... pip install output here ...
symlinking my_package
```

If you are not currently in a virtual environment, Slap will refuse to install unless you pass the `--no-venv-check`
option. This is to protect you from accidentally installing into a global Python installation.

    (3.10) $ deactivate
    $ slap install
    error: refusing to install because you are not in a virtual environment
           enter a virtual environment or use --no-venv-check

!!! note

    The `slap install` command will by default install all run dependencies, as well as development dependencies
    and any extra dependencies. You can change this behaviour with any of the `--only-extras`, `--extras` and
    `--no-dev` options. You can also install only dependencies and not your actual project by passing the
    `--no-root` option.

    Check out the [install command's documentation](commands/install.md) for more information.

## 5. Inspect what Slap knows about your project

At times, the [`info`](commands/init.md) command comes in handy to get a better understanding how Slap sees your project.

<details><summary><code>slap info</code> for Slap's project</summary>

``` title="$ slap info"
@shell cd .. && slap info
```

</details>

## 6. Sanity check your project configuration

The [`slap check`](commands/check.md) command provides some feedback on the sanity of your project configuration. The
below example is the check output for Slap's own project.

``` title="$ slap check"
@shell cd .. && slap check
```

!!! note

    👋 Please feel free to create a [GitHub Issue][] if you any suggestions on new types of checks to add or to
    improve any of the existing checks. 

  [GitHub Issue]: https://github.com/NiklasRosenstein/slap/issues

## 7. Run tests

The [`test`](commands/test.md) command runs the commands configured in your `pyproject.toml` configuration under the
`[tool.slap.test]` section. It is common to include `slap check` as one of the tests, as well as static type checking
and unit tests.

If you bootstrapped your project with Slap, you will already have some test commands set up. Otherwise, consider adding
test commands like the below example to your project configuration.

```toml title="Example pyproject.toml"
[tool.slap.test]
check = "slap check"
mypy = "mypy src/"
pytest = "pytest test/"
```

<details><summary><code>slap test</code> for Slap's project</summary>

``` title="$ slap test"
@shell cd .. && slap test
```

</details>

## 8. Run commands

Inspired by `npm run` and `yarn run`, [`slap run`](commands/run.md) is likewise a simple tool to run aliased commands
in your project configuration. For example, Slap uses the following aliases that can be run with `slap run docs:dev`
and `slap run docs:build`, respectively.

```toml
[tool.slap.run]
"docs:build" = "cd docs && novella --base-url slap/"
"docs:dev" = "cd docs && novella --serve"
```

## 9. Add a changelog entry

Slap provides a format for storing changelogs in a structure way. You can add entries to the changelog using the
[`slap changelog add`](commands/changelog.md#slap-changelog-add) command. A changelog entry contains at a minimum
contains a type, description and one or more authors. An entry may also be associated with one or more issues and/or
a Pull Request (stored as URLs).

!!! note

    If your repository is hosted on GitHub, you can use issue and PR numbers and they will be automatically converted
    to full URLs. If you don't supply an `-a,--author` option, your Git email will be used. In case of a GitHub
    repository, that email address will be converted to a Git username instead.

<details><summary>Example</summary>

```
$ slap changelog add -t improvement -cd 'Add this cool new feature' --issue 52
id = "9fad16b6-9da7-49a1-9c4d-63dbf6c8eae9"
type = "improvement"
description = "Add this cool new feature"
author = "@NiklasRosenstein"
issues = [
    "https://github.com/NiklasRosenstein/slap/issues/52",
]

[develop 1a131e2] improvement: Add this cool new feature
 1 file changed, 8 insertions(+)
 create mode 100644 .changelog/_unreleased.toml
```

</details>

!!! tip

    The `slap changelog update-pr` command can be used to add the `pr` URL to all changelog entries added between two
    Git revisions. If used from a CI job, you can automate the addition of the `pr` field when a PR is opened instead
    of manually having to add the URL after the PR was created.

    If your repository is hosted on GitHub, all you need to do is set up the 
    [`NiklasRosenstein/slap@gha/changelog/update/v1`](guides/github.md#update-changelogs) action.


## 10. Create a release

Slap's [`release`](commands/release.md) command updates version numbers in you code base and can also commit the
changes, tag them and push them to the Git remote. It can also be used to validate that all version references in
your project are the same.

!!! note "Supported version locations"

    Slap supports a few places where the version number of your project is hardcoded by default. You can always let Slap
    know about any other places by configuring additional version references (see the
    [release's commands Configuration documentation](commands/release.md#configuration)).

    * The `version` in your `pyproject.toml` (for Flit or Poetry) or `setup.cfg` (for Setuptools)
    * The `__version__` in your Python source code
    * Dependencies on other packages in the same mono-repository (aka. inter-dependencies)

    The `release` command will also automatically update the currently staged changelog entries in
    `.changelog/_unreleased.toml` by inserting the current date as the release date and renaming the
    file to `.changelog/{version}.toml`.

<details><summary>Example</summary>

To create a new release, pass the version number or a rule name instead.

``` title="$ slap release --tag --push patch"
@shell cd .. && slap release --dry --tag --push patch --no-branch-check --no-worktree-check 2>/dev/null
```

</details>

!!! tip

    You can also use the `--validate` flag to validate and show all known version number references:

    ``` title="$ slap release --validate"
@shell cd .. && slap release --validate :with prefix = "    " @
    ```

## 11. Publish to PyPI

The [`publish`](commands/publish.md) command builds distributions using your configured build backend and publishes
them to a Python package index using [Twine][]. For mono repositories, the command will build all projects before
publishing them.

  [Twine]: https://readthedocs.org/projects/twine/

``` title="$ slap publish"
Build slap-cli
  slap-cli-1.4.0.tar.gz
  slap_cli-1.4.0-py3-none-any.whl
Publishing
```

!!! note

    It is recommended that you perform this step only after you created a new release and all your CI checks have
    passed. Even better, you can configure your CI to publish the package for your once all checks have passed. You
    can pass the credentials to the `-u,--username` and `-p,--password` options just as with the [Twine][] CLI.
