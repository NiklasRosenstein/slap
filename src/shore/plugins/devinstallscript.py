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

from shore.core.plugins import FileToRender, IPlugin, Options, Option
from nr.commons.algo.graph import toposort
from nr.interface import implements, override
import os


@implements(IPlugin)
class DevInstallScriptRenderer(object):
  """ Renders a "bin/dev-install" shell script for a monorepo that installs
  Pip packages in the order, respecting their inter-dependencies. """

  def __init__(self, options):
    self._options = options

  @override
  @classmethod
  def get_options(cls):  # type: () -> Options
    return Options({
      'filename': Option(default='bin/dev-install')
    })

  @override
  def get_files_to_render(self, context):  # type: (PluginContext) -> Iterable[FileToRender]
    if not context.monorepo:
      return; yield

    # Collect packages and their dependencies for this monorepo.
    nodes = {}
    packages = context.monorepo.get_packages()
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

    yield FileToRender(context.monorepo.directory,
      self._options['filename'], write_script).with_chmod('+x')

  @override
  def perform_checks(self, context):
    return; yield
