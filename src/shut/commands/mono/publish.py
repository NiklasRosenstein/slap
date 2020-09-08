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

import click
from termcolor import colored

from shut.commands.pkg.publish import PublishError, publish_package
from shut.model.monorepo import MonorepoModel
from shut.model.target import TargetId
from . import mono, project


@mono.command()
@click.argument('target', type=lambda s: TargetId.parse(s, True))
@click.option('-t', '--test', is_flag=True, help='publish to the test repository instead')
@click.option('-v', '--verbose', is_flag=True, help='show more output')
@click.option('-b', '--build-dir', default='build', help='build output directory')
@click.option('--skip-build', is_flag=True, help='do not build artifacts that are to be published')
@click.option('-ff', '--fast-fail', is_flag=True, help='Fail after the first error.')
def publish(target, test, verbose, build_dir, skip_build, fast_fail):
  """
  Call `shut pkg publish` for every package. The mono repository must be single versioned
  in order to run this command.
  """

  monorepo = project.load_or_exit(expect=MonorepoModel)
  if not monorepo.release.single_version:
    sys.exit('error: $.release.single-version is not enabled')

  ok = True
  for package in project.packages:
    try:
      publish_package(package, target, build_dir, skip_build, test, verbose)
    except PublishError as exc:
      ok = False
      print(f'error in {colored(package.name, "yellow")}: {exc}', file=sys.stderr)
      if fast_fail:
        sys.exit(1)

  sys.exit(0 if ok else 1)
