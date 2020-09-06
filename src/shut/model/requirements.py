# -*- coding: utf8 -*-
# Copyright (c) 2020 Niklas Rosenstein
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

import abc
import enum
import os
import posixpath
import re
from typing import List, Union
from urllib.parse import urlparse

from databind.core import datamodel

from .version import bump_version, Version


class VersionSelector(object):
  """
  Represents a version selector that limits which versions of a requirement can be
  picked. It simply wraps a string, but if the string looks like a semver selector,
  it can be converted into a ``setuptools`` compatible version selector string (see
  #to_setuptools()).
  """

  ANY: 'VersionSelector'

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
    """
    Converts the version selector to a string that Setuptools/Pip can understand by
    expanding the `~` and `^` range selectors.

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

    s = self._string + '.0' * (3 - self._string.count('.') - 1)
    return re.sub(regex, sub, s)

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


@datamodel(serialize_as=lambda: Union[Requirement, VendoredRequirement])
class BaseRequirement(metaclass=abc.ABCMeta):

  @classmethod
  @abc.abstractmethod
  def databind_json_load(self, value, context):
    pass

  @abc.abstractmethod
  def databind_json_dump(self, context):
    pass


@datamodel
class Requirement(BaseRequirement):
  """
  A Requirement is simply combination of a package name and a version selector.
  """

  INVALID_CHARACTERS = '/&:;\'"!{}[]()%'

  package: str
  version: VersionSelector

  def __str__(self):
    if self.version == VersionSelector.ANY:
      return self.package
    return '{} {}'.format(self.package, self.version)

  def __repr__(self):
    return repr(str(self))

  @classmethod
  def parse(cls, requirement_string: str) -> 'Requirement':
    error = ValueError('invalid requirement: {!r}'.format(requirement_string))
    if set(requirement_string) & set(cls.INVALID_CHARACTERS):
      raise error
    match = re.match(r'^\s*([\w\d\-\._]+)(?:\s*(.+))?$', requirement_string)
    if not match:
      raise error
    package, version = match.groups()
    return cls(package, VersionSelector(version or VersionSelector.ANY))

  def to_setuptools(self) -> str:
    if self.version == VersionSelector.ANY:
      return self.package
    return '{} {}'.format(self.package, self.version.to_setuptools())

  @classmethod
  def databind_json_load(cls, value, context):
    if isinstance(value, str):
      try:
        return Requirement.parse(value)
      except ValueError as exc:
        raise context.type_error(str(exc))
    return NotImplemented

  def databind_json_dump(self, context):
    return str(self)


@datamodel
class VendoredRequirement(BaseRequirement):
  """
  A vendored requirement is either a relative path or a string prefixed with `git+` that
  Pip understands as an installable source.
  """

  INVALID_CHARACTERS = '*&^:;\'"!{}[]()%'

  class Type(enum.Enum):
    Git = enum.auto()
    Path = enum.auto()

  type: Type
  value: str

  def __str__(self):
    return self.value

  @classmethod
  def parse(cls, requirement_string: str, fallback_to_path: bool = False) -> 'VendoredRequirement':
    error = ValueError(f'invalid vendored requirement: {requirement_string!r}')
    if set(requirement_string) & set(cls.INVALID_CHARACTERS):
      raise error
    if requirement_string.startswith('git+'):
      url = requirement_string[4:]
      if not urlparse(url).scheme:
        raise error
      return cls(cls.Type.Git, requirement_string)
    result = urlparse(requirement_string)
    if result.scheme:
      raise error
    if not requirement_string.startswith('./'):
      if not fallback_to_path:
        raise error
      if os.name == 'nt':
        requirement_string = requirement_string.replace('\\', '/')
      requirement_string = './' + posixpath.normpath(requirement_string)
    return cls(cls.Type.Path, requirement_string)

  def to_setuptools(self) -> str:
    raise RuntimeError('VendoredRequirement is not supported in setuptools')

  def to_pip_args(self, root: str, develop: bool) -> List[str]:
    args = [self.value]
    if self.type == self.Type.Path and develop:
      args.insert(0, '-e')
      args[1] = os.path.join(root, args[1])
    return args

  @classmethod
  def databind_json_load(cls, value, context):
    if isinstance(value, str):
      try:
        return VendoredRequirement.parse(value)
      except ValueError as exc:
        raise context.type_error(str(exc))
    raise context.type_error()

  def databind_json_dump(self, context):
    return str(self)
