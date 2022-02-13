
import typing as t

from slam.application import Application
from .api import Check, CheckPlugin


class SlamChecksPlugin(CheckPlugin):

  # TODO (@NiklasRosenstein): Check if VCS remote is configured?

  def get_checks(self, app: 'Application') -> t.Iterable[Check]:
    self.app = app
    yield self._check_detect_packages()
    yield self._check_py_typed()

  def _check_detect_packages(self) -> Check:
    packages = self.app.get_packages()
    return Check(
      'packages',
      Check.Result.OK if packages else Check.Result.ERROR,
      'Detected ' + ", ".join(f'<b>{p.root}/{p.name}</b>' for p in packages)
    )

  def _check_py_typed(self) -> Check:
    check_name = 'typed'
    expect_typed = self.app.raw_config().get('typed')
    if expect_typed is None:
      return Check(check_name, Check.Result.WARNING, '<b>tool.slam.typed</b> is not set')

    has_py_typed = set[str]()
    has_no_py_typed = set[str]()
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
