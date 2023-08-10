""" Project handler for projects using the Flit build system. """

from __future__ import annotations

import logging
import typing as t

from slap.ext.project_handlers.base import PyprojectHandler

if t.TYPE_CHECKING:
    from slap.project import Dependencies, Project
    from slap.python.dependency import Dependency

logger = logging.getLogger(__name__)


class FlitProjectHandler(PyprojectHandler):
    # ProjectHandlerPlugin

    def matches_project(self, project: Project) -> bool:
        if not project.pyproject_toml.exists():
            return False
        build_backend = project.pyproject_toml.get("build-system", {}).get("build-backend")
        return build_backend == "flit_core.buildapi"

    def get_dist_name(self, project: Project) -> str | None:
        return project.pyproject_toml.get("tool", {}).get("flit", {}).get("metadata", {}).get("module", {}).get("name")

    def get_readme(self, project: Project) -> str | None:
        return (
            project.pyproject_toml.get("project", {}).get("readme")
            or project.pyproject_toml.get("tool", {}).get("flit", {}).get("metadata", {}).get("description-file")
            or super().get_readme(project)
        )

    def get_dependencies(self, project: Project) -> Dependencies:
        from slap.project import Dependencies
        from slap.python.dependency import PypiDependency, VersionSpec

        flit: dict[str, t.Any] | None = project.pyproject_toml.get("tool", {}).get("flit")
        project_conf: dict[str, t.Any] | None = project.pyproject_toml.get("project")
        build_dependencies = PypiDependency.parse_list(
            project.pyproject_toml.get("build-system", {}).get("requires", [])
        )

        if project_conf is not None:
            optional = project_conf.get("optional-dependencies", {})
            return Dependencies(
                VersionSpec(project_conf["requires-python"]) if "requires-python" in project_conf else None,
                PypiDependency.parse_list(project_conf.get("dependencies", [])),
                PypiDependency.parse_list(optional.pop("dev", [])),
                {extra: PypiDependency.parse_list(value) for extra, value in optional.items()},
                build_dependencies,
            )
        elif flit is not None:
            optional = flit.get("requires-extra", {})
            return Dependencies(
                VersionSpec(flit["requires-python"]) if "requires-python" in flit else None,
                PypiDependency.parse_list(flit.get("requires", [])),
                PypiDependency.parse_list(optional.pop("dev", [])),
                {extra: PypiDependency.parse_list(value) for extra, value in optional.items()},
                build_dependencies,
            )
        else:
            logger.warning("Unable to read dependencies for project <subj>%s</subj>", project)
            return Dependencies(None, [], [], {}, build_dependencies)

    def get_add_dependency_toml_location_and_config(
        self,
        project: Project,
        dependency: Dependency,
        where: str,
    ) -> tuple[list[str], list | dict]:
        from slap.python.dependency import PypiDependency

        if not isinstance(dependency, PypiDependency):
            raise Exception(f"Flit project handler only supports PypiDependency, got {dependency!r}")

        flit: dict[str, t.Any] | None = project.pyproject_toml.get("tool", {}).get("flit")
        if flit is not None:
            locator = ["requires"] if where == "run" else ["requires-extras", where]
            return ["tool", "flit"] + locator, [dependency.version.to_pep_508()]
        else:
            locator = ["dependencies"] if where == "run" else ["optional-dependencies", where]
            return ["project"] + locator, [dependency.version.to_pep_508()]
