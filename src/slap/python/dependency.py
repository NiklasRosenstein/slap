"""
An API to describe dependency specifications in a Python project.

References:

* [PEP 440][]
* [PEP 508][]
* [Poetry Dependencies][]

[PEP 440]: https://peps.python.org/pep-0440/
[PEP 508]: https://peps.python.org/pep-0508/
[Poetry Dependencies]: https://python-poetry.org/docs/dependency-specification/
"""

from __future__ import annotations

import dataclasses
import re
import typing as t
from pathlib import Path
from typing import TypeVar
from urllib.parse import parse_qs, parse_qsl, urlparse, urlunparse

from typing_extensions import TypeAlias

T = TypeVar("T")


class VersionSpec:
    """Represents a version specification, which is either a [PEP 440][] version number, a [PEP 508][]
    dependency specification, or a [Poetry Dependencies][] specification string."""

    def __init__(self, version_spec: str) -> None:
        from poetry.core.packages.dependency import Dependency as _PoetryDependency  # type: ignore[import]

        self.__original = version_spec.strip()
        self.__dependency = _PoetryDependency("", self.__original)

    def __bool__(self) -> bool:
        """Returns `True` if the version spec is initialized from an empty string. Note that it will otherwise
        behave exactly the same as if it was initialized with `*` (matching any package version)."""

        return bool(self.__original) and self.__original != "*"

    def __str__(self) -> str:
        return self.__original

    def __repr__(self) -> str:
        return f"VersionSpec({self.__original!r})"

    def __eq__(self, other: t.Any) -> bool:
        if isinstance(other, VersionSpec):
            return self.__dependency == other.__dependency and bool(self) == bool(other)
        return False

    def to_pep_508(self) -> str:
        # NOTE (@NiklasRosenstein): Removes parentheses around the spec.
        return self.__dependency.to_pep_508().strip()[1:-1]

    def accepts(self, version: str) -> bool:
        """Tests if the version spec accepts the given version string."""

        from poetry.core.constraints.version import Version  # type: ignore[import]

        return self.__dependency.constraint.allows(Version.parse(version))


@dataclasses.dataclass
class Dependency:
    """Base data model for dependency specifications."""

    #: The dependency name.
    name: str

    #: A list of extras to install.
    extras: list[str] | None = None

    #: A [PEP 440][] version or dependency specification or a [Poetry Dependencies][] specification that
    #: specifies the range of Python versions that this dependency should be installed for.
    python: VersionSpec | None = None

    #: A [PEP 508][] environment marker that gives more flexibility as to the conditions that the dependency
    #: should be installed.
    markers: str | None = None

    #: A list of hashes that the installed dependencies' package must match. Each value must be a combined string
    #: of the hash algorithm with the hash value separated by a colon. Note that this may not be supported by all
    #: dependency types (e.g. #GitDependency).
    hashes: list[str] | None = None


@dataclasses.dataclass
class _PypiDependency:
    name: str

    #: The version specification for the package.
    version: VersionSpec

    #: The alias of a PyPI index to install the package from.
    source: str | None = None


@dataclasses.dataclass
class _GitDependency:
    name: str

    #: The repository URL to get the Python package from.
    url: str

    #: The revision of the repository. Should not be combined with #branch or #tag.
    rev: str | None = None

    #: The branch of the repository. Should not be combined with #branch or #tag.
    branch: str | None = None

    #: The tag of the repository. Should not be combined with #branch or #tag.
    tag: str | None = None


@dataclasses.dataclass
class _PathDependency:
    name: str

    #: The path from which to install the Python package from.
    path: Path

    #: Whether the package should be installed in development mode.
    develop: bool = False

    #: Whether the package should be symlinked.
    link: bool = False


@dataclasses.dataclass
class _UrlDependency:
    name: str

    #: The URL to get the package to install from.
    url: str


@dataclasses.dataclass
class _MultiDependency:
    name: str

    #: Defines multiple possible ways to install a dependency. Each dependency should differ in their #Dependency.python
    #: and/or #Dependency.marker specification.
    dependencies: list[Dependency]


