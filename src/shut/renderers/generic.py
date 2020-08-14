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

import re
from typing import Iterable

from shut.model import AbstractProjectModel, MonorepoModel
from shut.utils.io.virtual import VirtualFiles
from .core import Renderer, get_version_refs, register_renderer, VersionRef


class GenericRenderer(Renderer[AbstractProjectModel]):

  # Renderer[AbstractProjectModel] Overrides

  def get_files(self, files: VirtualFiles, obj: AbstractProjectModel) -> None:
    pass

  def get_version_refs(self, obj: AbstractProjectModel) -> Iterable[VersionRef]:
    assert obj.filename
    assert obj.project

    # Return a reference to the version number in the package or monorepo model.
    regex = '^\s*version\s*:\s*[\'"]?(.*?)[\'"]?\s*(#.*)?$'
    with open(obj.filename) as fp:
      match = re.search(regex, fp.read(), re.S | re.M)
      if match:
        yield VersionRef(obj.filename, match.start(1), match.end(1), match.group(1))

    if isinstance(obj, MonorepoModel) and obj.release.single_version:
      for package in obj.project.packages:
        yield from get_version_refs(package)


register_renderer(AbstractProjectModel, GenericRenderer)
