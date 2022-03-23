
""" Project handler for projects using the Flit build system. """

import typing as t

from clap.project import Dependencies, Project
from clap.ext.project_handlers.default import DefaultProjectHandler


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
    flit: dict[str, t.Any] = project.pyproject_toml.get('tool', {}).get('flit', {})
    optional = flit.get('requires-extra', {}).get('dev', [])
    return Dependencies(
      flit.get('requires', []),
      optional.pop('dev', []),
      optional,
    )
