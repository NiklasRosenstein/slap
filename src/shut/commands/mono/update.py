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

import click

from shut.commands import project
from shut.commands.commons.new import write_files
from shut.commands.pkg.update import update_package
from shut.model import MonorepoModel
from shut.renderers import get_files
from shut.utils.io.virtual import VirtualFiles
from . import mono


def update_monorepo(monorepo: MonorepoModel, dry: bool = False, indent: int = 0) -> VirtualFiles:
  files = get_files(monorepo)
  write_files(files, monorepo.get_directory(), force=True, dry=dry, indent=indent)
  return files


@mono.command()
@click.option('--dry', is_flag=True)
@click.option('-a', '--all', 'all_', is_flag=True, help='Also update any packages in the monorepo.')
def update(all_, dry):
  """
  Update files auto-generated from the configuration file.
  """

  monorepo = project.load_or_exit(expect=MonorepoModel)
  update_monorepo(monorepo, dry)

  if all_:
    for package in project.packages:
      update_package(package, dry)
