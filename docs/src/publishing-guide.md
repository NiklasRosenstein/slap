# Publishing with Shut

> __Todo__: Describe publishing in more detail.

By default, every package is configured to publish to PyPI using the `warehouse:pypi` publishing
target. A test publish to `test.pypi.org` can be performed by using the `--test` option when using
the `shut pkg publish` command.

## Automate publishing in CI checls

You can specify the username and password in the config as environment variables. Most CI systems
allow you to securely store a secret as an environment variable.

```yml
name: my-package
# ...
publish:
  pypi:
    credentials:
      username: __token__
      password: '$PYPI_TOKEN'
      test_username: __token__
      test_password: '$PYPI_TEST_TOKEN'
```

When you're ready to publish from the CI checks, make it run the following commands:

```yml
- pip install shut
- shut pkg update --verify-tag "$CI_TAG"
- shut pkg publish warehouse:pypi
```

It is also recommended that you add a trial-publish step. Note that we add the `--allow-empty-tag`
to flag to allow that the value passed to `--verify-tag` can be empty. This is important because
most commits won't be tagged during development.

```yml
- pip install shut
- shut pkg update --verify-tag "$CI_TAG" --allow-empty-tag
- shut pkg publish warehouse:pypi --test
```

### Publishing Snapshots

The `bump` command can be used with the `--snapshot` option to update the version to one that
indicates the Git commit distance since the last tagged version. This is useful to publish
development snapshots. __Note__ that PyPI/Warehouse does not actually (yet?) support snapshot version
numbers. If you want to publish snapshots, you need an alternative package registry such as Artifactory).

```yaml
- shut pkg update --verify-tag "$CI_TAG" --allow-empty-tag
- shut pkg bump --snapshot
- shut pkg publish warehouse:pypi --test
```

__Important__: Many CI systems may not fetch tags when cloning your repository. This means `bump --snapshot`
can not figure out the commit distance and the generated snapshot version number will begin with `0.0.0`. If
you encounter this issue, run `git fetch --tags` before Shut.
