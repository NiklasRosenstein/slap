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

from nr.commons.py import classdef
from nr.databind.core import (
  Collection,
  Field,
  MutablePath,
  MixinDecoration,
  ObjectMapper,
  Struct,
  SerializationValueError,
  SerializationTypeError,
  translate_type_def)
from nr.databind.json import JsonDeserializer, JsonModule, JsonStoreRemainingKeys
from shore.core.plugins import (
  IBasePlugin,
  IBuildTarget,
  IPackagePlugin,
  IPublishTarget,
  IMonorepoPlugin,
  load_plugin,
  PluginNotFound)
from shore.util.ast import load_module_members
from typing import Any, Callable, Dict, Iterable, Optional, List, Type
import ast
import collections
import copy
import logging
import os
import re
import yaml

__all__ = ['Package', 'Monorepo']

logger = logging.getLogger(__name__)


class VersionSelector(object):
  """ A version selector string. """

  def __init__(self, selector):
    if isinstance(selector, VersionSelector):
      selector = selector._string
    self._string = selector.strip()

  def __str__(self):
    return str(self._string)

  def __repr__(self):
    return 'VersionSelector({!r})'.format(self._string)

  def __eq__(self, other):
    if type(self) == type(other):
      return self._string == other._string
    return False

  def __ne__(self, other):
    return not (self == other)

  def to_setuptools(self):  # type: () -> str
    """ Converts the version selector to a string that Setuptools/Pip can
    understand by expanding the `~` and `^` range selectors.

    Given a version number X.Y.Z, the selectors will be expanded as follows:

    - `^X.Y.Z` -> `>=X.Y.Z,<X+1.0.0`
    - `~X.Y.Z` -> `>=X.Y.Z,<X.Y+1.0`
    """

    regex = r'[~^](\d+\.\d+(\.\d+)?[.\-\w]*)'
    def sub(match):
      index = {'^': 0, '~': 1}[match.group(0)[0]]
      max_version = match.group(1).split('.')[:3]
      if len(max_version) == 2:
        max_version.append('0')
      if '-' in max_version[-1]:
        max_version[-1] = max_version[-1].partition('-')[0]
      max_version[index] = str(int(max_version[index]) + 1)
      for i in range(index+1, 3):
        max_version[i] = '0'
      return '>={},<{}'.format(match.group(1), '.'.join(max_version))
    return re.sub(regex, sub, self._string)


VersionSelector.ANY = VersionSelector('*')


class Requirement(object):
  """ A requirement is a combination of a package name and a version selector.
  """

  def __init__(self, package, version):  # type: (str, VersionSelector)
    if not isinstance(package, str):
      raise TypeError('expected str for package_name')
    if not isinstance(version, VersionSelector):
      raise TypeError('expected VersionSelector for version')
    self.package = package
    self.version = version

  def __str__(self):
    if self.version == VersionSelector.ANY:
      return self.package
    return '{} {}'.format(self.package, self.version)

  def __repr__(self):
    return repr(str(self))#'Requirement({!r})'.format(str(self))

  @classmethod
  def parse(cls, requirement_string):
    match = re.match(r'^\s*([^\s]+)(?:\s+(.+))?$', requirement_string)
    if not match:
      raise ValueError('invalid requirement: {!r}'.format(requirement_string))
    package, version = match.groups()
    return cls(package, VersionSelector(version or VersionSelector.ANY))

  def to_setuptools(self):  # type: () -> str
    if self.version == VersionSelector.ANY:
      return self.package
    return '{} {}'.format(self.package, self.version.to_setuptools())

  @JsonDeserializer
  def __deserialize(context, location):
    if not isinstance(location.value, str):
      raise SerializationTypeError(location)
    try:
      return Requirement.parse(location.value)
    except ValueError as exc:
      raise SerializationValueError(location, exc)


