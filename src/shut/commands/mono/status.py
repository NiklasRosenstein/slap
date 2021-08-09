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

import json as _json
import typing as t
import click

from shut.model import serialize
from . import mono
from .. import project
from ..commons.status import get_status, print_status, jsonify_status
from shut.model.monorepo import MonorepoModel


@mono.command(help="""
  Show which packages have been modified since their last release.
  """ + print_status.__doc__)
@click.option('--json', is_flag=True, help='Output as JSON.')
@click.option('--include-config', is_flag=True, help='Include the package config in the JSON output.')
def status(json: bool, include_config: bool) -> None:

  project.load_or_exit(expect=MonorepoModel)

  status = get_status(project)
  if json:
    result = jsonify_status(project, status, include_config)
    result.sort(key=lambda x: x['name'])
    print(_json.dumps(result, indent=2))
  else:
    print_status(status)
