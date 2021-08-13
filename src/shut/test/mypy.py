
import dataclasses
import datetime
import logging
import os
import subprocess as sp
import typing as t
from databind.core import annotations as A
from shut.model.requirements import Requirement
from shut.test.base import BaseTestDriver, Runtime, TestCase, TestCrashReport, TestEnvironment, TestRun, TestStatus

if t.TYPE_CHECKING:
  from shut.model.package import PackageModel

log = logging.getLogger(__name__)


@A.union.subtype(BaseTestDriver, 'mypy')
@dataclasses.dataclass
class MypyTestDriver(BaseTestDriver):
  """
  Runs Mypy.
  """

  env: t.Dict[str, str] = dataclasses.field(default_factory=lambda: {'MYPY_FORCE_COLOR': '1'})
  args: t.List[str] = dataclasses.field(default_factory=lambda: ['--check-untyped-defs'])

  def test_package(self, package: 'PackageModel', runtime: Runtime, capture: bool) -> TestRun:
    command = runtime.python + ['-m', 'mypy']
    command += [package.get_source_directory()] + self.args
    log.debug('Running command %s', command)

    env = os.environ.copy()
    env.update(self.env)

    crash: t.Optional[TestCrashReport] = None
    started = datetime.datetime.now()
    try:
      proc = sp.Popen(command, stdout=sp.PIPE, stderr=sp.STDOUT, stdin=sp.DEVNULL, env=env)
      output = proc.communicate()[0].decode()
    except OSError:
      status = TestStatus.ERROR
      crash = TestCrashReport.current_exception()
      output = ''
    else:
      status = TestStatus.PASSED if proc.returncode == 0 else TestStatus.FAILED
    duration = (datetime.datetime.now() - started).total_seconds()
    return TestRun(
      started=started,
      duration=duration,
      status=status,
      environment=runtime.get_environment(),
      tests=[TestCase(
        name='mypy',
        duration=duration,
        filename=package.get_source_directory(),
        lineno=0,
        status=status,
        crash=crash,
        stdout=output,
      )]
    )

  def get_test_requirements(self) -> t.List[Requirement]:
    return [Requirement('mypy')]
