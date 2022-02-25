
""" Implements the default package detection plugin. """

import logging
import re
import typing as t
from pathlib import Path

from nr.util.algorithm.longest_common_substring import longest_common_substring
from setuptools import find_namespace_packages, find_packages

from slam.plugins import ProjectHandlerPlugin
from slam.project import Dependencies, Package, Project

IGNORED_MODULES = ['test', 'tests', 'docs', 'build']
logger = logging.getLogger(__name__)


def detect_packages(directory: Path) -> list[Package]:
  """ Detects the Python packages in *directory*, making an effort to identify namespace packages correctly. """

  if not directory.is_dir():
    return []

  assert isinstance(directory, Path)
  modules = list(set(find_namespace_packages(str(directory)) + find_packages(str(directory))))

  # Also support toplevel modules.
  for path in directory.iterdir():
    if path.is_file() and path.suffix == '.py' and path.stem not in modules:
      modules.append(path.stem)

  if not modules:
    return []

  paths = {}
  for module in modules:
    tlm_file = (directory / (module + '.py'))
    pkg_file = directory / Path(*module.split('.'),  '__init__.py')
    use_file = tlm_file if tlm_file.is_file() else pkg_file.parent if pkg_file.is_file() else None
    if use_file is not None:
      paths[module] = use_file

  modules = [m for m in modules if m in paths]

  modules = [
    m for m in modules
    if m not in IGNORED_MODULES and
      ('.' not in m or m.split('.')[0] not in IGNORED_MODULES)
  ]

  if len(modules) > 1:
    # If we stil have multiple modules, we try to find the longest common path.
    common = longest_common_substring(*(x.split('.') for x in modules), start_only=True)
    if not common:
      return []
    modules = ['.'.join(common)]

  return [Package(module, paths[module], directory) for module in modules]


def convert_poetry_dependencies(dependencies: dict[str, str] | list[str]) -> list[str]:
  from poetry.core.packages.dependency import Dependency  # type: ignore[import]

  if isinstance(dependencies, list):
    result = []
    for dep in dependencies:
      match = re.match(r'\s*[\w\d\-\_]+', dep)
      if match:
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


class DefaultProjectHandler(ProjectHandlerPlugin):

  def __repr__(self) -> str:
    return type(self).__name__

  def _get_pyproject(self, project: Project) -> dict[str, t.Any] | None:
    if not project.is_python_project:
      return None
    return project.pyproject_toml.value_or({})

  def matches_project(self, project: Project) -> bool:
    return True

  def get_dist_name(self, project: Project) -> str | None:
    if (pyproject := self._get_pyproject(project)) is None:
      return None
    if (name := pyproject.get('project', {}).get('name')):
      return name
    if (name := pyproject.get('tool', {}).get('poetry', {}).get('name')):
      return name
    return None

  def get_readme(self, project: Project) -> str | None:
    if (pyproject := self._get_pyproject(project)) is None:
      return None
    if (readme := pyproject.get('tool', {}).get('poetry', {}).get('readme')):
      return readme
    return None

  def get_packages(self, project: Project) -> list[Package] | None:
    if (pyproject := self._get_pyproject(project)) is not None:
      packages = pyproject.get('tool', {}).get('poetry', {}).get('packages')
      if packages is not None:
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

    source_dir = project.config().source_directory
    if source_dir:
      return detect_packages(project.directory / source_dir)
    else:
      for source_dir in ('src', '.'):
        packages = detect_packages(project.directory / source_dir)
        if packages:
          return packages
    return []

  def get_dependencies(self, project: Project) -> Dependencies:
    if (pyproject := self._get_pyproject(project)) is None:
      return Dependencies([], [], {})

    poetry: dict[str, t.Any] | None = pyproject.get('tool', {}).get('poetry')
    flit: dict[str, t.Any] | None = pyproject.get('tool', {}).get('flit')
    project_conf: dict[str, t.Any] | None = pyproject.get('project')

    if project_conf:
      logger.info('Reading <val>[project]</val> dependencies for project <subj>%s</subj>', project)
      optional = project_conf.get('optional-dependencies', {})
      return Dependencies(
        project_conf.get('dependencies', []),
        optional.pop('dev', []),
        optional,
      )
    elif poetry:
      logger.info('Reading <val>[tool.poetry]</val> dependencies for project <subj>%s</subj>', project)
      return Dependencies(
        convert_poetry_dependencies(poetry.get('dependencies', [])),
        convert_poetry_dependencies(poetry.get('dev-dependencies', [])),
        {k: convert_poetry_dependencies(v) for k, v in poetry.get('extras', {}).items()},
      )
    elif flit:
      logger.info('Reading <val>[tool.flit]</val> dependencies for project <subj>%s</subj>', project)
      optional = flit.get('requires-extra', {}).get('dev', [])
      return Dependencies(
        flit.get('requires', []),
        optional.pop('dev', []),
        optional,
      )
    else:
      logger.info('Unable to identify dependencies source for project <subj>%s</subj>', project)
      return Dependencies([], [], {})
