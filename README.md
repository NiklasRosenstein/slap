# shore

[![Build Status](https://drone.niklasrosenstein.com/api/badges/NiklasRosenstein/shore/status.svg)](https://drone.niklasrosenstein.com/NiklasRosenstein/shore)

Shore is an opinionated distribution and release management tool for pure
Python packages and mono repositories and is most effectively used with Git
repositories.

__Goals of Shore__

* Automate as much as possible of the release and distribution of Python
  packages
* Prevent common mistakes from the beginning or provide tools to make it
  easier to catch them
* Provide tooling for to handle Python package mono repositories

## Getting Started

__Installation__

Shore can be installed from PyPI.

    $ pip install nr.shore
    $ shore --version

__Configuring a Python package__

Shore reads all configuration for your package from its `package.yaml` file.
The `shore new` command can help you to initialize such a file. Alternatively,
check out the [`src/shore/model.py`](src/shore/model.py) source code to find
the fields available for the `package.yaml` file.

    $ shore new mypackage . --license MIT

This command will also create a `LICENSE.txt` file as well as an initial
structure for your Python module if the files don't exist (ie.
`src/mypackage/__init__.py`). Note that if your module name differs from the
package name, you can specify the `--modulename <name>` option.

__Checking for misconfiguration__

Shore implements some automated checks to test the integrity of the data
in `package.yaml` with other files in the repository. Checks will be run on
`shore update` automatically, but for build automation they can also
be run separately. For CI checks, it's useful to turn on the
`--treat-warnings-as-errors` option which will cause the command to return a
non-zero status code if at least one warning is generated.

    $ shore checks --treat-warnings-as-errors

__Rendering setup files__

Shore generates setup file from the data defined in `package.yaml`. We
recommend that these generated files are commited to the version control
system of choice to ensure that users of your project do not need to depend
on shore to install your package.

    $ shore update

__Bumping the version number__

To bump the version number of your package at the same time, simply add the
`--version X.Y.Z` option add the specify `--patch`, `--minor` or `--major`
flags. Note that this will also update the version number in any files that
shore knows also contain the version number (eg. the entrypoin source file of
your package that contains the `__version__` variable).

    $ shore bump minor --tag

__Publishing your package__

After the setup files have been generated, you can use the package manager
to build and publish your package. Shore can do the same for you if you don't
want to leave your comfort zone however. ;-)

Currently shore only supports the `pypi` publishing target, which by default
publishes your package on `https://pypi.org` (or `https://test.pypi.org` if
you add the `--test` flag).

    $ shore publish pypi --test

> Note: If you explicityl specify the `use` section in `package.yaml`, you
> need to ensure that the `setuptools` and `pypi` plugin is in that list.

__Including package data__

There are two methods in which additional files can be shipped alongside a
Python package: "data files" and "package data". While files from the former
will be copied into a folder relative to `sys.prefix`, files from the latter
will be installed alongside the package and should be accessed with the
`pkg_resources` module.

Using "data files" usually requires some more effort to make it work with an
editable installation of your package during development (detecting that your
package is currently installed in editable mode and looking for the files in
a different location), thus using "package data" is usually the preferred
method. However if your additional files contain binaries that need to be
present on the file system, "data files" is the better bet.

"Data files" are configured with a special option called `datafiles` which
consists of alist of strings that define which files are to be copied to
what location inside `sys.prefix` as well as patterns for the files to copy.
The syntax is `<src>[:<dst>],<pattern>,<pattern>...`.

```yaml
datafiles:
  - src/datafiles,file.txt
  - src/datafiles:data,!file.txt
```

> Data files are always prefixed with `data/<packagename>`, thus to access the
> file at runtime you must add that to the path like this:
>
> ```py
> os.path.join(sys.prefix, 'data', 'mypackage', 'file.txt')
> ```

"Package files" on the other hand can be included by simply specifying them
in the `MANIFEST.in` file.

```yaml
manifest:
- include src/mypackage/data/file.txt
- recursive-include src/mypackage/data/models *.bin
```

> Tip: You can use the `shore build` command to produce a distribution archive
> of your package, which you can inspect to ensure the (package) data files
> are included as expected.

---

<p align="center">Copyright &copy; 2020, Niklas Rosenstein</p>
