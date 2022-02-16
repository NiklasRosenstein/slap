
import os
import subprocess as sp
from slam.application import Application, Command, option
from slam.plugins import ApplicationPlugin


class InstallCommandPlugin(Command, ApplicationPlugin):
  """ Install your project and its dependencies via Pip. """

  app: Application
  name = "install"
  options = [
    option(
      "--link",
      description="Symlink the root project using <opt>slam link</opt> instead of installing it directly.",
    ),
    option(
      "--no-dev",
      description="Do not install development dependencies.",
    ),
    option(
      "--no-root",
      description="Do not install the package itself, but only its dependencies.",
    ),
    option(
      "--no-venv-check",
      description="Do not check if the target Python environment is a virtual environment.",
    ),
    option(
      "--python", "-p",
      description="The Python executable to install to.",
      flag=False,
      default=os.getenv('PYTHON', 'python'),
    )
  ]

  def load_configuration(self, app: Application) -> None:
    return None

  def activate(self, app: Application, config: None) -> None:
    self.app = app
    app.cleo.add(self)

  def handle(self) -> int:
    dependencies = []

    # TODO: venv check

    for project in self.app.get_projects_in_topological_order():
      if not self.option("no-root") and not self.option("link"):
        dependencies.append(str(project.directory.resolve()))

      dependencies += project.dependencies().run
      if not self.option("no-dev"):
        dependencies += project.dependencies().dev

    sp.call([self.option("python"), "-m", "pip", "install"] + dependencies)

    if self.option("link"):
      self.call("link")
