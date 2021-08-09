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

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class WarehouseCredentials:
  username: Optional[str] = None
  password: Optional[str] = None
  test_username: Optional[str] = None
  test_password: Optional[str] = None


@dataclass
class WarehouseConfiguration(WarehouseCredentials):
  repository: Optional[str] = None
  repository_url: Optional[str] = None
  test_repository: Optional[str] = None
  test_repository_url: Optional[str] = None

  def with_creds(self, creds: WarehouseCredentials) -> 'WarehouseConfiguration':
    vars(self).update(vars(creds))
    return self


@dataclass
class PypiConfiguration:
  #: Whether publishing to PyPI is enabled.
  enabled: bool = True

  #: The credentials configuration for PyPI. Variables in the from `$VARNAME`
  #: will be substituted from environment variables.
  credentials: WarehouseCredentials = field(default_factory=WarehouseCredentials)


@dataclass
class PublishConfiguration:
  # Configuration for PyPI.
  pypi: PypiConfiguration = field(default_factory=PypiConfiguration)

  #: Additional warehouse targets to publish to.
  warehouses: Dict[str, WarehouseConfiguration] = field(default_factory=dict)
