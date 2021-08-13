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
import hashlib
import logging
import json
import os
import subprocess as sp
import sys
import traceback
from pathlib import Path
from typing import List, Optional

import click
import typing as t
from databind.core.annotations import typeinfo
from nr.stream import Stream
from termcolor import colored

from shut.commands import shut
from shut.commands.pkg.install import collect_requirement_args
from shut.model.package import PackageModel
from shut.test import Runtime, TestRun, TestStatus, Virtualenv
from shut.utils.text import indent_text
from . import pkg, project

log = logging.getLogger(__name__)


class _TestReqsInstalledTracker:
  """
  Internal. Helper class to track if we installed test driver requirements into an environment before.
  We use this as a performance optimization to avoid kicking off `pip install` if we don't need to.
  """

  def __init__(self, package: PackageModel, runtime: Runtime) -> None:
    self.package = package
    self.runtime = runtime

  def get_cache_filename(self) -> Path:
    if self.package.project.monorepo:
      directory = self.package.project.monorepo.get_directory()
    else:
      directory = self.package.get_directory()
    return Path(directory) / 'build' / '.shut' / 'test-reqs-installed-status.json'

  def get_requirements_hash(self, reqs: t.List[str]) -> str:
    reqs_str = ','.join(sorted(reqs)).lower()
    return hashlib.md5(f'{reqs_str}-{self.runtime.get_hash_code()}'.encode()).hexdigest()

  def get_stored_hash(self) -> Optional[str]:
    " Retrieves the currently stored hash. "

    filename = self.get_cache_filename()
    if not filename.exists():
      return None
    return json.loads(filename.read_text()).get(self.runtime.get_executable_path(), {}).get(self.package.name)

  def store_hash(self, hash: str) -> None:
    " Stores a new hash in the cache. "

    filename = self.get_cache_filename()
    data = json.loads(filename.read_text()) if filename.exists() else {}
    data.setdefault(self.runtime.get_executable_path(), {})[self.package.name] = hash
    filename.parent.mkdir(parents=True, exist_ok=True)
    filename.write_text(json.dumps(data))


def test_package(
  package: PackageModel,
  isolate: bool,
  keep_test_env: bool = False,
  capture: bool = True,
  install_test_reqs: t.Optional[bool] = None,
  only: Optional[List[str]] = None,
  quiet: bool = False,
) -> t.Iterator[t.Tuple[str, TestRun]]:
  drivers = package.get_test_drivers()
  if not drivers:
    raise RuntimeError('package has no test driver configured')

  if only is not None:
    drivers_by_name = {typeinfo.get_name(type(d)): d for d in drivers}
    try:
      drivers = [drivers_by_name[k] for k in only]
    except KeyError as exc:
      raise RuntimeError(f'package has no "{exc}" test driver configured')

  q = ['-q'] if quiet else []
  venv: Optional[Virtualenv] = None
  if isolate:
    if install_test_reqs is not None and not install_test_reqs:
      log.warning('--no-install is not compatible with --isolate, this will most likely result in an error '
        'when invoking the test drivers.')
    venv = Virtualenv(os.path.join(package.get_directory(), '.venv-test'))
    if venv.exists():
      print('Re-using existing virtual environment at .venv-test ...')
    else:
      print('Creating temporary virtual environment at .venv-test ...')
      venv.create(Runtime.from_env())
    runtime = venv.get_runtime()
    print(f'Installing package "{package.name}"...')
    try:
      orig_cwd = os.getcwd()
      os.chdir(package.get_directory())
      shut(['pkg', '--no-checks', 'install', '--pip', venv.bin('pip')] + q, standalone_mode=False)
    except SystemExit as exc:
      os.chdir(orig_cwd)
      if exc.code != 0:
        raise
  else:
    runtime = Runtime.from_env()

  test_reqs = Stream(
    [req.to_setuptools() for req in driver.get_test_requirements()]
    for driver in drivers).concat().collect()
  test_reqs += collect_requirement_args(package, develop=False, inter_deps=False, extra={'test'},
    skip_main_requirements=True)
  helper = _TestReqsInstalledTracker(package, runtime)
  reqs_hash = helper.get_requirements_hash(test_reqs)

  if install_test_reqs is None and test_reqs:
    if helper.get_stored_hash() == reqs_hash:
      log.debug('Skipping installation of test driver requirements because it appears we installed them before. This is '
        'a performance optimization that can be skipped using the --install option explicitly.')
    elif not runtime.is_venv():
      log.warning('Skipping installation of test driver requirements because it doesn\'t look like you are in a local '
        'Python environment (environment: %s)', runtime.get_environment())
    else:
      install_test_reqs = True

  if install_test_reqs and test_reqs:
    log.info('Installing test driver requirements %s...', test_reqs)
    sp.check_call(runtime.pip + ['install'] + q + test_reqs)
    helper.store_hash(reqs_hash)

  try:
    for driver in drivers:
      driver_name = typeinfo.get_name(type(driver))
      started = datetime.datetime.now()
      try:
        print('[{time}] Running test driver {driver} for package {pkg}'.format(
          driver=colored(driver_name, 'cyan'),
          pkg=colored(package.name, 'cyan', attrs=['bold']),
          time=datetime.datetime.now()))
        yield driver_name, driver.test_package(package, runtime, capture)
      except Exception:
        yield driver_name, TestRun(
          started=started,
          duration=(datetime.datetime.now() - started).total_seconds(),
          status=TestStatus.ERROR,
          environment=runtime.get_environment(),
          tests=[],
          errors=[],
          error=traceback.format_exc()
        )
  finally:
    if venv and not keep_test_env:
      venv.rm()


