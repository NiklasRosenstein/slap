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

import sys
import os
from typing import Optional

import click

from shut.commands import project
from shut.commands.commons.new import write_files
from shut.commands.pkg.update import verify_integrity, verify_tag
from shut.model import MonorepoModel
from shut.renderers import get_files
from shut.utils.io.virtual import VirtualFiles
from . import mono


def update_monorepo(
  monorepo: MonorepoModel,
  dry: bool = False,
  indent: int = 0,
  verify: bool = False,
  tag: Optional[str] = None,
  all_: bool = False,
) -> VirtualFiles:

  result = 0
  if tag and not verify_tag(monorepo, tag):
    result = 1

  files = get_files(monorepo)
  if all_:
    for package in monorepo.project.packages:
      files.update(get_files(package), os.path.basename(package.get_directory()))

  if verify and not verify_integrity(monorepo, files):
    result = 1
  if result != 0:
    sys.exit(result)
  if not verify:
    write_files(files, monorepo.get_directory(), force=True, dry=dry, indent=indent)
  return files


@mono.command()
@click.option('--dry', is_flag=True)
@click.option('--verify', is_flag=True, help='Verify the integrity of the managed files '
  '(asserting that they would not change from running this command).')
@click.option('--verify-tag', help='Parse the version number from the specified tag and '
  'assert that it matches the version in the package configuration. (implies --verify)')
def update(dry, verify, verify_tag):
  """
  Update files auto-generated from the configuration file.
  """

  monorepo = project.load_or_exit(expect=MonorepoModel)
  update_monorepo(monorepo, dry, verify=verify or bool(verify_tag), tag=verify_tag, all_=True)
