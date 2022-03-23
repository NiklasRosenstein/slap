
import subprocess as sp
from clap.application import Application, Command, argument
from clap.plugins import ApplicationPlugin


class RunCommandPlugin(Command, ApplicationPlugin):
  """ Run a command configured in <code>[tool.clap.run]</code>"""

  name = "run"
  arguments = [
    argument(
      "cmd",
      description="The name of the command to run as it is defined under the <code>clap.run</code> section.",
    ),
  ]

  def load_configuration(self, app: Application) -> dict[str, str]:
    project = app.main_project()
    if project:
      return project.raw_config().get('run', {})
    return {}

  def activate(self, app: Application, config: dict[str, str]) -> None:
    self.app = app
    self.config = config
    app.cleo.add(self)

  def handle(self) -> int:
    command = self.argument("cmd")
    if command not in self.config:
      self.line_error(f'error: command \"{command}\" does not exist', 'error')
      return 1
    return sp.call(self.config[command], shell=True)
