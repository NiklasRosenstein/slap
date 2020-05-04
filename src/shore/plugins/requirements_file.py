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

from shore.core.plugins import FileToRender, IPackagePlugin
from shore.model import Package
from shore.static import GENERATED_FILE_REMARK
from nr.interface import implements, override
from typing import Dict, Iterable
import json
import os


@implements(IPackagePlugin)
class RequirementsFileRenderer:

  @override
  def get_package_files(self, package: Package) -> Iterable[FileToRender]:
    def _render_requirements(_current, fp):
      fp.write(GENERATED_FILE_REMARK + '\n')
      for req in package.requirements.required:
        fp.write(req.to_setuptools() + '\n')
    yield FileToRender(package.directory, 'requirements.txt', _render_requirements)
