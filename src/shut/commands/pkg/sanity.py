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

from shore.model import Monorepo
from shore.core.plugins import CheckResult

from . import pkg, load_package_manifest
from nr.stream import Stream
from termcolor import colored
import click
import logging
import sys

logger = logging.getLogger(__name__)


def _run_for_subject(subject, func):  # type: (Union[Package, Monorepo], func) -> List[Any]
  if isinstance(subject, Monorepo):
    subjects = [subject] + sorted(subject.get_packages(), key=lambda x: x.name)
    return [func(x) for x in subjects]
  else:
    return [func(subject)]


def run_checks(package, warnings_as_errors):  # type: (Package, bool) -> bool
  package_name_c = colored(package.name, 'yellow')
  checks = list(Stream.concat(x.get_checks(package) for x in package.get_plugins()))
  if not checks:
    print('✔ no checks triggered on package {}'.format(package_name_c))
    return True

  max_level = max(x.level for x in checks)
  if max_level == CheckResult.Level.INFO:
    status = 0
  elif max_level == CheckResult.Level.WARNING:
    status = 1 if warnings_as_errors else 0
  elif max_level ==  CheckResult.Level.ERROR:
    status = 1
  else:
    assert False, max_level

  icon = '❌' if status != 0 else '✔'
  print(icon, len(checks), 'check(s) triggered on package {}:'.format(package_name_c))

  colors = {'ERROR': 'red', 'WARNING': 'magenta', 'INFO': None}
  for check in checks:
    level = colored(check.level.name, colors[check.level.name])
    print('-', level, check.message)

  logger.debug('exiting with status %s', status)
  return False


@pkg.command()
@click.option('-w', '--warnings-as-errors', is_flag=True)
def sanity(warnings_as_errors):
  """
  Sanity-check the package configuration and package files. Which checks are performed
  depends on the features that are enabled in the package configuration. Usually that
  will at least include the "setuptools" feature which will perform basic sanity checks
  on the package configuration and entrypoint definition.
  """

  package = load_package_manifest()
  result = run_checks(package, warnings_as_errors)
  if not result:
    sys.exit(1)
