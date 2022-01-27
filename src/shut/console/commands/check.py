
import dataclasses
import typing as t
from pathlib import Path

from cleo.io.io import IO
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
    check_name = 'poetry:readme'
    default_readmes = ['README.md', 'README.rst']
    detected_readme = Optional(self.app.get_readme_path())\
      .map(lambda p: str(p.resolve().relative_to(Path.cwd()))).or_else(None)
    poetry_readme = self.poetry.get('readme')

    if poetry_readme is None and detected_readme in default_readmes:
      return Check(
        check_name,
        Check.Result.OK,
        f'Poetry will autodetect your readme (<b>{detected_readme}</b>)'
      )

    if poetry_readme == detected_readme:
      return Check(
        check_name,
        Check.Result.OK,
        f'Poetry readme is configured correctly (path: <b>{detected_readme}</b>)'
      )

    return Check(
      check_name,
      Check.Result.WARNING,
      f'Poetry readme appears to be misconfigured (detected: <b>{detected_readme}</b>, configured: <b>{poetry_readme}</b>)'
    )

  def _check_poetry_urls(self) -> Check:
    has_homepage = 'homepage' not in self.poetry
    return Check(
      'poetry:urls',
      Check.Result.OK if has_homepage else Check.Result.WARNING,
      '<info>tool.poetry.homepage</info> is not configured' if not has_homepage else
        '<b>tool.poetry.homepage</b> is configured'
    )

  def _check_poetry_classifiers(self) -> Check:
    return Check('poetry:classifiers', Check.Result.SKIPPED, 'Not implemented')

  def _check_poetry_license(self) -> Check:
    return Check('poetry:license', Check.Result.SKIPPED, 'Not implemented')


class ShutChecksPlugin(_CheckPlugin):

  # TODO (@NiklasRosenstein): Check if VCS remote is configured?

  def get_checks(self, app: 'Application') -> t.Iterable[Check]:
    self.app = app
    yield self._check_detect_packages()
    yield self._check_source_version()
    yield self._check_changelogs()
    yield self._check_py_typed()

  def _check_detect_packages(self) -> Check:
    packages = self.app.get_packages()
    return Check(
      'shut:packages',
      Check.Result.OK if packages else Check.Result.ERROR,
      'Detected ' + ", ".join(f'<b>{p.root}/{p.name}</b>' for p in packages)
    )

  def _check_source_version(self) -> Check:
    from cleo.io.null_io import NullIO
    from shut.console.commands.release import SourceCodeVersionMatcherPlugin
    check_name = 'shut:version-in-code'
    packages = self.app.get_packages()
    if not packages:
      return Check(check_name, Check.Result.WARNING, 'No packages detected')
    matcher = SourceCodeVersionMatcherPlugin(packages)
    version_refs = matcher.get_version_refs(NullIO())
    packages_without_version = {p.name for p in packages}
    for ref in version_refs:
      for package in packages:
        if ref.file.is_relative_to(package.path):
          packages_without_version.discard(package.name)
    return Check(
      check_name,
      Check.Result.ERROR if packages_without_version else Check.Result.OK,
      (f'The following packages have no <b>__version__</b>: <b>{", ".join(packages_without_version)}</b>')
        if packages_without_version else
        f'Found <b>__version__</b> in <b>{", ".join(x.name for x in packages)}</b>')

  def _check_changelogs(self) -> Check:
    from databind.core import ConversionError
    from shut.console.commands.log import ChangelogApplication
    changelog = ChangelogApplication(self.app)
    bad_changelogs = []
    count = 0
    for entry in changelog.manager.all():
      count += 1
      try:
        changelog.validate_entry(entry.load())
      except (ConversionError, ValueError):
        bad_changelogs.append(entry.path.name)
    check_name = 'shut:validate-changelogs'
    if not count:
      return Check(check_name, Check.Result.SKIPPED, None)
    return Check(
      check_name,
      Check.Result.ERROR if bad_changelogs else Check.Result.OK,
      f'Broken or invalid changelogs: {", ".join(bad_changelogs)}' if bad_changelogs else
        f'All {count} changelogs are valid.',
    )

  def _check_py_typed(self) -> Check:
    check_name = 'shut:typed'
    expect_typed = self.app.project_config.typed
    if expect_typed is None:
      return Check(check_name, Check.Result.WARNING, '<b>tool.shut.typed</b> is not set')

    has_py_typed = set()
    has_no_py_typed = set()
    for package in self.app.get_packages():
      (has_py_typed if (package.path / 'py.typed').is_file() else has_no_py_typed).add(package.name)

    if expect_typed and has_no_py_typed:
      error = True
      message = f'<b>py.typed</b> missing in package(s) <b>{", ".join(has_py_typed)}</b>'
    elif not expect_typed and has_py_typed:
      error = True
      message = f'<b>py.typed</b> in package(s) should not exist <b>{", ".join(has_py_typed)}</b>'
    else:
      error = False
      message = '<b>py.typed</b> exists as expected' if expect_typed else '<b>py.typed</b> does not exist as expected'

    return Check(
      check_name,
      Check.Result.ERROR if error else Check.Result.OK,
      message
    )


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
    checks = []
    for plugin in load_plugins(CHECK_PLUGIN_ENTRYPOINT, _CheckPlugin, names=config.plugins).values():  # type: ignore[misc]  # https://github.com/python/mypy/issues/5374
      for check in plugin.get_checks(self.app):
        checks.append(check)

    for check in sorted(checks, key=lambda c: c.name):
      if check.result == Check.Result.SKIPPED:
        continue
      error = error or check.result != Check.Result.OK
      color = COLORS[check.result]
      self.io.write(f'<fg=light_{color}>{check.result.name.ljust(7)}</fg> <b>{check.name}</b>')
      if check.description:
        self.io.write(f' — {check.description}')
      self.io.write('\n')

    return 1 if error else 0


class CheckPlugin(ApplicationPlugin):

  def activate(self, app: 'Application') -> None:
    app.cleo.add(CheckCommand(app))
