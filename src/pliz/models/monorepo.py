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
from .package import CommonPackageData, Package
from nr.databind.core import Field, Struct
import os


class ProjectData(Struct):
  name = Field(str)
  version = Field(str, default=None)
  use = Field([str], default=list)


class Monorepo(Struct, DeserializableFromFileMixin):
  directory = Field(str, default=None)
  project = Field(ProjectData)
  packages = Field(CommonPackageData, default=None)
  plugins = Field(dict, default=dict)

  @property
  def name(self):
    return self.project.name

  def list_packages(self):
    results = []
    for name in os.listdir(self.directory):
      path = os.path.join(self.directory, name, 'package.yaml')
      if os.path.isfile(path):
        package = Package.load(path)
        package.inherit_fields(self)
        results.append(package)
    return results
