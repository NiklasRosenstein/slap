# Configuration

Shut uses YAML configuration files to configure Python packages and monorepositories. When invoking the `shut` CLI,
the configuration file for the entity you want to work with must be in your current working directory (ie.
`package.yml` when using `shut pkg` and `monorepo.yml` when using `shut mono`). Configuration files may use the `.yaml`
suffix instead of `.yml`.

## `package.yml`

### Package Metadata

__Example__

```yml
name: my-package
version: 0.1.0
description: This is my package.
license: MIT
author: Me <me@me.org>
url: https://github.com/me/my-package
readme: README.md  # default
license_file: LICENSE.txt  # default
classifiers: []  # default
keywords: []  # default
```

  [spdx]: https://spdx.org/licenses/
  [classifiers]: https://pypi.org/classifiers/

__Fields__

* `name` &ndash; The name of the package. This name is also passed to the `setuptools.set(name)` parameter
  in the generated `setup.py` file.
* `version` &ndash; The version of the package. This field may be unset if the package is part of a single-version
  monorepository. A semantic version should be used here (e.g. `0.0.1`, `1.4.2.post1` or `52.0.1.rc4`).
    
    __Checks__

    * Shut checks if the version given here matches the `__version__` in your package's main source file (e.g. either the `__init__.py`
      of your package or your module file in case of a single-module package).

* `author` &ndash; The author of the package, either as a string in the form `First Last <mail@email.org>` or in the
  form of a mapping as in `{name: "First Last", email: "mail@email.org"}`.

    __Checks__

    * Similar to the check for `version`, Shut will check that the author given here matches the `__author__` given in
      your package's main source file.

* `license` &ndash; An [SPDX Open Source license identifier][spdx] for the license of the package.

    __Checks__
    
    * Shut delivers license templates for some known license identifiers (e.g. `MIT`, `BSD2`, `BSD3`, `Apache2`) and will
      use it to generate a `LICENSE.txt` file for you. If the content of the current `LICENSE.txt` file does not match
      with the template or if the file does not exist, a check will indicate this.

* `description` &ndash; A short description for the package which is included in the package metadata when publishing.

* `readme` &ndash; The path to the readme file relative to the `package.yml` configuration file. If the path points to
  a parent directory, Shut will generate code in `setup.py` to temporarily copy the readme into the package directory
  during distribution to ensure the readme is included in the archive(s). Defaults to the first file of the following
  list that exists in the same directory: `README.md`, `README.rst`, `README.txt`,` README`. (See
  `PackageModel.get_readme_file()`)

    __Checks__

    * A check will trigger if the readme file does not exist.

* `license_file` &ndash; The path to the license file relative to the `package.yml` configuration file. Similar to
  the `readme` option, if the `license_file` points to a file not in the same project directory, Shut will generate
  code to temporarily copy the file into the package directory during distribution building. Defaults to the first
  file of the following list that exists in the same directory: `LICENSE`, `LICENSE.txt`, `LICENSE.rst`, `LICENSE.md`.
  If the package is part of a monorepository and the monorepository has a license file, it will default to that license
  file instead. (See `PackageModel.get_license_file()`)

    __Checks__

    * A check will trigger if the license file does not exist.

* `classifiers` &ndash; A list of classifiers for the package. Defaults to an empty list.

    __Checks__

    * A check will trigger if any of the listed classifiers are not known as per the the PyPI
      classifiers [reference][classifiers].

* `keywords` &ndash; A list of keywords for the package. Defaults to an empty list.

### Code Runtime

__Example__

```yml
modulename: my_package
source-directory: src  # default
typed: True
requirements:
- python ^2.7|^3.5
- requests ^2.22.0
test-requirements:
- pandas
extra-requirements:
  pdf:
  - pyPdf ~1.13
dev-requirements:
- pylint
render-requirements-txt: False  # default
```

__Fields__

Todo

### Packaging

__Example__

```yml
exclude: ['test', 'tests', 'docs']  # default
entrypoints:
  console_scripts:
  - my-cli = my_package.__main__:main
package-data:
  - include: data/ssl.pem
  - exclude: data/generated
install:
  hooks:
    before-install:
    - echo "Before install!"
    after-install:
    - echo "After install!"
  index-url: https://pypi.org/simple
  extra-index-urls:
  - https://test.pypi.org/simple
publish:
  pypi:
    enabled: true  # default
    credentials:
      username: __token__
      password: '$PYPI_PASSWORD'
```

__Fields__

Todo

### Testing

__Example__

```yml
test-drivers:
  - type: pytest
    parallelism: 8
  - type: mypy
```

__Fields__

Todo

### Releasing

__Example__

```yml
changelog:
  directory: '.changelog'  # default
release:
  tag-format: '{version}'  # default
```

__Fields__

* `changelog.directory` &ndash; The directory where `shut changelog` reads and writes changelog files to.
* `release.tag-format` &ndash; The template string used to construct the tag name for `shut pkg bump --tag`. If the
  package is part of a monorepository, `{name}@` is automatically prefixed to the value of this field (and `{name}`
  expands to the package name).

## `monorepo.yml`

Monorepositories are configured with a `monorepo.yml` file. Packages in the repository must be
in folder directly next to the configuration file. Many commands from `shut pkg` are also available
for `shut mono` and will apply over all packages in the monorepository.

Many of the fields in the monorepository configuration will remind you of those from `package.yml`. In
fact some of these fields (indicated with \*) are inherited by packages in a monorepository if they are
not set in the package itself.

__Example__

```yaml
name: my-monorepo
version: 0.1.0
author:
  name: First Last
  email: mail@email.org
license: MIT
license_file: LICENSE.txt  # default
url: https://github.com/me/my-monorepo
changelog:
  directory: '.changelog'
release:
  tag-format: '{version}'  # default
  single-version: true
publish: ...  # same as package.yml
```

__Fields__

* `name` &ndash; The name of the monorepository. This is not actually used in a lot of places.
* `version` &ndash; The version of the monorepository. Should only be set for monorepository where
  `release.single-version` is enabled.
* `author` \* &ndash; The author of the monorepository.
* `license` \* &ndash; The license of the monorepository.
* `license_file` \* &ndash; The license file of the monorepository.
* `url` \* &ndash; The URL where the monorepository source code can be found.
* `changelog.directory` &ndash; The directory where `shut changelog` reads and writes changelog files to.
* `release.tag-format` &ndash; The template string used to construct the tag name for `shut pkg bump --tag`. The
  tag format is only used if `release.single-version` is enabled.
* `release.single-version` &ndash; If enabled, enforce a consistent version number across all packages in the
  monorepository. `shut mono bump` can be used to uniformly bump the version across all packages. The `--tag` option
  will create a tag for the entire monorepository (instead of for each package individually).
* `publish` \* &ndash; The publish configuration for packages in the monorepository.
