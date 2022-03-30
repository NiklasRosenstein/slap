# `slap venv`

The `slap venv` command is a utility for managing virtual environments created using the standard library `venv`
module in the current directory or globally (in `~/.local/venvs`).
s across multiple projects in a monorepository and prints a summary of the results at the end.

<details><summary>Synopsis <code>venv</code></summary>
```
@shell slap venv --help
```
</details>

<details><summary>Synopsis <code>venv link</code></summary>
```
@shell slap venv link --help
```
</details>

## Configuration

The `venv` command does not have any Slap configuration options. However, in order to use the `slap venv --activate`
option properly, you need to configure your shell to shadow the `slap` command with a function such that it can
source the activate script.

To do this, run `$ slap venv -i <shell>` and add the output to your shell init scripts. Currently, the `-i` option
only supports `bash` as an argument.

```sh title="$ slap venv -i bash"
@shell slap venv -i bash
```

What will be evaluated in your init script then implements the shadow function:

```sh title="$ SLAP_SHADOW=true slap venv -i bash"
@shell SLAP_SHADOW=true slap venv -i bash
```

Now you can enjoy using `slap venv -a [-g] [<env>]` to activate a virtual environment.

## Activate behaviour

Using `-a,--activate` without arguments will pick the most recently activated environment in the current context,
or if that is not available, the one and only virtual environment. If multiple environments exist in that case,
it is an error.
