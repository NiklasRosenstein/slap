# -*- coding: utf8 -*-
# Copyright (c) 2021 Niklas Rosenstein
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
import click
from shut.commands import project
from shut.commands.commons.status import get_status, jsonify_status, print_status
from shut.commands.pkg import pkg
from shut.model import PackageModel


@pkg.command(help="""
  Shows whether the package was modified since the last release.
  """ + (print_status.__doc__ or ''))
@click.option('--json', is_flag=True, help='Output as JSON.')
@click.option('--include-config', is_flag=True, help='Include the package config in the JSON output.')
def status(json: bool, include_config: bool) -> None:
  project.load_or_exit(expect=PackageModel)
  status = get_status(project)
  if json:
    result = jsonify_status(project, status, include_config)
    print(_json.dumps(result, indent=2))
  else:
    print_status(status)
