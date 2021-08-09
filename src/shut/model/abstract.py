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

from dataclasses import dataclass, field
import abc
import os
import warnings
from typing import List, Optional

from .author import Author
from .changelog import ChangelogConfiguration
from .release import ReleaseConfiguration
from .version import Version
from shut.utils.fs import get_file_in_directory


@dataclass
class AbstractProjectModel(abc.ABC):
  name: str
  version: Optional[Version] = None
  author: Optional[Author] = None
  license: Optional[str] = None
  license_file: Optional[str] = None
  url: Optional[str] = None
  changelog: ChangelogConfiguration = field(default_factory=ChangelogConfiguration)
  release: ReleaseConfiguration = field(default_factory=ReleaseConfiguration)

  def __post_init__(self) -> None:
    # May be filled during the deserialization process to track additional metadata.
    self._project: Optional['Project'] = None
    self._filename: Optional[str] = None
    self.unknown_keys: List[str] = []

  @property
  def project(self) -> 'Project':
    if self._project is None:
      raise RuntimeError(f'{type(self).__name__}.project is not set')
    return self._project

  @project.setter
  def project(self, project: 'Project') -> None:
    self._project = project

  @property
  def filename(self) -> str:
    if self._filename is None:
      raise RuntimeError(f'{type(self).__name__}.filename is not set')
    return self._filename

  @filename.setter
  def filename(self, filename: str) -> None:
    self._filename = filename

  def get_name(self) -> str:
    warnings.warn(f'{type(self).__name__}.get_name() is deprecated, use .name instead', DeprecationWarning)
    return self.name

  def get_version(self) -> Optional[Version]:
    warnings.warn(f'{type(self).__name__}.get_version() is deprecated, use .version instead', DeprecationWarning)
    return self.version

  def get_tag(self, version: Version) -> str:
    return self.release.tag_format.format(name=self.get_name(), version=version)

  def get_directory(self) -> str:
    assert self.filename
    return os.path.dirname(self.filename)

  def get_author(self) -> Optional[Author]:
    return self.author

  def get_changelog_directory(self) -> str:
    assert self.filename
    return os.path.join(os.path.dirname(self.filename), self.changelog.directory)

  def get_license_file(self, inherit: bool = False) -> Optional[str]:
    """
    Returns the absolute path to the LICENSE file for this package.
    """

    assert self.filename
    if self.license_file:
      return self.license_file

    return get_file_in_directory(
      directory=os.path.dirname(self.filename),
      prefix='LICENSE.',
      preferred=['LICENSE', 'LICENSE.txt', 'LICENSE.rst', 'LICENSE.md'])


from . import Project  # pylint: disable=unused-import
