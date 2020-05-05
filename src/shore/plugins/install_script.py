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
from shore.core.plugins import FileToRender, IMonorepoPlugin
from shore.model import Monorepo, Package, Requirements
from shore.static import GENERATED_FILE_REMARK
from nr.databind.core import Field, Struct
from nr.interface import implements, override
from typing import Dict, Iterable, List
import networkx as nx
import json
import os


def _dirname(package: Package):
  return os.path.basename(package.directory)


@implements(IMonorepoPlugin)
class InstallScriptRenderer:
  """
  Renders a self-contained Python script for a monorepo that installs Pip packages
  in order, respecting their inter-dependencies.
  """

  class Config(Struct):
    filename = Field(str, default='bin/install')

  @override
  def get_monorepo_files(self, monorepo: Monorepo) -> Iterable[FileToRender]:
    graph = self._get_interpackage_dependencies(monorepo)
    pkg_order = list(nx.algorithms.dag.topological_sort(graph))
    package_def = '[\n'
    for pkgname in pkg_order:
      package = {
        'name': pkgname,
        'requires': graph.nodes[pkgname]['requires'],
        'extra_requires': graph.nodes[pkgname]['extra_requires']}
      package_def += '  ' + json.dumps(package, sort_keys=True) + ',\n'
    package_def += ']'

    def write_script(_current, fp):
      template = resource_string('shore', 'templates/install_script/install').decode('utf8')
      content = (template
        .replace('{{package_def}}', package_def)
        .replace('{{generated_file_remark}}', GENERATED_FILE_REMARK))
      fp.write(content)

    yield FileToRender(monorepo.directory,
      self.config.filename, write_script).with_chmod('+x')

  def _get_interpackage_dependencies(self, monorepo: Monorepo) -> nx.DiGraph:
    """
    Constructs a directed graph of the dependencies between the packages in
    *monorepo*. The nodes in the graph are the directory names of the packages.
    """

    packages = sorted(monorepo.get_packages(), key=lambda x: x.name, reverse=True)
    package_name_mapping = {}
    graph = nx.DiGraph()

    # Initialize graph nodes.
    for package in packages:
      node_id = _dirname(package)
      package_name_mapping[package.name] = node_id
      node = graph.add_node(
        node_id,
        directory=os.path.basename(package.directory),
        requires=[],
        extra_requires={})

    # Helper function to get just the deps that we need.
    def _flatten_reqs(dst: List[str], reqs: Requirements) -> List[str]:
      for req in reqs.required if reqs else ():
        if req.package in package_name_mapping:
          dst.append(package_name_mapping[req.package])
      return dst

    # Process requirements and create edges.
    for package in packages:
      node_id = package_name_mapping[package.name]
      extras = graph.nodes[node_id]['extra_requires']
      total_deps = _flatten_reqs([], package.requirements)
      graph.nodes[node_id]['requires'] += total_deps

      test = _flatten_reqs([], package.requirements.test)
      if test:
        total_deps += test
        extras['test'] = test

      for extra, reqs in package.requirements.extra.items():
        extra_reqs = _flatten_reqs([], reqs)
        if extra_reqs:
          total_deps += extra_reqs
          extras[extra] = extra_reqs

      [graph.add_edge(o, node_id) for o in total_deps]

    return graph
