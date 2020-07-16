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

from .author import Author
from .changelog import ChangelogConfiguration
from .linter import LinterConfiguration
from .release import ReleaseConfiguration
from .requirements import Requirement
from .version import Version
from nr.databind.core import Field, FieldName, Struct
from typing import Dict, List


class PackageData(Struct):
  name = Field(str)
  modulename = Field(str, default=None)
  version = Field(Version, default=None)
  author = Field(Author)
  description = Field(str, default=None)
  license = Field(str, default=None)
  url = Field(str, default=None)
  readme = Field(str, default=None)
  wheel = Field(bool, default=True)
  universal = Field(bool, default=None)
  typed = Field(bool, default=False)
  requirements = Field(List[Requirement], default=list)
  test_requirements = Field(List[Requirement], FieldName('test-requirements'), default=list)
  extra_requirements = Field(Dict[str, List[Requirement]], FieldName('extra-requirements'), default=dict)
  source_directory = Field(str, FieldName('source-directory'), default='src')
  exclude = Field(List[str], default=lambda: ['test', 'tests', 'docs'])
  entrypoints = Field(Dict[str, List[str]], default=dict)
  classifiers = Field(List[str], default=list)
  keywords = Field(List[str], default=list)
  # TODO: Data files


class InstallConfiguration(Struct):
  hooks = Field(dict(
    before_install=Field(List[str], FieldName('before-install'), default=list),
    after_install=Field(List[str], FieldName('after-install'), default=list),
    before_develop=Field(List[str], FieldName('before-develop'), default=list),
    after_develop=Field(List[str], FieldName('after-develop'), default=list),
  ), default=Field.DEFAULT_CONSTRUCT)


class PackageModel(Struct):
  filename = Field(str, hidden=True, default=None)
  data = Field(PackageData, FieldName('package'))
  changelog = Field(ChangelogConfiguration, default=Field.DEFAULT_CONSTRUCT)
  install = Field(InstallConfiguration, default=Field.DEFAULT_CONSTRUCT)
  linter = Field(LinterConfiguration, default=Field.DEFAULT_CONSTRUCT)
  release = Field(ReleaseConfiguration, default=Field.DEFAULT_CONSTRUCT)
