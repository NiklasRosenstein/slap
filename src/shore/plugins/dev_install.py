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

from pkg_resources import resource_string
from shore import __version__
from shore.core.plugins import FileToRender, IMonorepoPlugin
from shore.model import Monorepo, Package
from nr.algo.graph.toposort import toposort
from nr.databind.core import Field, Struct
from nr.interface import implements, override
from typing import Dict, Iterable
import json
import os


def _dirname(package: Package):
  return os.path.basename(package.directory)


@implements(IMonorepoPlugin)
class DevInstallRenderer:
  """ Renders a "bin/dev-install" shell script for a monorepo that installs
  Pip packages in the order, respecting their inter-dependencies. """

  class Config(Struct):
    filename = Field(str, default='bin/dev-install')

  @override
  def get_monorepo_files(self, monorepo: Monorepo) -> Iterable[FileToRender]:
    nodes = self._get_interpackage_dependencies(monorepo)
    pkg_order = list(toposort(sorted(nodes.keys()), lambda x: nodes[x]['requires']))
    package_def = '[\n'
    for pkgname in pkg_order:
      package = {
        'name': pkgname,
        'requires': nodes[pkgname]['requires'],
        'extra_requires': nodes[pkgname]['extra_requires']}
      package_def += '  ' + json.dumps(package, sort_keys=True) + ',\n'
    package_def += ']'

    def write_script(_current, fp):
      template = resource_string('shore', 'templates/dev_install/dev-install').decode('utf8')
      content = (template
        .replace('{{shore_version}}', __version__)
        .replace('{{package_def}}', package_def))
      fp.write(content)

    yield FileToRender(monorepo.directory,
      self.config.filename, write_script).with_chmod('+x')

  def _get_interpackage_dependencies(self, monorepo: Monorepo) -> Dict[str, Dict]:
    nodes = {}
    package_name_mapping = {}

    packages = list(monorepo.get_packages())
    for package in packages:
      package_name_mapping[package.name] = _dirname(package)
      nodes[_dirname(package)] = {
        'directory': os.path.basename(package.directory),
        'requires': [],
        'extra_requires': {}
      }

    def _flatten_reqs(dst, reqs):
      for req in reqs.required if reqs else ():
        if req.package in package_name_mapping:
          dst.append(package_name_mapping[req.package])

    for package in packages:
      _flatten_reqs(nodes[_dirname(package)]['requires'], package.requirements)
      _flatten_reqs(nodes[_dirname(package)].setdefault('test', []), package.requirements.test)
      for extra, reqs in package.requirements.extra.items():
        _flatten_reqs(nodes[_dirname(package)].setdefault(extra, []), reqs)

    return nodes
