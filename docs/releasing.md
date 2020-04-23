# Releasing with Shore

Shore can automatically bump version numbers, tag push and publish a release in a single command.
The `<part>` can be an actual version number or one of `major`, `minor` and `patch`. See also
[Publishing with Shore](publishing.md).

    $ shore bump <part> --tag --push --publish pypi

For initial releases (eg. `0.0.1`), the bump must be forced if the version you want to tag is
already the version number that is defined in `package.yaml`.

    $ shore bump 0.0.1 --force --tag --push --publish pypi
