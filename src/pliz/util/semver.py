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

import re


def expand_range_selectors(req):
  """ Expands semver range selectors of the form `^X.Y.Z` and `~X.Y.Z` in
  the string *req*.

  * `^` (caret) modifier expands into `>=X.Y.Z,<X+1.Y.Z`
  * `~` (caret) modifier expands into `>=X.Y.Z,<X.Y+1.Z`
 """

  regex = r'[~^](\d+\.\d+\.\d+[.\-\w]*)'
  def sub(match):
    index = {'^': 0, '~': 1}[match.group(0)[0]]
    max_version = match.group(1).split('.')[:3]
    if '-' in max_version[-1]:
      max_version[-1] = max_version[-1].partition('-')[0]
    max_version[index] = str(int(max_version[index]) + 1)
    for i in range(index+1, 3):
      max_version[i] = '0'
    return '>={},<{}'.format(match.group(1), '.'.join(max_version))
  return re.sub(regex, sub, req)
