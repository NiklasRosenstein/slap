
from __future__ import annotations

import abc
import typing as t

from nr.util.generic import T

if t.TYPE_CHECKING:
  from slam.application import Application
  from slam.project import Package, Project


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
