
""" Project handler for projects using the Flit build system. """

import logging
import typing as t

from slap.project import Dependencies, Project
from slap.ext.project_handlers.default import DefaultProjectHandler

logger = logging.getLogger(__name__)


class FlitProjectHandler(DefaultProjectHandler):

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
      optional = flit.get('requires-extra', {}).get('dev', [])
      return Dependencies(
        flit.get('requires', []),
        optional.pop('dev', []),
        optional,
      )
    else:
      logger.warning('Unable to read dependencies for project <subj>%s</subj>', project)
      return Dependencies([], [], {})
