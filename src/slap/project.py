
from __future__ import annotations

import dataclasses
import logging
import typing as t
from pathlib import Path

from databind.core.settings import Alias

from slap.configuration import Configuration

if t.TYPE_CHECKING:
  from nr.util.functional import Once
  from slap.repository import Repository
  from slap.plugins import ProjectHandlerPlugin
  from slap.release import VersionRef


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Dependencies:
  run: list[str]
  dev: list[str]
  extra: dict[str, list[str]]


@dataclasses.dataclass
class Package:
  name: str   #: The name of the package. Contains periods in case of a namespace package.
  path: Path  #: The path to the package directory. This points to the namespace package if applicable.
  root: Path  #: The root directory that contains the package.


@dataclasses.dataclass
class ProjectConfig:
  #: The name of the project handler plugin. If none is specified, the built-in project handlers are tested
  #: (see the #slap.ext.project_handlers module for more info on those).
  handler: str | None = None

  #: The source directory to use when relying on automatic package detection. If not set, the default project
  #: handler will search in `"src/"`` and then `"./"``.
  source_directory: t.Annotated[str | None, Alias('source-directory')] = None

  #: Whether the project source code is inteded to be typed.
  typed: bool | None = None


class Project(Configuration):
  """ Represents one Python project. Slap can work with multiple projects at the same time, for example if the same
  repository or source code project contains multiple individual Python projects. Every project has its own
  configuration, either loaded from `slap.toml` or `pyproject.toml`. """

  #: Reference to the Slap application object.
  repository: Repository

  #: The parsed configuration, accessible as a #Once.
  config: Once[ProjectConfig]

  #: The packages detected with #get_packages() as a #Once.
  packages: Once[t.Sequence[Package] | None]

  #: The packages detected readme as a #Once.
  readme: Once[str | None]

  #: The packages dependencies as a #Once.
  dependencies: Once[Dependencies]

  def __init__(self, repository: Repository, directory: Path) -> None:
    super().__init__(directory)
    from nr.util.functional import Once
    from slap.util.toml_file import TomlFile

    self.repository = repository
    self.usercfg = TomlFile(Path('~/.config/slap/config.toml').expanduser())
    self.handler = Once(self._get_project_handler)
    self.config = Once(self._get_project_configuration)
    self.packages = Once(self._get_packages)
    self.readme = Once(self._get_readme)
    self.dependencies = Once(self._get_dependencies)
    self.dist_name = Once(self._get_dist_name)
    self.version = Once(self._get_version)

  def _get_project_configuration(self) -> ProjectConfig:
    """ Loads the project-level configuration. """

    from databind.json import load
    from databind.json.settings import ExtraKeys
    return load(self.raw_config(), ProjectConfig, settings=[ExtraKeys(True)])

  def _get_project_handler(self) -> ProjectHandlerPlugin:
    """ Returns the handler for this project. """

    from nr.util.plugins import iter_entrypoints, load_entrypoint
    from slap.plugins import ProjectHandlerPlugin

    handler_name = self.config().handler
    if handler_name is None:
      for handler_name, loader in iter_entrypoints(ProjectHandlerPlugin):  # type: ignore[misc]
        handler = loader()()
        if handler.matches_project(self):
          break
      else:
        raise RuntimeError(f'unable to identify project handler for {self!r}')
    else:
      assert isinstance(handler_name, str), repr(handler_name)
      handler = load_entrypoint(ProjectHandlerPlugin, handler_name)()  # type: ignore[misc]
      assert handler.matches_project(self), (self, handler)
    return handler

  def _get_packages(self) -> list[Package] | None:
    """ Returns the packages that can be detected for this project. How the packages are detected depends on the
    #ProjectConfig.packages option. """

    if not self.is_python_project:
      return []
    packages = self.handler().get_packages(self)
    if packages:
      logger.debug(
        'Detected packages for project <subj>%s</subj> by package detector <obj>%s</obj>: <val>%s></val>',
        self, self.handler(), packages,
      )
    elif self.is_python_project and packages is not None:
      logger.warning(
        'No packages detected for project <subj>%s</subj> by any of package detectors <val>%s</val>',
        self, self.handler()
      )
    return packages

  def _get_dist_name(self) -> str | None:
    return self.handler().get_dist_name(self)

  def _get_readme(self) -> str | None:
    return self.handler().get_readme(self)

  def _get_dependencies(self) -> Dependencies:
    return self.handler().get_dependencies(self)

  def _get_version(self) -> str | None:
    return self.handler().get_version(self)

  def get_version_refs(self) -> list[VersionRef]:
    return self.handler().get_version_refs(self)

  def get_interdependencies(self, projects: t.Sequence[Project]) -> list[Project]:
    """ Returns the dependencies of this project in the list of other projects. The returned dictionary maps
    to the project and the dependency constraint. This will only take run dependencies into account. """

    import re

    dependency_names = set()
    for dep in self.dependencies().run:
      match = re.match(r'[\w\d\_\-\.]+\b', dep)
      if not match: continue
      dependency_names.add(match.group(0))

    result = []
    for project in projects:
      if project.dist_name() in dependency_names:
        result.append(project)

    return result

  @property
  def id(self) -> str:
    return self.dist_name() or self.directory.resolve().name

  @id.setter
  def id(self, value: str) -> None:
    self._id = value

  @property
  def is_python_project(self) -> bool:
    return self.pyproject_toml.exists()
