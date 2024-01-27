""" Implements the default package detection plugin. """

from __future__ import annotations

import abc
import re
import typing as t
from pathlib import Path

from setuptools import find_namespace_packages, find_packages

from slap.plugins import ProjectHandlerPlugin
from slap.project import Package, Project
from slap.release import VersionRef, match_version_ref_pattern, match_version_ref_pattern_on_lines
from slap.util.fs import get_file_in_directory
from slap.util.text import longest_common_substring

if t.TYPE_CHECKING:
    from slap.python.dependency import Dependency

IGNORED_MODULES = ["test", "tests", "docs", "build"]


def detect_packages(directory: Path) -> list[Package]:
    """Detects the Python packages in *directory*, making an effort to identify namespace packages correctly."""

    if not directory.is_dir():
        return []

    assert isinstance(directory, Path)
    modules = list(set(find_namespace_packages(str(directory)) + find_packages(str(directory))))

    # Also support toplevel modules.
    for path in directory.iterdir():
        if path.is_file() and path.suffix == ".py" and path.stem not in modules:
            modules.append(path.stem)

    # Remove modules that seem to be other Python projects.
    modules = [m for m in modules if not (directory / m.partition(".")[0] / "pyproject.toml").is_file()]

    if not modules:
        return []

    paths = {}
    for module in modules:
        tlm_file = directory / (module + ".py")
        pkg_file = directory / Path(*module.split("."), "__init__.py")
        use_file = tlm_file if tlm_file.is_file() else pkg_file.parent if pkg_file.is_file() else None
        if use_file is not None:
            paths[module] = use_file

    modules = [m for m in modules if m in paths]

    modules = [
        m for m in modules if m not in IGNORED_MODULES and ("." not in m or m.split(".")[0] not in IGNORED_MODULES)
    ]

    if len(modules) > 1:
        # If we stil have multiple modules, we try to find the longest common path.
        common = longest_common_substring(*(x.split(".") for x in modules), start_only=True)
        if not common:
            return []
        modules = [".".join(common)]

    return [Package(module, paths[module], directory) for module in modules]


class BaseProjectHandler(ProjectHandlerPlugin):
    """Base class for other project handlers. It cannot be used directly by a project."""

    package_dirs: t.Sequence[str] = ("src", ".")

    def __repr__(self) -> str:
        return type(self).__name__

    def get_readme(self, project: Project) -> str | None:
        path = get_file_in_directory(project.directory, "README", ["README.rst"])
        return path.name if path else None

    def get_packages(self, project: Project) -> list[Package] | None:
        """Detects packages in #package_dirs."""

        source_dir = project.config().source_directory
        if source_dir:
            return detect_packages(project.directory / source_dir)
        else:
            for source_dir in self.package_dirs:
                packages = detect_packages(project.directory / source_dir)
                if packages:
                    return packages
        return []


class PyprojectHandler(BaseProjectHandler):
    """A subclass that implements some functionality based on whether the project is configured using a
    `pyproject.toml` file."""

    def get_version_refs(self, project: Project) -> list[VersionRef]:
        """Returns the version ref in `pyproject.toml` it can be found, as well as the version references of project
        interdependencies (you can disable the interdependencies bit by setting `tool.slap.release.interdependencies`
        setting to `False` on the Slap root directory, usually in a `slap.toml` file)."""

        PYPROJECT_TOML_PATTERN = r'^version\s*=\s*[\'"]?(.*?)[\'"]'
        version_ref = match_version_ref_pattern(project.pyproject_toml.path, PYPROJECT_TOML_PATTERN, None)
        refs = [version_ref] if version_ref else []
        if interdependencies_enabled(project):
            refs += get_pyproject_interdependency_version_refs(project)
        return refs

    def add_dependency(self, project: Project, dependency: Dependency, where: str) -> None:
        """Adds a dependency to the respective location in the `pyproject.toml` file."""

        import tomlkit
        import tomlkit.container
        import tomlkit.items

        root = tomlkit.parse(project.pyproject_toml.path.read_text())
        keys, value = self.get_add_dependency_toml_location_and_config(project, dependency, where)
        assert isinstance(value, list | dict), type(value)

        current: tomlkit.items.Item | tomlkit.container.Container = root
        for idx, key in enumerate(keys):
            # NOTE (@NiklasRosenstein): I have no clue why this is needed, but if we don't access the internal
            #   container of this "OutOfOrderTableProxy", it appears the mutation later on doesn't actually work.
            if isinstance(current, tomlkit.container.OutOfOrderTableProxy):  # type: ignore[unreachable]
                current = current._internal_container

            if not isinstance(current, tomlkit.items.Table | tomlkit.container.Container):
                break  # Will triger an error below

            if key not in current:
                if idx == len(keys) - 1:
                    current[key] = tomlkit.array() if isinstance(value, list) else tomlkit.table()
                else:
                    current[key] = tomlkit.table()

            current = current[key]

        if isinstance(value, list):
            if not isinstance(current, tomlkit.items.Array):
                raise RuntimeError(f"expected array at {keys!r}, got {type(current).__name__}")
            for v in value:
                current.append(v)
        elif isinstance(value, dict):
            if not isinstance(current, tomlkit.items.Table | tomlkit.container.Container):
                raise RuntimeError(f"expected table at {keys!r}, got {type(current).__name__}")
            current.update(value)
        else:
            assert False, type(value)

        project.pyproject_toml.path.write_text(tomlkit.dumps(root))

    @abc.abstractmethod
    def get_add_dependency_toml_location_and_config(
        self,
        project: Project,
        dependency: Dependency,
        where: str,
    ) -> tuple[list[str], list | dict]:
        """Return the location and configuration to inject/update the TOML project configuration with in order
        to add the given *dependency* to the project.

        Returns:
          1. The sequence of keys that contains the dependencies based on the *where* argument.
          2. The element to inject extend/merge into the key at the location specified by the first tuple element.
        """


def interdependencies_enabled(project: Project) -> bool:
    return bool(project.repository.raw_config().get("release", {}).get("interdependencies", True))


def get_pyproject_interdependency_version_refs(project: Project) -> list[VersionRef]:
    """Identifies version references of another project in the set of projects loaded in the application. This is
    relevant in case when Slap is used in a mono-repository where all projects share the same version, and bumping
    version numbers should also bump the version number of dependencies between projects in that mono-repository."""

    pyproject_file = project.pyproject_toml.path
    other_projects: list[str] = [
        t.cast(str, p.dist_name())
        for p in project.repository.projects()
        if p.is_python_project and p is not project and p.dist_name()
    ]

    refs = []

    SELECTOR = r"([\^<>=!~\*]*)(?P<version>\d+\.[\w\d\.\-]+)"

    for name in other_projects:
        # Look for something that looks like a version number. In common TOML formats, that is usually as an entire
        # requirement string or as an assignment.
        expressions = [
            # This first one matches TOML key/value pairs.
            r'([\'"])?' + re.escape(name) + r'\1\s*=\s*([\'"])' + SELECTOR + r"\1",
            re.escape(name) + r'\s*=\s*([\'"])' + SELECTOR + r"\1",
            # This second one matches a TOML string that contains the dependency.
            r'([\'"])' + re.escape(name) + r"(?![^\w\d\_\.\-\ ])\s*" + SELECTOR + r"\1\s*($|,|\]|\})",
        ]

        for expr in expressions:
            refs += match_version_ref_pattern_on_lines(pyproject_file, expr)

    return refs
