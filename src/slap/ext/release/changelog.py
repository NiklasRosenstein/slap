
import typing as t
from pathlib import Path

from slap.ext.application.changelog import get_changelog_manager
from slap.plugins import ReleasePlugin
from slap.project import Project


class ChangelogReleasePlugin(ReleasePlugin):
  """ Renames the `_unreleased.toml` file when a release is created. """

  def create_release(self, project: Project, target_version: str, dry: bool) -> t.Sequence[Path]:
    manager = get_changelog_manager(project.repository, project)
    unreleased = manager.unreleased()
    new_version = manager.version(target_version)
    if unreleased.exists():
      cwd = Path.cwd()
      old = unreleased.path.relative_to(cwd)
      new = new_version.path.relative_to(cwd)
      self.io.write_line(f'releasing changelog')
      self.io.write_line(f'  <fg=cyan>{old}</fg> → <b>{new}</b>')
      if not dry:
        unreleased.release(target_version)
      return [unreleased.path, new_version.path]
    return []
