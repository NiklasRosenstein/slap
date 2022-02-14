
import collections
import dataclasses
import typing as t

from nr.util.plugins import load_entrypoint

from slam.application import Application, Command, option
from slam.plugins import ApplicationPlugin, CheckPlugin
from slam.check import Check
from slam.project import Project

COLORS = {
  Check.Result.OK: 'green',
  Check.Result.RECOMMENDATION: 'magenta',
  Check.Result.WARNING: 'yellow',
  Check.Result.ERROR: 'red',
  Check.Result.SKIPPED: 'light_gray',
}


@dataclasses.dataclass
class CheckConfig:
  #: A list of checks that are enabled for the project.
  enable: list[str] = dataclasses.field(default_factory=lambda: ['general', 'poetry'])#, 'poetry', 'release'])


class CheckCommand(Command):
  """ Run sanity checks on your Python project. """

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

    counter: t.Mapping[Check.Result, int] = collections.defaultdict(int)
    for project in self.app.projects:
      for check in self._run_checks(project, self.app.is_monorepo):
        counter[check.result] += 1

    if self.option("warnings-as-errors") and counter.get(Check.WARNING, 0) > 0:
      exit_code = 1
    elif counter.get(Check.ERROR, 0) > 0:
      exit_code = 1
    else:
      exit_code = 0

    self.line('')
    self.line(f'Summary: ' + ', '.join(f'{count} <fg={COLORS[result]};options=bold>{result.name}</fg>'
      for result, count in sorted(counter.items())) + f', exit code: {exit_code}')

    return exit_code

  def _run_checks(self, project: Project, print_project_header: bool) -> t.Iterator[Check]:

    import databind.json
    config = databind.json.load(project.raw_config().get('check', {}), CheckConfig)

    plugins: dict[str, CheckPlugin] = {}
    for plugin_name in config.enable:
      plugins[plugin_name] = load_entrypoint(CheckPlugin, plugin_name)()

    checks = []
    for plugin_name, plugin in sorted(plugins.items(), key=lambda t: t[0]):
      for check in sorted(plugin.get_checks(project), key=lambda c: c.name):
        check.name = f'{plugin_name}:{check.name}'
        yield check
        checks.append(check)

    max_w = max(len(c.name) for c in checks)

    for check in checks:

      if print_project_header:
        self.line(f'Checks for project <info>{project.id}</info>')
        self.line('')
        print_project_header = False

      if not self.option("show-skipped") and check.result == Check.SKIPPED:
        continue

      color = COLORS[check.result]
      self.io.write(f'  <b>{check.name.ljust(max_w)}</b>  <fg={color};options=bold>{check.result.name.ljust(14)}</fg>')
      if check.description:
        self.io.write(f' — {check.description}')
      self.io.write('\n')

      if check.details:
        for line in check.details.splitlines():
          self.io.write_line(f'    {line}')


class CheckCommandPlugin(ApplicationPlugin):

  def load_configuration(self, app: 'Application') -> None:
    return None

  def activate(self, app: 'Application', config: None) -> None:
    app.cleo.add(CheckCommand(app, None))
