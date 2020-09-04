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
import subprocess as sp
import sys
from typing import List

import click
from nr.stream import concat
from termcolor import colored

from shut.model import PackageModel
from . import pkg
from .. import project


class Requirement:

  def __init__(self, name: str, develop: bool = False, extras: str = None) -> None:
    self.name = name
    self.develop = develop
    self.extras = extras

  def __str__(self):
    return ' '.join(self.to_args())

  def __repr__(self):
    return 'Requirement({})'.format(str(self))

  def to_args(self) -> List[str]:
    args = [self.name + ('[{}]'.format(self.extras) if self.extras else '')]
    if self.develop:
      args.insert(0, '-e')
    return args


@pkg.command()
@click.option('--develop/--no-develop', default=True,
  help='Install in develop mode (default: true)')
@click.option('--inter-deps/--no-inter-deps', default=True,
  help='Install package inter dependencies from inside the same monorepo (default: true)')
@click.option('--extra', help='Specify one or more extras to install.')
@click.option('-U', '--upgrade', is_flag=True, help='Upgrade all packages (forwarded to pip install).')
@click.option('-q', '--quiet', is_flag=True, help='Quiet install')
@click.option('--pip-args', help='Additional arguments to pass to Pip.')
@click.option('--dry', is_flag=True, help='Print the Pip command to stdout instead of running it.')
def install(develop, inter_deps, extra, upgrade, quiet, pip_args, dry):
  """
  Install the package using `python -m pip`. If the package is part of a mono repository,
  inter-dependencies will be installed from the mono repsitory rather than from PyPI.

  The command used to invoke Pip can be overwritten using the `PIP` environment variable.
  """

  package = project.load_or_exit(expect=PackageModel)
  extras = set((extra or '').split(','))
  reqs = []

  # Pip does not understand "test" as an extra and does not have an option to
  # install test requirements.
  if 'test' in extras:
    extras.discard('test')
    extra = ','.join(extras)
    reqs += [Requirement(x.to_setuptools()) for x in package.test_requirements]

  reqs.append(Requirement(package.get_directory(), develop, extra))

  if project.monorepo and inter_deps:
    # TODO(NiklasRosenstein): get_inter_dependencies_for() does not currently differentiate
    #   between normal, test and extra requirements.
    project_packages = {p.name: p for p in project.packages}
    for ref in project.monorepo.get_inter_dependencies_for(package):
      dep = project_packages[ref.package_name]
      if not ref.version_selector.matches(dep.version):
        print('note: skipping inter-dependency on package "{}" because the version selector '
              '{} does not match the present version {}'
              .format(dep.name, ref.version_selector, dep.version), file=sys.stderr)
      else:
        reqs.insert(0, Requirement(dep.get_directory(), develop))

  pip_bin = shlex.split(os.getenv('PIP', 'python -m pip'))
  command = pip_bin + ['install'] + list(concat(r.to_args() for r in reqs))
  if upgrade:
    command.append('--upgrade')
  if quiet:
    command.append('--quiet')
  command += shlex.split(pip_args) if pip_args else []

  if dry:
    print(' '.join(map(shlex.quote, command)))
  else:
    sys.exit(sp.call(command))
