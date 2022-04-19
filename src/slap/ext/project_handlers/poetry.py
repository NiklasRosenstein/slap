""" Project handler for projects using the Poetry build system. """

from __future__ import annotations

import logging
import typing as t

from slap.ext.project_handlers.base import PyprojectHandler
from slap.project import Dependencies, Package, Project
from slap.python.dependency import Dependency, PypiDependency

if t.TYPE_CHECKING:
    from slap.python.dependency import Dependency

logger = logging.getLogger(__name__)


class PoetryProjectHandler(PyprojectHandler):

    # ProjectHandlerPlugin

    def matches_project(self, project: Project) -> bool:
        if not project.pyproject_toml.exists():
            return False
        build_backend = project.pyproject_toml.get("build-system", {}).get("build-backend")
        return build_backend == "poetry.core.masonry.api"

    def get_dist_name(self, project: Project) -> str | None:
        return project.pyproject_toml.get("tool", {}).get("poetry", {}).get("name")

    def get_readme(self, project: Project) -> str | None:
        return project.pyproject_toml.get("tool", {}).get("poetry", {}).get("readme") or super().get_readme(project)

    def get_packages(self, project: Project) -> list[Package] | None:
        packages = project.pyproject_toml.get("tool", {}).get("poetry", {}).get("packages")
        if packages is None:
            return super().get_packages(project)  # Fall back to automatically determining the packages
        if not packages:
            return None  # Indicate explicitly that the project does not expose packages

        return [
            Package(
                name=p["include"].replace("/", "."),
                path=project.directory / p.get("from", "") / p["include"],
                root=project.directory / p.get("from", ""),
            )
            for p in packages
        ]

    def get_dependencies(self, project: Project) -> Dependencies:
        from slap.install.installer import Indexes
        from slap.python.dependency import PypiDependency, parse_dependencies

        poetry: dict[str, t.Any] = project.pyproject_toml.get("tool", {}).get("poetry", {})
        dependencies = parse_dependencies(poetry.get("dependencies", []))
        python = next((d for d in dependencies if d.name == "python"), None)
        if python is not None:
            assert isinstance(python, PypiDependency), repr(python)

        # Collect the package indexes from the Poetry config.
        indexes = Indexes()
        for source in poetry.get("source", []):
            if source.get("default", False):
                indexes.default = source["name"]
            indexes.urls[source["name"]] = source["url"]

        return Dependencies(
            python=python.version if python else None,
            run=[d for d in dependencies if d.name != "python"],
            dev=parse_dependencies(poetry.get("dev-dependencies", [])),
            extra={k: parse_dependencies(v) for k, v in poetry.get("extras", {}).items()},
            indexes=indexes,
        )

    def get_add_dependency_toml_location_and_config(
        self,
        project: Project,
        dependency: Dependency,
        where: str,
    ) -> tuple[list[str], list | dict]:
        from slap.python.dependency import PypiDependency

        if not isinstance(dependency, PypiDependency):
            raise Exception(f"Poetry project handler only supports PypiDependency, got {dependency!r}")

        locator = ["dependencies"] if where == "run" else ["dev-dependencies"] if where == "dev" else ["extras", where]
        value: list | dict = (
            {dependency.name: convert_dependency_to_poetry_config(dependency)}
            if where in ("run", "dev")
            else [f"{dependency.name} {dependency.version}"]
        )
        return ["tool", "poetry"] + locator, value


def convert_dependency_to_poetry_config(dependency: Dependency) -> t.Mapping[str, t.Any] | str:
    import tomlkit.api

    from slap.python.dependency import PypiDependency

    if isinstance(dependency, PypiDependency):
        if not dependency.markers and not dependency.python and not dependency.source:
            return str(dependency.version)
        result = tomlkit.api.inline_table()
        result["version"] = str(dependency.version)
        if dependency.markers:
            result["markers"] = dependency.markers
        if dependency.python:
            result["python"] = str(dependency.python)
        if dependency.extras:
            result["extras"] = dependency.extras
        if dependency.source:
            result["source"] = dependency.source
        return result
    else:
        raise ValueError(f"currently only supports PypiDependency, got {dependency!r}")