def print_test_run(test_run: TestRun) -> None:
  if test_run.status == TestStatus.ERROR:
    print(f'There was an unexpected error when running the tests.')
    if test_run.error:
      print()
      print(colored(indent_text(test_run.error.strip(), 4), 'red'))
      print()

  sorted_tests = sorted(test_run.tests, key=lambda t: t.name)

  # Print a summary.
  n_passed = sum(1 for t in test_run.tests if t.status == TestStatus.PASSED)
  n_skipped = sum(1 for t in test_run.tests if t.status == TestStatus.SKIPPED)
  status_line = (
    f'Ran {len(test_run.tests)} test(s) in {test_run.duration:.3f}s '
    f'({n_passed} passed, {n_skipped} skipped, {len(test_run.tests) - n_passed - n_skipped} failed, '
    f'{len(test_run.errors)} error(s)). {test_run.status.name}')
  print()
  for test in sorted_tests:
    color = {
      TestStatus.PASSED: 'green',
      TestStatus.SKIPPED: 'yellow',
      TestStatus.FAILED: 'red',
      TestStatus.ERROR: 'magenta'
    }[test.status]
    print(f'  {colored(test.name, color, attrs=["bold"])} {test.status.name}')
  if sorted_tests:
    print()

  if (n_passed + n_skipped) < len(test_run.tests):
    # Print error details.
    print('Failed test details:')
    print('====================')
    not_passed_not_skipped = lambda t: t.status not in (TestStatus.PASSED, TestStatus.SKIPPED)
    for i, test in enumerate(filter(not_passed_not_skipped, sorted_tests)):
      print()
      line = f'  {colored(test.name, "red", attrs=["bold"])} ({test.filename}:{test.lineno})'
      print(line)
      print('  ' + '-' * (len(line) - 2))
      print()
      if test.crash:
        print(indent_text(test.crash.longrepr, 6))
      if test.stdout:
        print('\n  captured stdout:\n')
        print(indent_text(test.stdout, 6))
    print()

  if test_run.errors:
    header = f'Encountered {len(test_run.errors)} error(s)'
    print(header)
    print('=' * len(header))
    for err in test_run.errors:
      print()
      if err.filename:
        print(f'  {colored(err.filename, "red")}')
        print('  ' + '-' * len(err.filename))
        print()
      else:
        print('  ----')
      print(indent_text(err.longrepr, 6))
    print()

  print(colored(status_line))


@pkg.command()
@click.option('--isolate/--no-isolate', default=False,
  help='Isolate all test runs in virtual environments. This greatly increases the duration '
       'for tests to run as the environment needs to be created and packages installed first, '
       'but it ensures that the unit tests work for a vanilla installation (default: false)')
@click.option('--keep-test-env', is_flag=True,
  help='Do not delete the virtual environment created when testing with --isolate.')
@click.option('--capture/--no-capture', default=True,
  help='Capture the output of the underlying testing framework. If set to false, the output '
       'will be routed to stderr (default: true)')
@click.option('--install/--no-install', default=None,
  help='Install test driver requirements required by the driver. This is enabled by default unless this '
       'command is run not from a virtual environment. Shut performs a minor optimization in that '
       'it skips the installation if it appears to have installed the dependencies before (you can '
       'pass --install explicitly to ensure that the test driver requirements are installed before invoking '
       'the test drivers).')
@click.option('-q', '--quiet', is_flag=True, help='Quiet Pip install of test requirements.')
def test(isolate: bool, keep_test_env: bool, capture: bool, install: t.Optional[bool], quiet: bool) -> None:
  """
  Run the package's unit tests.
  """

  package = project.load_or_exit(expect=PackageModel)
  num_passed = 0
  num_tests = 0
  for _driver_name, test_run in test_package(package, isolate, keep_test_env, capture, install, None, quiet):
    num_tests += 1
    print_test_run(test_run)
    print()
    if test_run.status in (TestStatus.PASSED, TestStatus.SKIPPED):
      num_passed += 1

  sys.exit(0 if num_passed == num_tests else 1)
