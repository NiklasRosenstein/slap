
""" Project handler for projects using the Poetry build system. """

from __future__ import annotations
import typing as t

from slap.ext.project_handlers.base import PyprojectHandler
from slap.project import Dependencies, Package, Project
from slap.util.semver import parse_dependency

if t.TYPE_CHECKING:
  from poetry.core.packages.dependency import Dependency  # type: ignore[import]


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
    poetry: dict[str, t.Any] = project.pyproject_toml.get('tool', {}).get('poetry', {})
    return Dependencies(
      convert_poetry_dependencies(poetry.get('dependencies', [])),
      convert_poetry_dependencies(poetry.get('dev-dependencies', [])),
      {k: convert_poetry_dependencies(v) for k, v in poetry.get('extras', {}).items()},
    )

  def get_dependency_location_key_sequence(
    self,
    project: Project,
    selector: Dependency,
    where: str,
  ) -> tuple[list[str], list | dict]:
    locator = ['dependencies'] if where == 'run' else ['dev-dependencies'] if where == 'dev' else ['extras', where]
    value: list | dict = {selector.name: str(selector.pretty_constraint)} if where in ('run', 'dev') else [f'{selector.name} {selector.pretty_constraint}']
    return ['tool', 'poetry'] + locator, value


def convert_poetry_dependencies(dependencies: dict[str, str] | list[str]) -> list[str]:
  from poetry.core.packages.dependency import Dependency  # type: ignore[import]

  if isinstance(dependencies, list):
    result = []
    for dep in dependencies:
      if not dep.startswith('git+'):
        result.append(parse_dependency(dep).to_pep_508())
      else:
        result.append(dep)
    return result
  elif isinstance(dependencies, dict):
    result = []
    for key, version in dependencies.items():
      if key == 'python': continue
      result.append(Dependency(key, version).to_pep_508())
    return result
  else:
    raise TypeError(type(dependencies))
