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

from packaging.version import LegacyVersion, parse, Version


def parse_version(version_string: str) -> Version:
  version = parse(version_string)
  if isinstance(version, LegacyVersion):
    raise ValueError('invalid version string: {!r}'.format(version_string))
  return version


def bump_version(version: Version, kind: str) -> Version:
  major, minor, patch, post = version.major, version.minor, version.micro, \
    version.post
  if kind == 'post':
    if post is None:
      post = 1
    else:
      post += 1
  elif kind == 'patch':
    post = None
    patch += 1
  elif kind == 'minor':
    post = None
    patch = 0
    minor += 1
  elif kind == 'major':
    post = None
    patch = minor = 0
    major += 1
  else:
    raise ValueError('invalid kind: {!r}'.format(kind))
  string = '%s.%s.%s' % (major, minor, patch)
  if post:
    string += '.post' + str(post)
  return Version(string)