class Requirements(object):
  """ Represents package requirements, consisting of a #RequirementsList *any*
  that is comprised of requirements that always need to be present, and
  additional #RequirementsList#s in *platforms* that depend on the platform
  or environment (eg. `linux`, `win32` or `test` may be the platform keys).

  Additionally, the dependency on `python` is stored as the extra *python*
  attribute.

  This class is deserialized the same that it is represented in memory.
  Example:

  ```yaml
  - python ^2.7|^3.4
  - nr.interface ^1.0.0
  - test:
    - pytest
    - PyYAML
  ```

  Results in a #Requirements object like

  ```
  Requirements(python=VersionSelector('^2.7|^3.4'), required=[
    Requirement('nr.interface ^1.0.0')], test=[Requirement('pytest'),
    Requirement('PyYAML')], platforms={})
  ```

  Attributes:
    python (Optional[VersionSelector]): A selector for the Python version.
    required (List[Requirement]): A list of requirements that always need
      to be installed for a package, no matter the environment.
    test (List[Requirement]): A list of requirements that need to be installed
      for testing.
    platforms (Dict[str, Requirements]): A mapping of platform names to
      the requirements that need to be installed in that environment.
      Environments are tested against `sys.platform` in the rendered setup
      file.
  """

  classdef.repr('python,required,platforms')

  def __init__(self):
    self.python = None
    self.required = []
    self.platforms = {}

  @JsonDeserializer
  def __deserialize(context, location):
    deserialize_type = [(Requirement, dict)]
    items = context.deserialize(location.value, deserialize_type)

    self = location.datatype.cls()
    for index, item in enumerate(items):
      self._extract_from_item(context, (index,), item)
    return self

  def _extract_from_item(self, context, path, item):
    if isinstance(item, Requirement):
      if item.package == 'python':
        self.python = item.version
      else:
        self.required.append(item)
    elif isinstance(item, dict):
      if len(item) != 1:
        raise ValueError('expected only a single key in requirements list')
      for key, value in item.items():
        # Deserialize the requirements in this platform selector.
        deser = lambda i, v: context.deserialize(v, Requirement, path + (key, i))
        value = [deser(i, v) for i, v in enumerate(value)]
        if key in self.platforms:
          self.platforms[key].extend(value)
        else:
          self.platforms[key] = value


class RootRequirements(Requirements):

  classdef.repr(Requirements.__repr_properties__ + ['test', 'extra',])

  def __init__(self):
    super(RootRequirements, self).__init__()
    self.test = None
    self.extra = {}

  def _extract_from_item(self, context, path, item):
    if isinstance(item, dict) and len(item) == 1 and 'extra' in item:
      for key, value in item['extra'].items():
        self.extra[key] = context.deserialize(value, Requirements, path + ('extra', key))
    elif isinstance(item, dict) and len(item) == 1 and 'test' in item:
      self.test = context.deserialize(item['test'], Requirements, path + ('test',))
    else:
      super(RootRequirements, self)._extract_from_item(context, path, item)


class Author(Struct):
  name = Field(str)
  email = Field(str)

  AUTHOR_EMAIL_REGEX = re.compile(r'([^<]+)<([^>]+)>')

  def __str__(self):
    return '{} <{}>'.format(self.name, self.email)

  @JsonDeserializer
  def __deserialize(context, location):
    if isinstance(location.value, str):
      match = Author.AUTHOR_EMAIL_REGEX.match(location.value)
      if match:
        author = match.group(1).strip()
        email = match.group(2).strip()
        return Author(author, email)
    raise NotImplementedError


class Datafile(Struct):
  """ Represents an entry in the #Package.datafiles configuration. Can be
  deserialized from a JSON-like object or a string formatted as
  `source:target,includepattern,!excludepattern`. """

  source = Field(str)
  target = Field(str, default='.')
  include = Field([str])
  exclude = Field([str])

  @JsonDeserializer
  def __deserialize(context, location):
    if isinstance(location.value, str):
      left, patterns = location.value.partition(',')[::2]
      if ':' in left:
        source, target = left.partition(':')[::2]
      else:
        source, target = left, '.'
      if not source or not target:
        raise SerializationValueError(location, 'invalid DataFile spec: {!r}'.format(location.value))
      include = []
      exclude = []
      for pattern in patterns.split(','):
        (exclude if pattern.startswith('!') else include).append(pattern.lstrip('!'))
      return Datafile(source, target, include, exclude)
    raise NotImplementedError


