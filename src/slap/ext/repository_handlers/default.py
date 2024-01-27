import dataclasses
import typing as t

from databind.core.settings import Alias

from slap.plugins import RepositoryHandlerPlugin
from slap.project import Project
from slap.repository import Repository, RepositoryHost
from slap.util.fs import get_file_in_directory
from slap.util.vcs import Vcs, detect_vcs


@dataclasses.dataclass
class DefaultRepositoryConfig:
    #: A list of paths pointing to projects to include in the application invokation. This is useful if multiple
    #: projects should be usable with the Slap CLI in unison. Note that if this option is not set and either no
    #: configuration file exists in the CWD or the `slap.toml` is used, all immediate subdirectories that contain
    #: a `pyproject.toml` will be considered included projects.
    include: list[str] | None = None

    #: The repository hosting service. If not specified, it will be detected automatically.
    repository_host: t.Annotated[RepositoryHost | None, Alias("repository-host")] = None


class DefaultRepositoryHandler(RepositoryHandlerPlugin):
    """The default implementation of the repository handler.

    Applies only if either

    * A VCS can be detected (and projects are loaded from the VCS root).
    * If a README file, LICENSE file, or a Pyproject or Slap configuration file exists. This is to avoid mistakenly
      considering a directory that contains independent Python projects as a mono-repository.

    !!! note

        In a future version, this handler may update the #Repository.directory to point to the VCS root directory
        (if a VCS can be detected) to allow using the Slap CLI from a subdirectory as if it were used in the root
        directory.
    """

    def _get_config(self, repository: Repository) -> DefaultRepositoryConfig:
        import databind.json

        raw_config = repository.raw_config().get("repository", {})
        raw_config.pop("handler", None)
        config = databind.json.load(raw_config, DefaultRepositoryConfig)
        return config

    def matches_repository(self, repository: Repository) -> bool:
        if repository.pyproject_toml.exists() or repository.slap_toml.exists():
            return True
        # NOTE(@NiklasRosenstein): This is where we would update the repository root directory.
        # vcs = self.get_vcs(repository)
        # if vcs is not None:
        #   repository.__init__(vcs.get_toplevel())
        #   return True
        if get_file_in_directory(repository.directory, "readme", [], case_sensitive=False):
            return True
        if get_file_in_directory(repository.directory, "license", [], case_sensitive=False):
            return True
        return False

    def get_vcs(self, repository: Repository) -> Vcs | None:
        return detect_vcs(repository.directory)

    def get_repository_host(self, repository: Repository) -> RepositoryHost | None:
        from slap.util.plugins import iter_entrypoints

        config = self._get_config(repository)
        if config.repository_host:
            return config.repository_host
        for _plugin_name, loader in iter_entrypoints(RepositoryHost):  # type: ignore[type-abstract]
            if instance := loader().detect_repository_host(repository):
                return instance
        return None

    def get_projects(self, repository: Repository) -> list[Project]:
        from slap.project import Project

        projects = []
        if repository.pyproject_toml.exists():
            projects.append(Project(repository, repository.directory))

        config = self._get_config(repository)
        if config.include is None or not repository.pyproject_toml.exists():
            for path in repository.directory.iterdir():
                if not path.is_dir():
                    continue
                project = Project(repository, path)
                if project.pyproject_toml.exists():
                    projects.append(project)
        else:
            for subdir in config.include:
                projects.append(Project(repository, repository.directory / subdir))

        return projects
