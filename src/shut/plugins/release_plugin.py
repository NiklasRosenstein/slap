
import abc
import dataclasses
import typing as t
from pathlib import Path

if t.TYPE_CHECKING:
  from cleo.io.io import IO

ENTRYPOINT = 'shut.plugins.release'


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
  " Interface for Shut plugins that want to hook into the release process. "

  def get_version_refs(self, io: 'IO') -> list[VersionRef]:
    return []

  def bump_to_version(self, target_version: str, dry: bool, io: 'IO') -> list[str]:
    return []