class PluginConfig(Struct):
  name = Field(str)
  plugin = Field(IBasePlugin)

  @property
  def is_package_plugin(self) -> bool:
    return IPackagePlugin.provided_by(self.plugin)

  @property
  def is_monorepo_plugin(self) -> bool:
    return IMonorepoPlugin.provided_by(self.plugin)

  def get_checks(self, subject: 'BaseObject'):
    if isinstance(subject, Package) and self.is_package_plugin:
      logger.debug('getting package checks for plugin {}'.format(self.name))
      return self.plugin.check_package(subject)
    if isinstance(subject, Monorepo) and self.is_monorepo_plugin:
      logger.debug('getting monorepo checks for plugin {}'.format(self.name))
      return self.plugin.check_monorepo(subject)
    logger.debug('skipping plugin {}'.format(self.name))
    return ()

  def get_files(self, subject: 'BaseObject'):
    if isinstance(subject, Package) and self.is_package_plugin:
      logger.debug('getting package files for plugin {}'.format(self.name))
      return self.plugin.get_package_files(subject)
    if isinstance(subject, Monorepo) and self.is_monorepo_plugin:
      logger.debug('getting monorepo files for plugin {}'.format(self.name))
      return self.plugin.get_monorepo_files(subject)
    logger.debug('skipping plugin {}'.format(self.name))
    return ()

  def get_version_refs(self, subject: 'BaseObject'):
    if isinstance(subject, Package) and self.is_package_plugin:
      logger.debug('getting package version refs for plugin {}'.format(self.name))
      return self.plugin.get_package_version_refs(subject)
    if isinstance(subject, Monorepo) and self.is_monorepo_plugin:
      logger.debug('getting monorepo version refs for plugin {}'.format(self.name))
      return self.plugin.get_monorepo_version_refs(subject)
    logger.debug('skipping plugin {}'.format(self.name))
    return ()

  def get_build_targets(self, subject: 'BaseObject'):
    if isinstance(subject, Package) and self.is_package_plugin:
      logger.debug('getting package builders for plugin {}'.format(self.name))
      return self.plugin.get_package_build_targets(subject)
    logger.debug('skipping plugin {}'.format(self.name))
    return ()

  def get_publish_targets(self, subject: 'BaseObject'):
    if isinstance(subject, Package) and self.is_package_plugin:
      logger.debug('getting package publishers for plugin {}'.format(self.name))
      return self.plugin.get_package_publish_targets(subject)
    logger.debug('skipping plugin {}'.format(self.name))
    return ()

  @JsonDeserializer
  def __deserialize(context, location):
    if isinstance(location.value, str):
      plugin_name = location.value
      config = {}
    elif isinstance(location.value, dict):
      if len(location.value) != 1:
        raise SerializationValueError(location, 'expected only one key')
      plugin_name, config = next(location.value.items())
    else:
      raise SerializationTypeError(location, 'expected str or dict')
    try:
      plugin_cls = load_plugin(plugin_name)
    except PluginNotFound as exc:
      raise SerializationValueError(location, 'plugin "{}" not found'.format(exc))
    if plugin_cls.Config is not None:
      config = context.deserialize(
        config,
        translate_type_def(plugin_cls.Config),
        plugin_name)
    elif plugin_cls.Config is None and config:
      raise SerializationTypeError(location,
        'plugin {} expects no configuration'.format(plugin_name))
    else:
      config = None
    return PluginConfig(plugin_name, plugin_cls.new_instance(config))


class CommonPackageData(Struct):
  """ Represents common fields for a package that can be defined in the
  `monorepo.yaml` to inherit by packages inside the mono repository. """

  version = Field(str, default=None)
  author = Field(Author, default=None)
  license = Field(str, default=None)
  url = Field(str, default=None)
  use = Field([PluginConfig], default=list)


