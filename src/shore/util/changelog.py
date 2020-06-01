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

from nr.databind.core import Field, ObjectMapper, Struct
from shore.util.version import Version
from typing import Optional
import os
import yaml


class ChangelogEntry(Struct):
  types = Field([str])
  issues = Field([(str, int)], default=list)
  components = Field([str])
  description = Field(str)


class Changelog:

  def __init__(self, filename: str, version: Optional[Version], mapper: ObjectMapper) -> None:
    self.filename = filename
    self.version = version
    self.mapper = mapper
    self.entries = []

  def exists(self) -> bool:
    return os.path.isfile(self.filename)

  def load(self) -> None:
    with open(self.filename) as fp:
      data = yaml.safe_load(fp)
    self.entries = self.mapper.deserialize(data, [ChangelogEntry], filename=self.filename)

  def save(self, create_directory: bool = False) -> None:
    if create_directory:
      os.makedirs(os.path.dirname(self.filename), exist_ok=True)
    data = self.mapper.serialize(self.entries, [ChangelogEntry])
    with open(self.filename, 'w') as fp:
      yaml.safe_dump(data, fp, sort_keys=False)

  def add_entry(self, entry: ChangelogEntry) -> None:
    self.entries.append(entry)


class ChangelogManager:

  TYPES = frozenset(['fix', 'improvement', 'docs', 'change', 'refactor', 'feature'])

  def __init__(self, directory: str, mapper: ObjectMapper) -> None:
    self.directory = directory
    self.mapper = mapper
    self._cache = {}

  def _get(self, name: str, version: Optional[str]) -> Changelog:
    key = (name, str(version))
    if key in self._cache:
      return self._cache[key]
    changelog = Changelog(os.path.join(self.directory, name), version, self.mapper)
    if os.path.isfile(changelog.filename):
      changelog.load()
    self._cache[key] = changelog
    return changelog

  @property
  def unreleased(self) -> Changelog:
    return self._get('_unreleased.yml', None)

  def version(self, version: Version) -> Changelog:
    return self._get(str(version) + '.yml', version)

  def release(self, version: Version) -> Changelog:
    """
    Renames the unreleased changelog to the file name for the specified *version*.
    """

    unreleased = self.unreleased
    os.rename(unreleased.filename, self.version(version).filename)
    self._cache.clear()
    return self.version(version)
