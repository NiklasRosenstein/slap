# -*- coding: utf8 -*-
# Copyright (c) 2019 Niklas Rosenstein
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

from shore.core.plugins import CheckResult, FileToRender, IPackagePlugin, IMonorepoPlugin, VersionRef
from shore.model import BaseObject, Monorepo, Package
from shore.plugins._util import find_readme_file
from shore.util.classifiers import get_classifiers
from nr.interface import implements, override
from typing import Iterable, Optional
import os
import re


@implements(IPackagePlugin, IMonorepoPlugin)
class CorePlugin:

  def _unhandled_keys(self, object: BaseObject) -> Iterable[CheckResult]:
    for path in object.unhandled_keys:
      yield CheckResult(object, CheckResult.Level.WARNING, 'unknown key {}'.format(path))

  @override
  def check_package(self, package: Package) -> Iterable[CheckResult]:
    yield from self._unhandled_keys(package)

    for name in ('LICENSE', 'LICENSE.txt', 'LICENSE.rst', 'LICENSE.md'):
      filename = os.path.join(package.directory, name)
      if os.path.isfile(filename):
        break
    else:
      yield CheckResult(package, 'WARNING', 'No LICENSE file found.')

    if not find_readme_file(package.directory):
      yield CheckResult(package, 'WARNING', 'No README file found.')

    if not package.get_author():
      yield CheckResult(package, 'WARNING', 'missing $.author')
    if not package.get_license():
      yield CheckResult(package, 'WARNING', 'missing $.license')
    if not package.get_url():
      yield CheckResult(package, 'WARNING', 'missing $.url')

    data = package.get_entry_metadata()
    rel_entry_file = os.path.relpath(package.get_entry_file(), package.directory)
    if package.get_author() and data.author != str(package.get_author()):
      yield CheckResult(package, 'ERROR',
        'Inconsistent package author (package.yaml: {!r} != {}: {!r})'.format(
          data.author, rel_entry_file, str(package.get_author())))
    if package.get_version() and data.version != str(package.get_version()):
      yield CheckResult(package, 'ERROR',
        'Inconsistent package version (package.yaml: {!r} != {}: {!r})'.format(
          data.version, rel_entry_file, str(package.get_version())))

    classifiers = get_classifiers()
    unknown_classifiers = [x for x in package.classifiers if x not in classifiers]
    if unknown_classifiers:
      yield CheckResult(package, 'WARNING',
        'unknown $.classifiers: {}'.format(unknown_classifiers))

  @override
  def get_package_version_refs(self, package: Package) -> Iterable[VersionRef]:
    ref = self._version_ref(package.filename)
    assert ref is not None, "packages must always have a version"
    yield ref

  @override
  def get_monorepo_version_refs(self, monorepo: Monorepo) -> Iterable[VersionRef]:
    ref = self._version_ref(monorepo.filename)
    if ref is not None:
      yield ref

  _VERSION_REGEX = '^version\s*:\s*[\'"]?(.*?)[\'"]?\s*(#.*)?$'

  def _version_ref(self, filename: str) -> Optional[VersionRef]:
    with open(filename) as fp:
      match = re.search(self._VERSION_REGEX, fp.read(), re.S | re.M)
      if match:
        return VersionRef(filename, match.start(1), match.end(1), match.group(1))
    return None
