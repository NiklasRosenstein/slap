
import dataclasses
import datetime
import logging
import os
import subprocess as sp
import typing as t
from databind.core import annotations as A
from shut.model.requirements import Requirement
from shut.test.base import BaseTestDriver, Runtime, TestCase, TestCrashReport, TestEnvironment, TestRun, TestStatus, run_program_as_testcase

if t.TYPE_CHECKING:
  from shut.model.package import PackageModel

log = logging.getLogger(__name__)


@dataclasses.dataclass
class MypyTestDriver(BaseTestDriver):
  """
  Runs Mypy.
  """

  NAME = 'mypy'

  env: t.Dict[str, str] = dataclasses.field(default_factory=lambda: {'MYPY_FORCE_COLOR': '1'})
  args: t.List[str] = dataclasses.field(default_factory=lambda: ['--check-untyped-defs'])

  def test_package(self, package: 'PackageModel', runtime: Runtime, capture: bool) -> TestRun:
    source_dir = package.get_source_directory()
    command = runtime.python + ['-m', 'mypy']
    command += [source_dir] + self.args
    return run_program_as_testcase(
      runtime.get_environment(), source_dir, 'mypy',
      command=command, env=self.env, cwd=package.get_directory(), capture=capture)

  def get_test_requirements(self) -> t.List[Requirement]:
    return [Requirement('mypy')]
