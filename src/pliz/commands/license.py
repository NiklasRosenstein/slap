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

""" A CLI to retrieve license metadata from DejaCode. """

from . import Command
from ..util.license import get_license_metadata, wrap_license_text
from nr.proxy import proxy_decorator
import json


class LicenseCommand(Command):

  name = 'license'
  description = __doc__

  def update_parser(self, parser):
    parser.add_argument('license_name')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--text', action='store_true')
    parser.add_argument('--notice', action='store_true')

  def execute(self, parser, args):
    @proxy_decorator(deref=True, lazy=True)
    def data():
      try:
        return get_license_metadata(args.license_name)
      except Exception as exc:  # TODO (@NiklasRosenstein): Catch the right exception(s)
        parser.error(exc)

    if args.json:
      print(json.dumps(data(), sort_keys=True))
    elif args.text:
      print(wrap_license_text(data['license_text']))
    elif args.notice:
      print(wrap_license_text(data['standard_notice'] or data['license_text']))
    else:
      parser.error('missing operation')
