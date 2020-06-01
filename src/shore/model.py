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

from nr.databind.core import Field, Struct, FieldName, Collect
from nr.databind.json import JsonDefault, JsonSerializer, JsonMixin
from nr.interface import implements
from nr.pylang.utils import classdef
from nr.stream import Stream
from shore.core.plugins import (
  IBasePlugin,
  IBuildTarget,
  IPackagePlugin,
  IPublishTarget,
  IMonorepoPlugin,
  load_plugin,
  PluginNotFound)
from shore.mapper import mapper
from shore.util.ast import load_module_members
from shore.util.version import bump_version, Version
from typing import Any, Callable, Dict, Iterable, Optional, List, Type, Union
import ast
import collections
import copy
import logging
import os
import re
import shlex
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
    - `X.Y.Z -> ==X.Y.Z`
    """

    # Poor-mans test if this looks like the form 'X.Y.Z' without anything around it.
    if not ',' in self._string and self._string[0].isdigit():
      return '==' + self._string

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

  def is_semver_selector(self) -> bool:
    return self._string and self._string[0] in '^~' and ',' not in self._string

  def matches(self, version: Union[Version, str]) -> bool:
    if not self.is_semver_selector():
      # TODO (@NiklasRosenstein): Match setuptools version selectors.
      return False
    min_version = Version(self._string[1:])
    if self._string[0] == '^':
      max_version = bump_version(min_version, 'major')
    elif self._string[0] == '~':
      max_version = bump_version(min_version, 'minor')
    else:
      raise RuntimeError('invalid semver selector string {!r}'.format(self._string))
    return min_version <= Version(version) < max_version


VersionSelector.ANY = VersionSelector('*')


@JsonSerializer(deserialize='_deserialize')
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

  @classmethod
  def _deserialize(cls, mapper, node):
    if not isinstance(node.value, str):
      raise node.type_error()
    return Requirement.parse(node.value)


@JsonSerializer(deserialize='_deserialize')
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

  def __bool__(self):
    return bool(self.python or self.required or self.platforms)

  @classmethod
  def _deserialize(cls, mapper, node):
    deserialize_type = [(Requirement, dict)]
    items = mapper.deserialize_node(node.replace(datatype=deserialize_type))

    self = node.datatype.cls()
    for index, item in enumerate(items):
      self._extract_from_item(mapper, node.make_child(index, None, item))
    return self

  def _extract_from_item(self, mapper, node):
    item = node.value
    if isinstance(item, Requirement):
      if item.package == 'python':
        self.python = item.version
      else:
        self.required.append(item)
    elif isinstance(item, dict):
      if len(item) != 1:
        raise ValueError('expected only a single key in requirements list')
      for key, value in item.items():
        value = mapper.deserialize_node(node.make_child(key, [Requirement], value))
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

  def _extract_from_item(self, mapper, node):
    item = node.value
    if isinstance(item, dict) and len(item) == 1 and 'extra' in item:
      values_node = node.make_child('extra', None, item['extra'])
      for key, value in item['extra'].items():
        self.extra[key] = mapper.deserialize_node(values_node.make_child(key, Requirements, value))
    elif isinstance(item, dict) and len(item) == 1 and 'test' in item:
      test_node = node.make_child('test', Requirements, item['test'])
      self.test = mapper.deserialize_node(test_node)
    else:
      super(RootRequirements, self)._extract_from_item(mapper, node)


@JsonSerializer(deserialize='_deserialize')
class Author(Struct):
  name = Field(str)
  email = Field(str)

  AUTHOR_EMAIL_REGEX = re.compile(r'([^<]+)<([^>]+)>')

  def __str__(self):
    return '{} <{}>'.format(self.name, self.email)

  @classmethod
  def _deserialize(cls, mapper, node):
    if isinstance(node.value, str):
      match = Author.AUTHOR_EMAIL_REGEX.match(node.value)
      if match:
        author = match.group(1).strip()
        email = match.group(2).strip()
        return Author(author, email)
    raise NotImplementedError


@JsonSerializer(deserialize='_deserialize')
class Datafile(Struct):
  """ Represents an entry in the #Package.datafiles configuration. Can be
  deserialized from a JSON-like object or a string formatted as
  `source:target,includepattern,!excludepattern`. """

  source = Field(str)
  target = Field(str, default='.')
  include = Field([str])
  exclude = Field([str])

  @classmethod
  def _deserialize(cls, mapper, node):
    if isinstance(node.value, str):
      left, patterns = node.value.partition(',')[::2]
      if ':' in left:
        source, target = left.partition(':')[::2]
      else:
        source, target = left, '.'
      if not source or not target:
        raise ValueError('invalid DataFile spec: {!r}'.format(node.value))
      include = []
      exclude = []
      for pattern in patterns.split(','):
        (exclude if pattern.startswith('!') else include).append(pattern.lstrip('!'))
      return Datafile(source, target, include, exclude)
    raise NotImplementedError


@JsonSerializer(deserialize='_deserialize')
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

  @classmethod
  def _deserialize(cls, mapper, node):
    if isinstance(node.value, str):
      plugin_name = node.value
      config = None
    elif isinstance(node.value, dict):
      if 'type' not in node.value:
        node.value_error('missing "type" key')
      config = node.value.copy()
      plugin_name = config.pop('type')
    else:
      raise TypeError('expected str or dict')
    try:
      plugin_cls = load_plugin(plugin_name)
    except PluginNotFound as exc:
      raise ValueError('plugin "{}" not found'.format(exc))
    if plugin_cls.Config is not None and config is not None:
      config = mapper.deserialize_node(node.make_child(plugin_name, plugin_cls.Config, config))
    elif plugin_cls.Config is None and config:
      raise TypeError('plugin {} expects no configuration'.format(plugin_name))
    else:
      config = None
    return PluginConfig(plugin_name, plugin_cls.new_instance(config))


@JsonSerializer(deserialize='_deserialize')
class InstallHook(JsonMixin, Struct):
  event = Field(str, default=None)
  command = Field((str, [str]))  #: Can be a string or list of strings.

  def normalize(self) -> 'InstallHook':
    if isinstance(self.command, str):
      return InstallHook(self.event, shlex.split(self.command))
    return self

  @classmethod
  def _deserialize(cls, mapper, node):
    if isinstance(node.value, str):
      return InstallHook(None, node.value)
    elif isinstance(node.value, dict):
      if len(node.value) != 1:
        raise ValueError('expected only one key')
      event, command = next(iter(node.value.items()))
      command = mapper.deserialize_node(node.make_child('command', InstallHook.command.datatype, command))
      return InstallHook(event, command)
    else:
      raise NotImplementedError  # Default deserialization


class ObjectCache(object):
  """ Helper class for loading #Package or #Monorepo objects from files. It
  caches the loaded object so that the same is not loaded multiple times into
  separate instances. """

  def __init__(self):
    self._cache = {}

  def clear(self):
    self._cache.clear()

  def get_or_load(self, filename: str, load_func: Callable[[str], Any]) -> Any:
    filename = os.path.normpath(os.path.abspath(filename))
    if filename not in self._cache:
      self._cache[filename] = load_func(filename)
    return self._cache[filename]


class BaseObject(Struct):

  #: The name of the object (ie. package or repository name).
  name = Field(str)

  #: The version of the object.
  version = Field(Version)

  #: Plugins for this object.
  use = Field([PluginConfig])

  #: Directory where the "shore changelog" command stores the changelog
  #: YAML files.
  changelog_directory = Field(str, default='.changelog')

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
      collect = Collect()
      with open(filename) as fp:
        obj = mapper.deserialize(yaml.safe_load(fp), cls, filename=filename, decorations=[collect])
      obj.filename = filename
      obj.unhandled_keys = Stream.concat(
        (x.locator.append(k) for k in x.unknowns)
        for x in collect.nodes).collect()
      obj.cache = cache
      obj.on_load_hook()
      return obj

    return cache.get_or_load(filename, _load)

  def on_load_hook(self):
    """ Called after the object was loaded with #load(). """

    pass


