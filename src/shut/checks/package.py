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

from .core import CheckResult, CheckStatus, Checker, check, register_checker
from shut.model import MonorepoModel, PackageModel, Project
from typing import Iterable, Optional

import os


class PackageChecker(Checker[PackageModel]):

  @check('readme')
  def _check_readme(self, project: Project, package: PackageModel) -> Iterable[CheckResult]:
    if package.get_readme():
      yield CheckResult(CheckStatus.PASSED, 'No README file found.')

  @check('license')
  def _check_license(self, project: Project, package: PackageModel) -> Iterable[CheckResult]:
    if package.data.license and not package.get_license():
      yield CheckResult('license', CheckStatus.WARNING, 'No LICENSE file found.')

    monorepo = project.monorepo
    if package.data.license and monorepo and monorepo.license \
        and monorepo.license != package.data.license:
      yield CheckResult('license-consistency', CheckStatus.ERROR,
        'License is not consistent with parent mono repository (package: {}, monorepo: {}).'
          .format(package.license, monorepo.license))

  @check('classifiers')
  def _check_classifiers(self, project: Project, package: PackageModel) -> Iterable[CheckResult]:
    classifiers = get_classifiers()
    unknown_classifiers = [x for x in package.data.classifiers if x not in classifiers]
    if unknown_classifiers:
      yield CheckResult('classifiers', CheckStatus.WARNING,
        'Unknown classifiers: ' + ', '.join(unknown_classifiers))

  @check('package-config')
  def _check_metadata_completeness(self, project: Project, package: PackageModel) -> Iterable[CheckResult]:
    if not package.data.author:
      yield CheckResult('metadata-completeness', CheckStatus.WARNING, 'no $.package.author')
    if not package.data.license: #and not package.get_private():
      yield CheckResult('metadata-completeness', CheckStatus.WARNING, 'no $.package.license')
    if not package.data.url:
      yield CheckResult('metadata-completeness', CheckStatus.WARNING, 'no $.package.url')

  @check('consistent-author')
  def _check_consistent_author(self, project: Project, package: PackageModel) -> Iterable[CheckResult]:
    metadata = package.get_python_package_metadata()
    if package.data.author and metadata.author != str(package.data.author):
      yield CheckResult(
        CheckStatus.ERROR,
        'Inconsistent package author (package.yaml: {!r} != {}: {!r})'.format(
          str(package.data.author), metadata.filename, metadata.author))

  @check('consistent-version')
  def _check_consistent_version(self, project: Project, package: PackageModel) -> Iterable[CheckResult]:
    metadata = package.get_python_package_metadata()
    if package.data.version and metadata.version != str(package.data.version):
      yield CheckResult(
        CheckStatus.ERROR,
        '{!r} ({}) != {!r} ({})'.format(
          str(package.data.version),
          os.path.basename(package.filename),
          metadata.version,
          os.path.relpath(metadata.filename)))

  @check('typed')
  def _check_typed(self, project: Project, package: PackageModel) -> Iterable[CheckResult]:
    metadata = package.get_python_package_metadata()
    try:
      py_typed_file = os.path.join(metadata.package_directory, 'py.typed')
    except ValueError:
      if package.data.typed:
        yield CheckResult('typed', CheckStatus.WARNING,
          '$.package.typed only works with packages, but this is a module')
    else:
      if os.path.isfile(py_typed_file) and not package.data.typed:
        yield CheckResult('typed', CheckStatus.WARNING,
          'file "py.typed" exists but $.typed is not set')


register_checker(PackageChecker, PackageModel)
