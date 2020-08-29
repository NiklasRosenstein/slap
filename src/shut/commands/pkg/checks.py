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

import enum
import logging
import os
import sys
import time
from typing import Iterable, Union

import click
import termcolor
from nr.stream import Stream
from termcolor import colored

from shut.checkers import CheckStatus, get_checks
from shut.commands import project
from shut.commands.commons.checks import print_checks_all, get_checks_status
from shut.model import PackageModel, Project
from . import pkg

logger = logging.getLogger(__name__)


def check_package(package: PackageModel, warnings_as_errors: bool = False) -> int:
  start_time = time.perf_counter()
  checks = sorted(get_checks(project, package), key=lambda c: c.name)
  seconds = time.perf_counter() - start_time
  print_checks_all(package.name, checks, seconds)
  return get_checks_status(checks, warnings_as_errors)


@pkg.command()
@click.option('-w', '--warnings-as-errors', is_flag=True)
def checks(warnings_as_errors):
  """
  Sanity-check the package configuration and package files. Which checks are performed
  depends on the features that are enabled in the package configuration. Usually that
  will at least include the "setuptools" feature which will perform basic sanity checks
  on the package configuration and entrypoint definition.
  """

  package = project.load(expect=PackageModel)
  sys.exit(check_package(package, warnings_as_errors))
