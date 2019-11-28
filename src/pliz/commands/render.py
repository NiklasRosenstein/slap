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

""" Renders monorepo and package files. """

from .base import PlizCommand
from ..render import render_monorepo, render_package
from termcolor import colored

def _get_package_warnings(package):  # type: (Package) -> Iterable[str]
  package = package.package
  if not package.author:
    yield 'missing ' + colored('$.package.author', 'yellow')
  if not package.license:
    yield 'missing ' + colored('$.package.license', 'yellow')
  if not package.url:
    yield 'missing ' +  colored('$.package.url', 'yellow')


class RenderCommand(PlizCommand):

  name = 'render'
  description = __doc__

  def execute(self, parser, args):
    super(RenderCommand, self).execute(parser, args)
    monorepo, package = self.get_configuration()
    if monorepo:
      packages = [package] if package else monorepo.list_packages()
      render_monorepo(monorepo)
      for package in packages:
        self._package_warnings(package)
        render_package(package)
    else:
      self._package_warnings(package)
      render_package(package)
    print(package)

  def _package_warnings(self, package):
    warnings = list(_get_package_warnings(package))
    if warnings:
      print(colored('WARNINGS', 'magenta', attrs=['bold']),
        '({}) for package'.format(len(warnings)),
        colored(package.package.name, 'cyan', attrs=['bold']),
        '({})'.format(package.directory))
      for warning in warnings:
        print('  |', warning)
