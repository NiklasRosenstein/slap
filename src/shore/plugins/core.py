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
from shore.model import BaseObject, Monorepo, Package, VersionSelector
from shore.plugins._util import find_readme_file
from shore.util.classifiers import get_classifiers
from shore.util.version import Version
from nr.interface import implements, override
from typing import Iterable, Optional
import collections
import logging
import os
import re

logger = logging.getLogger(__name__)
VersionSelectorRef = collections.namedtuple('VersionSelectorRef', 'filename,start,end,package,sel,new_sel')


@implements(IPackagePlugin, IMonorepoPlugin)
class CorePlugin:

  def _unhandled_keys(self, object: BaseObject) -> Iterable[CheckResult]:
    for path in object.unhandled_keys:
      yield CheckResult(object, CheckResult.Level.WARNING, 'unknown key {}'.format(path))

  @override
  def check_package(self, package: Package) -> Iterable[CheckResult]:
    yield from self._unhandled_keys(package)

    if not find_readme_file(package.directory):
      yield CheckResult(package, 'WARNING', 'No README file found.')

    if not package.get_author():
      yield CheckResult(package, 'WARNING', 'missing $.author')
    if not package.get_license() and not package.get_private():
      yield CheckResult(package, 'WARNING', 'missing $.license')
    if not package.get_url():
      yield CheckResult(package, 'WARNING', 'missing $.url')

    if package.license and package.monorepo and package.monorepo.license \
        and package.monorepo.license != package.license:
      yield CheckResult(package, 'ERROR', '$.license ({!r}) is inconsistent '
        'with monorepo license ({!r})'.format(package.license, package.monorepo.license))

    if package.get_license():
      for name in ('LICENSE', 'LICENSE.txt', 'LICENSE.rst', 'LICENSE.md'):
        filename = os.path.join(package.directory, name)
        if os.path.isfile(filename):
          break
      else:
        yield CheckResult(package, 'WARNING', 'No LICENSE file found.')

    data = package.get_entry_metadata()
    if package.get_author() and data.author != str(package.get_author()):
      yield CheckResult(package, 'ERROR',
        'Inconsistent package author (package.yaml: {!r} != {}: {!r})'.format(
          str(package.get_author()), package.get_entry_file(), data.author))
    if package.get_version() and data.version != str(package.get_version()):
      yield CheckResult(package, 'ERROR',
        'Inconsistent package version (package.yaml: {!r} != {}: {!r})'.format(
          str(package.get_version()), package.get_entry_file(), data.version))

    classifiers = get_classifiers()
    unknown_classifiers = [x for x in package.classifiers if x not in classifiers]
    if unknown_classifiers:
      yield CheckResult(package, 'WARNING',
        'unknown $.classifiers: {}'.format(unknown_classifiers))

    try:
      py_typed_file = os.path.join(package.get_entry_directory(), 'py.typed')
    except ValueError:
      pass
    else:
      if os.path.isfile(py_typed_file) and not package.typed:
        yield CheckResult(package, 'WARNING', 'file "py.typed" exists but $.typed is not set')

  @override
  def check_monorepo(self, monorepo: Monorepo) -> Iterable[CheckResult]:
    yield from self._unhandled_keys(monorepo)

  @override
  def get_package_version_refs(self, package: Package) -> Iterable[VersionRef]:
    ref = self._package_version_ref(package.filename)
    assert ref is not None, "packages must always have a version"
    yield ref

    ref = self._entry_version_ref(package.get_entry_file_abs())
    if ref:
      yield ref

  @override
  def get_monorepo_version_refs(self, monorepo: Monorepo) -> Iterable[VersionRef]:
    ref = self._package_version_ref(monorepo.filename)
    if ref is not None:
      yield ref

  _PACKAGE_VERSION_REGEX = '^version\s*:\s*[\'"]?(.*?)[\'"]?\s*(#.*)?$'
  _ENTRY_VERSION_REGEX = '__version__\s*=\s*[\'"]([^\'"]+)[\'"]'

  def _package_version_ref(self, filename: str) -> Optional[VersionRef]:
    with open(filename) as fp:
      match = re.search(self._PACKAGE_VERSION_REGEX, fp.read(), re.S | re.M)
      if match:
        return VersionRef(filename, match.start(1), match.end(1), match.group(1))
    return None

  def _entry_version_ref(self, filename: str) -> Optional[VersionRef]:
    if not os.path.isfile(filename):
      # This should be captured by the package checks as well.
      return None
    with open(filename) as fp:
      match = re.search(self._ENTRY_VERSION_REGEX, fp.read())
      if match:
        return VersionRef(filename, match.start(1), match.end(1), match.group(1))
    return None


def get_monorepo_interdependency_version_refs(monorepo: Monorepo, new_version: Version) -> Iterable[VersionSelectorRef]:
  """
  Generates #VersionSelectorRef#s for every dependency between packages in *monorepo*
  that needs to be updated.
  """

  regex = re.compile(r'^\s*- +([A-z0-9\.\-_]+) *([^\n:]+)?$', re.M)
  packages = list(monorepo.get_packages())
  package_names = set(p.name for p in packages)

  for package in packages:
    with open(package.filename) as fp:
      content = fp.read()
      for match in regex.finditer(content):
        package_name, version_selector = match.groups()
        if version_selector:
          version_selector = VersionSelector(version_selector)
        new_version_selector = None
        if package_name in package_names and version_selector:
          if not version_selector.matches(new_version):
            if version_selector.is_semver_selector():
              new_version_selector = VersionSelector(str(version_selector)[0] + str(new_version))
            else:
              logger.warning('%s: %s %s does not match version %s of monorepo %s and cannot be automatically bumped.',
                package.filename, name, version_selector, new_version, subject.name)
        if new_version_selector:
          yield VersionSelectorRef(package.filename, match.start(2), match.end(2),
            package_name, str(version_selector), str(new_version_selector))
