
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
class PylintTestDriver(BaseTestDriver):
  """
  Runs Pylint.
  """

  env: t.Dict[str, str] = dataclasses.field(default_factory=dict)
  args: t.List[str] = dataclasses.field(default_factory=list)

  def test_package(self, package: 'PackageModel', runtime: Runtime, capture: bool) -> TestRun:
    source_dir = package.get_source_directory()
    metadata = package.get_python_package_metadata()
    path = metadata.package_directory if not metadata.is_single_module else metadata.filename
    command = runtime.python + ['-m', 'pylint', path] + self.args
    return run_program_as_testcase(
      runtime.get_environment(), source_dir, 'pylint',
      command=command, env=self.env, cwd=source_dir, capture=capture)

  def get_test_requirements(self) -> t.List[Requirement]:
    return [Requirement('pylint')]
