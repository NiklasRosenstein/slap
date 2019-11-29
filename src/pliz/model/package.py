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

from .base import DeserializableFromFileMixin
from nr.databind import Collection, Field, Struct, SerializationValueError, \
  SerializationTypeError
from nr.databind.json import JsonDeserializer
import re
import yaml


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
    return 'Requirement({!r})'.format(str(self))

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
  def __json_deserialize(cls, context, location):
    if not isinstance(location.value, str):
      raise SerializationTypeError(location)
    try:
      return cls.parse(location.value)
    except ValueError as exc:
      raise SerializationValueError(location, exc)


class AuthorData(Struct):
  name = Field(str)
  email = Field(str)

  AUTHOR_EMAIL_REGEX = re.compile(r'([^<]+)<([^>]+)>')

  @JsonDeserializer
  def __json_deserialize(cls, context, location):
    if isinstance(location.value, str):
      match = cls.AUTHOR_EMAIL_REGEX.match(location.value)
      if match:
        author = match.group(1).strip()
        email = match.group(2).strip()
        return cls(author, email)
    raise NotImplementedError


class CommonPackageData(Struct):
  author = Field(AuthorData, default=None)
  license = Field(str, default=None)
  url = Field(str, default=None)


class PackageData(CommonPackageData):
  name = Field(str)
  version = Field(str)
  description = Field(str)
  long_description = Field(str, default=None)
  entry_file = Field(str, default=None)


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

  def __init__(self):
    self.python = None
    self.required = []
    self.test = []
    self.platforms = {}

  def __repr__(self):
    return 'Requirements(python={!r}, required={!r}, test={!r}, platforms={!r})'\
      .format(self.python, self.required, self.test, self.platforms)

  @JsonDeserializer
  def __deserialize(cls, context, location):
    deserialize_type = [(Requirement, {"value_type": [Requirement]})]
    items = context.deserialize(location.value, deserialize_type)

    self = cls()
    for item in items:
      if isinstance(item, Requirement):
        if item.package == 'python':
          self.python = item.version
        else:
          self.required.append(item)
      elif isinstance(item, dict):
        for key, value in item.items():
          if key == 'test':
            self.test.extend(value)
          elif key in result.platforms:
            self.platforms[key].extend(value)
          else:
            self.platforms[key] = value

    return self


class Package(Struct, DeserializableFromFileMixin):
  directory = Field(str, default=None)
  package = Field(PackageData)
  requirements = Field(Requirements, default=Requirements)
  entrypoints = Field({"value_type": [str]}, default={})

  def inherit_fields(self, monorepo):  # type: (Monorepo) -> None
    if not monorepo.packages:
      return
    for key in CommonPackageData.__fields__:
      if not getattr(self.package, key):
        setattr(self.package, key, getattr(monorepo.packages, key))
