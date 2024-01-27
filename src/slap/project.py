from __future__ import annotations

import dataclasses
import logging
import typing as t
from pathlib import Path

from databind.core.settings import Alias

from slap.configuration import Configuration

if t.TYPE_CHECKING:
    from slap.install.installer import Indexes
    from slap.plugins import ProjectHandlerPlugin
    from slap.python.dependency import Dependency, VersionSpec
    from slap.release import VersionRef
    from slap.repository import Repository
    from slap.util.once import Once


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Dependencies:
    python: VersionSpec | None
    run: t.Sequence[Dependency]
    dev: t.Sequence[Dependency]
    extra: t.Mapping[str, t.Sequence[Dependency]]
    build: t.Sequence[Dependency]
    indexes: Indexes = None  # type: ignore  # To avoid having to import the Indexes class globally

    def __post_init__(self) -> None:
        from slap.install.installer import Indexes

        if self.indexes is None:
            self.indexes = Indexes()  # type: ignore[unreachable]


@dataclasses.dataclass
class Package:
    name: str  #: The name of the package. Contains periods in case of a namespace package.
    path: Path  #: The path to the package directory. This points to the namespace package if applicable.
    root: Path  #: The root directory that contains the package.


@dataclasses.dataclass
class ProjectConfig:
    #: The name of the project handler plugin. If none is specified, the built-in project handlers are tested
    #: (see the #slap.ext.project_handlers module for more info on those).
    handler: str | None = None

    #: The source directory to use when relying on automatic package detection. If not set, the default project
    #: handler will search in `"src/"`` and then `"./"``.
    source_directory: t.Annotated[str | None, Alias("source-directory")] = None

    #: Whether the project source code is intended to be typed.
    typed: bool | None = None

    #: Whether the virtual environment for this project should be shared with other projects in the same repository.
    #: This means that the `.venvs` folder is not checked in the project's folder, but in the repository's folder.
    #: This is useful for monorepos and by default will be inherit from the #Repository.use_shared_venv option. For
    #: non-mono-repos, this doesn't have any effect.
    shared_venv: bool | None = None


class Project(Configuration):
    """Represents one Python project. Slap can work with multiple projects at the same time, for example if the same
    repository or source code project contains multiple individual Python projects. Every project has its own
    configuration, either loaded from `slap.toml` or `pyproject.toml`."""

    #: Reference to the Slap application object.
    repository: Repository

    #: The parsed configuration, accessible as a #Once.
    config: Once[ProjectConfig]

    #: The packages detected with #get_packages() as a #Once.
    packages: Once[t.Sequence[Package] | None]

    #: The packages detected readme as a #Once.
    readme: Once[str | None]

    #: The packages dependencies as a #Once.
    dependencies: Once[Dependencies]

    def __init__(self, repository: Repository, directory: Path) -> None:
        super().__init__(directory)
        from slap.util.once import Once
        from slap.util.toml_file import TomlFile

        self.repository = repository
        self.usercfg = TomlFile(Path("~/.config/slap/config.toml").expanduser())
        self.handler = Once(self._get_project_handler)
        self.config = Once(self._get_project_configuration)
        self.packages = Once(self._get_packages)
        self.readme = Once(self._get_readme)
        self.dependencies = Once(self._get_dependencies)
        self.dist_name = Once(self._get_dist_name)
        self.version = Once(self._get_version)

    def _get_project_configuration(self) -> ProjectConfig:
        """Loads the project-level configuration."""

        from databind.core.settings import ExtraKeys
        from databind.json import load

        return load(self.raw_config(), ProjectConfig, settings=[ExtraKeys(True)])

    def _get_project_handler(self) -> ProjectHandlerPlugin:
        """Returns the handler for this project."""

        from slap.plugins import ProjectHandlerPlugin
        from slap.util.plugins import iter_entrypoints, load_entrypoint

        handler_name = self.config().handler
        if handler_name is None:
            for handler_name, loader in iter_entrypoints(ProjectHandlerPlugin):  # type: ignore[type-abstract]
                handler = loader()()
                if handler.matches_project(self):
                    break
            else:
                raise RuntimeError(f"unable to identify project handler for {self!r}")
        else:
            assert isinstance(handler_name, str), repr(handler_name)
            handler = load_entrypoint(ProjectHandlerPlugin, handler_name)()  # type: ignore[type-abstract]
            assert handler.matches_project(self), (self, handler)
        return handler

    def _get_packages(self) -> list[Package] | None:
        """Returns the packages that can be detected for this project. How the packages are detected depends on the
        #ProjectConfig.packages option."""

        if not self.is_python_project:
            return []
        packages = self.handler().get_packages(self)
        if packages:
            logger.debug(
                "Detected packages for project <subj>%s</subj> by package detector <obj>%s</obj>: <val>%s></val>",
                self,
                self.handler(),
                packages,
            )
        elif self.is_python_project and packages is not None:
            logger.warning(
                "No packages detected for project <subj>%s</subj> by any of package detectors <val>%s</val>",
                self,
                self.handler(),
            )
        return packages

    def _get_dist_name(self) -> str | None:
        return self.handler().get_dist_name(self)

    def _get_readme(self) -> str | None:
        return self.handler().get_readme(self)

    def _get_dependencies(self) -> Dependencies:
        return self.handler().get_dependencies(self)

    def _get_version(self) -> str | None:
        return self.handler().get_version(self)

    def get_version_refs(self) -> list[VersionRef]:
        return self.handler().get_version_refs(self)

    def get_interdependencies(self, projects: t.Sequence[Project], recursive: bool = False) -> list[Project]:
        """Returns the dependencies of this project in the list of other projects. The returned dictionary maps
        to the project and the dependency constraint. This will only take run dependencies into account."""

        dependency_names = set()
        for dep in self.dependencies().run:
            dependency_names.add(dep.name)

        result = []
        for project in projects:
            if project.dist_name() in dependency_names:
                result.append(project)
                if recursive:
                    result += project.get_interdependencies(projects, True)

        return result

    def add_dependency(self, dependency: Dependency, where: str) -> None:
        """Add a dependency to the project configuration.

        Arguments:
          selector: The dependency to add.
          where: The location of where to add the dependency. This is either `'run'`, `'dev'`, or otherwise
            refers to the name of an extra requirement.
        Raises:
          NotImplementedError: If the operation is not supported on the project.
        """

        from slap.python.dependency import Dependency

        assert isinstance(dependency, Dependency), type(dependency)
        self.handler().add_dependency(self, dependency, where)
        self.raw_config.flush()
        self.dependencies.flush()

    @property
    def id(self) -> str:  # type: ignore[override]
        return self.dist_name() or self.directory.resolve().name

    @property
    def is_python_project(self) -> bool:
        return self.pyproject_toml.exists()

    @property
    def shared_venv(self) -> bool:
        """
        If True, the project will share the venv with the other projects from the mono repository. This takes
        precedence over #Repository.use_shared_venv.
        """

        shared_venv = self.config().shared_venv
        if shared_venv is None:
            shared_venv = self.repository.use_shared_venv
        return shared_venv
