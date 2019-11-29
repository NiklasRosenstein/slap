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
from ..render import IRenderer
from termcolor import colored
import os


def _get_package_warnings(package):  # type: (Package) -> Iterable[str]
  package = package.package
  if not package.author:
    yield 'missing ' + colored('$.package.author', attrs=['bold'])
  if not package.license:
    yield 'missing ' + colored('$.package.license', attrs=['bold'])
  if not package.url:
    yield 'missing ' +  colored('$.package.url', attrs=['bold'])


class RenderCommand(PlizCommand):

  name = 'render'
  description = __doc__

  def update_parser(self, parser):
    super(RenderCommand, self).update_parser(parser)
    parser.add_argument('--dry', action='store_true', help='Dry rendering. '
      'Output a list of files that would be rendered instead of actually '
      'rendering them.')

  def execute(self, parser, args):
    super(RenderCommand, self).execute(parser, args)
    monorepo, package = self.get_configuration()
    if monorepo:
      packages = [package] if package else monorepo.list_packages()
      self._render_monorepo(monorepo)
      for package in packages:
        self._render_package(package)
    else:
      self._render_package(package)

  def _render_monorepo(self, monorepo):
    self._print_title(monorepo.project.name, monorepo.directory, [])
    files = []
    for impl in IRenderer.implementations():
      files.extend(impl().files_for_monorepo(monorepo))
    self._render_files(monorepo.directory, files)

  def _render_package(self, package):
    self._print_title(package.package.name, package.directory,
      _get_package_warnings(package))
    files = []
    for impl in IRenderer.implementations():
      files.extend(impl().files_for_package(package))
    self._render_files(package.directory, files)

  def _print_title(self, name, directory, warnings):
    print(
      colored('RENDER', 'blue', attrs=['bold']),
      name,
      colored('({})'.format(directory), 'grey', attrs=['bold']),
      end=' ')

    warnings = list(warnings)
    if warnings:
      print(colored('{} warning(s)'.format(len(warnings)), 'magenta'))
      for warning in warnings:
        print('  -', warning)
    else:
      print()

  def _render_files(self, directory, files):
    for f in files:
      print('  rendering "{}" ...'.format(f.name), end=' ')
      try:
        if not self.args.dry:
          with open(os.path.join(directory, f.name), 'w') as fp:
            f.render(fp)
      finally:
        print('done.')
