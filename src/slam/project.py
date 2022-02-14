
from __future__ import annotations

import dataclasses
import logging
import typing as t
from pathlib import Path

from databind.core.annotations import alias

from slam.plugins import ProjectHandlerPlugin

if t.TYPE_CHECKING:
  from nr.util.functional import Once
  from slam.util.toml_file import TomlFile


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Package:
  name: str   #: The name of the package. Contains periods in case of a namespace package.
  path: Path  #: The path to the package directory. This points to the namespace package if applicable.
  root: Path  #: The root directory that contains the package.


@dataclasses.dataclass
class ProjectConfig:
  #: The name of the project handler plugin. If none is specified, the built-in project handlers are tested
  #: (see the {@link slam.ext.project_handlers} module for more info on those).
  handler: str = None

  #: The source directory to use when relying on automatic package detection. If not set, the default project
  #: handler will search in `"src/"`` and then `"./"``.
  source_directory: t.Annotated[str | None, alias('source-directory')] = None


class Project:
  """ Represents one Python project. Slam can work with multiple projects at the same time, for example if the same
  repository or source code project contains multiple individual Python projects. Every project has its own
  configuration, either loaded from `slam.toml` or `pyproject.toml`. """

  #: The directory of the project. This is the directory where the `slam.toml` or `pyproject.toml` configuration
  #: would usually reside in, but the existence of neither is absolutely required.
  directory: Path

  #: Points to the `pyproject.toml` file in the project and can be used to conveniently check for its existence
  #: or to access its contents.
  pyproject_toml: TomlFile

  #: Points to the `slam.toml` file in the project and can be used to conveniently check for its existence
  #: or to access its contents.
  slam_toml: TomlFile

  #: Use this to access the Slam configuration, automatically loaded from either `slam.toml` or the `tool.slam`
  #: section in `pyproject.toml`. The attribute is a {@link Once} instance, thus it needs to be called to retrieve
  #: the contents. This is the same as {@link get_raw_configuration()}, but is more efficient.
  raw_config: Once[dict[str, t.Any]]

  #: The parsed configuration, accessible as a {@link Once}.
  config: Once[ProjectConfig]

  #: The packages detected with {@link get_packages()} as a {@link Once}.
  packages: Once[list[Package]]

  def __init__(self, directory: Path, parent: Project | None = None) -> None:
    from nr.util.functional import Once

    from slam.util.toml_file import TomlFile

    self.directory = directory
    self.parent = parent
    self.pyproject_toml = TomlFile(directory / 'pyproject.toml')
    self.slam_toml = TomlFile(directory / 'slam.toml')
    self.usercfg = TomlFile(Path('~/.config/slam/config.toml').expanduser())
    self.raw_config = Once(self.get_raw_configuration)
    self.handler = Once(self.get_project_handler)
    self.config = Once(self.get_project_configuration)
    self.packages = Once(self.get_packages)

  def __repr__(self) -> str:
    return f'Project(id="{self.id}", directory="{self.directory}")'

  def get_raw_configuration(self) -> dict[str, t.Any]:
    """ Loads the raw configuration data for Slam from either the `slam.toml` configuration file or `pyproject.toml`
    under the `[slam.tool]` section. If neither of the files exist or the section in the pyproject does not exist,
    an empty dictionary will be returned. """

    if self.slam_toml.exists():
      logger.debug(
        'Reading configuration for project <subj>%s</subj> from <val>%s</val>',
        self, self.slam_toml.path
      )
      return self.slam_toml.value()
    if self.pyproject_toml.exists():
      logger.debug(
        'Reading configuration for project <subj>%s</subj> from <val>%s</val>',
        self, self.pyproject_toml.path
      )
      return self.pyproject_toml.value().get('tool', {}).get('slam', {})
    return {}

  def get_project_configuration(self) -> ProjectConfig:
    """ Loads the project-level configuration. """

    import databind.json
    from databind.core.annotations import enable_unknowns
    return databind.json.load(self.raw_config(), ProjectConfig, options=[enable_unknowns()])

  def get_project_handler(self) -> ProjectHandlerPlugin:
    """ Loads the project handler for this project. """

    from nr.util.plugins import load_entrypoint

    from slam.plugins import ProjectHandlerPlugin

    config = self.config()
    if config.handler:
      handler = load_entrypoint(ProjectHandlerPlugin, config.handler)()
      if not handler.matches_project(self):
        logger.error(
          'Project handler <obj>%s</obj> for project <subj>%s</subj> does not seem to match the project',
          config.handler, self
        )
      return handler
    else:
      # TODO (@NiklasRosenstein): Add Poetry package detector here before default package detector.
      from slam.ext.project_handlers.default import DefaultProjectHandler
      handlers = [DefaultProjectHandler()]
      for handler in handlers:
        if handler.matches_project(self):
          return handler
      raise RuntimeError(f'no fallback package handler found for project <subj>%s</subj>', self)

  def get_packages(self) -> list[Package]:
    """ Returns the packages that can be detected for this project. How the packages are detected depends on the
    {@link ProjectConfig.packages} option. """

    packages = self.handler().get_packages(self)
    if packages:
      logger.debug(
        'Detected packages for project <subj>%s</subj> by package detector <obj>%s</obj>: <val>%s></val>',
        self, self.handler(), packages,
      )
    else:
      logger.warning(
        'No packages detected for project <subj>%s</subj> by any of package detectors <val>%s</val>',
        self, self.handler()
      )
    return packages

  def get_dist_name(self) -> str:
    return self.handler().get_dist_name(self)

  @property
  def id(self) -> str:
    if not self.parent:
      return '$'
    if self.handler and (name := self.handler().get_dist_name(self)):
      return name
    return self.directory.resolve().name

  @id.setter
  def id(self, value: str) -> None:
    self._id = value
