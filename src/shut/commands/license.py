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

"""
Get license information from DejaCode.
"""

import json

import click
from shut.utils.external.license import get_license_metadata, wrap_license_text
from . import shut


@shut.group(help=__doc__)
def license():
  pass


@license.command()
@click.option('--name', help='The name of the license to retrieve.', required=True)
@click.option('--long', 'format_', flag_value='long', default=True)
@click.option('--short', 'format_', flag_value='short')
@click.option('--json', 'format_', flag_value='json')
def get(name, format_):
  " Retrieve the license text or a JSON description of the license. "

  data = get_license_metadata(name)
  if format_ == 'json':
    print(json.dumps(data, sort_keys=True))
  elif format_ == 'long':
    print(wrap_license_text(data['license_text']))
  elif format_ == 'short':
    print(wrap_license_text(data['standard_notice'] or data['license_text']))
