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

from .base import PlizCommand
from termcolor import colored


class InfoCommand(PlizCommand):

  name = 'info'
  description = 'Show information on the current monorepo/package.'

  def execute(self, parser, args):
    monorepo, package = self.get_configuration()
    if monorepo:
      display = colored(monorepo.project.name, 'blue', attrs=['bold'])
      if monorepo.project.version:
        display += colored('@v' + monorepo.project.version, 'magenta')
      print(display + '/')
      for child in monorepo.list_packages():
        self._display_package(child, full=package==child, indent=2)
    elif package:
      self._display_package(package)

  def _display_package(self, package, full=True, indent=0):
      display = colored(package.package.name, 'cyan', attrs=['bold'])
      display += colored('@v' + package.package.version, 'magenta')
      print(indent * ' ' + display + ('/' if full else ''))
