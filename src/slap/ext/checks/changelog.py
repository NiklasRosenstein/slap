import dataclasses
import typing as t

from slap.check import Check, CheckResult, check, get_checks
from slap.ext.application.changelog import get_changelog_manager
from slap.plugins import CheckPlugin
from slap.project import Project


@dataclasses.dataclass
class ChangelogValidationCheckPlugin(CheckPlugin):
    """This check plugin validates the structured changelog files, if any.

    Plugin ID: `changelog`"""

    def get_project_checks(self, project: Project) -> t.Iterable[Check]:
        return get_checks(self, project)

    @check("validate")
    def _validate_changelogs(self, project: Project) -> tuple[CheckResult, str | None, str | None]:
        import tomli
        from databind.core.converter import ConversionError

        manager = get_changelog_manager(project.repository, project)
        bad_files = []
        bad_changelogs = []
        count = 0
        for changelog in manager.all():
            count += 1
            try:
                for entry in changelog.load().entries:
                    try:
                        manager.validate_entry(entry)
                    except (ConversionError, ValueError) as exc:
                        bad_changelogs.append((changelog.path.name, str(exc), entry.id))
            except (tomli.TOMLDecodeError, ConversionError) as exc:
                bad_files.append((changelog.path.name, str(exc)))

        if not count:
            return CheckResult.SKIPPED, None, None

        return (
            Check.ERROR if bad_changelogs else Check.Result.OK,
            "Broken or invalid changelogs" if bad_changelogs else f"All {count} changelogs are valid.",
            (
                "\n".join(f"<i>{fn}</i>: {err}" for fn, err in bad_files)
                if bad_files
                else (
                    ""
                    + "\n"
                    + "\n".join(
                        f'<i>{fn}</i>: id=<fg=yellow>"{entry_id}"</fg>: {err}' for fn, err, entry_id in bad_changelogs
                    )
                    if bad_changelogs
                    else ""
                )
            ).strip()
            or None,
        )
