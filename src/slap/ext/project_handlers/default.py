
""" Implements the default package detection plugin. """

import re
import typing as t
from pathlib import Path

from nr.util.algorithm.longest_common_substring import longest_common_substring
from nr.util.fs import get_file_in_directory
from setuptools import find_namespace_packages, find_packages

from slap.plugins import ProjectHandlerPlugin
from slap.project import Dependencies, Package, Project
from slap.release import VersionRef, match_version_ref_pattern, match_version_ref_pattern_on_lines

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

  package_dirs: t.Sequence[str] = ('src', '.')

  def __repr__(self) -> str:
    return type(self).__name__

  def get_readme(self, project: Project) -> str | None:
    path = get_file_in_directory(project.directory, 'README', ['README.rst'])
    return path.name if path else None

  def get_packages(self, project: Project) -> list[Package] | None:
    """ Detects packages in #package_dirs. """

    source_dir = project.config().source_directory
    if source_dir:
      return detect_packages(project.directory / source_dir)
    else:
      for source_dir in self.package_dirs:
        packages = detect_packages(project.directory / source_dir)
        if packages:
          return packages
    return []

  def get_version_refs(self, project: Project) -> list[VersionRef]:
    """ Returns the version ref in `pyproject.toml` it can be found, as well as the version references of project
    interdependencies (you can disable the interdependencies bit by setting `tool.slap.release.interdependencies`
    setting to `False` on the Slap root directory, usually in a `slap.toml` file). """

    PYPROJECT_TOML_PATTERN = r'^version\s*=\s*[\'"]?(.*?)[\'"]'
    version_ref = match_version_ref_pattern(project.pyproject_toml.path, PYPROJECT_TOML_PATTERN, None)
    refs = [version_ref] if version_ref else []
    if interdependencies_enabled(project):
      refs += get_pyproject_interdependency_version_refs(project)
    return refs


def interdependencies_enabled(project: Project) -> bool:
  return bool(project.repository.raw_config().get('release', {}).get('interdependencies', True))


def get_pyproject_interdependency_version_refs(project: Project) -> list[VersionRef]:
  """ Identifies version references of another project in the set of projects loaded in the application. This is
  relevant in case when Slap is used in a monorepository where all projects share the same version, and bumping
  version numbers should also bump the version number of dependencies between projects in that monorepository. """

  pyproject_file = project.pyproject_toml.path
  other_projects: list[str] = [
    t.cast(str, p.dist_name()) for p in project.repository.projects()
    if p.is_python_project and p is not project and p.dist_name()
  ]

  refs = []

  SELECTOR = r'([\^<>=!~\*]*)(?P<version>\d+\.[\w\d\.\-]+)'

  for name in other_projects:
    # Look for something that looks like a version number. In common TOML formats, that is usually as an entire
    # requirement string or as an assignment.
    expressions = [
      # This first one matches TOML key/value pairs.
      r'([\'"])?' + re.escape(name) + r'\1\s*=\s*([\'"])' + SELECTOR + r'\1',
      re.escape(name) + r'\s*=\s*([\'"])' + SELECTOR + r'\1',
      # This second one matches a TOML string that contains the dependency.
      r'([\'"])' + re.escape(name) + r'(?![^\w\d\_\.\-\ ])\s*' + SELECTOR + r'\1\s*($|,|\]|\})'
    ]

    for expr in expressions:
      refs += match_version_ref_pattern_on_lines(pyproject_file, expr)

  return refs
