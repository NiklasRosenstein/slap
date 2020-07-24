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

from shut.checks import CheckStatus, get_checks
from shut.commands.pkg import pkg, project
from shut.model import PackageModel, Project

from nr.stream import Stream
from termcolor import colored
from typing import Iterable, Union
import click
import enum
import logging
import os
import sys

logger = logging.getLogger(__name__)


def print_package_checks(project: Project, package: PackageModel, warnings_as_errors: bool = False) -> int:
  icons = {
    CheckStatus.PASSED: '✔️',
    CheckStatus.WARNING: '⚠️',
    CheckStatus.ERROR: '❌'}

  colors = {
    CheckStatus.PASSED: 'green',
    CheckStatus.WARNING: 'magenta',
    CheckStatus.ERROR: 'red'}

  package_name_c = colored(package.data.name, 'yellow')
  checks = sorted(get_checks(project, package), key=lambda c: c.name)

  print()
  for check in checks:
    print(' ', icons[check.result.status], check.name, end='')
    if check.result.status != CheckStatus.PASSED:
      print(':', check.result.message)
    else:
      print()

  print()
  print('run', len(checks), 'check(s) for package', package_name_c)
  print()

  max_level = max(x.result.status for x in checks)
  if max_level == CheckStatus.PASSED:
    status = 0
  elif max_level == CheckStatus.WARNING:
    status = 1 if warnings_as_errors else 0
  elif max_level ==  CheckStatus.ERROR:
    status = 1
  else:
    assert False, max_level

  logger.debug('exiting with status %s', status)
  return status


@pkg.command()
@click.option('-w', '--warnings-as-errors', is_flag=True)
def checks(warnings_as_errors):
  """
  Sanity-check the package configuration and package files. Which checks are performed
  depends on the features that are enabled in the package configuration. Usually that
  will at least include the "setuptools" feature which will perform basic sanity checks
  on the package configuration and entrypoint definition.
  """

  package = project.load(expect=PackageModel)
  sys.exit(print_package_checks(project, package, warnings_as_errors))
