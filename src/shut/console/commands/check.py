
import dataclasses
import pkg_resources
import typing as t
from pathlib import Path

from nr.util import Optional
from nr.util.plugins import load_plugins

from shut.console.command import Command
from shut.console.application import Application
from shut.plugins.application_plugin import ApplicationPlugin
from shut.plugins.check_plugin import Check, CheckPlugin as _CheckPlugin, ENTRYPOINT as CHECK_PLUGIN_ENTRYPOINT

COLORS = {
  Check.Result.OK: 'green',
  Check.Result.WARNING: 'magenta',
  Check.Result.ERROR: 'red',
}


@dataclasses.dataclass
class CheckConfig:
  plugins: list[str] = dataclasses.field(default_factory=lambda: ['shut', 'poetry'])


class PoetryChecksPlugin(_CheckPlugin):
  """ Check plugin to validate the Poetry configuration and compare it with Shut's expectations. """

  def get_checks(self, app: 'Application') -> t.Iterable[Check]:
    self.app = app
    self.poetry = app.load_pyproject().get('tool', {}).get('poetry')
    if self.poetry is None:
      return; yield

    yield self._check_poetry_readme()
    yield self._check_poetry_urls()
    yield self._check_poetry_classifiers()
    yield self._check_poetry_license()

  def _check_poetry_readme(self) -> Check:
    check_name = 'poetry readme'
    default_readmes = ['README.md', 'README.rst']
    detected_readme = Optional(self.app.get_readme_path())\
      .map(lambda p: str(p.resolve().relative_to(Path.cwd()))).or_else(None)
    poetry_readme = self.poetry.get('readme')

    if poetry_readme is None and detected_readme in default_readmes:
      return Check(check_name, Check.Result.OK, None, f'Poetry will autodetect your readme ({detected_readme})')
    if poetry_readme == detected_readme:
      return Check(check_name, Check.Result.OK, f'Poetry readme is configured correctly ({detected_readme})', None)
    return Check(check_name, Check.Result.WARNING, f'Poetry readme appears to be misconfigured',
      f'Detected readme: {detected_readme}\nConfigured in Poetry: {poetry_readme}')

  def _check_poetry_urls(self) -> Check:
    return Check('poetry urls', Check.Result.WARNING, 'Not implemented', None)

  def _check_poetry_classifiers(self) -> Check:
    return Check('poetry classifiers', Check.Result.WARNING, 'Not implemented', None)

  def _check_poetry_license(self) -> Check:
    return Check('poetry license', Check.Result.WARNING, 'Not implemented', None)


class ShutChecksPlugin(_CheckPlugin):

  # TODO (@NiklasRosenstein): Check if VCS remote is configured?

  def get_checks(self, app: 'Application') -> t.Iterable[Check]:
    self.app = app
    yield self._check_detect_packages()
    yield self._check_detect_version()
    yield self._check_changelogs()
    yield self._check_py_typed()

  def _check_detect_packages(self) -> Check:
    source_directory, packages = self.app.get_packages()
    return Check(
      'detect packages',
      Check.Result.OK if packages else Check.Result.ERROR,
      ", ".join(f'<b>{p.name}</b>' for p in packages) + f' (source directory: {source_directory})',
      None,
    )

  def _check_detect_version(self) -> Check:
    return Check('__version__', Check.Result.WARNING, 'Not implemented', None)

  def _check_changelogs(self) -> Check:
    return Check('changelogs', Check.Result.WARNING, 'Not implemented', None)

  def _check_py_typed(self) -> Check:
    return Check('py.typed', Check.Result.WARNING, 'Not implemented', None)


class CheckCommand(Command):

  name = "check"
  description = "Perform sanity checks of your project configuration."

  def __init__(self, app: Application):
    super().__init__()
    self.app = app

  def handle(self) -> int:
    import databind.json
    config = databind.json.load(self.app.project_config.extras.get('check', {}), CheckConfig)

    error = False
    for plugin in load_plugins(CHECK_PLUGIN_ENTRYPOINT, _CheckPlugin, names=config.plugins).values():  # type: ignore[misc]  # https://github.com/python/mypy/issues/5374
      for check in plugin.get_checks(self.app):
        error = error or check.result != Check.Result.OK
        color = COLORS[check.result]
        self.io.write(f'<fg={color}>• [{check.result.name}]</fg> <b>{check.name}</b>')
        if check.description:
          self.io.write(f' — {check.description}')
        self.io.write('\n')
        if check.details:
          for line in check.details.splitlines():
            indent = ' ' * (5 + len(check.result.name))
            self.io.write_line(f'{indent}{line}')

    return 1 if error else 0


class CheckPlugin(ApplicationPlugin):

  def activate(self, app: 'Application') -> None:
    app.cleo.add(CheckCommand(app))
