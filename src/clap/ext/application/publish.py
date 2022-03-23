
import contextlib
import tempfile
from pathlib import Path

from slap.application import Application, Command, option
from slap.plugins import ApplicationPlugin
from slap.util.python import Pep517BuildBackend


class PublishCommandPlugin(Command, ApplicationPlugin):
  """ A wrapper to publish the Python project to a repository such as PyPI.

  Uses the PEP 517 build system defined in the <code>pyproject.toml</code> to build
  packages and then uploads them with Twine. Note that it currently expects the build
  backend to be installed already.

  The command-line options are almost identical to the <code>twine upload</code> command.

  Note: You can combine the `-d` and `-b` options to effectively perform a build, storing
  the artifacts into the specified directory but not publishing them.
  """

  app: Application

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
    option("dry", "d"),
    option("build-directory", "b", flag=False),
  ]

  def load_configuration(self, app: Application) -> None:
    return None

  def activate(self, app: Application, config: None) -> None:
    self.app = app
    return app.cleo.add(self)

  def handle(self) -> int:
    from twine.settings import Settings
    from twine.commands.upload import upload

    distributions: list[Path] = []

    with contextlib.ExitStack() as stack:
      build_dir = self.option("build-directory")
      if build_dir is None:
        build_dir = stack.enter_context(tempfile.TemporaryDirectory())

      for project in self.app.repository.projects():
        if not project.is_python_project: continue

        self.line(f'Build <info>{project.dist_name()}</info>')
        backend = Pep517BuildBackend(
          project.pyproject_toml.value()['build-system']['build-backend'],
          project.directory,
          Path(build_dir)
        )

        sdist = backend.build_sdist()
        self.line(f'  <comment>{sdist.name}</comment>')
        wheel = backend.build_wheel()
        self.line(f'  <comment>{wheel.name}</comment>')

        distributions += [sdist, wheel]

      if not self.option("dry"):
        kwargs = {option.name.replace('-', '_'): self.option(option.name) for option in self.options}
        kwargs['repository_name'] = kwargs.pop('repository')
        settings = Settings(**kwargs)
        upload(settings, [str(d) for d in distributions])

    return 0
