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

from typing import Iterable

from shut.model import PackageModel, Project
from shut.model.publish import WarehouseCredentials, WarehouseConfiguration
from shut.model.target import TargetId
from .core import Publisher, PublisherProvider, register_publisher_provider


class WarehousePublisher(Publisher):

  def __init__(self, id_: TargetId, config: WarehouseConfiguration) -> None:
    self._id = id_
    self.config = config

  @classmethod
  def from_pypi_credentials(cls, id_: TargetId, creds: WarehouseCredentials) -> 'WarehousePublisher':
    return cls(id_, WarehouseCredentials().with_creds(creds))

  # Publisher Overrides

  def publish(self):
    raise NotImplementedError('todo')

  # Target Overrides

  @property
  def id(self) -> TargetId:
    return self._id


class WarehouseProvider(PublisherProvider[PackageModel]):

  # PublisherProvider Overrides

  def get_publishers(self) -> Iterable[Publisher]:
    if package.data.publish.pypi.enabled:
      yield WarehousePublisher.from_pypi_credentials(
        TargetId('warehouse', 'pypi'),
        package.data.publish.pypi.credentials)

    for name, config in package.data.publish.warehouse.items():
      yield WarehouseProvider(TargetId('warehouse', name), config)


register_publisher_provider(PackageModel, WarehouseProvider)
