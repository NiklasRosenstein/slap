from __future__ import annotations

import dataclasses
import functools
import json
import logging
import pickle
import shutil
import subprocess as sp
import textwrap
import typing as t
from pathlib import Path

from importlib_metadata import PathDistribution

from slap.python import pep508

if t.TYPE_CHECKING:
    from importlib_metadata import Distribution

    from slap.python.dependency import Dependency

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class PythonEnvironment:
    """Represents a Python environment. Provides functionality to introspect the environment."""

    executable: str
    version: str
    version_tuple: tuple[int, int, int]
    platform: str
    prefix: str
    base_prefix: str | None
    real_prefix: str | None
    pep508: pep508.Pep508Environment
    _has_pkg_resources: bool | None = None

    def is_venv(self) -> bool:
        """Checks if the Python environment is a virtual environment."""

        return bool(self.real_prefix or (self.base_prefix and self.prefix != self.base_prefix))

    def has_importlib_metadata(self) -> bool:
        """Checks if the Python environment has the `importlib_metadata` module available."""

        if self._has_pkg_resources is None:
            code = textwrap.dedent(
                """
                try: import importlib_metadata
                except ImportError: print('false')
                else: print('true')
                """
            )
            self._has_pkg_resources = json.loads(sp.check_output([self.executable, "-c", code]).decode())
        return self._has_pkg_resources

    @staticmethod
    @functools.lru_cache()
    def of(python: str | t.Sequence[str]) -> "PythonEnvironment":
        """Introspects the given Python installation to construct a #PythonEnvironment."""

        if isinstance(python, str):
            python = [python]

        # NOTE(NiklasRosenstein): On Windows, we might not end up running the Python version of the current
        #   virtual environment when just calling "python" or "python.exe", which is why we need to use
        #   `shutil.which()` to manually resolve it.
        #
        #   A similar issue is described here: https://stackoverflow.com/q/65283987/791713
        full_path = shutil.which(python[0])
        if full_path:
            python = [full_path] + list(python[1:])

        # We ensure that the Pep508 module is importable.
        pep508_path = str(Path(pep508.__file__).parent)

        code = textwrap.dedent(
            f"""
            import sys, platform, json, pickle
            sys.path.append({pep508_path!r})
            import pep508
            try: import importlib_metadata as metadata
            except ImportError: metadata = None
            print(json.dumps({{
                "executable": sys.executable,
                "version": sys.version,
                "version_tuple": sys.version_info[:3],
                "platform": platform.platform(),
                "prefix": sys.prefix,
                "base_prefix": getattr(sys, 'base_prefix', None),
                "real_prefix": getattr(sys, 'real_prefix', None),
                "pep508": pep508.Pep508Environment.current().as_json(),
                "_has_pkg_resources": metadata is not None,
            }}))
            """
        )

        payload = json.loads(sp.check_output(list(python) + ["-c", code]).decode())
        payload["version_tuple"] = tuple(payload["version_tuple"])
        payload["pep508"] = pep508.Pep508Environment(**payload["pep508"])
        return PythonEnvironment(**payload)

    def get_distribution(self, distribution: str) -> Distribution | None:
        """Query the details for a single distribution in the Python environment."""

        return self.get_distributions([distribution])[distribution]

    def get_distributions(self, distributions: t.Collection[str]) -> dict[str, Distribution | None]:
        """Query the details for the given distributions in the Python environment with
        #importlib_metadata.distribution()."""

        code = textwrap.dedent(
            """
            import sys, importlib_metadata as metadata, pickle
            result = []
            for arg in sys.argv[1:]:
                try:
                    dist = metadata.distribution(arg)
                except metadata.PackageNotFoundError:
                    dist = None
                result.append(dist)
            sys.stdout.buffer.write(pickle.dumps(result))
            """
        )

        keys = list(distributions)
        result = pickle.loads(sp.check_output([self.executable, "-c", code] + keys))
        return dict(zip(keys, result))


@dataclasses.dataclass
class DistributionMetadata:
    """Additional metadata for a distribution."""

    location: str | None
    version: str
    license_name: str | None
    platform: str | None
    requires_python: str | None
    requirements: list[str]
    extras: set[str]


