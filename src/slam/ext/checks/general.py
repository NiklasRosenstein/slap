
import typing as t

from slam.plugins import CheckPlugin
from slam.check import Check
from slam.project import Project


class GeneralChecksPlugin(CheckPlugin):

  # TODO (@NiklasRosenstein): Check if VCS remote is configured?

  def get_project_checks(self, project: Project) -> t.Iterable[Check]:
    yield self._check_detect_packages(project)
    yield self._check_py_typed(project)

  def _check_detect_packages(self, project: Project) -> Check:
    packages = project.packages()
    return Check(
      'packages',
      Check.Result.SKIPPED if packages is None else Check.Result.OK if packages else Check.Result.ERROR,
      'Detected ' + ", ".join(f'<b>{p.root}/{p.name}</b>' for p in packages) if packages else None
    )

  def _check_py_typed(self, project: Project) -> Check:
    check_name = 'typed'
    expect_typed = project.config().typed
    if expect_typed is None:
      return Check(check_name, Check.Result.WARNING, '<b>tool.slam.typed</b> is not set')

    has_py_typed = set[str]()
    has_no_py_typed = set[str]()
    for package in project.packages() or []:
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
