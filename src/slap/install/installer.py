
""" Provides an installer for dependencies. """

from __future__ import annotations

import abc
import dataclasses
import logging
import shlex
import subprocess as sp
import typing as t
from pathlib import Path

from slap.python.dependency import MultiDependency
from slap.python.pep508 import filter_dependencies, test_dependency

if t.TYPE_CHECKING:
  from slap.python.dependency import Dependency
  from slap.python.environment import PythonEnvironment

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class InstallOptions:
  quiet: bool


class Installer(abc.ABC):
  """ An installer for dependencies into a #PythonEnvironment. """

  @abc.abstractmethod
  def install(self, dependencies: list[Dependency], target: PythonEnvironment, options: InstallOptions) -> int:
    ...


class SymlinkHelper(t.Protocol):
  """
  A helper for introspecting a project for additional dependencies and symlinking it. This is needed when a
  #PathDependency is encountered with #PathDependency.link enabled.
  """

  def get_dependencies_for_project(self, project: Path) -> list[Dependency]: ...

  def link_project(self, project: Path) -> None: ...


class PipInstaller(Installer):
  """ Installs dependencies via Pip. """

  def __init__(self,symlink_helper: SymlinkHelper) -> None:
    """
    Args:
      symlink_helper: A helper for implementing #PathDependency.link when it is encountered.
    """

    self.symlink_helper = symlink_helper

  def install(self, dependencies: t.Sequence[Dependency], target: PythonEnvironment, options: InstallOptions) -> int:

    from slap.python.dependency import GitDependency, PathDependency, PypiDependency, UrlDependency

    # Collect the Pip arguments and the dependencies that need to be installed through other methods.
    supports_hashes = {PypiDependency, UrlDependency}
    unsupported_hashes: dict[type[Dependency], list[Dependency]] = {}
    link_projects: list[Path] = []
    pip_arguments: list[str] = []
    dependencies = list(dependencies)
    while dependencies:
      dependency = dependencies.pop()

      # TODO (@NiklasRosenstein): Pass extras from PipInstaller caller.
      if not test_dependency(dependency, target.pep508, {}):
        continue

      # Collect dependencies for which hashes are not supported so we can report it later.
      if dependency.hashes and type(dependency) not in supports_hashes:
        unsupported_hashes.setdefault(type(dependency), []).append(dependency)

      if isinstance(dependency, PathDependency) and dependency.link:
        logger.info('Collecting recursive dependencies for project <val>%s</val>', dependency.path)
        dependencies += filter_dependencies(
          dependencies=self.symlink_helper.get_dependencies_for_project(dependency.path),
          env=target.pep508,
          extras=set(dependency.extras or []),
        )
        link_projects.append(dependency.path)
        continue

      elif isinstance(dependency, MultiDependency):
        for sub_dependency in dependency:
          # TODO (@NiklasRosenstein): Pass extras from the caller so we can evaluate them here
          if test_dependency(sub_dependency, target.pep508, {}):
            dependencies.insert(0, sub_dependency)

      else:
        pip_arguments += self.dependency_to_pip_arguments(dependency)

    # Construct the Pip command to run.
    pip_command = [target.executable, "-m", "pip", "install"] + pip_arguments
    if options.quiet:
      pip_command += ['-q']

    logger.info('Installing with Pip using command <subj>$ %s</subj>', ' '.join(map(shlex.quote, pip_command)))
    if (res := sp.call(pip_command)) != 0:
      return res

    # Symlink all projects that need to be linked.
    for project_path in link_projects:
      self.symlink_helper.link_project(project_path)

    return 0

  @staticmethod
  def dependency_to_pip_arguments(dependency: Dependency) -> list[str]:
    """ Converts a dependency to a list of arguments for Pip.

    Args:
      dependency: The dependency to convert. Must be one of #GitDependency, #PathDependency,
        #PypiDependency or #UrlDependency. A #MultiDependency is not supported by this function.
    Raises:
      Exception: If an unexpected kind of dependency was encountered.
    """

    from slap.python.dependency import GitDependency, PathDependency, PypiDependency, UrlDependency

    extras = '' if not dependency.extras else f'[{",".join(dependency.extras)}]'
    hashes = ' '.join(f'--hash={h}' for h in dependency.hashes or [])
    pip_arguments = []

    if isinstance(dependency, GitDependency):
      # TODO (@NiklasRosenstein): Add Git branch/rev/tag to the URL.
      if dependency.branch or dependency.rev or dependency.tag:
        logger.warning(
          'PipInstaller does not currently support Git branch/rev/tag, dependency will be installed '
          'from main branch: <val>%s</val>', dependency,
        )
      pip_arguments += [f'{dependency.name}{extras} @ git+{dependency.url}']

    elif isinstance(dependency, PathDependency):
      assert not dependency.link  # We caught that case before
      if dependency.develop:
        pip_arguments += ['-e']
      prefix = '' if dependency.path.is_absolute() else './'
      pip_arguments += [f'{prefix}{dependency.path}{extras}']

    elif isinstance(dependency, PypiDependency):
      if dependency.source:
      # TODO (@NiklasRosenstein): Make sure the dependency gets installed from the respective source.
        logger.warning(
          'PipInstaller does not currently support installing PyPI packages from a different source, '
          'dependency <val>%s</val> will be installed like a normal PyPI dependency.',
          dependency
        )
      pip_arguments += [f'{dependency.name}{extras} {dependency.version.to_pep_508()} {hashes}'.rstrip()]

    elif isinstance(dependency, UrlDependency):
      pip_arguments += [f'{dependency.name}{extras} @ {dependency.url} {hashes}'.rstrip()]

    else:
      raise Exception(f'Unexpected dependency type: {dependency}')

    assert pip_arguments, dependency
    return pip_arguments
