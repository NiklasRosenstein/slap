import typing as t
from pathlib import Path

import requests
from nr.stream import Optional

from slap.check import Check, CheckResult, check, get_checks
from slap.ext.project_handlers.poetry import PoetryProjectHandler
from slap.plugins import CheckPlugin
from slap.project import Project
from slap.util.external.pypi_classifiers import get_classifiers
from slap.util.fs import get_file_in_directory


def get_readme_path(project: Project) -> Path | None:
    """Tries to detect the project readme. If `tool.poetry.readme` is set, that file will be returned."""

    # TODO (@NiklasRosenstein): Support other config styles that specify a readme.

    poetry: dict = project.pyproject_toml.value_or({})
    poetry = poetry.get("tool", {}).get("poetry", {})

    if (readme := poetry.get("readme")) and Path(readme).is_file():
        return Path(readme)

    return get_file_in_directory(Path.cwd(), "README", ["README.md", "README.rst", "README.txt"], case_sensitive=False)


class PoetryChecksPlugin(CheckPlugin):
    """Check plugin to validate the Poetry configuration and compare it with Slap's expectations.

    Plugin ID: `poetry`"""

    def get_project_checks(self, project: Project) -> t.Iterable[Check]:
        self.project = project
        pyproject: dict[str, t.Any] = project.pyproject_toml.value_or({})
        if isinstance(project.handler(), PoetryProjectHandler):
            self.poetry = pyproject.get("tool", {}).get("poetry")
            if self.poetry is None:
                yield Check(
                    "config", CheckResult.ERROR, "No [tool.poetry] configuration in <code>pyproject.toml</code>"
                )
                return
            yield from get_checks(self, project)

    @check("readme")
    def get_readme_check(self, project: Project) -> tuple[CheckResult, str]:
        """Checks if Poetry will be able to pick up the right readme file."""

        default_readmes = ["README.md", "README.rst"]
        detected_readme = (
            Optional(get_readme_path(self.project))
            .map(lambda p: str(p.resolve().relative_to(Path.cwd())))
            .or_else(None)
        )
        poetry_readme = self.poetry.get("readme")
        if poetry_readme is None and detected_readme in default_readmes:
            return Check.Result.OK, f"Poetry will autodetect your readme (<b>{detected_readme}</b>)"
        if poetry_readme == detected_readme:
            return Check.Result.OK, f"Poetry readme is configured correctly (path: <b>{detected_readme}</b>)"
        return (
            Check.Result.WARNING,
            f"Poetry readme appears to be misconfigured (detected: <b>{detected_readme}</b>, "
            f"configured: <b>{poetry_readme}</b>)",
        )

    @check("urls")
    def get_urls_check(self, project: Project) -> tuple[CheckResult, str]:
        """Checks if URLs are configured in the Poetry configuration and recommends to configure the `Homepage`,
        `Repository`, `Documentation` and `Bug Tracker` URLs under `[tool.poetry.urls]`."""

        has_homepage = "homepage" in self.poetry or "homepage" in {
            x.lower() for x in self.poetry.get("urls", {}).keys()
        }
        has_repository = "repository" in {x.lower() for x in self.poetry.get("urls", {}).keys()}
        has_documentation = "documentation" in {x.lower() for x in self.poetry.get("urls", {}).keys()}
        has_bug_tracker = "bug tracker" in {x.lower() for x in self.poetry.get("urls", {}).keys()}

        if has_homepage and has_repository and has_documentation and has_bug_tracker:
            return Check.OK, "Your project URLs are in top condition."
        else:
            missing = [
                k
                for k, v in {
                    "Homepage": has_homepage,
                    "Repository": has_repository,
                    "Documentation": has_documentation,
                    "Bug Tracker": has_bug_tracker,
                }.items()
                if not v
            ]
            result = Check.RECOMMENDATION if has_homepage else Check.WARNING
            message = "Please configure the following URLs: " + ", ".join(f'<s>"{k}"</s>' for k in missing)
            return result, message

    @check("classifiers")
    def get_classifiers_check(self, project: Project) -> tuple[CheckResult, str]:
        """Checks if all Python package classifiers are valid and recommends to configure them if none are set."""

        # TODO: Check for recommended classifier topics (Development State, Environment,
        #       Programming Language, Topic, Typing, etc.)
        classifiers = self.poetry.get("classifiers")  # TODO: Support classifiers in [project]
        if not classifiers:
            return Check.RECOMMENDATION, "Please configure classifiers."
        else:
            try:
                good_classifiers = get_classifiers()
            except requests.RequestException as exc:
                return Check.WARNING, f"Could not validate classifiers because list could not be fetched ({exc})"
            else:
                bad_classifiers = set(classifiers) - set(good_classifiers)
                if bad_classifiers:
                    return Check.ERROR, "Found bad classifiers: " + ",".join(f'<s>"{c}"</s>' for c in bad_classifiers)
                else:
                    return Check.OK, "All classifiers are valid."

    @check("license")
    def get_license_check(self, project: Project) -> tuple[CheckResult, str]:
        """Checks if package license is a valid SPDX license identifier and recommends to configure a license if
        none is set."""

        from slap.util.external.licenses import get_spdx_licenses

        license = self.poetry.get("license")
        if not license:
            return Check.ERROR, "Missing license"
        else:
            if license not in get_spdx_licenses():
                return Check.WARNING, f'License <s>"{license}"</s> is not a known SPDX license identifier.'
            else:
                return Check.OK, f'License <s>"{license}"</s> is a valid SPDX identifier.'