class ObjectCache(object):
  """ Helper class for loading #Package or #Monorepo objects from files. It
  caches the loaded object so that the same is not loaded multiple times into
  separate instances. """

  def __init__(self):
    self._cache = {}

  def get_or_load(self, filename: str, load_func: Callable[[str], Any]) -> Any:
    filename = os.path.normpath(os.path.abspath(filename))
    if filename not in self._cache:
      self._cache[filename] = load_func(filename)
    return self._cache[filename]


class BaseObject(Struct):

  #: The name of the object (ie. package or repository name).
  name = Field(str)

  #: The version of the object.
  version = Field(str)

  #: Plugins for this object.
  use = Field([PluginConfig])

  #: A hidden attribute that is not deserialized but set during
  #: deserialization from file to know the file that the data was
  #: loaded from.
  filename = Field(str, default=None, hidden=True)

  #: Contains all the unhandled keys from the deserialization.
  unhandled_keys = Field([str], default=None, hidden=True)

  #: The cache that this object is stored in.
  cache = Field(ObjectCache, default=None, hidden=True)

  @property
  def directory(self) -> str:
    return os.path.dirname(self.filename)

  def has_plugin(self, plugin_name: str) -> bool:
    return any(x.name == plugin_name for x in self.use)

  def get_plugins(self) -> List[PluginConfig]:
    plugins = list(self.use)
    if not self.has_plugin('core'):
      core_plugin = load_plugin('core')
      plugins.insert(0, PluginConfig('core', core_plugin.new_instance(None)))
    return plugins

  def get_build_targets(self) -> Dict[str, IBuildTarget]:
    targets = {}
    for plugin in self.get_plugins():
      for target in plugin.get_build_targets(self):
        target_id = plugin.name + ':' + target.get_name()
        if target_id in targets:
          raise RuntimeError('build target ID {} is not unique'.format(target_id))
        targets[target_id] = target
    return targets

  def get_publish_targets(self) -> Dict[str, IPublishTarget]:
    targets = {}
    for plugin in self.get_plugins():
      for target in plugin.get_publish_targets(self):
        target_id = plugin.name + ':' + target.get_name()
        if target_id in targets:
          raise RuntimeError('publish target ID {} is not unique'.format(target_id))
        targets[target_id] = target
    return targets

  @classmethod
  def load(cls, filename: str, cache: ObjectCache) -> '_DeserializableFromFile':
    """ Deserializes *cls* from a YAML file specified by *filename*. """

    def _load(filename):
      with open(filename) as fp:
        obj = ObjectMapper(JsonModule).deserialize(
          yaml.safe_load(fp),
          cls,
          filename=filename,
          decorations=[JsonStoreRemainingKeys()])
      obj.filename = filename
      obj.unhandled_keys = list(JsonStoreRemainingKeys().iter_paths(obj))
      obj.cache = cache
      obj.on_load_hook()
      return obj

    return cache.get_or_load(filename, _load)

  def on_load_hook(self):
    """ Called after the object was loaded with #load(). """

    pass


class Monorepo(BaseObject):
  #: Overrides the version field as it's optional for monorepos.
  version = Field(str, default=None)

  #: The data in this field propagates to the packages that are inside this
  #: mono repository.
  packages = Field(CommonPackageData, default=None)

  #: The use field is optional on monorepos.
  use = Field([PluginConfig], default=list)

  def get_packages(self) -> Iterable['Package']:
    """ Loads the packages for this mono repository. """

    for name in os.listdir(self.directory):
      path = os.path.join(self.directory, name, 'package.yaml')
      if os.path.isfile(path):
        package = Package.load(path, self.cache)
        assert package.monorepo is self, "woah hold up"
        yield package


