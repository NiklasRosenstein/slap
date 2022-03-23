
from __future__ import annotations

import abc
import dataclasses
import typing as t
from pathlib import Path

from databind.core.settings import Union
from nr.util.functional import Once

from slap.configuration import Configuration

if t.TYPE_CHECKING:
  from slap.plugins import RepositoryHandlerPlugin
  from slap.project import Project
  from slap.util.vcs import Vcs


@dataclasses.dataclass
class Issue:
  """ Represents an issue. """

  id: str
  url: str
  shortform: str


@dataclasses.dataclass
class PullRequest:
  """ Represents a pull request. """

  id: str
  url: str
  shortform: str


@Union('!slap.plugins.repository_host')
class RepositoryHost(abc.ABC):
  """ Interface for repository hosting services to resolve issue and pull request references, comment on issues
  and create releases. """

  ENTRYPOINT = 'slap.plugins.repository_host'

  @abc.abstractmethod
  def get_username(self, repository: Repository) -> str | None: ...

  @abc.abstractmethod
  def get_issue_by_reference(self, issue_reference: str) -> Issue: ...

  @abc.abstractmethod
  def get_pull_request_by_reference(self, pr_reference: str) -> PullRequest: ...

  @abc.abstractmethod
  def comment_on_issue(self, issue_reference: str, message: str) -> None: ...

  @abc.abstractmethod
  def create_release(self, version: str, description: str, attachments: list[Path]) -> None: ...

  @staticmethod
  @abc.abstractmethod
  def detect_repository_host(repository: Repository) -> RepositoryHost | None: ...


class Repository(Configuration):
  """ A repository represents a directory that contains one or more projects. A repository represents one or more
  projects in one logical unit, usually tracked by a single version control repository. The class  """

  handler: Once[RepositoryHandlerPlugin]

  def __init__(self, directory: Path) -> None:
    super().__init__(directory)
    self._handler = Once(self._get_repository_handler)
    self.projects = Once(self._get_projects)
    self.vcs = Once(self._get_vcs)
    self.host = Once(self._get_repository_host)

  @property
  def is_monorepo(self) -> bool:
    if len(self.projects()) > 1 or (len(self.projects()) == 1 and self.projects()[0].directory != self.directory):
      return True
    return False

  def _get_repository_handler(self) -> RepositoryHandlerPlugin | None:
    """ Returns the handler for this repository. """

    from nr.util.plugins import load_entrypoint
    from slap.plugins import RepositoryHandlerPlugin
    from slap.ext.repository_handlers.default import DefaultRepositoryHandler

    handler: RepositoryHandlerPlugin
    handler_name = self.raw_config().get('repository', {}).get('handler')
    if handler_name is None:
      handler = DefaultRepositoryHandler()
      if not handler.matches_repository(self):
        return None
    else:
      assert isinstance(handler_name, str), repr(handler_name)
      handler = load_entrypoint(RepositoryHandlerPlugin, handler_name)()  # type: ignore[misc]
      assert handler.matches_repository(self), (self, handler)
    return handler

  def _get_projects(self) -> list[Project]:
    """ Returns the projects provided by the project handler, but sorted in topological order. """

    from nr.util.digraph import DiGraph
    from nr.util.digraph.algorithm.topological_sort import topological_sort

    handler = self._handler()
    if not handler:
      return []

    projects = sorted(handler.get_projects(self), key=lambda p: p.id)
    graph: DiGraph[Project, None, None] = DiGraph()
    for project in projects:
      graph.add_node(project, None)
      for dep in project.get_interdependencies(projects):
        graph.add_node(dep, None)
        graph.add_edge(dep, project, None)

    return list(topological_sort(graph, sorting_key=lambda p: p.id))

  def _get_vcs(self) -> Vcs | None:
    from nr.util.optional import Optional
    return Optional(self._handler()).map(lambda h: h.get_vcs(self)).or_else(None)

  def _get_repository_host(self) -> RepositoryHost | None:
    from nr.util.optional import Optional
    return Optional(self._handler()).map(lambda h: h.get_repository_host(self)).or_else(None)
