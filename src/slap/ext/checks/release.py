import typing as t

from cleo.io.null_io import NullIO  # type: ignore[import]

from slap.application import Application
from slap.check import Check, CheckResult, check, get_checks
from slap.ext.application.release import ReleaseCommandPlugin
from slap.ext.release.source_code_version import SourceCodeVersionReferencesPlugin
from slap.plugins import CheckPlugin
from slap.project import Project


class ReleaseChecksPlugin(CheckPlugin):
    """Performs some checks relevant for the `slap release` command."""

    def get_project_checks(self, project: Project) -> t.Iterable[Check]:
        return get_checks(self, project)

    def get_application_checks(self, app: Application) -> t.Iterable[Check]:
        return get_checks(self, app)

    @check("source-code-version")
    def check_packages_have_source_code_version(self, project: Project) -> tuple[CheckResult, str]:
        """Checks if all Python packages in the project have a version defined in the source code."""

        if not project.packages():
            return Check.WARNING, "No packages detected"

        matcher = SourceCodeVersionReferencesPlugin()
        matcher.io = NullIO()
        version_refs = matcher.get_version_refs(project)
        packages_without_version = {p.name for p in project.packages() or []}

        for ref in version_refs:
            for package in project.packages() or []:
                if ref.file.is_relative_to(package.path):
                    packages_without_version.discard(package.name)

        return (
            Check.ERROR if packages_without_version else Check.OK,
            (
                (f'The following packages have no <b>__version__</b>: <b>{", ".join(packages_without_version)}</b>')
                if packages_without_version
                else f'Found <b>__version__</b> in <b>{", ".join(x.name for x in project.packages() or [])}</b>'
            ),
        )

    @check("consistent-versions")
    def check_version_number_consistency(self, app: Application) -> tuple[CheckResult, str]:
        """Checks if the version numbers in the project source code, project configuration and any other instances
        that are detected by release plugins or in the `[tool.slap.release].references` option are consistent."""

        releaser = ReleaseCommandPlugin(app)
        releaser.load_configuration(app)

        version_refs = releaser._get_version_refs()
        cardinality = len(set(r.value for r in version_refs))

        if cardinality == 0:
            result = Check.WARNING
            message = "No version references found"
        elif cardinality == 1:
            result = Check.OK
            message = "All version references are equal"
        else:
            result = Check.ERROR
            message = f"Found <b>{cardinality}</b> differing version references"

        return result, message
