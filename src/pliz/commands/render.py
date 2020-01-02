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

""" CLI dispatcher for renderers. """

from .base import PlizCommand
from ..render import get_renderer, RendererNotFound
from termcolor import colored
import os


class InvalidOption(Exception):
  pass


def _get_package_warnings(package):  # type: (Package) -> Iterable[str]
  if not package.package.author:
    yield 'missing ' + colored('$.package.author', attrs=['bold'])
  if not package.package.license:
    yield 'missing ' + colored('$.package.license', attrs=['bold'])
  if not package.package.url:
    yield 'missing ' +  colored('$.package.url', attrs=['bold'])
  for check in _get_package_consistency_checks(package):
    yield check


def _get_package_consistency_checks(package):
  data = package.load_entry_file_data()
  if data.author != str(package.package.author):
    yield 'Inconsistent package author ({!r} != {!r})'.format(
      data.author, str(package.package.author))
  if data.version != package.package.version:
    yield 'Inconsistent package version ({!r} != {!r})'.format(
      data.version, package.package.version)


class RenderSession(object):

  def __init__(self, renderers, options, recursive, dry):
    if isinstance(renderers, str):
      renderers = renderers.split(',')
    self.options = options
    self.unseen_options = set(options.keys())
    self.recursive = recursive
    self.dry = dry
    self.renderers = [self._make_renderer(x) for x in renderers]

  def _make_renderer(self, name):
    renderer_cls = get_renderer(name)
    options = renderer_cls.get_options_from(self.options)
    self.unseen_options -= set(options.keys())
    return renderer_cls(options)

  def handle_unexpected_options(self, kind='warn'):
    assert kind in ('ignore', 'warn', 'error')
    if self.unseen_options and kind == 'warn':
      print(colored('warning: unrecognized option(s) for the selected '
            'renderer(s): {}'.format(self.unseen_options), 'magenta'))
    elif self.unseen_options and kind == 'error':
      raise InvalidOption(self.unseen_options)

  def render(self, monorepo, package):
    if monorepo:
      self._render_monorepo(monorepo)
      if self.recursive:
        packages = [package] if package else monorepo.list_packages()
        for package in packages:
          self._render_package(package)
    else:
      self._render_package(package)

  def _render_monorepo(self, monorepo):
    self._print_title(monorepo.project.name, monorepo.directory, [])
    files = []
    for impl in self.renderers:
      files.extend(impl.files_for_monorepo(monorepo))
    self._render_files(monorepo.directory, files)

  def _render_package(self, package):
    self._print_title(package.package.name, package.directory,
      _get_package_warnings(package))
    files = []
    for impl in self.renderers:
      files.extend(impl.files_for_package(package))
    self._render_files(package.directory, files)

  def _print_title(self, name, directory, warnings):
    print()
    print(
      colored('RENDER', 'blue', attrs=['bold']),
      name,
      colored('({})'.format(directory), 'grey', attrs=['bold']),
      end=' ')

    warnings = list(warnings)
    if warnings:
      print(colored('{} warning(s)'.format(len(warnings)), 'magenta', attrs=['bold']))
      for warning in warnings:
        print(' ', warning)
      print('  ----')
    else:
      print()

  def _render_files(self, directory, files):
    for f in files:
      print('  rendering "{}" ...'.format(f.name), end=' ')
      try:
        if not self.dry:
          with open(os.path.join(directory, f.name), 'w') as fp:
            f.render(fp)
      finally:
        print('done.')


class RenderCommand(PlizCommand):

  name = 'render'
  description = __doc__

  def update_parser(self, parser):
    super(RenderCommand, self).update_parser(parser)
    parser.add_argument('renderers', help='A comma-separated list of '
      'renderers to invoke for the current package or monorepo.')
    parser.add_argument('options', nargs='*', help='Zero or more key=value '
      'pairs that represent options to pass to the renderer(s).')
    parser.add_argument('--recursive', action='store_true', help='Render the '
      'individual packages in a monorepo as well.')
    parser.add_argument('--dry', action='store_true', help='Dry rendering. '
      'Output a list of files that would be rendered instead of actually '
      'rendering them.')

  def execute(self, parser, args):
    super(RenderCommand, self).execute(parser, args)
    options = self.parse_options(args.options)
    monorepo, package = self.get_configuration()
    try:
      session = RenderSession(args.renderers, options, args.recursive, args.dry)
      session.handle_unexpected_options('warn')
      session.render(monorepo, package)
    except (InvalidOption, RendererNotFound) as exc:
      parser.error(exc)

  def parse_options(self, options):  # type: (List[str]) -> Dict[str, Any]
    """ Parses a list of `key=value` formatted strings. """

    result = {}
    for e in options:
      if '=' not in e:
        raise ValueError('invalid option format: {!r}, expected key=value'.format(e))
      k, v = e.partition('=')[::2]
      if v.lower().strip() in ('true', 'yes', '1', 'y', 'on', 'enabled'):
        v = True
      elif v.lower().strip() in ('false', 'no', '0', 'n', 'off', 'disabled'):
        v = False
      else:
        for f in (float, int):
          try:
            v = f(v)
          except ValueError:
            pass
      result[k] = v
    return result