@dataclasses.dataclass
class PypiDependency(Dependency, _PypiDependency):
    """A dependency on a package in a Python Package Index."""

    @staticmethod
    def parse(value: str) -> PypiDependency:
        """Parses a package name and its version spec from a string."""

        value, markers = value.partition(";")[::2]

        match = re.match(r"\s*[^<>=!~\^\(\)\*]+", value)
        if match:
            name = match.group(0)
            constraint = value[match.end() :].strip() or "*"
            if constraint.startswith("("):
                if not constraint.endswith(")"):
                    raise ValueError(f"invalid version constraint {constraint!r}")
                constraint = constraint[1:-1].strip()
            version_spec = VersionSpec(constraint)  # noqa: E203
        else:
            name = value
            version_spec = VersionSpec("")

        name, extras = split_package_name_with_extras(name)
        return PypiDependency(name=name, version=version_spec, extras=extras, markers=markers.strip() or None)

    @staticmethod
    def parse_list(lst: t.Iterable[str]) -> list[PypiDependency]:
        """Parses a list of strings as #PypiDependency#s."""

        return [PypiDependency.parse(x) for x in lst]


@dataclasses.dataclass
class GitDependency(Dependency, _GitDependency):
    """A dependency on a Python package that can be installed from a Git repository."""


@dataclasses.dataclass
class PathDependency(Dependency, _PathDependency):
    """A dependency on a Python package that can be installed from a Path."""


@dataclasses.dataclass
class UrlDependency(Dependency, _UrlDependency):
    """A dependency on a Python package that can be installed from a URL."""


@dataclasses.dataclass
class MultiDependency(Dependency, _MultiDependency):
    """Express multiple possible ways to install a Python package."""


#: Represents a dependency configuration that does not contain the dependency name, such as is used for example
#: by Poetry. A plain string is parsed like a dependency string (see #parse_dependency_string()), while a dictionary
#: represents a more complex dependency configuration that can be parsed into other types of dependencies as well.
DependencyConfig: TypeAlias = "str | dict[str, t.Any] | list[dict[str, t.Any]]"


def split_package_name_with_extras(value: str) -> tuple[str, list[str] | None]:
    """Splits *value* as a string that contains a package name and optionally its extras into components."""

    match = re.match(r"\s*([^\[\]]+?)?\s*(?:\[([^\[\]]+)\])?\s*$", value)
    if not match:
        raise ValueError(f"invalid package name with extras: {value!r}")

    extras = [x.strip() for x in match.group(2).split(",")] if match.group(2) else None
    if extras is not None and not all(extras):
        raise ValueError(f"invalid package name with extras: {value!r}")

    return match.group(1), extras


def parse_dependency_string(value: str) -> Dependency:
    """
    Convert *value* to a representation as a #Dependency subclass.

    * In addition to the [PEP 508][] dependency specification, the function supports a `--hash` option as is also
      supported by Pip. Hashes in URL fragments are also parsed into #Dependency.hashes.
    * URL formatted specifications can also be Git repository URLs or paths (must be in Posix format as absolute
      path, or an explicit relative path, i.e. begin with curdir or pardir).

    Args:
      value: The dependency specification.
    Raises:
      ValueError: If the string cannot be parsed into a #Dependency.

    !!! note A URL or Git dependency must still contain a package name (i.e. be of the form `<name> @ <url>`). If
      a URL or Git repository URL is encountered without a package name, a #ValueError is raised.
    """

    value = value.strip()
    if value.startswith("http://") or value.startswith("https://") or value.startswith("git+"):
        raise ValueError(f"A plain URL or Git repository URL must be prefixed with a package name: {value!r}")

    # Extract trailing options from the dependency.
    hashes: list[str] = []

    def handle_option(match: re.Match) -> str:
        if match.group(1) == "hash":
            hashes.append(match.group(2))
        return ""

    value = re.sub(r"\s--(\w+)=(.*)(\s|$)", handle_option, value)

    # Check if it's a dependency of the form `<name> @ <package>`. This can be either a
    # #UrlDependency or #GitDependency.
    if "@" in value:
        markers: str | None
        name, url = value.partition("@")[::2]
        name, extras = split_package_name_with_extras(name)
        url, markers = url.partition(";")[::2]
        markers = markers.strip() or None
        urlparts = urlparse(url.strip())

        # Remove the fragments from the URL.
        url = urlunparse((urlparts.scheme, urlparts.netloc, urlparts.path, urlparts.params, urlparts.query, None))

        # Parse it as a Git URL.
        if url.startswith("git+"):

            def unpack(val: t.Sequence[T] | None) -> T | None:
                return val[0] if val else None

            options = parse_qs(urlparts.fragment)
            return GitDependency(
                name=name,
                url=url[4:],
                rev=unpack(options.get("rev")),
                branch=unpack(options.get("branch")),
                tag=unpack(options.get("tag")),
                extras=extras,
                markers=markers,
                hashes=hashes or None,
            )

        # Parse it as a path.
        elif url.startswith("/") or url.startswith("./") or url.startswith("../"):
            options = parse_qs(urlparts.fragment)
            return PathDependency(
                name=name,
                path=Path(url),
                develop="develop" in options,
                link="link" in options,
                extras=extras,
                markers=markers,
                hashes=hashes or None,
            )

        elif urlparts.scheme:
            # Treat all fragments as hash options.
            hashes += [f"{item[0]}:{item[1]}" for item in parse_qsl(urlparts.fragment)]
            return UrlDependency(
                name=name,
                url=url,
                extras=extras,
                markers=markers,
                hashes=hashes or None,
            )

        else:
            raise ValueError(f"invalid URL-formatted dependency: {value!r}")

    # TODO (@NiklasRosenstein): Support parsing path dependencies.

    dependency = PypiDependency.parse(value)
    dependency.hashes = hashes or None
    return dependency


