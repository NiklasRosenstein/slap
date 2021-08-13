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

import logging
import os
import subprocess as sp
import sys
from typing import List, Optional

import click
import typing as t
from databind.core.annotations import typeinfo
from nr.stream import Stream
from termcolor import colored

from shut.commands import shut
from shut.model.package import PackageModel
from shut.test import Runtime, TestRun, TestStatus, Virtualenv
from shut.utils.text import indent_text
from . import pkg, project

log = logging.getLogger(__name__)


def test_package(
  package: PackageModel,
  isolate: bool,
  keep_test_env: bool = False,
  capture: bool = True,
  install_test_reqs: t.Optional[bool] = None,
  only: Optional[List[str]] = None,
) -> t.Iterator[TestRun]:
  drivers = package.get_test_drivers()
  if not drivers:
    raise RuntimeError('package has no test driver configured')

  if only is not None:
    drivers_by_name = {typeinfo.get_name(type(d)): d for d in drivers}
    try:
      drivers = [drivers_by_name[k] for k in only]
    except KeyError as exc:
      raise RuntimeError(f'package has no "{exc}" test driver configured')

  venv: Optional[Virtualenv] = None
  if isolate:
    venv = Virtualenv(os.path.join(package.get_directory(), '.venv-test'))
    if venv.exists():
      print('Re-using existing virtual environment at .venv-test ...')
    else:
      print('Creating temporary virtual environment at .venv-test ...')
      venv.create(Runtime.from_env())
    runtime = venv.get_runtime()
    print(f'Installing package "{package.name}" and test requirements ...')
    try:
      orig_cwd = os.getcwd()
      os.chdir(package.get_directory())
      shut(['pkg', '--no-checks', 'install', '--pip', venv.bin('pip'), '--extra', 'test', '-q'], standalone_mode=False)
    except SystemExit as exc:
      os.chdir(orig_cwd)
      if exc.code != 0:
        raise
  else:
    runtime = Runtime.from_env()

  if install_test_reqs is None:
    install_test_reqs = runtime.is_venv()
    if not install_test_reqs:
      log.warning('Not installing test driver requirements because it doesn\'t look like you are in a local '
        'Python environment (environment: %s)', runtime.get_environment())

  if install_test_reqs:
    test_reqs = Stream(
      [req.to_setuptools() for req in driver.get_test_requirements()]
      for driver in drivers).concat().collect()
    if test_reqs:
      log.info('Installing test requirements %s...', test_reqs)
      sp.check_call(runtime.pip + ['install', '-q'] + test_reqs)

  try:
    for driver in drivers:
      yield driver.test_package(package, runtime, capture)
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
  print(status_line)
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

  if n_passed < len(test_run.tests):
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
  help='Install test requirements required by the driver. This is enabled by default unless this '
       'command is run not from a virtual environment.')
def test(isolate: bool, keep_test_env: bool, capture: bool, install: t.Optional[bool]) -> None:
  """
  Run the package's unit tests.
  """

  package = project.load_or_exit(expect=PackageModel)
  num_passed = 0
  num_tests = 0
  for test_run in test_package(package, isolate, keep_test_env, capture, install):
    num_tests += 1
    print_test_run(test_run)
    if test_run.status in (TestStatus.PASSED, TestStatus.SKIPPED):
      num_passed += 1

  sys.exit(0 if num_passed == num_tests else 1)
