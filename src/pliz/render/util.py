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

import collections
import os

Readme = collections.namedtuple('Readme', 'file,content_type')


def get_default_entry_file(package):
  name = package.package.name.replace('-', '_')
  parts = name.split('.')
  prefix = os.sep.join(parts[:-1])
  for filename in [parts[-1] + '.py', os.path.join(parts[-1], '__init__.py')]:
    filename = os.path.join('src', prefix, filename)
    if os.path.isfile(os.path.join(package.directory, filename)):
      return filename
  raise EnvironmentError('Entry file for package "{}" could not be determined'
                         .format(package.package.name))


def find_readme_file(directory):
  preferred = {
    'README.md': 'text/markdown',
    'README.rst': 'text/x-rst',
    'README.txt': 'text/plain',
    'README': 'text/plain'
  }
  choices = []
  for name in os.listdir(directory):
    if name in preferred:
      return Readme(name, preferred[name])
    if name.startswith('README.'):
      choices.append(name)
  if choices:
    return Readme(sorted(choices)[0], 'text/plain')
  return None
