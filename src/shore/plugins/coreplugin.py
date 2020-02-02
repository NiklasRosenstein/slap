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

from shore.core.plugins import CheckResult, IPlugin, PluginContext
from nr.interface import implements
from typing import Iterable
import os


@implements(IPlugin)
class CorePlugin:

  def __init__(self, options):
    pass

  @classmethod
  def get_options(self):
    return; yield

  def perform_checks(self, context: PluginContext) -> Iterable[CheckResult]:
    items = list(filter(bool, [context.monorepo] + context.packages))
    for item in items:
      for path in item.unhandled_keys:
        yield CheckResult(item, CheckResult.Level.WARNING, 'unknown key {}'.format(path))

    for package in context.packages:
      for name in ('LICENSE', 'LICENSE.txt', 'LICENSE.rst', 'LICENSE.md'):
        filename = os.path.join(package.directory, name)
        if os.path.isfile(filename):
          break
      else:
        yield CheckResult(package, 'WARNING', 'No LICENSE file found.')

    if not package.package.author:
      yield CheckResult(package, 'WARNING', 'missing $.package.author')
    if not package.package.license:
      yield CheckResult(package, 'WARNING', 'missing $.package.license')
    if not package.package.url:
      yield CheckResult(package, 'WARNING', 'missing $.package.url')

    data = package.load_entry_file_data()
    if package.package.author and data.author != str(package.package.author):
      yield CheckResult(package, 'ERROR',
        'Inconsistent package author ({!r} != {!r})'.format(
          data.author, str(package.package.author)))
    if package.package.version and data.version != package.package.version:
      yield CheckResult(package, 'ERROR',
        'Inconsistent package version ({!r} != {!r})'.format(
          data.version, package.package.version))

  def get_files_to_render(self, context):
    return; yield