def _parse_single_dependency_config(name: str, dep: str | dict[str, t.Any]) -> Dependency:
    """Convert a single dependency expressed as a table or dictionary to a Slap dependency specification.

    Examples:

        >>> _parse_single_dependency_config('foo', 'git+https://github.com/foo/foo.git') == GitDependency('foo', 'https://github.com/foo/foo.git')
        >>> _parse_single_dependency_config('foo', {'version': '1.2.3'}) == PypiDependency('foo', VersionSpec('1.2.3'))
        >>> _parse_single_dependency_config('foo', {'git': 'https://...'}) == GitDependency('foo', 'https://...')
    """  # noqa: E501

    dependency: Dependency

    if isinstance(dep, str):
        dep = dep.strip()

        # Check if the dependency specification appears to be in URL format.
        if (
            dep.startswith("git+")
            or dep.startswith("http://")
            or dep.startswith("https://")
            or dep.startswith("../")
            or dep.startswith("./")
            or dep.startswith("/")
        ):
            dependency = parse_dependency_string(f"{name} @ {dep}")
        else:
            # If dep is _just_ a version number, we need to prefix it with a = to ensure the PypiDependency
            # is parsed correctly.
            dep = dep.strip()
            if dep and dep[0].isnumeric():
                dep = f"={dep}"
            dependency = parse_dependency_string(f"{name} {dep}")

    elif "git" in dep:
        dependency = GitDependency(
            name=name, url=dep["git"], rev=dep.get("rev"), branch=dep.get("branch"), tag=dep.get("tag")
        )

    elif "path" in dep:
        # NOTE (@NiklasRosenstein): The "link" key is actually not a Poetry feature, but it won't complain if
        #   you are just using Slap anyway.
        dependency = PathDependency(
            name=name, path=Path(dep["path"]), develop=dep.get("develop", False), link=dep.get("link", False)
        )

    elif "url" in dep:
        dependency = UrlDependency(name=name, url=dep["url"])

    elif "version" in dep:
        dependency = PypiDependency(
            name=name,
            version=VersionSpec(dep["version"]),
            source=dep.get("source"),
        )

    else:
        raise ValueError(f"Cannot interpret dependency: {name} = {dep!r}")

    if not isinstance(dep, str):
        dependency.python = VersionSpec(dep["python"]) if dep.get("python") else None
        dependency.markers = dep.get("markers")
        dependency.extras = dep.get("extras")

    return dependency


def parse_dependency_config(name: str, dep: DependencyConfig) -> Dependency:
    """Converts a dependency configuration. This "happens" to be compatible with the Poetry configuration format."""

    if isinstance(dep, (dict, str)):
        dependency = _parse_single_dependency_config(name, dep)
    elif isinstance(dep, list):
        dependency = MultiDependency(name, [_parse_single_dependency_config(name, x) for x in dep])
    else:
        raise ValueError(f"Cannot interpret dependency: {name} = {dep!r}")

    return dependency


def parse_dependencies(dependencies: list[str] | dict[str, DependencyConfig]) -> list[Dependency]:
    """Converts Poetry dependencies to Slap dependencies.

    Args:
      dependencies: Either a list of strings (for example used in the `tool.poetry.extras` section where you just
        specify a list of strings that contain the package name and version spec as one), or a dictionary mapping
        the dependency name to its specification. The specification can be a list of specifications to describe a
        #MultiDependency.
    """

    if isinstance(dependencies, list):
        return [parse_dependency_string(dep) for dep in dependencies]

    elif isinstance(dependencies, dict):
        return [parse_dependency_config(key, value) for key, value in dependencies.items()]

    else:
        raise TypeError(type(dependencies))
