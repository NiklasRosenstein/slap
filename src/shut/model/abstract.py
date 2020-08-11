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
import os
from typing import List, Optional
from databind.core import datamodel, field
from .changelog import ChangelogConfiguration
from .release import ReleaseConfiguration
from .version import Version


@datamodel
class AbstractProjectModel(metaclass=abc.ABCMeta):
  filename: Optional[str] = field(derived=True, default=None)
  unknown_keys: List[str] = field(derived=True, default_factory=list)
  changelog: ChangelogConfiguration = field(default_factory=ChangelogConfiguration)
  release: ReleaseConfiguration = field(default_factory=ReleaseConfiguration)

  @abc.abstractmethod
  def get_name(self) -> str:
    pass

  @abc.abstractmethod
  def get_version(self) -> Optional[Version]:
    pass

  def get_tag(self, version: Version) -> str:
    return self.release.tag_format.format(name=self.get_name(), version=version)

  def get_directory(self) -> str:
    return os.path.dirname(self.filename)

  def get_changelog_directory(self) -> str:
    return os.path.join(os.path.dirname(self.filename), self.changelog.directory)
