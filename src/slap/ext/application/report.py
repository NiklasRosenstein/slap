
""" Commands that produce reports. """

import logging
import json
import typing as t

from slap.plugins import ApplicationPlugin
from slap.application import Application, Command, option

if t.TYPE_CHECKING:
  from slap.python.dependency import Dependency

logger = logging.getLogger(__name__)


class ReportDependenciesCommand(Command):
  """ Reports the installed run dependencies of your current project(s) as JSON. """

  name = 'report dependencies'
  options = [
    option(
      'extras',
      description="A comma-separated list of extra dependencies to include.",
      flag=False,
    ),
  ]

  def __init__(self, app: Application) -> None:
    super().__init__()
    self.app = app

  def handle(self) -> None:
    import databind.json
    import tqdm  # type: ignore[import]
    from slap.python.environment import DistributionGraph, PythonEnvironment, build_distribution_graph
    from slap.python.pep508 import filter_dependencies

    extras = set(filter(bool, map(str.strip, (self.option('extras') or '').split(','))))

    requirements: list[Dependency] = []
    for project in self.app.repository.projects():
      requirements += project.dependencies().run
      if 'dev' in extras:
        requirements += project.dependencies().dev
      for extra in extras:
        requirements += project.dependencies().extra.get(extra, [])

    python_environment = PythonEnvironment.of("python")
    requirements = filter_dependencies(requirements, python_environment.pep508, extras)
    with tqdm.tqdm(desc='Resolving requirements graph') as progress:
      graph = build_distribution_graph(python_environment, requirements, lambda d: progress.update(len(d)))

    graph.sort()
    print(databind.json.dumps(graph, DistributionGraph, indent=2, sort_keys=True))
    # missing_distributions: set[str] = set()
    # metadata: dict[str, dict[str, t.Any] | None] = {}

    # # TODO (@NiklasRosenstein): Resolve dependency markers, including required extras.
    #   while requirements:
    #     logger.info('Fetching requirements: <val>%s</val>', requirements)
    #     distributions = python_environment.get_distributions([d.name for d in requirements])
    #     progress.update(len(requirements))
    #     requirements = []
    #     for dist_name, dist in distributions.items():
    #       if dist is None:
    #         missing_distributions.add(dist_name)
    #         metadata[dist_name] = None
    #       else:
    #         dist_meta = get_distribution_metadata(dist)
    #         metadata[dist_name] = t.cast(dict[str, t.Any], dump(dist_meta, DistributionMetadata))
    #         requirements += [
    #           dependency
    #           for dependency in parse_dependencies(dist_meta.requirements)
    #           if not dependency.markers or
    #             python_environment.pep508.evaluate_markers(dependency.markers, set(dependency.extras or []))
    #         ]
    #     # requirements -= metadata.keys()
    #     # requirements -= missing_distributions

    # print(json.dumps(metadata, indent=2))

    # if missing_distributions:
    #   logger.warning('Unable to find the following required distributions: <val>%s</val>', missing_distributions)


class ReportPlugin(ApplicationPlugin):

  def load_configuration(self, app: Application) -> None:
    return None

  def activate(self, app: Application, config: None) -> None:
    app.cleo.add(ReportDependenciesCommand(app))
