""" Commands that produce reports. """

import json
import logging
import typing as t

import pkg_resources

from slap.application import Application, option
from slap.ext.application.venv import VenvAwareCommand
from slap.plugins import ApplicationPlugin

if t.TYPE_CHECKING:
    from slap.python.dependency import Dependency

logger = logging.getLogger(__name__)


class ReportDependenciesCommand(VenvAwareCommand):
    """Reports the installed run dependencies of your current project(s) as JSON."""

    name = "report dependencies"
    options = VenvAwareCommand.options + [
        option(
            "extras",
            description="A comma-separated list of extra dependencies to include.",
            flag=False,
        ),
        option("with-license-text", description="Include license text in the output."),
    ]

    def __init__(self, app: Application) -> None:
        super().__init__()
        self.app = app

    def handle(self) -> int:
        import databind.json
        import tqdm  # type: ignore[import]

        from slap.python.environment import DistributionGraph, PythonEnvironment, build_distribution_graph
        from slap.python.pep508 import filter_dependencies

        result = super().handle()
        if result != 0:
            return result

        extras = set(filter(bool, map(str.strip, (self.option("extras") or "").split(","))))

        requirements: list[Dependency] = []
        for project in self.app.repository.projects():
            requirements += project.dependencies().run
            if "dev" in extras:
                requirements += project.dependencies().dev
            for extra in extras:
                requirements += project.dependencies().extra.get(extra, [])

        dists_cache: dict[str, pkg_resources.Distribution | None] = {}
        python_environment = PythonEnvironment.of("python")
        requirements = filter_dependencies(requirements, python_environment.pep508, extras)
        with tqdm.tqdm(desc="Resolving requirements graph") as progress:
            graph = build_distribution_graph(
                env=python_environment,
                dependencies=requirements,
                resolved_callback=lambda d: progress.update(len(d)),
                dists_cache=dists_cache,
            )

        graph.sort()
        output = t.cast(dict[str, t.Any], databind.json.dump(graph, DistributionGraph))

        # Retrieve the license text from the distributions.
        if self.option("with-license-text"):
            for dist_name, dist_data in output["metadata"].items():
                dist = dists_cache[dist_name]
                dist_data["license_text"] = None
                if dist is not None:
                    for filename in ("LICENSE", "LICENSE.txt", "LICENSE.text", "LICENSE.rst"):
                        try:
                            dist_data["license_text"] = dist.get_metadata(filename)
                            break
                        except FileNotFoundError:
                            pass

        print(json.dumps(output, indent=2, sort_keys=True))
        return 0


class ReportPlugin(ApplicationPlugin):
    def load_configuration(self, app: Application) -> None:
        return None

    def activate(self, app: Application, config: None) -> None:
        app.cleo.add(ReportDependenciesCommand(app))
