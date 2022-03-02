
from __future__ import annotations

import typing as t
from pathlib import Path

from nr.util.functional import Once

from slam.configuration import Configuration

if t.TYPE_CHECKING:
  from slam.plugins import RepositoryHandlerPlugin
  from slam.project import Project
  from slam.util.vcs import Vcs, VcsRemote


class Repository(Configuration):
  """ A repository represents a directory that contains one or more projects. """

  handler: Once[RepositoryHandlerPlugin]

  def __init__(self, directory: Path) -> None:
    super().__init__(directory)
    self._handler = Once(self._get_repository_handler)
    self.projects = Once(self._get_projects)
    self.vcs = Once(self._get_vcs)
    self.vcs_remote = Once(self._get_vcs_remote)

  @property
  def is_monorepo(self) -> bool:
    if len(self.projects()) > 1 or (len(self.projects()) == 1 and self.projects()[0].directory != self.directory):
      return True
    return False

  def _get_repository_handler(self) -> RepositoryHandlerPlugin:
    """ Returns the handler for this repository. """

    from nr.util.plugins import load_entrypoint
    from slam.plugins import RepositoryHandlerPlugin

    handler_name = self.raw_config().get('repository', {}).get('handler') or 'default'
    assert isinstance(handler_name, str), repr(handler_name)

    handler = load_entrypoint(RepositoryHandlerPlugin, handler_name)()  # type: ignore[misc]
    assert handler.matches_repository(self), (self, handler)
    return handler

  def _get_projects(self) -> list[Project]:
    """ Returns the projects provided by the project handler, but sorted in topological order. """

    from nr.util.digraph import DiGraph
    from nr.util.digraph.algorithm.topological_sort import topological_sort

    projects = sorted(self._handler().get_projects(self), key=lambda p: p.id)
    graph: DiGraph[Project, None, None] = DiGraph()
    for project in projects:
      graph.add_node(project, None)
      for dep in project.get_interdependencies(projects):
        graph.add_node(dep, None)
        graph.add_edge(dep, project, None)

    return list(topological_sort(graph, sorting_key=lambda p: p.id))

  def _get_vcs(self) -> Vcs | None:
    return self._handler().get_vcs(self)

  def _get_vcs_remote(self) -> VcsRemote | None:
    return self._handler().get_vcs_remote(self)
