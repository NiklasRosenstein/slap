
""" Commands that produce reports. """

import logging
import json
import typing as t

from slap.plugins import ApplicationPlugin
from slap.application import Application, Command

logger = logging.getLogger(__name__)


class ReportDependenciesCommand(Command):
  """ Reports the installed run dependencies of your current project(s) as JSON. """

  name = "report dependencies"

  def __init__(self, app: Application) -> None:
    super().__init__()
    self.app = app

  def handle(self) -> None:
    import tqdm  # type: ignore[import]
    from databind.json import dump
    from slap.python.dependency import parse_dependencies
    from slap.python.environment import PythonEnvironment, DistributionMetadata, get_distribution_metadata

    requirements: set[str] = set()
    for project in self.app.repository.projects():
      for dependency in project.dependencies().run:
        requirements.add(dependency.name)

    missing_distributions: set[str] = set()
    metadata: dict[str, dict[str, t.Any] | None] = {}
    python_environment = PythonEnvironment.of("python")

    # TODO (@NiklasRosenstein): Resolve dependency markers, including required extras.
    with tqdm.tqdm(desc='Resolving requirements graph') as progress:
      while requirements:
        logger.info('Fetching requirements: <val>%s</val>', requirements)
        distributions = python_environment.get_distributions(requirements)
        progress.update(len(requirements))
        requirements = set()
        for dist_name, dist in distributions.items():
          if dist is None:
            missing_distributions.add(dist_name)
            metadata[dist_name] = None
          else:
            dist_meta = get_distribution_metadata(dist)
            metadata[dist_name] = t.cast(dict[str, t.Any], dump(dist_meta, DistributionMetadata))
            requirements |= {dependency.name for dependency in parse_dependencies(dist_meta.requirements)}
        requirements -= metadata.keys()
        requirements -= missing_distributions

    print(json.dumps(metadata, indent=2))

    if missing_distributions:
      logger.warning('Unable to find the following required distributions: <val>%s</val>', missing_distributions)


class ReportPlugin(ApplicationPlugin):

  def load_configuration(self, app: Application) -> None:
    return None

  def activate(self, app: Application, config: None) -> None:
    app.cleo.add(ReportDependenciesCommand(app))
