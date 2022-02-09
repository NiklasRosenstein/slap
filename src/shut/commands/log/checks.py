
import dataclasses
import typing as t

from shut.application import Application
from shut.changelog.changelog_manager import ChangelogManager
from shut.commands.check.api import Check, CheckPlugin


@dataclasses.dataclass
class ChangelogConsistencyCheck(CheckPlugin):

  manager: ChangelogManager

  def get_checks(self, app: Application) -> t.Iterable[Check]:
    yield self._check_changelogs()

  def _check_changelogs(self) -> Check:
    from databind.core import ConversionError

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
