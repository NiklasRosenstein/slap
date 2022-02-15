
""" Implements the default package detection plugin. """

import typing as t
from pathlib import Path

from nr.util.algorithm.longest_common_substring import longest_common_substring
from setuptools import find_namespace_packages

from slam.plugins import ProjectHandlerPlugin
from slam.project import Package, Project

IGNORED_MODULES = ['test', 'tests', 'docs']


def detect_packages(directory: Path) -> list[Package]:
  """ Detects the Python packages in *directory*, making an effort to identify namespace packages correctly. """

  assert isinstance(directory, Path)
  modules = find_namespace_packages(str(directory))
  if not modules:
    return []

  if len(modules) > 1:
    def _filter(module: str) -> bool:
      return (directory / module.replace('.', '/') / '__init__.py').is_file()
    modules = list(filter(_filter, modules))

  if len(modules) > 1:
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

  return [Package(module, directory / Path(*module.split('/')), directory) for module in modules]


class DefaultProjectHandler(ProjectHandlerPlugin):

  def __repr__(self) -> str:
    return type(self).__name__

  def matches_project(self, project: Project) -> bool:
    return True

  def get_dist_name(self, project: Project) -> str | None:
    if not project.is_python_project:
      return None
    pyproject: dict[str, t.Any] = project.pyproject_toml.value_or({})
    if (name := pyproject.get('project', {}).get('name')):
      return name
    if (name := pyproject.get('tool', {}).get('poetry', {}).get('name')):
      return name
    return None

  def get_readme(self, project: Project) -> str | None:
    if not project.is_python_project:
      return None
    pyproject: dict[str, t.Any] = project.pyproject_toml.value_or({})
    if (readme := pyproject.get('tool', {}).get('poetry', {}).get('readme')):
      return readme
    return None

  def get_packages(self, project: Project) -> list[Package]:
    source_dir = project.config().source_directory
    if source_dir:
      return detect_packages(project.directory / source_dir)
    else:
      for source_dir in ('src', '.'):
        packages = detect_packages(project.directory / source_dir)
        if packages:
          return packages
    return []
