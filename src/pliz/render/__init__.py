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

from .base import *
from nr import sumtype
from nr.databind.core import Field, Struct
from ..model import Monorepo, Package
from pkg_resources import iter_entry_points
import enum

_RENDERER_ENTRYPOINT = 'pliz.render'
assert _RENDERER_ENTRYPOINT == __name__

__all__ = [
  'RendererNotFound',
  'get_renderer',
  'RenderType',
  'RenderStatus',
  'RenderContext',
  'Renderer'
]


class RendererNotFound(Exception):

  def __str__(self):
    return 'unknown renderer "{}"'.format(self.args[0])


def get_renderer(name):
  for ep in iter_entry_points(_RENDERER_ENTRYPOINT, name):
    return ep.load()
  raise RendererNotFound(name)


class RenderType(enum.Enum):
  General = 'General'
  Monorepo = 'Monorepo'
  Package = 'Package'


class RenderStatus(enum.Enum):
  NotImplemented = 'NotImplemented'
  StartRender = 'StartRender'
  EndRender = 'EndRender'
  RenderFile = 'RenderFile'


class RenderContext(Struct):
  directory = Field(str)
  dry = Field(bool, default=False)
  reporter = Field(object)
  monorepo = Field(Monorepo, default=None)
  package = Field(Package, default=None)
  file = Field(IFileToRender, default=None)


class Renderer(BaseRenderer):

  def __init__(self, impl, options, unknown_options='error'):
    assert callable(unknown_options) or unknown_options in ('ignore', 'error')

    if isinstance(impl, str):
      impl = get_renderer(impl)
    assert issubclass(impl, BaseRenderer), type(impl)

    try:
      config = impl._get_options(options)
    except KeyError as exc:
      raise RendererMisconfiguration('missing required option {}'.format(exc))

    unknowns = set(options.keys()) - set(config.keys())
    if unknowns and callable(unknown_options):
      unknown_options(unknowns)
    elif unknowns and unknown_options == 'error':
      raise RendererMisconfiguration('unknown option(s): {}'.format(unknowns))

    self._options = config
    self._impl = impl(options)

  def files(self):
    return self._impl.files()

  def files_for_monorepo(self, monorepo):
    return self._impl.files_for_monorepo(monorepo)

  def files_for_package(self, package):
    return self._impl.files_for_package(package)

  def render(self, type, directory, dry, reporter):
    if type == RenderType.General:
      method = self.files()
    elif type == RenderType.Monorepo:
      method = lambda: self.files_for_monorepo(monorepo)

  def render_general(self, context):
    self._render(RenderType.General, context)

  def render_monorepo(self, context):
    self._render(RenderType.Monorepo, context)

  def render_package(self, context):
    self._render(RenderType.Package, context)

  def _render(self, type, context):  # type: (RenderType, RenderContext)
    if type == RenderType.General:
      get_files = self.files
    elif type == RenderType.Monorepo:
      get_files = lambda: self.files_for_monorepo(context.monorepo)
    elif type == RenderType.Package:
      get_files = lambda: self.files_for_package(context.package)
    else:
      raise RuntimeError(type)
    try:
      files = list(get_files())
    except NotImplementedError:
      context.reporter(type, RenderStatus.NotImplemented, context)
    else:
      context.reporter(type, RenderStatus.StartRender, context)
      for file in files:
        context.file = file
        context.reporter(type, RenderStatus.RenderFile, context)
      context.reporter(type, RenderStatus.EndRender, context)
