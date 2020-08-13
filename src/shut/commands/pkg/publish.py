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

from typing import List

import click

from shut.model import PackageModel
from shut.publish import Publisher
from shut.publish.warehouse import WarehousePublisher
from . import pkg
from .. import project


def get_publisher(package: PackageModel, target: str) -> Publisher:
  if target == 'pypi' and package.data.publish.pypi:
    publisher = WarehousePublisher.pypi_from_credentials(
      package.data.publish.pypi_credentials)
  elif target in package.data.publish.warehouses:
    publisher = WarehousePublisher.from_config(package.data.publish.warehouses[target])
  else:
    raise ValueError(f'unknown publish target {target!r}')

  return publisher


def get_publisher_names(package: PackageModel) -> List[str]:
  targets = []
  if package.data.publish.pypi.enabled:
    targets.append('pypi')
  targets.extend(package.data.publish.warehouses.keys())
  return targets


@pkg.command()
@click.argument('target')
@click.option('--ls', is_flag=True)
def publish(target, ls):
  """
  Publish the package to PyPI or another target.
  """

  if ls and target:
    sys.exit('error: conflicting options')

  if ls:
    names = get_publisher_names()
    if not names:
      print('no publishes configured')
    else:
      print('available publishers:')
      for name in names:
        print(f'  {name}')
    return

  package = project.load_or_exit(expect=PackageModel)

  try:
    publisher = get_publisher(package, target)
  except ValueError as exc:
    sys.exit(f'error: {exc}')

  if isinstance(publisher, WarehousePublisher):
    build_targets = get_build_targets('setuptools')
  else:
    raise RuntimeError

  run_build_targets(build_targets)
  publisher.publish(build_targets)
