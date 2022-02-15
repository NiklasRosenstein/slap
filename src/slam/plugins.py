
from __future__ import annotations

import abc
import typing as t

from databind.core.annotations import union
from nr.util.generic import T

if t.TYPE_CHECKING:
  from pathlib import Path
  from poetry.core.semver.version import Version
  from slam.application import Application, IO
  from slam.check import Check
  from slam.project import Package, Project
  from slam.release import VersionRef
  from slam.util.vcs import VcsHost


class ApplicationPlugin(t.Generic[T], abc.ABC):
  """ A plugin that is activated on application load, usually used to register additional CLI commands. """

  ENTRYPOINT = 'slam.plugins.application'

  @abc.abstractmethod
  def load_configuration(self, app: Application) -> T:
    """ Load the configuration of the plugin. Usually, plugins will want to read the configuration from the Slam
    configuration, which is either loaded from `pyproject.toml` or `slam.toml`. Use {@attr Application.raw_config}
    to access the Slam configuration. """

  @abc.abstractmethod
  def activate(self, app: Application, config: T) -> None:
    """ Activate the plugin. Register a {@link Command} to {@attr Application.cleo} or another type of plugin to
    the {@attr Application.plugins} registry. """


class ProjectHandlerPlugin(abc.ABC):
  """ A plugin that implements the core functionality of a project. Project handlers are intermediate layers between
  the Slam tooling and the actual project configuration, allowing different types of configurations to be adapted and
  used with Slam. """

  ENTRYPOINT = 'slam.plugins.project'

  @abc.abstractmethod
  def matches_project(self, project: Project) -> bool:
    """ Return `True` if the handler is able to provide data for the given project. """

  @abc.abstractmethod
  def get_dist_name(self, project: Project) -> str | None:
    """ Return the distribution name for the project. """

  @abc.abstractmethod
  def get_readme(self, project: Project) -> str | None:
    """ Return the readme file configured for the project. """

  @abc.abstractmethod
  def get_packages(self, project: Project) -> list[Package]:
    """ Return a list of packages for the project. """


class CheckPlugin(abc.ABC):
  """ This plugin type can be implemented to add custom checks to the `shut check` command. Note that checks will
  be grouped and their names prefixed with the plugin name, so that name does not need to be included in the name
  of the returned checks. """

  ENTRYPOINT = 'slam.plugins.check'

  def get_project_checks(self, project: Project) -> t.Iterable[Check]:
    return []

  def get_application_checks(self, app: Application) -> t.Iterable[Check]:
    return []


class ReleasePlugin(abc.ABC):
  """ This plugin can provide additional version references that need to be updated when a release is created or
  perform custom actions when `shut release` is used. """

  ENTRYPOINT = 'slam.plugins.release'

  app: Application
  io: IO

  def get_version_refs(self, project: Project) -> list[VersionRef]:
    return []

  def create_release(self, project: Project, target_version: str, dry: bool) -> t.Sequence[Path]:
    return []


class VersionIncrementingRulePlugin(abc.ABC):
  """ A plugin to bump a version number according to a rule. """

  ENTRYPOINT = 'slam.plugins.version_incrementing_rule'

  def increment_version(self, version: Version) -> Version: ...


@union(union.Subtypes.entrypoint('slam.plugins.vcs_host_provider'))
class VcsHostProvider(abc.ABC):
  """ A plugin class for providing a VCS remote for changelog and release management that can be defined in
  the Slam configuration. """

  @abc.abstractmethod
  def get_vcs_host(self, project: Project) -> VcsHost: ...


class VcsHostDetector(abc.ABC):
  """ This plugin type is used to automatically detect a matching {@link VcsHost}. """

  ENTRYPOINT = 'slam.plugins.vcs_host_detector'

  @abc.abstractmethod
  def detect_vcs_host(self, project: Project) -> VcsHost | None: ...
