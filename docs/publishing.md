# Publishing with Shore

By default, every Shore package has the `setuptools` and `pypi` plugins. (This is defined in
`shore.models.Package.get_plugins()`). The `setuptools` plugin is responsible for building
source distributions. The `pypi` plugin consumes these distributions and publishes them on
a package index using [Twine][] (PyPI and test.pypi.org by default).

  [Twine]: https://github.com/pypa/twine

To publish packages, use the `shore publish pypi` command. Optionally add the `--test` option
which will publish to the test PyPI instance instead.

    $ shore publish pypi --test
    $ shore publish pypi

When adding the `pypi` plugin manually, the defaults do not apply unless you specify
`defaults: true`. If the package is marked as `private`, the default `pypi` plugin configuration
will not be added to the package.

Example configuration for publishing from CI checks:

```
name: my-package
# ...
use:
- type: pypi
  defaults: true
  username: __token__
  password: '$PYPI_TOKEN'
  test_username: __token__
  test_password: '$PYPI_TEST_TOKEN'
```

Then from CI checks you can do

```
- pipx install shore-release-tool
- shore --version
- shore publish pypi --test
- shore publish pypi
```
