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
from typing import Iterable, Optional

import networkx as nx
from databind.core import datamodel, field

from .abstract import AbstractProjectModel
from .version import Version
from .requirements import VersionSelector
from .release import MonorepoReleaseConfiguration
from .package import PackageModel
from .publish import PublishConfiguration


@datamodel
class InterdependencyRef:
  filename: str
  package_name: str
  version_selector: VersionSelector
  version_start: int
  version_end: int


@datamodel
class MonorepoModel(AbstractProjectModel):

  def get_inter_dependencies(self) -> Iterable[InterdependencyRef]:
    """
    Returns an iterable that contains the names of packages in the mono repository to a list
    of their dependencies on other packages in the same repository. Note that it does so
    by regex-matching in the package configuration file rather than reading the deserialized
    package data in order to return start and end index data.
    """

    for package in self.project.packages:
      yield from self.get_inter_dependencies_for(package)

  def get_inter_dependencies_for(self, package: PackageModel) -> Iterable[InterdependencyRef]:
    """
    Like #get_inter_dependencies() but for a single package.
    """

    regex = re.compile(r'^\s*- +([A-z0-9\.\-_]+) *([^\n:]+)?$', re.M)
    package_names = set(p.name for p in self.project.packages)
    with open(package.filename) as fp:
      content = fp.read()
      for match in regex.finditer(content):
        package_name, version_selector = match.groups()
        if package_name not in package_names:
          continue
        if version_selector:
          version_selector = VersionSelector(version_selector)
        yield InterdependencyRef(package.filename, package_name, version_selector, match.start(2), match.end(2))

  def get_inter_dependencies_graph(self) -> nx.DiGraph:
    """
    Create a directed graph from the inter dependencies of packages in the mono repo.
    """

    graph = nx.DiGraph()
    for package in self.project.packages:
      graph.add_node(package.name)
    for package in self.project.packages:
      for ref in self.get_inter_dependencies_for(package):
        graph.add_edge(ref.package_name, package.name)

    return graph

  # AbstractProjectModel Overrides

  publish: PublishConfiguration = field(default_factory=PublishConfiguration)
  release: MonorepoReleaseConfiguration = field(default_factory=MonorepoReleaseConfiguration)

  def get_name(self) -> str:
    return self.name

  def get_version(self) -> Optional[Version]:
    return self.version
