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
from typing import Optional

import click
from termcolor import colored

from shut.commands import project
from shut.commands.commons.new import write_files
from shut.model import PackageModel
from shut.renderers import get_files
from shut.utils.io.virtual import VirtualFiles
from . import pkg


def update_package(
  package: PackageModel,
  dry: bool = False,
  indent: int = 0,
  verify_tag: Optional[str] = None
) -> VirtualFiles:

  result = 0

  if verify_tag:
    assert package.version is not None
    expected_tag = package.get_tag(package.version)
    if expected_tag != verify_tag:
      print(f'{colored("error", "red")}: tag "{verify_tag}" does not match expected tag "{expected_tag}"')
      result = 1

  files = get_files(package)

  if verify_tag:
    modified_files = files.get_modified_files(package.get_directory())
    if modified_files:
      print(f'{colored("error", "red")}: the following files would be modified with an update')
      for filename in modified_files:
        print(f'  {filename}')
      result = 1

  if result != 0:
    sys.exit(result)

  if verify_tag:
    return files

  write_files(files, package.get_directory(), force=True, dry=dry, indent=indent)
  return files


@pkg.command()
@click.option('--dry', is_flag=True)
@click.option('--verify-tag', help='Verify the integrity of the managed files (asserting that '
  'they would not change from running this command) and parse the version number from the '
  'specified tag and assert that the version matches the version in the package.')
def update(dry, verify_tag):
  """
  Update files auto-generated from the configuration file.
  """

  package = project.load_or_exit(expect=PackageModel)
  update_package(package, verify_tag=verify_tag)
