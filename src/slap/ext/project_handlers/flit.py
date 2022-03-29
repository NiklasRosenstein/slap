
""" Project handler for projects using the Flit build system. """

from __future__ import annotations
import logging
import typing as t

from slap.project import Dependencies, Project
from slap.ext.project_handlers.base import PyprojectHandler

if t.TYPE_CHECKING:
  from poetry.core.packages.dependency import Dependency  # type: ignore[import]


logger = logging.getLogger(__name__)


class FlitProjectHandler(PyprojectHandler):

  # ProjectHandlerPlugin

  def matches_project(self, project: Project) -> bool:
    if not project.pyproject_toml.exists():
      return False
    build_backend = project.pyproject_toml.get('build-system', {}).get('build-backend')
    return build_backend == 'flit_core.buildapi'

  def get_dist_name(self, project: Project) -> str | None:
    return project.pyproject_toml.get('tool', {}).get('flit', {}).get('metadata', {}).get('module', {}).get('name')

  def get_readme(self, project: Project) -> str | None:
    return (
      project.pyproject_toml.get('project', {}).get('readme') or
      project.pyproject_toml.get('tool', {}).get('flit', {}).get('metadata', {}).get('description-file') or
      super().get_readme(project)
    )

  def get_dependencies(self, project: Project) -> Dependencies:
    flit: dict[str, t.Any] | None = project.pyproject_toml.get('tool', {}).get('flit')
    project_conf: dict[str, t.Any] | None = project.pyproject_toml.get('project')

    if project_conf is not None:
      optional = project_conf.get('optional-dependencies', {})
      return Dependencies(
        project_conf.get('dependencies', []),
        optional.pop('dev', []),
        optional,
      )
    elif flit is not None:
      optional = flit.get('requires-extra', {})
      return Dependencies(
        flit.get('requires', []),
        optional.pop('dev', []),
        optional,
      )
    else:
      logger.warning('Unable to read dependencies for project <subj>%s</subj>', project)
      return Dependencies([], [], {})

  def get_dependency_location_key_sequence(
    self,
    project: Project,
    selector: Dependency,
    where: str,
  ) -> tuple[list[str], list | dict]:
    flit: dict[str, t.Any] | None = project.pyproject_toml.get('tool', {}).get('flit')

    if flit is not None:
      locator = ['requires'] if where == 'run' else ['requires-extras', where]
      return ['tool', 'flit'] + locator, [selector.to_pep_508()]
    else:
      locator = ['dependencies'] if where == 'run' else ['optional-dependencies', where]
      return ['project'] + locator, [selector.to_pep_508()]
