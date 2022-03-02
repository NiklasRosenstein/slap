
import dataclasses
from slam.plugins import RepositoryHandlerPlugin
from slam.project import Project
from slam.repository import Repository
from slam.util.vcs import Vcs, VcsHost, detect_vcs, detect_vcs_host


@dataclasses.dataclass
class DefaultRepositoryConfig:
  #: A list of paths pointing to projects to include in the application invokation. This is useful if multiple
  #: projects should be usable with the Slam CLI in unison. Note that if this option is not set and either no
  #: configuration file exists in the CWD or the `slam.toml` is used, all immediate subdirectories that contain
  #: a `pyproject.toml` will be considered included projects.
  include: list[str] | None = None


class DefaultRepositoryHandler(RepositoryHandlerPlugin):
  """ The default implementation of the repository handler. """

  def matches_repository(self, repository: Repository) -> bool:
    return True

  def get_vcs(self, repository: Repository) -> Vcs | None:
    return detect_vcs(repository.directory)

  def get_vcs_remote(self, repository: Repository) -> VcsHost | None:
    return detect_vcs_host(repository.directory)

  def get_projects(self, repository: Repository) -> list[Project]:
    import databind.json
    from nr.util.fs import is_relative_to
    from slam.project import Project

    projects = []
    if repository.pyproject_toml.exists():
      projects.append(Project(repository, repository.directory))

    raw_config = repository.raw_config().get('repository', {})
    raw_config.pop('handler', None)
    config = databind.json.load(raw_config, DefaultRepositoryConfig)

    if config.include is None or not repository.pyproject_toml.exists():
      for path in repository.directory.iterdir():
        if not path.is_dir(): continue
        project = Project(repository, path)
        if project.pyproject_toml.exists():
          projects.append(project)
    else:
      for subdir in config.include:
        projects.append(Project(repository, repository.directory / subdir))

    return projects
