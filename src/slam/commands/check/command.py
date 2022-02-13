
import collections
import dataclasses

from slam.application import Application, ApplicationPlugin, Command, option
from slam.commands.check.api import Check, CheckPlugin
from .builtin import SlamChecksPlugin

COLORS = {
  Check.Result.OK: 'green',
  Check.Result.RECOMMENDATION: 'magenta',
  Check.Result.WARNING: 'yellow',
  Check.Result.ERROR: 'red',
  Check.Result.SKIPPED: 'light_gray',
}


@dataclasses.dataclass
class CheckConfig:
  plugins: list[str] = dataclasses.field(default_factory=lambda: ['slam', 'log', 'poetry', 'release'])


class CheckCommand(Command):
  """
  Run sanity checks on your Python project.
  """

  name = "check"
  options = [
    option(
      "show-skipped",
      description="Show skipped checks.",
    ),
    option(
      "warnings-as-errors", "w",
      description="Treat warnings as errors.",
    )
  ]

  def __init__(self, app: Application, config: CheckConfig):
    super().__init__()
    self.app = app
    self.config = config

  def handle(self) -> int:

    error = False
    checks: list[tuple[str, Check]] = []
    for plugin_name, plugin in self.app.plugins.group(CheckPlugin, CheckPlugin):  # type: ignore[misc]
      # TODO (@NiklasRosenstein): Take into account enabled/disabled checks.
      if plugin_name in self.config.plugins:
        for check in plugin.get_checks(self.app):
          checks.append((plugin_name + ':' + check.name, check))

    max_check_id_len = max(len(check_id) for check_id, _ in checks)
    self.line(f'Checking project {self.app.project_directory}')
    self.line('')
    for check_id, check in sorted(checks, key=lambda c: c[0]):
      if not self.option("show-skipped") and check.result == Check.SKIPPED:
        continue
      if check.result == Check.ERROR:
        error = True
      elif self.option("warnings-as-errors") and check.result == Check.WARNING:
        error = True
      color = COLORS[check.result]
      self.io.write(f'  <b>{check_id.ljust(max_check_id_len)}</b>  <fg={color};options=bold>{check.result.name.ljust(14)}</fg>')
      if check.description:
        self.io.write(f' — {check.description}')
      self.io.write('\n')
      if check.details:
        for line in check.details.splitlines():
          self.io.write_line(f'    {line}')

    exit_code = 1 if error else 0
    counts = collections.Counter(check.result for _, check in checks)
    if not self.option("show-skipped"):
      counts.pop(Check.SKIPPED, None)
    self.line('')
    self.line(f'Summary: ' + ', '.join(f'{count} <fg={COLORS[result]};options=bold>{result.name}</fg>'
      for result, count in sorted(counts.items())) + f', exit code: {exit_code}')

    return exit_code

class CheckCommandPlugin(ApplicationPlugin):

  def load_configuration(self, app: 'Application') -> CheckConfig:
    import databind.json
    return databind.json.load(app.raw_config().get('check', {}), CheckConfig)

  def activate(self, app: 'Application', config: CheckConfig) -> None:
    app.plugins.register(CheckPlugin, 'slam', SlamChecksPlugin())
    app.cleo.add(CheckCommand(app, config))