def get_distribution_metadata(dist: Distribution) -> DistributionMetadata:
    """Parses the distribution metadata."""

    return DistributionMetadata(
        location=str(dist._path) if isinstance(dist, PathDistribution) else None,  # type: ignore[attr-defined]
        version=dist.metadata["Version"],
        license_name=dist.metadata.get("License"),
        platform=dist.metadata.get("Platform"),
        requires_python=dist.metadata.get("Requires-Python"),
        requirements=dist.metadata.get_all("Requires-Dist") or [],
        extras=set(dist.metadata.get_all("Provides-Extra") or []),
    )


@dataclasses.dataclass
class DistributionGraph:
    """Represents a resolved graph of distributions, their metadata and dependencies in a Python environment."""

    #: Maps a distribution name to it's metadata.
    metadata: dict[str, DistributionMetadata]

    #: Maps out the dependencies between distributions.
    dependencies: dict[str, t.MutableSet[str]]

    #: A set of the distributions that have been found to be required but could not be resolved.
    missing: set[str]

    def sort(self) -> None:
        from slap.util.orderedset import OrderedSet

        for dist_name, dependencies in self.dependencies.items():
            self.dependencies[dist_name] = OrderedSet(sorted(dependencies))

    def update(self, other: DistributionGraph) -> None:
        self.metadata.update(other.metadata)
        self.dependencies.update(other.dependencies)
        self.missing.update(other.missing)


def build_distribution_graph(
    env: PythonEnvironment,
    dependencies: list[Dependency],
    resolved_callback: t.Callable[[dict[str, Distribution | None]], t.Any] | None = None,
    dists_cache: dict[str, Distribution | None] | None = None,
) -> DistributionGraph:
    """Builds a #DistributionGraph in the given #PythonEnvironment using the given dependencies.

    Args:
      env: The Python environment in which to resolve the dependencies.
      dependencies: The dependencies to resolve. Note that this list should already be filtered by its markers.
      resolved_callback: A callback that is invoked with the list of dependencies that have been successfully
        resolved. This is useful for progress reporting.
    """

    from slap.python.dependency import parse_dependencies
    from slap.python.pep508 import filter_dependencies

    graph = DistributionGraph({}, {}, set())

    if dists_cache is None:
        dists_cache = {}

    logger.info("Fetching requirements: <val>%s</val>", dependencies)

    # TODO (@NiklasRosenstein): Should we warn here if the dependencies map is smaller than the dependencies list?
    dependencies_map = {dependency.name: dependency for dependency in dependencies}

    # Resolve the distributions available in the Python environment.
    distributions = {dist_name: dists_cache[dist_name] for dist_name in dependencies_map if dist_name in dists_cache}
    fetch_distributions = dependencies_map.keys() - distributions.keys()
    if fetch_distributions:
        fetched_distributions = env.get_distributions(fetch_distributions)
        distributions.update(fetched_distributions)
        dists_cache.update(fetched_distributions)

    if resolved_callback:
        resolved_callback(distributions)

    # Parse the dependencies of the distributions.
    prefetch_distributions: set[str] = set()
    metadata: dict[str, tuple[DistributionMetadata, list[Dependency]]] = {}
    for dist_name, dist in distributions.items():
        if dist is None:
            graph.missing.add(dist_name)
        else:
            dist_meta = get_distribution_metadata(dist)
            dist_extras = set(dependencies_map[dist_name].extras or [])
            parsed_dependencies = filter_dependencies(
                parse_dependencies(dist_meta.requirements), env.pep508, dist_extras
            )
            metadata[dist_name] = (dist_meta, parsed_dependencies)
            prefetch_distributions |= {dependency.name for dependency in parsed_dependencies}

    # Prefetch distributions.
    prefetch_distributions -= dists_cache.keys()
    if prefetch_distributions:
        dists_cache.update(env.get_distributions(prefetch_distributions))

    # Continue building the graph recursively.
    for dist_name, (dist_meta, parsed_dependencies) in metadata.items():
        graph.metadata[dist_name] = dist_meta

        for dependency in parsed_dependencies:
            graph.dependencies.setdefault(dist_name, set()).add(dependency.name)

        # TODO (@NiklasRosenstein): Potential optimization here is to cache which distributions have already been
        #   resolved; and to pre-fetch all distributions needed in the recursive call in the parent collectively
        #   across all the dependencies of the current set of distributions.
        new_graph = build_distribution_graph(
            env=env,
            dependencies=parsed_dependencies,
            resolved_callback=resolved_callback,
            dists_cache=dists_cache,
        )

        graph.update(new_graph)

    return graph
