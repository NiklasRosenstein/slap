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

import sys

import click
from termcolor import colored

from shut.commands.pkg.test import test_package, print_test_run
from shut.model.monorepo import MonorepoModel
from shut.test.base import TestStatus
from . import mono, project


@mono.command()
@click.option('--isolate/--no-isolate', default=False,
  help='Isolate all test runs in virtual environments. This greatly increases the duration '
       'for tests to run as the environment needs to be created and packages installed first, '
       'but it ensures that the unit tests work for a vanilla installation (default: false)')
@click.option('--capture/--no-capture', default=True,
  help='Capture the output of the underlying testing framework. If set to false, the output '
       'will be routed to stderr (default: true)')
def test(isolate: bool, capture: bool) -> None:
  """
  Run unit tests for all packages in the mono repository.
  """

  monorepo = project.load_or_exit(expect=MonorepoModel)
  exit_code = 0
  for package in project.packages:
    if package.test.driver:
      print(f'Testing package {colored(package.name, "yellow", attrs=["bold"])}:')
      print()
      test_run = test_package(package, isolate, capture)
      print_test_run(test_run)
      if test_run.status != TestStatus.PASSED:
        exit_code = 1

  sys.exit(exit_code)
