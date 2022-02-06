
import abc
import dataclasses
import re
import typing as t
from pathlib import Path

if t.TYPE_CHECKING:
  from shut.application import IO


def match_version_ref_pattern(filename: Path, pattern: str) -> 'VersionRef':
  """ Matches a regular expression in the given file and returns the location of the match. The *pattern*
  should contain at least one capturing group. The first capturing group is considered the one that contains
  the version number exactly.

  :param filename: The file of which the contents will be checked against the pattern.
  :param pattern: The regular expression that contains at least one capturing group.
  """

  compiled_pattern = re.compile(pattern, re.M | re.S)
  if not compiled_pattern.groups:
    raise ValueError(
      f'pattern must contain at least one capturing group (filename: {filename!r}, pattern: {pattern!r})'
    )

  with open(filename) as fp:
    match = compiled_pattern.search(fp.read())
    if match:
      return VersionRef(filename, match.start(1), match.end(1), match.group(1))

  raise ValueError(f'pattern {pattern!r} does not match in file {filename!r}')


@dataclasses.dataclass
class VersionRef:
  " Represents a reference to a version number in a file. "

  file: Path
  start: int
  end: int
  value: str

  def __post_init__(self) -> None:
    assert isinstance(self.file, Path), self


class ReleasePlugin(abc.ABC):
  """ Interface for Shut plugins that want to hook into the release process. Should be registered to a Shut
  application object from an application plugin under the {@link ReleasePlugin} group. """

  def get_version_refs(self, io: 'IO') -> list[VersionRef]:
    return []

  def bump_to_version(self, target_version: str, dry: bool, io: 'IO') -> t.Sequence[Path]:
    return []
