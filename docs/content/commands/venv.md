# Venv

The `slap venv` command is a utility for managing virtual environments created using the standard library `venv`
module in the current directory or globally (in `~/.local/venvs`).

## Usage

First, the `slap` command needs to be shadowed by a function in your shell to make proper use of the `-a,--activate`
option. The `-i,--init-code` option can provide you with a snippet to place in your shell init scripts. Currently,
it only supports Bash.

=== "$ slap venv -i bash"

    ```
@shell slap venv -i bash :with prefix = "    " @
    ```

=== "$ SLAP_SHADOW=true slap venv -i bash"

    ```
@shell SLAP_SHADOW=true slap venv -i bash :with prefix = "    " @
    ```

## Synopsis

### venv

```
@shell cd .. && slap venv -h
```

### venv link

```
@shell cd .. && slap venv link -h
```
