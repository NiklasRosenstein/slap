
import collections
import dataclasses
import typing as t

from nr.util.plugins import load_entrypoint

from slam.application import Application, Command, option
from slam.plugins import ApplicationPlugin, CheckPlugin
from slam.check import Check, CheckResult
from slam.project import Project

DEFAULT_PLUGINS = ['changelog', 'general', 'poetry', 'release']
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
  plugins: list[str] = dataclasses.field(default_factory=lambda: DEFAULT_PLUGINS[:])


class CheckCommandPlugin(Command, ApplicationPlugin):
  """ Run sanity checks on your Python project. """

  app: Application
  config: dict[Project, CheckConfig]

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

  def load_configuration(self, app: 'Application') -> dict[Project, CheckConfig]:
    import databind.json
    result = {}
    for project in app.projects:
      config = databind.json.load(project.raw_config().get('check', {}), CheckConfig)
      result[project] = config
    return result

  def activate(self, app: 'Application', config: dict[Project, CheckConfig]) -> None:
    self.app = app
    self.config = config
    app.cleo.add(self)

  def handle(self) -> int:

    counter: t.MutableMapping[CheckResult, int] = collections.defaultdict(int)
    if self.app.is_monorepo:
      for check in self._run_application_checks():
        counter[check.result] += 1
    for project in self.app.projects:
      if not project.is_python_project: continue
      for check in self._run_project_checks(project):
        counter[check.result] += 1

    if self.option("warnings-as-errors") and counter.get(Check.WARNING, 0) > 0:
      exit_code = 1
    elif counter.get(Check.ERROR, 0) > 0:
      exit_code = 1
    else:
      exit_code = 0

    self.line(f'Summary: ' + ', '.join(f'{count} <fg={COLORS[result]};options=bold>{result.name}</fg>'
      for result, count in sorted(counter.items())) + f', exit code: {exit_code}')

    return exit_code

  def _print_checks(self, checks: t.Sequence[Check]) -> None:
    max_w = max(len(c.name) for c in checks)
    for check in checks:

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

  def _run_project_checks(self, project: Project) -> t.Iterator[Check]:
    checks = []
    for plugin_name in sorted(self.config[project].plugins):
      plugin = load_entrypoint(CheckPlugin, plugin_name)()
      for check in sorted(plugin.get_project_checks(project), key=lambda c: c.name):
        check.name = f'{plugin_name}:{check.name}'
        yield check
        checks.append(check)
      if not self.app.is_monorepo:
        for check in sorted(plugin.get_application_checks(self.app), key=lambda c: c.name):
          check.name = f'{plugin_name}:{check.name}'
          yield check
          checks.append(check)

    if checks:
      if self.app.is_monorepo:
        self.line(f'Checks for project <info>{project.id}</info>')
        self.line('')
      self._print_checks(checks)
      self.line('')

  def _run_application_checks(self) -> t.Iterable[Check]:
    plugin_names = {p for project in self.app.projects for p in self.config[project].plugins}
    checks = []
    for plugin_name in sorted(plugin_names):
      plugin = load_entrypoint(CheckPlugin, plugin_name)()
      for check in sorted(plugin.get_application_checks(self.app), key=lambda c: c.name):
        check.name = f'{plugin_name}:{check.name}'
        yield check
        checks.append(check)

    if checks:
      self.line(f'Global checks:')
      self._print_checks(checks)
      self.line('')
