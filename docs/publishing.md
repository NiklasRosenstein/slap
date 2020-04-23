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

### Automate publishing in CI checls

You can specify the username and password in the config as environment variables. Most CI systems
allow you to securely store a secret as an environment variable.

```yml
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

When you're ready to publish from the CI checks, make it run the following commands:

```yml
- pip install nr.shore
- shore --version
- shore verify -et "$CI_TAG"
- shore publish pypi
```

It is also recommended that you add a trial-publish step. Note that we do not pass `-e` to
`shore verify` as most commits during development won't be tagged (so we do not _expect_ a tag
to be present).

```yml
- pip install nr.shore
- shore --version
- shore verify -t "$CI_TAG"
- shore bump
- shore publish pypi --test
```

> __Work in progress__: The `shore bump git` command allows you to bump to a version number
> that describes the commit distance since the last tagged version, but the version number
> format is not PEP440 compliant.
