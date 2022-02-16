
import os
import subprocess as sp

from slam.application import Application, Command, option
from slam.plugins import ApplicationPlugin
from slam.util.python import Environment

venv_check_option = option(
  "--no-venv-check",
  description="Do not check if the target Python environment is a virtual environment.",
)


def venv_check(cmd: Command, message='refusing to install') -> bool:
  if not cmd.option("no-venv-check"):
    env = Environment.of(cmd.option("python"))
    if not env.is_venv():
      cmd.line_error(f'error: {message} because you are not in a virtual environment', 'error')
      cmd.line_error('       enter a virtual environment or use <opt>--no-venv-check</opt>', 'error')
      return False
  return True


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
    venv_check_option,
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
    if not venv_check(self):
      return 1

    dependencies = []
    for project in self.app.get_projects_in_topological_order():
      if not self.option("no-root") and not self.option("link"):
        dependencies.append(str(project.directory.resolve()))

      dependencies += project.dependencies().run
      if not self.option("no-dev"):
        dependencies += project.dependencies().dev

    sp.call([self.option("python"), "-m", "pip", "install"] + dependencies)

    if self.option("link"):
      self.call("link")
