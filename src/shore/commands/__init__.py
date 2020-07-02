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

"""
This package implements the Shut CLI.
"""

from nr.proxy import Proxy

import click
import logging

context = Proxy(lambda: click.get_current_context().obj)


@click.group()
@click.option('-v', '--verbose', count=True, help='Increase the log verbosity.')
@click.option('-q', '--quiet', is_flag=True, help='Quiet mode, wins over --verbose.')
def shut(verbose, quiet):
  """
  Shut is a tool to manage the lifecycle of pure Python packages. It automates tasks such
  as bootstrapping a project, bumping version numbers, managing changelogs and publishing
  packages to PyPI all the while performing sanity checks.

  Shut makes strong assumptions on the project structure and assumes that the source-control
  system of choice is Git.
  """

  ctx = click.get_current_context()
  ctx.ensure_object(dict)
  context['quiet'] = quiet

  if quiet:
    level = logging.CRITICAL
  elif verbose >= 2:
    level = logging.DEBUG
  elif verbose >= 1:
    level = logging.INFO
  else:
    level = logging.WARNING

  logging.basicConfig(
    format='[%(levelname)s|%(asctime)s|%(name)s]: %(message)s',
    level=level,
  )


from . import classifiers
from . import license
from . import pkg
