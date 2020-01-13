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
from nr.commons.notset import NotSet
from nr.interface import Interface, attr, implements, override
from pliz.models import Monorepo, Package
from pkg_resources import iter_entry_points
import enum
import nr.fs

_PLUGINS_ENTRYPOINT = 'pliz.core.plugins'
assert _PLUGINS_ENTRYPOINT == __name__


class PluginContext(object):
  """ Contextual data for plugin execution. """

  def __init__(self, monorepo, packages):
    # type: (Optional[Monorepo], List[Packages])
    self.monorepo = monorepo
    self.packages = packages

  def iter_plugin_ctx_combinations(self):
    """ Returns a generator yielding pairs of #IPlugin and #PluginContext
    objects, where the plugins are created as defined in #Monorepo.project.use
    and #Package.package.use. """

    for plugin in self.monorepo.project.use:
      config = self.monorepo.plugins.get(plugin, {})
      yield construct_plugin(plugin, config), PluginContext(self.monorepo, [])
    for package in self.packages:
      for plugin in package.package.use:
        config = package.plugins.get(plugin, {})
        yield construct_plugin(plugin, config), PluginContext(None, [package])


class CheckResult(object):
  """ The result of a check performed by a plugin. """

  class Level(enum.Enum):
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'

  def __init__(self, on, level, message):
    # type: (Union[Monorepo, Package], str, Level)
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


class Option(object):

  def __init__(self, name=None, default=NotSet):
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


class Options(object):

  def __init__(self, options):  # type: (Union[List[Option], Dict[str, Option]])
    if isinstance(options, abc.Mapping):
      for key, value in options.items():
        assert value.name is None or value.name == key, (key, value)
        value.name = key
      options = dict(options.items())
    else:
      options = {v.name: v for v in options}
    self._options = options

  def __getitem__(self, name):
    return self._options[name]

  def __setitem__(self, name, option):
    assert isinstance(name, str), repr(name)
    assert isinstance(option, Option), repr(option)
    assert option.name is None or option.name == name, (name, option)
    option.name = name
    self._options[name] = option

  def __iter__(self):
    return iter(self._options.values())

  def __len__(self):
    return len(self._options)

  def __repr__(self):
    return 'Options({})'.format(self._options)


class IPlugin(Interface):
  """ Interface for plugins. Plugins must be constructible with an options
  dictionary as an argument. """

  @classmethod
  def get_options(cls):  # type: () -> Options
    """ Returns #Options for this plugin. """

  def get_files_to_render(self, context):
    # type: (PluginContext) -> Iterable[IFileToRender]
    """ Given a monorepo and/or a list of packages, the plugin shall return
    an iterable of #IFileToRender objects that represent the files to be
    rendered by this plugin. """

  def perform_checks(self, context):
    # type: (PluginContext) -> Iterable[CheckResult]
    """ Perform checks on the data given via the context. """


class PluginNotFound(Exception):
  pass


def load_plugin(name):  # type: (str) -> Type[IPlugin]
  """ Loads a plugin by its entrypoint name. Returns the class that implements
  the #IPlugin interface. Raises a #PluginNotFound exception if *name* does
  not describe a known plugin implementation. """

  for ep in iter_entry_points(_PLUGINS_ENTRYPOINT, name):
    cls = ep.load()
    break
  else:
    raise PluginNotFound(name)

  assert IPlugin.implemented_by(cls), (name, cls)
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


def write_to_disk(file):  # type: (IFileToRender)
  """ Writes an #IFileToRender to disk. """

  nr.fs.makedirs(nr.fs.dir(file.name))
  with nr.fs.atomic_file(file.name, text=True, encoding=file.encoding) as dst:
    if nr.fs.isfile(file.name):
      current = open(file.name, 'r', encoding=file.encoding)
    else:
      current = None
    try:
      file.render(current, dst)
    finally:
      if current:
        current.close()
  if file.chmod:
    nr.fs.chmod(file.name, file.chmod)
