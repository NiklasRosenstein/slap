
""" Implements the default package detection plugin. """

from pathlib import Path

from nr.util.algorithm.longest_common_substring import longest_common_substring
from nr.util.fs import get_file_in_directory
from setuptools import find_namespace_packages, find_packages

from clap.plugins import ProjectHandlerPlugin
from clap.project import Dependencies, Package, Project

IGNORED_MODULES = ['test', 'tests', 'docs', 'build']


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


class DefaultProjectHandler(ProjectHandlerPlugin):
  """ Base class for other project handlers. It cannot be used directly by a project. """

  def __repr__(self) -> str:
    return type(self).__name__

  def get_readme(self, project: Project) -> str | None:
    path = get_file_in_directory(project.directory, 'README', ['README.rst'])
    return path.name if path else None

  def get_packages(self, project: Project) -> list[Package] | None:
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
    return Dependencies([], [], {})
