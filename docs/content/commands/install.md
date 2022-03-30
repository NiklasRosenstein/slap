# `slap install`

Install the current project or all projects in a mono-repository into the current Python environment, including
development dependencies and extras. After cloning a new repository, this is often the first command you run
after creating a virtual environment (for that, see [`slap venv`](venv.md)).

Common options to add are `--link` if you want to develop on the project(s) and `--no-venv-check` if you want
don't want Slap to protect you from accidentally installing the project(s) into a non-virtual Python environment.

<details><summary>Synopsis</summary>
```
@shell slap install --help
```
</details>
