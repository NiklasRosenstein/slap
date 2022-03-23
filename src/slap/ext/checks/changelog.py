
import dataclasses
import typing as t

from slap.check import Check
from slap.ext.application.changelog import get_changelog_manager
from slap.plugins import CheckPlugin
from slap.project import Project


@dataclasses.dataclass
class ChangelogValidationCheckPlugin(CheckPlugin):

  def get_project_checks(self, project: Project) -> t.Iterable[Check]:
    self.manager = get_changelog_manager(project.repository, project)
    yield self._check_changelogs()

  def _check_changelogs(self) -> Check:
    from databind.core.converter import ConversionError

    bad_changelogs = []
    count = 0
    for changelog in self.manager.all():
      count += 1
      try:
        for entry in changelog.load().entries:
          self.manager.validate_entry(entry)
      except (ConversionError, ValueError) as exc:
        bad_changelogs.append((changelog.path.name, str(exc), entry.id))

    check_name = 'validate'
    if not count:
      return Check(check_name, Check.Result.SKIPPED, None)

    return Check(
      check_name,
      Check.ERROR if bad_changelogs else Check.Result.OK,
      f'Broken or invalid changelogs' if bad_changelogs else
        f'All {count} changelogs are valid.',
      '\n'.join(f'<i>{fn}</i>: id=<fg=yellow>"{entry_id}"</fg>: {err}' for fn, err, entry_id in bad_changelogs) if bad_changelogs else None,
    )
