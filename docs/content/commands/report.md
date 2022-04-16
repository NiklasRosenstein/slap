# report

The `slap report` commands generate reports about your project.

## Subcommands

### `slap report dependencies`

> This command is venv aware.

Generates a JSON report on the dependencies of your project based on the packages
installed in your environment. Usually, the most interesting piece is the license
information of every dependency, which is contained in the JSON report. The license
name (and text if `--with-license-text` is specified) is read from the package
distribution metadata.

The command will only resolve only runtime dependencies by default. You can specify
additional extras to include in the resolution using the `--extras` option.

<details><summary>Synopsis <code>report dependencies</code></summary>
```
@shell slap report dependencies --help
```
</details>

<details><summary>Dependencies report for Slap</summary>
```json
@shell cd .. && slap report dependencies
```
</details>
