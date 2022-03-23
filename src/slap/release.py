
from __future__ import annotations
import dataclasses
import re
import typing as t
from pathlib import Path

from nr.util.generic import T
from nr.util.singleton import NotSet


@t.overload
def match_version_ref_pattern(filename: Path, pattern: str) -> VersionRef: ...


@t.overload
def match_version_ref_pattern(filename: Path, pattern: str, fallback: T) -> T | VersionRef: ...


def match_version_ref_pattern(filename: Path, pattern: str, fallback: NotSet | T = NotSet.Value) -> T | VersionRef:
  """ Matches a regular expression in the given file and returns the location of the match. The *pattern*
  should contain at least one capturing group. The first capturing group is considered the one that contains
  the version number exactly.

  Arguments:
    filename: The file of which the contents will be checked against the pattern.
    pattern: The regular expression that contains at least one capturing group.
  """

  compiled_pattern = re.compile(pattern, re.M | re.S)
  if not compiled_pattern.groups:
    raise ValueError(
      f'pattern must contain at least one capturing group (filename: {filename!r}, pattern: {pattern!r})'
    )

  with open(filename) as fp:
    match = compiled_pattern.search(fp.read())
    if match:
      return VersionRef(filename, match.start(1), match.end(1), match.group(1), match.group(0))

  if fallback is not NotSet.Value:
    return fallback
  raise ValueError(f'pattern {pattern!r} does not match in file {filename!r}')


def match_version_ref_pattern_on_lines(filename: Path, pattern: str) -> list[VersionRef]:
  """ Like #match_version_ref_pattern(), but returns all matches, but matches it on a line-by-line basis. The
  *pattern* must have a `version` group. The pattern is compiled with #re.M and #re.S flags. """

  compiled_pattern = re.compile(pattern, re.M | re.S)
  refs = []
  for match in re.finditer(compiled_pattern, filename.read_text()):
    refs.append(VersionRef(
      file=filename,
      start=match.start('version'),
      end=match.end('version'),
      value=match.group('version'),
      content=match.group(0),
    ))
  return refs


@dataclasses.dataclass
class VersionRef:
  """ Represents a reference to a version number in a file. """

  file: Path
  start: int
  end: int
  value: str
  content: str

  def __post_init__(self) -> None:
    assert isinstance(self.file, Path), self
