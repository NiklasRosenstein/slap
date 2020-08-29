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

import os
import shlex
import subprocess
import sys
from typing import Dict, List

import click

from shut.commands import project
from shut.model import dump, PackageModel
from shut.model.requirements import Requirement, VersionSelector
from . import pkg


@pkg.group()
def requirements():
  """
  Update requirements in the package configuration.
  """


@requirements.command(no_args_is_help=True)
@click.argument('packages', nargs=-1)
@click.option('--test', is_flag=True)
def add(packages, test):
  """
  Install packages and save them to the package requirements.

  Note that this will remove any extranous whitespaces, empty lines and comments
  from the package configuration.
  """

  package = project.load_or_exit(expect=PackageModel)

  reqs = [Requirement.parse(x) for x in packages]

  python = shlex.split(os.getenv('PYTHON', 'python'))
  pip = python + ['-m', 'pip']
  res = subprocess.call(pip + ['install'] + [r.to_setuptools() for r in reqs])
  if res != 0:
    sys.exit('error: pip install failed')

  scoped_reqs = [r for r in reqs if r.version != VersionSelector.ANY]
  unscoped_packages = [r.package for r in reqs if r.version == VersionSelector.ANY]

  if unscoped_packages:
    package_versions = get_pip_versions(pip, unscoped_packages)
    scoped_reqs += [Requirement.parse(f'{k} ^{v}') for k, v in package_versions.items()]

  target = package.test_requirements if test else package.requirements

  # Update any existing requirements.
  seen = set()
  for req in target:
    matching_req = next((x for x in scoped_reqs if x.package == req.package), None)
    if matching_req:
      seen.add(req.package)
      req.version = matching_req.version

  # Append the remaining reqs.
  target += [r for r in scoped_reqs if r.package not in seen]

  dump(package, package.filename)


def get_pip_versions(pip: List[str], package_names: List[str]) -> Dict[str, str]:
  command = pip + ['show'] + package_names
  output = subprocess.check_output(command).decode()
  result = {}
  for chunk in output.split('---'):
    current = {}
    for line in chunk.splitlines():
      key, value = line.partition(':')[::2]
      if key:
        current[key] = value.strip()
    result[current['Name']] = current['Version']
  return result