class Monorepo(BaseObject):
  private = Field(bool, default=False)

  #: Overrides the version field as it's optional for monorepos.
  version = Field(Version, default=None)

  #: If this option is enabled, individual packages in the monorepo have
  #: no individual version number. The "version" field in the package.yaml
  #: must be consistent with the version of the monorepo. Bumping the version
  #: of the monorepo will automatically bump the version in all packages.
  #: Bumping the version of individual packages will fail.
  mono_versioning = Field(bool, FieldName('mono-versioning'), default=False)

  #: The use field is optional on monorepos.
  use = Field([PluginConfig], default=list)

  #: Plugins to be used for all packages in the monorepo (unless explicitly
  #: overwritten in the package.yaml file).
  packages_use = Field([PluginConfig], default=list)

  #: Fields that can be inherited by the package.
  author = Field(Author, default=None)
  license = Field(str, default=None)
  url = Field(str, default=None)
  tag_format = Field(str, FieldName('tag-format'), default='{version}')

  @property
  def local_name(self) -> str:
    return self.name

  def get_packages(self) -> Iterable['Package']:
    """ Loads the packages for this mono repository. """

    for name in os.listdir(self.directory):
      path = os.path.join(self.directory, name, 'package.yaml')
      if os.path.isfile(path):
        package = Package.load(path, self.cache)
        assert package.monorepo is self, "woah hold up"
        yield package

  def get_private(self) -> bool:
    return self.private

  def get_tag_format(self) -> str:
    return self.tag_format

  def get_tag(self, version: str) -> str:
    tag_format = self.get_tag_format()
    return tag_format.format(name=self.name, version=version)

  def get_build_targets(self) -> Dict[str, IBuildTarget]:
    """
    Returns the publish targets for the monorepo. This includes the targets for
    packages in the monorepo.
    """

    targets = super().get_build_targets()
    for package in self.get_packages():
      for key, publisher in package.get_build_targets().items():
        targets[package.name + ':' + key] = self._BuildTargetWrapper(package.name, publisher)
    return targets

  def get_publish_targets(self) -> Dict[str, IPublishTarget]:
    """
    Returns the publish targets for the monorepo. If #mono_versioning is enabled,
    this includes the targets of child packages.
    """

    targets = super().get_publish_targets()
    for package in self.get_packages():
      for key, publisher in package.get_publish_targets().items():
        targets[package.name + ':' + key] = self._PublishTargetWrapper(package.name, publisher)
    return targets

  @implements(IBuildTarget)
  class _BuildTargetWrapper:
    def __init__(self, prefix, target):
      self.prefix = prefix
      self.target = target
    def get_name(self):
      return self.prefix + ':' + self.target.get_name()
    def get_build_artifacts(self):
      return self.target.get_build_artifacts()
    def build(self, build_directory):
      return self.target.build(build_directory)

  @implements(IPublishTarget)
  class _PublishTargetWrapper:
    def __init__(self, prefix, target):
      self.prefix = prefix
      self.target = target
    def get_name(self):
      return self.prefix + ':' + self.target.get_name()
    def get_build_selectors(self):
      return [self.prefix + ':' + k for k in self.target.get_build_selectors()]
    def publish(self, builds, test, build_directory, skip_existing):
      return self.target.publish(builds, test, build_directory, skip_existing)


