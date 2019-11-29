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

from nr.interface import Interface, attr, default, implements
from ..model import Monorepo, Package

__all__ = ['IFileToRender', 'FileToRender', 'IRenderer']


class IFileToRender(Interface):

  name = attr(str)

  def render(self, fp):
    pass


@implements(IFileToRender)
class FileToRender(object):

  def __init__(self, name, callable, *args, **kwargs):
    self.name = name
    self._callable = callable
    self._args = args
    self._kwargs = kwargs

  def render(self, fp):
    return self._callable(fp, *self._args, *self._kwargs)


class IRenderer(Interface):

  @default
  def files_for_monorepo(self, item):  # type: (Monorepo) -> Iterable[IFileToRender]
    return; yield

  @default
  def files_for_package(self, item):  # type: (Package) -> Iterable[IFileToRender]
    return; yield
