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

from nr.commons.notset import NotSet
from nr.fs import atomic_file, makedirs
from nr.interface import Interface, attr, default, implements
from ..model import Monorepo, Package
import os

__all__ = [
  'write_to_disk',
  'IFileToRender',
  'FileToRender',
  'Option',
  'BaseRenderer',
  'RendererMisconfiguration',
]


def write_to_disk(file, directory='.'):  # type: (IFileToRender)
  target_fn = os.path.join(directory, file.name)
  makedirs(os.path.dirname(target_fn))
  with atomic_file(target_fn, text=True, encoding=file.encoding) as dst:
    if os.path.isfile(target_fn):
      current = open(target_fn, 'r', encoding=file.encoding)
    else:
      current = None
    try:
      file.render(current, dst)
    finally:
      if current:
        current.close()



class RendererMisconfiguration(Exception):
  pass


class IFileToRender(Interface):

  name = attr(str)
  encoding = attr(str, default='utf8')

  def render(self, current, dst):  # types: (Optional[TextIO], TextIO)
    pass


@implements(IFileToRender)
class FileToRender(object):

  def __init__(self, name, callable, *args, **kwargs):
    super(FileToRender, self).__init__()
    self.name = name
    self.encoding = kwargs.pop('encoding', self.encoding)
    self._callable = callable
    self._args = args
    self._kwargs = kwargs

  def render(self, current, dst):
    return self._callable(current, dst, *self._args, *self._kwargs)


class Option(object):

  def __init__(self, name, default=NotSet):
    self.name = name
    self.default = default

  def __repr__(self):
    return 'Option(name={!r}, default={!r})'.format(self.name, self.default)

  @property
  def required(self):
    return self.default is NotSet

  def get_default(self):
    if self.default is NotSet:
      raise RuntimeError('{!r} no default set'.format(self.name))
    if callable(self.default):
      return self.default()
    return self.default


class BaseRenderer(object):

  options = []  # type: List[Option]

  def __init__(self, config):
    try:
      self.config = self._get_options(config)
    except KeyError as exc:
      raise RendererMisconfiguration('missing option {}'.format(exc))

  @classmethod
  def _get_options(cls, options):  # type: (Dict[str, Any]) -> Dict[str, Any]
    """ May raise a #KeyError if a required option is not in *options*. """

    result = {}
    for option in cls.options:
      if option.name in options or option.required:
        result[option.name] = options[option.name]
      else:
        result[option.name] = option.get_default()
    return result

  def files(self):  # type: () -> Iterable[IFileToRender]
    raise NotImplementedError

  def files_for_monorepo(self, item):  # type: (Monorepo) -> Iterable[IFileToRender]
    raise NotImplementedError

  def files_for_package(self, item):  # type: (Package) -> Iterable[IFileToRender]
    raise NotImplementedError
