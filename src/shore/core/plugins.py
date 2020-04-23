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

""" Plugins are defined in the Monorepo and Package configuration and can
perform several types of actions.

* On render, they may generate or modify existing files in the project.
* Also on render, or on performing checks, a plugin may check for any
  inconsistencies and produce warnings or errors.
"""

from nr.collections import abc
from nr.interface import Interface, attr, default, implements, override, staticattr
from pkg_resources import iter_entry_points
from typing import Iterable
import collections
import contextlib
import enum
import nr.fs

_PLUGINS_ENTRYPOINT = 'shore.core.plugins'
assert _PLUGINS_ENTRYPOINT == __name__

VersionRef = collections.namedtuple('VersionRef', 'filename,start,end,value')


class BuildResult(enum.Enum):
  SUCCESS = 'SUCCESS'
  FAILURE = 'FAILURE'


class IBuildTarget(Interface):

  def get_name(self) -> str:
    pass

  def get_build_artifacts(self) -> Iterable[str]:
    pass

  def build(self, build_directory: str) -> BuildResult:
    pass


class IPublishTarget(Interface):

  def get_name(self) -> str:
    pass

  def get_build_selectors(self) -> Iterable[str]:
    pass

  def publish(
    self,
    builds: Iterable[IBuildTarget],
    test: bool,
    build_directory: str,
    skip_existing: bool
  ):
    pass


class CheckResult(object):
  """ The result of a check performed by a plugin. """

  class Level(enum.IntEnum):
    INFO = 0
    WARNING = 1
    ERROR = 2

  def __init__(self, on, level, message):
    # type: (Union[Monorepo, Package], str, Level)
    if isinstance(level, str):
      level = self.Level[level]
    assert isinstance(level, self.Level)
    self.on = on
    self.level = level
    self.message = message

  def __repr__(self):
    return 'CheckResult(on={!r}, level={}, message={!r})'.format(
      self.on, self.level, self.message)


class IFileToRender(Interface):
  """ Represents a file that is to be rendered to disk. The #render() function
  has access to the file's previous contents if it existed. """

  name = attr(str)
  encoding = attr(str, default='utf8')
  chmod = attr(str, default=None)

  def render(self, current, dst):  # types: (Optional[TextIO], TextIO)
    pass


@implements(IFileToRender)
class FileToRender(object):
  """ An implementation of the #IFileToRender interface that forwards the
  #render() call to a callable. """

  def __init__(self, directory, name, callable, *args, **kwargs):
    super(FileToRender, self).__init__()
    self.name = nr.fs.norm(nr.fs.join(directory or '.', name))
    self.encoding = kwargs.pop('encoding', self.encoding)
    self._callable = callable
    self._args = args
    self._kwargs = kwargs

  def with_chmod(self, chmod):
    self.chmod = chmod
    return self

  @override
  def render(self, current, dst):
    return self._callable(current, dst, *self._args, *self._kwargs)


class IBasePlugin(Interface):
  """ Interface for plugins. """

  Config = staticattr(None)
  config = attr(default=None)

  @default
  @classmethod
  def get_default_config(cls):
    return cls.Config()

  @default
  @classmethod
  def new_instance(cls, config: 'Config') -> 'IBasePlugin':
    """ Create a new instance of the plugin. The default implementation
    assumes that the constructor does not accept any arguments and the
    #config member is set after construction. """

    if cls.Config is None and config is not None:
      raise ValueError('{} does not expect a config, got {}'.format(
        cls.__name__, type(config).__name__))
    elif cls.Config is not None:
      if config is None:
        config = cls.get_default_config()
      elif not isinstance(config, cls.Config):
        raise ValueError('{} expects a config of type {}, got {}'.format(
          cls.__name__, cls.Config.__name__, type(config).__name__))

    instance = cls()
    instance.config = config
    return instance


class IPackagePlugin(IBasePlugin):
  """ A plugin that can be used with packages to render files. """

  @default
  def get_package_files(self, package: 'Package') -> Iterable[IFileToRender]:
    return ()

  @default
  def check_package(self, package: 'Package') -> Iterable[CheckResult]:
    return ()

  @default
  def get_package_version_refs(self, package: 'Package') -> Iterable[VersionRef]:
    return ()

  @default
  def get_package_build_targets(self, package: 'Package') -> Iterable[IBuildTarget]:
    return ()

  @default
  def get_package_publish_targets(self, package: 'Package') -> Iterable[IPublishTarget]:
    return ()


class IMonorepoPlugin(IBasePlugin):
  """ A plugin that can be used with monorepos. """

  @default
  def get_monorepo_files(self, package: 'Monorepo') -> Iterable[IFileToRender]:
    return ()

  @default
  def check_monorepo(self, package: 'Monorepo') -> Iterable[CheckResult]:
    return ()

  @default
  def get_monorepo_version_refs(self, monorepo: 'Monorepo') -> Iterable[VersionRef]:
    return ()


class PluginNotFound(Exception):
  pass


def load_plugin(name):  # type: (str) -> Type[IBasePlugin]
  """ Loads a plugin by its entrypoint name. Returns the class that implements
  the #IBasePlugin interface. Raises a #PluginNotFound exception if *name* does
  not describe a known plugin implementation. """

  for ep in iter_entry_points(_PLUGINS_ENTRYPOINT, name):
    cls = ep.load()
    break
  else:
    raise PluginNotFound(name)

  assert IBasePlugin.implemented_by(cls), (name, cls)
  return cls


def construct_plugin(name_or_cls, options):
  cls = load_plugin(name_or_cls) if isinstance(name_or_cls, str) else name_or_cls
  base_options = {o.name: o.get_default() for o in cls.get_options() if not o.required}
  base_options.update(options)
  missing_options = [o.name for o in cls.get_options()
    if o.required and o.name not in base_options]
  if missing_options:
    raise ValueError('missing options for {!r}: {}'.format(cls, missing_options))
  return cls(base_options)


def write_to_disk(file, fp=None):  # type: (IFileToRender, Optional[TextIO])
  """ Writes an #IFileToRender to disk. If *fp* is specified, it will be used
  as the target file to write to and the function simply handles the opening
  of the current file version on disk.

  Note also that if *fp* is specified, no file permissions will be changed. """

  dst = fp
  current = None
  nr.fs.makedirs(nr.fs.dir(file.name) or '.')
  with contextlib.ExitStack() as stack:
    if dst is None:
      dst = stack.enter_context(nr.fs.atomic_file(
        file.name, text=True, encoding=file.encoding))
    if nr.fs.isfile(file.name):
      current = stack.enter_context(
        open(file.name, 'r', encoding=file.encoding))
    file.render(current, fp or dst)
  if file.chmod and not fp:
    nr.fs.chmod(file.name, file.chmod)
