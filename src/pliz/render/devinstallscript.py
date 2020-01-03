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

from .base import Option, BaseRenderer, FileToRender
from nr.commons.algo.graph import toposort
import os


class DevInstallScriptRenderer(BaseRenderer):
  """ Renders a "bin/dev-install" shell script for a monorepo that installs
  Pip packages in the order, respecting their inter-dependencies. """

  options = [
    Option('filename', default='bin/dev-install'),
  ]

  def files_for_monorepo(self, item):  # type: (Monorepo) -> Iterable[FileToRender]
    # Collect packages and their dependencies for this monorepo.
    nodes = {}
    packages = item.list_packages()
    for package in packages:
      nodes[package.package.name] = {
        'directory': os.path.basename(package.directory),
        'dependencies': []
      }
    for package in packages:
      for req in package.requirements.required:
        if req.package in nodes:
          nodes[package.package.name]['dependencies'].append(req.package)
    # Sort the packages in topological order for the install script.
    ordered = list(toposort(sorted(nodes.keys()), lambda x: nodes[x]['dependencies']))
    # Write the install script.
    def write_script(_current, fp):
      fp.write('#!/bin/sh\n\n')
      fp.write('${PYTHON:-python} -m pip install \\\n')
      for package in ordered:
        directory = nodes[package]['directory']
        dependencies = nodes[package]['dependencies']
        fp.write('  -e "{}"'.format(directory))
        if dependencies:
          fp.write(' `# depends on {}`'.format(', '.join(dependencies)))
        if package != ordered[-1]:
          fp.write(' \\')
        fp.write('\n')

    yield FileToRender(self.config['filename'], write_script)
