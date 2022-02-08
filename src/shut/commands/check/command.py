
import dataclasses

from shut.application import Application, ApplicationPlugin, Command
from shut.commands.check.api import Check, CheckPlugin
from .builtin import ShutChecksPlugin

COLORS = {
  Check.Result.OK: 'green',
  Check.Result.WARNING: 'magenta',
  Check.Result.ERROR: 'red',
}


@dataclasses.dataclass
class CheckConfig:
  plugins: list[str] = dataclasses.field(default_factory=lambda: ['shut', 'poetry'])


class CheckCommand(Command):
  """
  Run sanity checks on your Python project.
  """

  name = "check"

  def __init__(self, app: Application, config: CheckConfig):
    super().__init__()
    self.app = app
    self.config = config

  def handle(self) -> int:

    error = False
    checks: list[tuple[str, Check]] = []
    for plugin_name, plugin in self.app.plugins.group(CheckPlugin, CheckPlugin):  # type: ignore[misc]
      # TODO (@NiklasRosenstein): Take into account enabled/disabled checks.
      for check in plugin.get_checks(self.app):
        checks.append((plugin_name + ':' + check.name, check))

    for check_id, check in sorted(checks, key=lambda c: c[0]):
      if check.result == Check.Result.SKIPPED:
        continue
      error = error or check.result != Check.Result.OK
      color = COLORS[check.result]
      self.io.write(f'<fg={color};options=bold>{check.result.name.ljust(7)}</fg> <b>{check_id}</b>')
      if check.description:
        self.io.write(f' — {check.description}')
      self.io.write('\n')
      if check.details:
        for line in check.details.splitlines():
          self.io.write_line(f'  {line}')

    return 1 if error else 0


class CheckCommandPlugin(ApplicationPlugin):

  def load_configuration(self, app: 'Application') -> CheckConfig:
    import databind.json
    return databind.json.load(app.raw_config().get('check', {}), CheckConfig)

  def activate(self, app: 'Application', config: CheckConfig) -> None:
    app.plugins.register(CheckPlugin, 'shut', ShutChecksPlugin())
    app.cleo.add(CheckCommand(app, config))