class Package(BaseObject):
  #: Filled with the Monorepo if the package is associated with one. A package
  #: is associated with a monorepo if the parent directory of it's own
  #: directory contains a `monorepo.yaml` file.
  monorepo = Field(Monorepo, default=None, hidden=True)

  #: A private package will be prevented from being published with the
  #: "shore publish" command.
  private = Field(bool, default=None)

  #: The version number of the package.
  version = Field(Version, default=None)

  #: The author of the package.
  author = Field(Author, default=None)

  #: The license of the package. If #private is set to True, this can be None
  #: without a check complaining about it.
  license = Field(str, default=None)

  #: The URL of the package (eg. the GitHub repository).
  url = Field(str, default=None)

  #: A format specified when tagging a version of the package. This defaults
  #: to `"{version}"`. If the package is a member of a monorepo, #get_tag_format()
  #: adds the package name as a prefix.
  tag_format = Field(str, FieldName('tag-format'), default='{version}')

  #: The package description.
  description = Field(str)

  #: The default "use" field is populated with setuptools and pypi.
  use = Field([PluginConfig], default=list)

  #: The long description of the package. If this is not defined, the
  #: setuptools plugin will load the README file.
  long_description = Field(str, FieldName('long-description'), default=None)

  #: The content type for the long description. If not specified, the
  #: setuptools plugin will base that on the suffix of the README file.
  long_description_content_type = Field(str,
    FieldName('long-description-content-type'), default=None)

  #: The name of the module (potentially as a dottet path for namespaced
  #: modules). This is used to find the entry file in #get_entry_file().
  #: If not specified, the package #name is used.
  modulename = Field(str, default=None)

  #: The directory for the source files.
  source_directory = Field(str, FieldName('source-directory'), default='src')

  #: The names of packages that should be excluded when installing the
  #: package. The setuptools plugin will automatically expand the names
  #: here to conform with what the #setuptools.find_packages() function
  #: expects (eg. 'test' is converted into 'test' and 'test.*').
  exclude_packages = Field([str], FieldName('exclude-packages'),
    default=lambda: ['test', 'docs'])

  #: The requirements for the package.
  requirements = Field(RootRequirements, default=RootRequirements)

  #: The entrypoints for the package. The structure here is the same as
  #: for #setuptools.setup().
  entrypoints = Field({"value_type": [str]}, default=dict)

  #: A list of datafile definitions.
  datafiles = Field([Datafile], default=list)

  #: A list of instructions to render in the MANIFEST.in file.
  manifest = Field([str], default=list)

  #: Hooks that will be executed on install events (install/develop).
  install_hooks = Field([InstallHook], FieldName('install-hooks'), default=list)

  #: List of classifiers for the package.
  classifiers = Field([str], default=list)

  #: List of keywords.
  keywords = Field([str], default=list)

  #: Set to true to indicate that the package is typed. This will render a
  #: "py.typed" file in the source directory and include it in the package
  #: data.
  typed = Field(bool, default=False)

  @property
  def local_name(self) -> str:
    if self.monorepo:
      relpath = os.path.relpath(self.directory, self.monorepo.directory)
      return os.path.normpath(relpath)
    return self.name

  def _get_inherited_field(self, field_name: str) -> Any:
    value = getattr(self, field_name)
    if value is None and self.monorepo and hasattr(self.monorepo, field_name):
      value = getattr(self.monorepo, field_name)
    return value

  def get_private(self) -> bool:
    return self._get_inherited_field('private')

  def get_modulename(self) -> str:
    return self.modulename or self.name

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
    if self.monorepo and self.monorepo.packages_use:
      plugins.extend(x for x in self.monorepo.packages_use
        if not self.has_plugin(x.name))

    # Make sure there exists a setuptools and pypi target.
    if not any(x.name == 'setuptools' for x in plugins):
      plugins.append(mapper.deserialize('setuptools', PluginConfig))
    if not self.get_private():
      if not any(x.name == 'pypi' for x in plugins):
        plugins.append(mapper.deserialize('pypi', PluginConfig))

    return plugins

  def get_tag_format(self) -> str:
    tag_format = self._get_inherited_field('tag_format')
    if self.monorepo and '{name}' not in tag_format:
      tag_format = '{name}@' + tag_format
    return tag_format

  def get_tag(self, version: str) -> str:
    tag_format = self.get_tag_format()
    return tag_format.format(name=self.name, version=version)

  def on_load_hook(self):
    """ Called when the package is loaded. Attempts to find the Monorepo that
    belongs to this package and load it. """

    monorepo_fn = os.path.join(os.path.dirname(self.directory), 'monorepo.yaml')
    if os.path.isfile(monorepo_fn):
      self.monorepo = Monorepo.load(monorepo_fn, self.cache)

  def get_entry_file(self) -> str:
    """ Returns the filename of the entry file that contains package metadata
    such as `__version__` and `__author__`. """

    name = self.get_modulename().replace('-', '_')
    parts = name.split('.')
    prefix = os.sep.join(parts[:-1])
    for filename in [parts[-1] + '.py', os.path.join(parts[-1], '__init__.py')]:
      filename = os.path.join(self.source_directory, prefix, filename)
      if os.path.isfile(os.path.join(self.directory, filename)):
        return filename
    raise ValueError('Entry file for package "{}" could not be determined'
                     .format(self.name))

  def is_single_module(self) -> bool:
    return (
      self.get_modulename().count('.') == 0 and
      os.path.basename(self.get_entry_file()) != '__init__.py')

  def get_entry_file_abs(self) -> str:
    return os.path.normpath(os.path.join(self.directory, self.get_entry_file()))

  def get_entry_directory(self) -> str:
    """
    Returns the package directory. If this package is distributed in module-only
    form, a #ValueError is raised.
    """

    entry_file = self.get_entry_file()
    dirname, basename = os.path.split(entry_file)
    if basename != '__init__.py':
      raise ValueError('this package is in module-only form')
    return dirname

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
