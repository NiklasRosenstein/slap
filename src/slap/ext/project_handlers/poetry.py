
""" Project handler for projects using the Poetry build system. """

from __future__ import annotations
import logging
import typing as t

from slap.ext.project_handlers.base import PyprojectHandler
from slap.project import Dependencies, Package, Project

if t.TYPE_CHECKING:
  from slap.python.dependency import VersionSpec

logger = logging.getLogger(__name__)


class PoetryProjectHandler(PyprojectHandler):

  # ProjectHandlerPlugin

  def matches_project(self, project: Project) -> bool:
    if not project.pyproject_toml.exists():
      return False
    build_backend = project.pyproject_toml.get('build-system', {}).get('build-backend')
    return build_backend == 'poetry.core.masonry.api'

  def get_dist_name(self, project: Project) -> str | None:
    return project.pyproject_toml.get('tool', {}).get('poetry', {}).get('name')

  def get_readme(self, project: Project) -> str | None:
    return project.pyproject_toml.get('tool', {}).get('poetry', {}).get('readme') or super().get_readme(project)

  def get_packages(self, project: Project) -> list[Package] | None:
    packages = project.pyproject_toml.get('tool', {}).get('poetry', {}).get('packages')
    if packages is None:
      return super().get_packages(project)  # Fall back to automatically determining the packages
    if not packages:
      return None  # Indicate explicitly that the project does not expose packages

    return [
      Package(
        name=p['include'].replace('/', '.'),
        path=project.directory / p.get('from', '') / p['include'],
        root=project.directory / p.get('from', ''),
      )
      for p in packages
    ]

  def get_dependencies(self, project: Project) -> Dependencies:
    from slap.python.dependency import PypiDependency, parse_dependencies

    poetry: dict[str, t.Any] = project.pyproject_toml.get('tool', {}).get('poetry', {})
    dependencies = parse_dependencies(poetry.get('dependencies', []))
    python = next((d for d in dependencies if d.name == 'python'), None)
    if python is not None:
      assert isinstance(python, PypiDependency), repr(python)
    return Dependencies(
      python.version if python else None,
      [d for d in dependencies if d.name != 'python'],
      parse_dependencies(poetry.get('dev-dependencies', [])),
      {k: parse_dependencies(v) for k, v in poetry.get('extras', {}).items()},
    )

  def get_dependency_location_key_sequence(
    self,
    project: Project,
    package: str,
    version_spec: VersionSpec,
    where: str,
  ) -> tuple[list[str], list | dict]:
    locator = ['dependencies'] if where == 'run' else ['dev-dependencies'] if where == 'dev' else ['extras', where]
    value: list | dict = {package: str(version_spec)} if where in ('run', 'dev') else [f'{package} {version_spec}']
    return ['tool', 'poetry'] + locator, value


