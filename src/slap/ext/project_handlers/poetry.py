
""" Project handler for projects using the Poetry build system. """

import re
import typing as t

from slap.project import Dependencies, Package, Project
from slap.ext.project_handlers.default import DefaultProjectHandler


class PoetryProjectHandler(DefaultProjectHandler):

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


def convert_poetry_dependencies(dependencies: dict[str, str] | list[str]) -> list[str]:
  from poetry.core.packages.dependency import Dependency  # type: ignore[import]

  if isinstance(dependencies, list):
    result = []
    for dep in dependencies:
      match = re.match(r'\s*[\w\d\-\_]+', dep)
      if match and not dep.startswith('git+'):
        result.append(Dependency(match.group(0), dep[match.end():]).to_pep_508())
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
