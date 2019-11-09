# Piz

Piz is a tool for describing metadata for pure Python packages and automating
everything around the distribution and release process.

## How does it work?

Piz reads a YAML configuration file for your package and automatically
generates Python setup files, package metadata files and Conda recipes for
you. Files generated with Piz may be committed to a repository, but they
don't have to be.

Piz is designed to take away some of the heavy lifting required for package
release and distribution management and integrates well with CI tools.

## Project structure

Piz makes a strong assumption about the structure of your project. A project
may consist of multiple packages. If a multi-package project is called a
"monorepo". If there is only one package in a project, the mono-repo level
may be ommitted.

```
project/
    monorepo.yaml
    package-a/
        package.yaml
        src/
            package_a/
                __init__.py
    package-b/
        package.yaml
        src/
            package_b/
                __ini__.py
    my-module/
        package.yaml
        src/
            my_module.py
```

## Monorepo configuration

The `monorepo.yaml` describes how the packages in the project belong together.
Some projects may choose to version packages independently and distributed
them as such, but also provide a bundled release. There may be different
variants of bundled releases with different content, etc. All of this is
optional though.

```yaml
project-name: mega-bundle
package-versioning: independent
bundle-version: 1.3.5
bundles:
  - include: '*'
  - variant: client-safe
    include: [package-a, my-module]
publish:
  - layout: pypi
  - layout: conda
    channel-url: https://my.artifactory.com/artifactory/conda-main
    channel-auth: "${ARTIFACTORY_USERNAME}:${ARTIFACTORY_PASSWORD}"
```

## Package configuration

The `package.yaml` describes metadata about a single Python package, basically
everything that would go into a `setup.py` file, and a bit more than that.
Most parameters are used to automatically generate a `setup.py` files, while
others are used to build a `MANIFEST.in`.

Piz will automatically extract the version number and author name and email
from the package's main entrypoint file if it is not already defined in the
package configuration file.

Piz is also able to translate some version range specifiers to a format that
Pip and setuptools will understand.

```yaml
package:
  name: package-a
  license: MIT
  description: MY package A.
  requirements:
    - python ^2.7|^3.4
    - requests
  requirements-win32:
    - windows-curses
  data-files:
    - data/**

publish:
  - layout: pypi
  - layout: conda
```

## Distribution and release management CLI

The Piz CLI allows you to easily render setup files and Conda recipes. Beyond
that, it can fully automate the building of binary and source distributions as
well as the publishing of said distributions to public or internal PyPI and
Conda channels.

It also provides steps for validating the integrity of the package metadata
across the package before executing the publication process.

### `piz release`

Creates a new release by updating the version number(s) of the
monorepo/package(s). If the project is tracked in a Git repository, tags are
automatically created. (The tag format can be defined in the `$.git.tag-format`
field)

The `--publish` option may be specified to perform `piz verify` and
`piz publish` directly after the command has finished.

### `piz verify`

Verifies the integrity of committed files that are automatically generated
by Piz. If version and author information is defined in the `package.yaml`,
it will ensure that the main package file defines the same values. 

It is recommended to run this command before `piz publish` to prevent a
package with inconsistent information from being published.

Note that Piz does not currently detect the license in `LICENSE.txt` and as
such does not error if the license does not match (although it will error if
there is no license file at all).

If the current project is tracked in a Git repository, the command will also
check that there exists a Git-tag for the current revision that matches the
version number of the monorepo/package(s). Additionally, it will ensure that
there are no uncommitted changes to track files in the repository (unless
disabled with `--git-dont-check-uncommitted-changes`.

### `piz render`

Render all files that Piz can generate from the monorepo and package
configuration. Note that this will files that already exist. If in a package
the `$.render.namespace-files` option is not set, package namespace files
will be automatically generated only if they don't already exist, but will not
be overwritten (`piz verify` will show a warning if the files look off).

The command will only render Conda recipes if either `$.render.conda-recipe`
is set to `true` or there is at least one `conda` item in the `$.publish`
section.

### `piz build`

Builds the monorepo/package(s) and puts the resulting files into the `dist/`
directory. A build target can be explicily specified to build only that target.
The output filenames are derived deterministically from the monorepo/package
configuration.

### `piz publish`

Publishes the monorepo/package(s) to the configured publishing targets. A
target can be explicitly specified to publish to that target only. The packages
to publish must be  This step
includes the build step of the packages that are to be published (which can
also be produced with `piz build`).
