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

from .core import Command
from ..model.monorepo import Monorepo
from ..model.package import Package
import os

_stop_searching_if_found = ['.git']


def find_configuration(path=None, load=True):
  """ Finds the current Package and Monorepo configuration from the specified
  *path* or the current working directory. Returns a tuple of (monorepo,
  package). If *load* is set to True, the files will be loaded, otherwise
  the filenames are returned. """

  filenames = {'monorepo.yaml': None, 'package.yaml': None}

  path = path or os.getcwd()
  while True:
    for name in filenames:
      if filenames[name]:
        continue
      filename = os.path.join(path, name)
      if os.path.isfile(filename):
        filenames[name] = filename
    if sum(1 for x in filenames.values() if x is not None) == 2:
      break
    for filename in _stop_searching_if_found:
      if os.path.exists(os.path.join(path, filename)):
        break
    next_path = os.path.dirname(path)
    if next_path == path:
      break
    path = next_path

  monorepo, package = filenames['monorepo.yaml'], filenames['package.yaml']
  if load and filenames['monorepo.yaml']:
    monorepo = Monorepo.load(filenames['monorepo.yaml'])
  if load and filenames['package.yaml']:
    package = Package.load(filenames['package.yaml'])

  return monorepo, package


class PlizCommand(Command):

  def get_configuration(self, load=True, error=True):  # (Bool, Bool) -> Union[Tuple[Monorepo, Package], Tuple[str, str]]
    monorepo, package = find_configuration(load=load)
    if error and (not monorepo and not package):
      self.parser.error('could not find package.yaml or monorepo.yaml')
    if load and (monorepo and package):
      package.inherit_fields(monorepo)
    return monorepo, package

  def update_parser(self, parser):
    parser.add_argument('-C', '--current-dir', help='Change to this directory.')

  def execute(self, parser, args):
    self.parser = parser
    self.args = args
    if args.current_dir:
      os.chdir(args.current_dir)
