# Venv

The `slam venv` command is a utility for managing virtual environments created using the standard library `venv`
module in the current directory or globally (in `~/.local/venvs`).

## Usage

First, the `slam` command needs to be shadowed by a function in your shell to make proper use of the `-a,--activate`
option. The `-i,--init-code` option can provide you with a snippet to place in your shell init scripts. Currently,
it only supports Bash.

=== "$ slam venv -i bash"

    ```
@shell slam venv -i bash :with prefix = "    " @
    ```

=== "$ SLAM_SHADOW=true slam venv -i bash"

    ```
@shell SLAM_SHADOW=true slam venv -i bash :with prefix = "    " @
    ```

## Synopsis

### venv

```
@shell cd .. && slam venv -h
```

### venv link

```
@shell cd .. && slam venv link -h
```
