
import typing as t

from poetry.core.semver.version import Version  # type: ignore[import]

from slap.plugins import VersionIncrementingRulePlugin


def incrementing_rule(func: t.Callable[[Version], Version]) -> type[VersionIncrementingRulePlugin]:
  class _Incrementor(VersionIncrementingRulePlugin):
    def increment_version(self, version: Version) -> Version:
      return func(version)

  _Incrementor.__name__ = func.__name__
  return _Incrementor


@incrementing_rule
def major(version: Version) -> Version:
  return version.next_major()


@incrementing_rule
def premajor(version: Version) -> Version:
  return version.next_major().first_prerelease()


@incrementing_rule
def minor(version: Version) -> Version:
  return version.next_minor()


@incrementing_rule
def preminor(version: Version) -> Version:
  return version.next_minor().first_prerelease()


@incrementing_rule
def patch(version: Version) -> Version:
  return version.next_patch()


@incrementing_rule
def prepatch(version: Version) -> Version:
  return version.next_patch().first_prerelease()


@incrementing_rule
def prerelease(version: Version) -> Version:
  if version.is_unstable():
    assert version.pre
    return Version(version.epoch, version.release, version.pre.next())
  else:
    return version.next_patch().first_prerelease()
