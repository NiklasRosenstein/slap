
import typing as t
from pathlib import Path

from slam.application import IO
from slam.changelog.manager import ChangelogManager
from slam.commands.release.api import ReleasePlugin


class RenameChangelogOnReleasePlugin(ReleasePlugin):
  """ Renames the `_unreleased.toml` file when a release is created. """

  def __init__(self, manager: ChangelogManager) -> None:
    self.manager = manager

  def bump_to_version(self, target_version: str, dry: bool, io: 'IO') -> t.Sequence[Path]:
    unreleased = self.manager.unreleased()
    new_version = self.manager.version(target_version)
    if unreleased.exists():
      io.write_line(f'releasing changelog')
      io.write_line(f'  <fg=cyan>{unreleased.path}</fg> → <b>{new_version.path}</b>')
      if not dry:
        unreleased.release(target_version)
    return [unreleased.path, new_version.path]