class Package(BaseObject, CommonPackageData):
  #: Filled with the Monorepo if the package is associated with one. A package
  #: is associated with a monorepo if the parent directory of it's own
  #: directory contains a `monorepo.yaml` file.
  monorepo = Field(Monorepo, default=None, hidden=True)

  #: The package description.
  description = Field(str)

  #: The long description of the package. If this is not defined, the
  #: setuptools plugin will load the README file.
  long_description = Field(str, default=None)

  #: The content type for the long description. If not specified, the
  #: setuptools plugin will base that on the suffix of the README file.
  long_description_content_type = Field(str, default=None)

  #: The name of the module (potentially as a dottet path for namespaced
  #: modules). This is used to find the entry file in #get_entry_file().
  #: If not specified, the package #name is used.
  modulename = Field(str, default=None)

  #: The directory for the source files.
  source_directory = Field(str, default='src')

  #: The names of packages that should be excluded when installing the
  #: package. The setuptools plugin will automatically expand the names
  #: here to conform with what the #setuptools.find_packages() function
  #: expects (eg. 'test' is converted into 'test' and 'test.*').
  exclude_packages = Field([str], default=lambda: ['test', 'docs'])

  #: The requirements for the package.
  requirements = Field(RootRequirements, default=RootRequirements)

  #: The entrypoints for the package. The structure here is the same as
  #: for #setuptools.setup().
  entrypoints = Field({"value_type": [str]}, default=dict)

  #: A list of datafile definitions.
  datafiles = Field([Datafile], default=list)

  #: A list of instructions to render in the MANIFEST.in file.
  manifest = Field([str], default=list)

  def _get_inherited_field(self, field_name: str) -> Any:
    value = getattr(self, field_name)
    if value is None and self.monorepo and self.monorepo.packages:
      value = getattr(self.monorepo.packages, field_name)
    return value

  def get_version(self) -> str:
    version: str = self._get_inherited_field('version')
    if version is None:
      raise RuntimeError('version is not set')
    return version

  def get_author(self) -> Optional[Author]:
    return self._get_inherited_field('author')

  def get_license(self) -> str:
    return self._get_inherited_field('license')

  def get_url(self) -> str:
    return self._get_inherited_field('url')

  def get_plugins(self) -> List[PluginConfig]:
    plugins = super().get_plugins()

    # Inherit only plugins from the monorepo that are not defined in the
    # package itself.
    if self.monorepo and self.monorepo.packages:
      plugins.extend(x for x in self.monorepo.packages.use
        if not self.has_plugin(x.name))

    return plugins

  def on_load_hook(self):
    """ Called when the package is loaded. Attempts to find the Monorepo that
    belongs to this package and load it. If there is a Monorepo, the package
    will inherit some of the fields defined in #Monorepo.packages. """

    monorepo_fn = os.path.join(os.path.dirname(self.directory), 'monorepo.yaml')
    if os.path.isfile(monorepo_fn):
      self.monorepo = Monorepo.load(monorepo_fn, self.cache)

  def get_entry_file(self) -> str:
    """ Returns the filename of the entry file that contains package metadata
    such as `__version__` and `__author__`. """

    name = (self.modulename or self.name).replace('-', '_')
    parts = name.split('.')
    prefix = os.sep.join(parts[:-1])
    for filename in [parts[-1] + '.py', os.path.join(parts[-1], '__init__.py')]:
      filename = os.path.join('src', prefix, filename)
      if os.path.isfile(os.path.join(self.directory, filename)):
        return filename
    raise ValueError('Entry file for package "{}" could not be determined'
                     .format(self.package.name))

  EntryMetadata = collections.namedtuple('EntryFileData', 'author,version')

  def get_entry_metadata(self) -> EntryMetadata:
    """ Loads the entry file (see #get_entry_file()) and parses it with the
    #abc module to retrieve the value of the `__author__` and `__version__`
    variables defined in the file. """

    # Load the package/version data from the entry file.
    entry_file = self.get_entry_file()
    members = load_module_members(os.path.join(self.directory, entry_file))

    author = None
    version = None

    if '__version__' in members:
      try:
        version = ast.literal_eval(members['__version__'])
      except ValueError as exc:
        version = '<Non-literal expression>'

    if '__author__' in members:
      try:
        author = ast.literal_eval(members['__author__'])
      except ValueError as exc:
        author = '<Non-literal expression>'

    return self.EntryMetadata(author, version)
