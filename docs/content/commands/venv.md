# Venv

The `clap venv` command is a utility for managing virtual environments created using the standard library `venv`
module in the current directory or globally (in `~/.local/venvs`).

## Usage

First, the `clap` command needs to be shadowed by a function in your shell to make proper use of the `-a,--activate`
option. The `-i,--init-code` option can provide you with a snippet to place in your shell init scripts. Currently,
it only supports Bash.

=== "$ clap venv -i bash"

    ```
@shell clap venv -i bash :with prefix = "    " @
    ```

=== "$ SLAM_SHADOW=true clap venv -i bash"

    ```
@shell SLAM_SHADOW=true clap venv -i bash :with prefix = "    " @
    ```

## Synopsis

### venv

```
@shell cd .. && clap venv -h
```

### venv link

```
@shell cd .. && clap venv link -h
```
