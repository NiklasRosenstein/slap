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
from ..render import (
  get_renderer,
  write_to_disk,
  RenderContext,
  Renderer,
  RenderStatus,
  RenderType,
  RendererNotFound,
  RendererMisconfiguration)
from termcolor import colored
import os


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


class RenderCommand(PlizCommand):

  name = 'render'
  description = __doc__

  def update_parser(self, parser):
    super(RenderCommand, self).update_parser(parser)
    parser.add_argument('renderer', help='The name of a renderer to use.')
    parser.add_argument('--recursive', action='store_true')
    parser.add_argument('--dry', action='store_true')

  def handle_unknown_args(self, parser, args, argv):
    """ Parses additional `--` flags for the renderer options. """

    renderer_cls = get_renderer(args.renderer)
    options = {o.name: o for o in renderer_cls.options}
    config = {}
    pos_args = []

    it = iter(argv)
    queue = []
    while True:
      item = queue.pop(0) if queue else next(it, None)
      if item is None:
        break
      if not item.startswith('--'):
        if not config:  # No options have been parsed yet.
          pos_args.append(item)
          continue
        parser.error('unexpected argument {!r}'.format(item))
      if '=' in item:
        k, v = item[2:].partition('=')[::2]
      else:
        k = item[2:]
        v = next(it, 'true')
        if v.startswith('--'):
          queue.append(v)
          v = 'true'
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
      config[k] = v

    if len(pos_args) > len(renderer_cls.options):
      parser.error('expected at max {} positional arguments, got {}'.format(
        len(renderer_cls.options), len(pos_args)))
    for option, value in zip(renderer_cls.options, pos_args):
      if option.name in config:
        parser.error('duplicate argument value for option "{}"'.format(option.name))
      config[option.name] = value

    try:
      args._renderer = Renderer(renderer_cls, config)
    except RendererMisconfiguration as exc:
      parser.error(exc)

  def execute(self, parser, args):
    super(RenderCommand, self).execute(parser, args)
    monorepo, package = self.get_configuration()

    context = RenderContext(
      directory='.',
      dry=args.dry,
      reporter=self._report,
      monorepo=monorepo,
      package=package)

    self._rendered_any = False

    renderer = args._renderer
    renderer.render_general(context)
    if monorepo:
      renderer.render_monorepo(context)
      if args.recursive:
        packages = [package] if package else monorepo.list_packages()
        for package in packages:
          context.package = package
          renderer.render_package(context)
    else:
      renderer.render_package(context)

    if not self._rendered_any:
      print(colored(
        'fatal: renderer "{}" is not applicable in this context'.format(args.renderer),
        'red'))
      exit(1)

  def _report(self, type, status, context):
    if status == RenderStatus.NotImplemented:
      pass
    elif status == RenderStatus.StartRender:
      if type == RenderType.General:
        name = 'GENERAL'
        directory = None
      elif type == RenderType.Monorepo:
        name = context.monorepo.project.name
        directory = os.path.relpath(context.monorepo.directory)
      elif type == RenderType.Package:
        name = context.package.package.name
        directory = os.path.relpath(context.package.directory)
      if directory == '.':
        directory += '/'
      elif directory:
        directory = './' + directory
      self._rendered_any = True
      print(colored('RENDER', 'blue', attrs=['bold']), name, end=' ')
      if directory:
        print(colored('({})'.format(directory), 'grey', attrs=['bold']))
      else:
        print()
    elif status == RenderStatus.EndRender:
      print()
    elif status == RenderStatus.RenderFile:
      print('  rendering "{}" ...'.format(context.file.name))
      write_to_disk(context.file, context.directory)
