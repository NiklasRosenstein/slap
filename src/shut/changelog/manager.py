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

from shore.util.version import Version

from . import v1, v2, v3
from nr.databind.core import ObjectMapper, SkipDefaults
from nr.databind.json import JsonModule
from typing import Iterable, Optional
import datetime
import os
import yaml

mapper = ObjectMapper(JsonModule())
supported_changelog_types = (
  v3.Changelog,
  v2.Changelog,
  v1.Changelog,
)


class Changelog:
  """
  Represents a changelog on disk.
  """

  def __init__(self, filename: str, version: Optional[Version]) -> None:
    self.filename = filename
    self.version = version
    self.data = v3.Changelog(changes=[])

  @property
  def entries(self):
    return self.data.changes

  def exists(self) -> bool:
    " Returns #True if the changelog file exists. "

    return os.path.isfile(self.filename)

  def load(self) -> None:
    " Loads the data from the file of this changelog. "

    with open(self.filename) as fp:
      raw_data = yaml.safe_load(fp)

    data = mapper.deserialize(raw_data, supported_changelog_types, filename=self.filename)
    if not isinstance(data, v3.Changelog):
      data = v3.Changelog.migrate(data)

    self.data = data

  def save(self, create_directory: bool = False) -> None:
    " Saves the changelog. It will always save the changelog in the newest supported format. "

    if create_directory:
      os.makedirs(os.path.dirname(self.filename), exist_ok=True)
    data = mapper.serialize(self.data, v3.Changelog)
    with open(self.filename, 'w') as fp:
      yaml.safe_dump(data, fp, sort_keys=False)

  def set_release_date(self, date: datetime.date) -> None:
    self.data.release_date = date

  def add_entry(self, entry) -> None:
    assert isinstance(entry, v3.Changelog.Entry), type(entry)
    self.data.changes.append(entry)


class ChangelogManager:

  def __init__(self, directory: str) -> None:
    self.directory = directory
    self._cache = {}

  def _get(self, name: str, version: Optional[str]) -> Changelog:
    key = (name, str(version))
    if key in self._cache:
      return self._cache[key]
    changelog = Changelog(os.path.join(self.directory, name), version)
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
    unreleased.data.release_date = datetime.date.today()
    unreleased.save()

    os.rename(unreleased.filename, self.version(version).filename)
    self._cache.clear()

    return self.version(version)

  def all(self) -> Iterable[Changelog]:
    """
    Yields all changelogs.
    """

    for name in os.listdir(self.directory):
      if not name.endswith('.yml'):
        continue
      if name == '_unreleased.yml':
        yield self.unreleased
      else:
        version = Version(name[:-4])
        yield self.version(version)
