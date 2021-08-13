# -*- coding: utf8 -*-
# Copyright (c) 2020 Niklas Rosenstein
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

import datetime
import json
import os
import subprocess as sp
import sys
from dataclasses import dataclass, field
from datetime import timezone
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
from typing_extensions import Annotated

from databind.core import annotations as A
from nr.parsing.date import tzlocal

from shut.model.requirements import Requirement
from .base import (BaseTestDriver, Runtime, StackTrace, TestCase, TestCrashReport,
  TestEnvironment, TestError, TestRun, TestStatus)

if TYPE_CHECKING:
  from shut.model.package import PackageModel


def load_report_file(report_file: str) -> TestRun:
  """
  Loads a Pytest-json-report file into a #TestRun.
  """

  with open(report_file) as fp:
    raw = json.load(fp)

  started_time = datetime.datetime.fromtimestamp(raw['created']).replace(tzinfo=tzlocal()).astimezone(timezone.utc)
  duration = raw['duration']
  status = TestStatus.PASSED if raw['exitcode'] == 0 else TestStatus.FAILED
  environment = TestEnvironment(raw['environment']['Python'], raw['environment']['Platform'])
  errors: List[TestError] = []
  tests: List[TestCase] = []

  # Map the nodes to the line and function that they are defined in.
  # NOTE (NiklasRosenstein): This key is not present when there are no test cases or
  #   when parallelizing tests with pytest-xdist.
  testid_to_source: Dict[str, Tuple[str, int]] = {}
  for node in raw.get('collectors', []):
    if node['nodeid'] and node['result']:
      for result in node['result']:
        if 'lineno' in result:
          testid_to_source[result['nodeid']] = (node['nodeid'], result['lineno'])
    if node['outcome'] != 'passed':
      errors.append(TestError(node['nodeid'], node['longrepr']))

  # Collect the test results.
  for test in raw['tests']:
    failed_stage = next((test[k] for k in ('setup', 'call', 'teardown')
      if k in test and test[k]['outcome'] == 'failed'), None)
    crash: Optional[TestCrashReport] = None
    stdout: str = ''
    if failed_stage:
      crash = TestCrashReport(
        filename=failed_stage['crash']['path'],
        lineno=failed_stage['crash']['lineno'],
        message=failed_stage['crash']['message'],
        traceback=[StackTrace(trace['path'], trace['lineno'], trace['message']) for trace in failed_stage['traceback']],
        longrepr=failed_stage['longrepr'],
      )
      stdout = failed_stage.get('stdout')
    test_status = {'passed': TestStatus.PASSED, 'failed': TestStatus.FAILED, 'skipped': TestStatus.SKIPPED}[test['outcome'].lstrip('x')]
    if test['nodeid'] in testid_to_source:
      filename, lineno = testid_to_source[test['nodeid']]
    else:
      filename = test['nodeid'].partition('::')[0]
      lineno = test['lineno']
    tests.append(TestCase(
      name=test['nodeid'],
      duration=sum(test[k]['duration'] for k in ('setup', 'call', 'teardown') if k in test),
      filename=filename,
      lineno=lineno,
      status=test_status,
      crash=crash,
      stdout=stdout,
    ))

  return TestRun(started_time, duration, status, environment, tests, errors)


@A.union.subtype(BaseTestDriver, 'pytest')
@dataclass
class PytestDriver(BaseTestDriver):
  """
  A driver for running unit tests using [Pytest][1].

  [1]: https://docs.pytest.org/en/latest/
  """

  directory: Optional[str] = None
  args: List[str] = field(default_factory=lambda: ['-vv'])
  report_file: Annotated[str, A.alias('report-file')] = '.pytest-report.json'
  parallelism: int = 1

  # BaseTestDriver

  def test_package(self, package: 'PackageModel', runtime: Runtime, capture: bool) -> TestRun:
    test_dir = os.path.join(package.source_directory, self.directory) if self.directory else package.source_directory
    test_dir = os.path.join(package.get_directory(), test_dir)
    command = runtime.python + ['-m', 'pytest', test_dir]
    command += ['--json-report', '--json-report-file', self.report_file]
    if self.parallelism != 1:
      command += ['-n', str(self.parallelism)]
    command += self.args

    if os.path.isfile(self.report_file):
      os.remove(self.report_file)

    started_time = datetime.datetime.now(timezone.utc)
    proc = sp.Popen(command, stdout=sp.PIPE if capture else sys.stderr,
      stderr=sp.STDOUT if capture else None)
    output, _ = proc.communicate()
    result = proc.wait()

    if os.path.isfile(self.report_file):
      test_run = load_report_file(self.report_file)
      if result != 0:
        test_run.status = TestStatus.FAILED
      os.remove(self.report_file)
    else:
      test_run = TestRun(
        started=started_time,
        duration=(datetime.datetime.now(timezone.utc) - started_time).total_seconds(),
        status=TestStatus.ERROR,
        environment=runtime.get_environment(),
        tests=[],
        errors=[TestError(None, output.decode())],
      )

    return test_run

  def get_test_requirements(self) -> List[Requirement]:
    reqs = [
      Requirement.parse('pytest'),
      Requirement.parse('pytest-json-report ^1.2.1'),
    ]
    if self.parallelism > 1:
      reqs += [Requirement.parse('pytest-xdist')]
    return reqs
