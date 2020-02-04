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

from nr.databind.core import Field, Struct
from nr.interface import implements, override
from nr.stream import Stream
from shore.core.plugins import IPackagePlugin, IPublishTarget
from shore.model import Package
from typing import Iterable
import os
import subprocess


@implements(IPublishTarget)
class TwinePublishTarget(Struct):
  name = Field(str)
  selectors = Field([str])
  repository = Field(str, default=None)
  repository_url = Field(str, default=None)
  test_repository = Field(str, default=None)
  test_repository_url = Field(str, default=None)
  sign = Field(bool, default=False)
  sign_with = Field(str, default=None)
  identity = Field(str, default=None)
  username = Field(str, default=None)
  password = Field(str, default=None)
  skip_existing = Field(bool, default=False)
  cert = Field(str, default=None)
  client_cert = Field(str, default=None)

  def get_name(self) -> str:
    return self.name

  def get_build_selectors(self) -> Iterable[str]:
    return self.selectors

  def publish(self, builds, test, build_directory):
    files = Stream.concat(x.get_build_artifacts() for x in builds)
    files = files.map(lambda x: os.path.join(build_directory, x)).collect()
    command = ['twine', 'upload']
    repo, repo_url = (self.repository, self.repository_url) if not test else \
        (self.test_repository, self.test_repository_url)
    if repo:
      command += ('--repository', repo)
    if repo_url:
      command += ('--repository-url', repo_url)
    if self.sign:
      command.append('--sign')
    if self.sign_with:
      command += ('--sign-with', self.sign_with)
    if self.identity:
      command += ('--identity', self.identity)
    if self.username:
      command += ('--username', self.username)
    if self.password:
      command += ('--password', self.password)
    if self.skip_existing:
      command.append('--skip-existing')
    if self.cert:
      command += ('--cert', self.cert)
    if self.client_cert:
      command += ('--client-cert', self.client_cert)
    command += files
    command += ['--verbose']
    subprocess.check_call(command)


@implements(IPackagePlugin)
class PypiPublisher:

  @override
  def get_package_publish_targets(self, package: Package) -> Iterable[IPublishTarget]:
    yield TwinePublishTarget('pypi', ['setuptools'], test_repository_url='https://test.pypi.org/legacy/')
