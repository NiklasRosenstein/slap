
import typing as t
from pathlib import Path

from slam.ext.application.changelog import get_changelog_manager
from slam.plugins import ReleasePlugin
from slam.project import Project


class ChangelogReleasePlugin(ReleasePlugin):
  """ Renames the `_unreleased.toml` file when a release is created. """

  def create_release(self, project: Project, target_version: str, dry: bool) -> t.Sequence[Path]:
    manager = get_changelog_manager(project)
    unreleased = manager.unreleased()
    new_version = manager.version(target_version)
    if unreleased.exists():
      self.io.write_line(f'releasing changelog')
      self.io.write_line(f'  <fg=cyan>{unreleased.path}</fg> → <b>{new_version.path}</b>')
      if not dry:
        unreleased.release(target_version)
      return [unreleased.path, new_version.path]
    return []
