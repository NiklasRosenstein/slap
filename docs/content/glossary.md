# Glossary

## Project

At it's core, any directory can be a "project", but most projects would have a `pyproject.toml` or `shut.toml`
configuration file. Most commonly, it will have a `pyproject.toml` file that contains the Clap configuration
under the `[tool.clap]` namespace. Many concepts in Clap are attached directly to a project. For example if
the project has a `pyproject.toml`, it is considered a Python project, and Python projects can have packages
that can be installed, built or published to PyPI or another repository.

A project with a `clap.toml` configuration file (or with no configuration file) is usually used as the parent
project for two or more sub-projects. This configuration represents a mono-repository where multiple projects
are stored and versioned together.

Clap understands most details about a project through a {@pylink clap.plugins.ProjectHandlerPlugin}. It comes
with a default implementation that supports Poetry and Flit Python projects.

## Repository

A repository is a directory that contains one or more projects. For singular projects, the repository directory
is the same as the project directory. For a mono-repository configuration, any directory that contains multiple
projects is considered the repository directory (it usually contains a `shut.toml` configuration file).

Note that the repository directory is _also_ considered a project directory, but if it isn't also a Python
project (i.e. if it has a `pyproject.toml` instead of a `clap.toml`) it will be ignored for most Clap commands.

=== "Single project"

    ```
    my_pacakge/                           -> Repository / Project "my_package"
      pyproject.toml
      readme.md
      src/
      tests/
    ```

=== "Mono repository"

    ```
    /                                     -> Repository / Project "$"
      my_first_package/                   -> Project "my_first_package"
        pyproject.toml
        readme.md
        src/
        tests/
      my_second_package/                  -> Project "my_second_package"
        pyproject.toml
        readme.md
        src/
        tests/
      shut.toml
    ```

Clap understands most details about a repository through a {@pylink clap.plugins.RepositoryHandlerPlugin}. It
comes with a default implementation that supports Git repositories and GitHub.
