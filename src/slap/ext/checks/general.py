import typing as t

from slap.check import Check, CheckResult, check, get_checks
from slap.plugins import CheckPlugin
from slap.project import Project


class GeneralChecksPlugin(CheckPlugin):
    """This plugin provides general checks applicable to all types of projects managed with Slap.

    Plugin ID: `general`."""

    # TODO (@NiklasRosenstein): Check if VCS remote is configured?

    def get_project_checks(self, project: Project) -> t.Iterable[Check]:
        return get_checks(self, project)

    @check("packages")
    def _check_detect_packages(self, project: Project) -> tuple[CheckResult, str | None]:
        """Checks if the project handler employed by Slap for your project is detecting any Python packages. If no
        Python packages can be detected, it might hint at a configuration issue."""

        packages = project.packages()
        result = Check.Result.SKIPPED if packages is None else Check.Result.OK if packages else Check.Result.ERROR
        message = "Detected " + ", ".join(f"<b>{p.root}/{p.name}</b>" for p in packages) if packages else None
        return result, message

    @check("typed")
    def _check_py_typed(self, project: Project) -> tuple[CheckResult, str]:
        expect_typed = project.config().typed
        if expect_typed is None:
            return Check.Result.WARNING, "<b>tool.slap.typed</b> is not set"

        has_py_typed = set[str]()
        has_no_py_typed = set[str]()
        for package in project.packages() or []:
            (has_py_typed if (package.path / "py.typed").is_file() else has_no_py_typed).add(package.name)

        if expect_typed and has_no_py_typed:
            error = True
            message = f'<b>py.typed</b> missing in package(s) <b>{", ".join(has_no_py_typed)}</b>'
        elif not expect_typed and has_py_typed:
            error = True
            message = f'<b>py.typed</b> in package(s) should not exist <b>{", ".join(has_py_typed)}</b>'
        else:
            error = False
            message = (
                "<b>py.typed</b> exists as expected" if expect_typed else "<b>py.typed</b> does not exist as expected"
            )

        return (Check.Result.ERROR if error else Check.Result.OK, message)
