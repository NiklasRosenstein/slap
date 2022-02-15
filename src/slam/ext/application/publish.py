
import os
import importlib
from pathlib import Path
import tempfile
from slam.application import Application, Command, option
from slam.plugins import ApplicationPlugin


class BuildBackend:
  """ A wrapper around a [PEP 517][] build backend.

    [PEP 517]: https://www.python.org/dev/peps/pep-0517/
  """

  class _InternalBackend:
    def build_sdist(self, sdist_directory: str, config_settings: dict | None) -> str: ...
    def build_wheel(self, wheel_directory: str, config_settings: dict | None, metadata_directory:  str | None = None) -> str: ...

  _module: _InternalBackend

  def __init__(self, name: str, project_directory: Path, build_directory: Path) -> None:
    self.name = name
    self.project_directory = project_directory.resolve()
    self.build_directory = build_directory.resolve()
    self._module = importlib.import_module(name)

  def __repr__(self) -> str:
    return f'BuildBackend("{self.name}")'

  def build_sdist(self, config_settings: dict[str, str | list[str]] | None = None) -> Path:
    old_cwd = Path.cwd()
    try:
      os.chdir(self.project_directory)
      filename = self._module.build_sdist(str(self.build_directory), config_settings)
      return self.build_directory / filename
    finally:
      os.chdir(old_cwd)

  def build_wheel(self, config_settings: dict[str, str | list[str]] | None = None) -> Path:
    old_cwd = Path.cwd()
    try:
      os.chdir(self.project_directory)
      filename = self._module.build_wheel(str(self.build_directory), config_settings, None)
      return self.build_directory / filename
    finally:
      os.chdir(old_cwd)


class PublishCommand(Command):
  """ A wrapper to publish the Python project to a repository such as PyPI.

  Uses the PEP 517 build system defined in the <code>pyproject.toml</code> to build
  packages and then uploads them with Twine. Note that it currently expects the build
  backend to be installed already.

  The command-line options are almost identical to the <code>twine upload</code> command.
  """

  name = "publish"

  options = [
    option("repository", "r", flag=False, default='pypi'),
    option("repository-url", flag=False),
    option("sign", "s"),
    option("sign-with", flag=False),
    option("identity", "i", flag=False),
    option("username", "u", flag=False),
    option("password", "p", flag=False),
    option("non-interactive"),
    option("comment", "c", flag=False),
    option("config-file", flag=False, default="~/.pypirc"),
    option("skip-existing"),
    option("cert", flag=False),
    option("client-cert", flag=False),
    #option("verbose"),
    option("disable-progress-bar"),
  ]

  def __init__(self, app: Application):
    super().__init__()
    self.app = app

  def handle(self) -> int:
    from twine.settings import Settings
    from twine.commands.upload import upload

    distributions: list[Path] = []

    with tempfile.TemporaryDirectory() as tmpdir:
      for project in self.app.projects:
        if not project.is_python_project: continue

        self.line(f'Build <info>{project.get_dist_name()}</info>')
        backend = BuildBackend(
          project.pyproject_toml.value()['build-system']['build-backend'],
          project.directory,
          Path(tmpdir)
        )

        sdist = backend.build_sdist()
        self.line(f'  <comment>{sdist.name}</comment>')
        wheel = backend.build_wheel()
        self.line(f'  <comment>{wheel.name}</comment>')

        distributions += [sdist, wheel]

      kwargs = {option.name.replace('-', '_'): self.option(option.name) for option in self.options}
      kwargs['repository_name'] = kwargs.pop('repository')
      settings = Settings(**kwargs)
      upload(settings, [str(d) for d in distributions])


class PublishCommandPlugin(ApplicationPlugin):

  def load_configuration(self, app: Application) -> None:
    return None

  def activate(self, app: Application, config: None) -> None:
    return app.cleo.add(PublishCommand(app))
