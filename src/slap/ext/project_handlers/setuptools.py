""" Project handler for projects using the Setuptools build system. """

from __future__ import annotations

import re
import typing as t

from slap.ext.project_handlers.base import BaseProjectHandler, interdependencies_enabled
from slap.project import Dependencies, Package, Project
from slap.release import VersionRef, match_version_ref_pattern, match_version_ref_pattern_on_lines

if t.TYPE_CHECKING:
    from slap.python.dependency import VersionSpec


class SetuptoolsProjectHandler(BaseProjectHandler):
    def __init__(self) -> None:
        self._project: Project | None = None
        self._setup_cfg: t.Dict[str, t.Dict[str, t.Any]] | None = None

    def _get_setup_cfg(self, project: Project) -> t.Dict[str, t.Any]:
        import configparser

        if self._project is None:
            parser = configparser.ConfigParser()
            parser.read(project.directory / "setup.cfg")
            self._setup_cfg = {s: dict(parser.items(s)) for s in parser.sections()}
            self._project = project
        else:
            assert self._project is project
            assert self._setup_cfg is not None
        return self._setup_cfg

    # ProjectHandlerPlugin

    def matches_project(self, project: Project) -> bool:
        if not project.pyproject_toml.exists():
            return False
        build_backend = project.pyproject_toml.get("build-system", {}).get("build-backend")
        return build_backend == "setuptools.build_meta"

    def get_dist_name(self, project: Project) -> str | None:
        return self._get_setup_cfg(project).get("metadata", {}).get("name")

    def get_readme(self, project: Project) -> str | None:
        cfg = self._get_setup_cfg(project)
        long_description = cfg.get("metadata", {}).get("long_description", "").strip()
        if long_description.startswith("file:"):
            return (
                long_description.partition("file:")[2].partition(",")[0].strip()
            )  # Apparently can be a comma separated list of multiple files
        return None

    def get_packages(self, project: Project) -> list[Package] | None:
        # TODO (@NiklasRosenstein): Handle namespace_packages as well
        options = self._get_setup_cfg(project).get("options", {})
        packages: str | None = options.get("packages")
        if packages is None or packages.strip() == "find:":
            # Auto detect packages
            # TODO (@NiklasRosenstein): Limit to the package_dir in setup.cfg?
            return super().get_packages(project)
        elif packages.strip() == "":
            return None  # Intentionally no packages
        package_dir = project.directory / options.get("package_dir", ".")
        return [Package(p, package_dir / p, package_dir) for p in parse_list_semi(packages)]

    def get_dependencies(self, project: Project) -> Dependencies:
        from slap.python.dependency import PypiDependency, VersionSpec

        options = self._get_setup_cfg(project).get("options", {})
        return Dependencies(
            VersionSpec(options["python_requires"]) if "python_requires" in options else None,
            PypiDependency.parse_list(parse_list_semi(options.get("install_requires", ""))),
            PypiDependency.parse_list(
                parse_list_semi(options.get("setup_requires", "")) + parse_list_semi(options.get("tests_require", ""))
            ),
            {
                extra: PypiDependency.parse_list(parse_list_semi(value))
                for extra, value in options.get("extras_require", {}).items()
            },
            PypiDependency.parse_list(parse_list_semi(options.get("setup_requires", ""))),
        )

    def get_version_refs(self, project: Project) -> list[VersionRef]:
        """Returns the version reference in `setup.cfg`."""

        VERSION_PATTERN = r"^version\s*=\s*(.*?)$"
        version_ref = match_version_ref_pattern(project.directory / "setup.cfg", VERSION_PATTERN, None)
        refs = [version_ref] if version_ref else []
        if interdependencies_enabled(project):
            refs += get_setup_cfg_interdependency_version_refs(project)
        return refs

    def get_add_dependency_toml_location_and_config(
        self,
        project: Project,
        package: str,
        version_spec: VersionSpec,
        where: str,
    ) -> tuple[list[str], list | dict]:
        raise NotImplementedError


def parse_list_semi(val: str) -> list[str]:
    """Parses a string to a list of strinsg according to the `list-semi` specification in the [setuptools docs][1].

    [1]: https://setuptools.pypa.io/en/latest/userguide/declarative_config.html#specifying-values"""

    from nr.stream import Stream

    return Stream(val.splitlines()).map(lambda v: v.split(";")).concat().map(str.strip).filter(bool).collect()


def get_setup_cfg_interdependency_version_refs(project: Project) -> list[VersionRef]:
    setup_cfg = project.directory / "setup.cfg"
    other_projects: list[str] = [
        t.cast(str, p.dist_name())
        for p in project.repository.projects()
        if p.is_python_project and p is not project and p.dist_name()
    ]

    refs = []
    for project_name in other_projects:
        # Look for occurrences of the project name in the context of requirements.
        expressions = [
            # Match requirements split over multiple lines.
            r"^\w+_requires?\s*=.*^\s+(?:" + re.escape(project_name) + r"\s*(?:==|>=|<=|>|<)\s*(?P<version>[^\n;]+))",
            # TODO (@NiklasRosenstein): Also match if the requirements is on the same line
            # TODO (@NiklasRosenstein): Also match extra requires
        ]
        for expr in expressions:
            refs += match_version_ref_pattern_on_lines(setup_cfg, expr)
    return refs
