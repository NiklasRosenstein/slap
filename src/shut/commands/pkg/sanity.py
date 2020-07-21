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

from shore.util.classifiers import get_classifiers

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


class CheckResult:
  """
  Represents a sanity check result.
  """

  class Level(enum.IntEnum):
    INFO = 0
    WARNING = 1
    ERROR = 2

  def __init__(self, on: PackageModel, level: Union[str, Level], message: str):
    if isinstance(level, str):
      level = self.Level[level]
    assert isinstance(level, self.Level)
    self.on = on
    self.level = level
    self.message = message

  def __repr__(self):
    return 'CheckResult(on={!r}, level={}, message={!r})'.format(
      self.on, self.level, self.message)


def sanity_check_package(project: Project, package: PackageModel) -> Iterable[CheckResult]:
  for path in package.unknown_keys:
    yield CheckResult(package, CheckResult.Level.WARNING, 'unknown key {}'.format(path))

  if not package.get_readme():
    yield CheckResult(package, 'WARNING', 'No README file found.')

  classifiers = get_classifiers()
  unknown_classifiers = [x for x in package.data.classifiers if x not in classifiers]
  if unknown_classifiers:
    yield CheckResult(package, 'WARNING',
      'unknown $.classifiers: {}'.format(unknown_classifiers))

  if not package.data.author:
    yield CheckResult(package, 'WARNING', 'missing $.package.author')
  if not package.data.license: #and not package.get_private():
    yield CheckResult(package, 'WARNING', 'missing $.license')
  if not package.data.url:
    yield CheckResult(package, 'WARNING', 'missing $.url')

  if package.data.license and project.monorepo and project.monorepo.license \
      and project.monorepo.license != package.data.license:
    yield CheckResult(package, 'ERROR', '$.license ({!r}) is inconsistent '
      'with monorepo license ({!r})'.format(package.license, package.monorepo.license))

  if package.data.license:
    for name in ('LICENSE', 'LICENSE.txt', 'LICENSE.rst', 'LICENSE.md'):
      filename = os.path.join(os.path.dirname(package.filename), name)
      if os.path.isfile(filename):
        break
    else:
      yield CheckResult(package, 'WARNING', 'No LICENSE file found.')

  metadata = package.get_python_package_metadata()
  if package.data.author and metadata.author != str(package.data.author):
    yield CheckResult(package, 'ERROR',
      'Inconsistent package author (package.yaml: {!r} != {}: {!r})'.format(
        str(package.data.author), metadata.filename, metadata.author))
  if package.data.version and metadata.version != str(package.data.version):
    yield CheckResult(package, 'ERROR',
      'Inconsistent package version (package.yaml: {!r} != {}: {!r})'.format(
        str(package.data.version), metadata.filename, metadata.version))

  try:
    py_typed_file = os.path.join(metadata.package_directory, 'py.typed')
  except ValueError:
    if package.data.typed:
      yield CheckResult(package, 'WARNING', '$.package.typed only works with packages, but this is a module')
  else:
    if os.path.isfile(py_typed_file) and not package.data.typed:
      yield CheckResult(package, 'WARNING', 'file "py.typed" exists but $.typed is not set')


def print_package_checks(project: Project, package: PackageModel, warnings_as_errors: bool = False) -> bool:
  """
  Formats the checks created with #sanity_check_package().
  """

  package_name_c = colored(package.data.name, 'yellow')
  checks = list(sanity_check_package(project, package))
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

  package = project.load(expect=PackageModel)
  result = print_package_checks(project, package, warnings_as_errors)
  if not result:
    sys.exit(1)
