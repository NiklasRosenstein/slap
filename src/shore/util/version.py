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

from packaging.version import Version as _Version
from typing import Union
import re


class Version(_Version):
  """ An extension of #packageing.version.Version which supports a
  commit-distance and commit SHA suffix in the format of `-X-gY` (where
  X is the distance and Y is the lowercase 7-character SHA sum). """

  def __init__(self, s: Union['Version', str]):
    if isinstance(s, Version):
      s = str(s)
    elif not isinstance(s, str):
      raise TypeError('expected Version or str, got {}'.format(type(s).__name__))
    match = re.match(r'(.*)-(\d+)-g([0-9a-f]{7})', s)
    if match:
      s = match.group(1)
      commit_distance = int(match.group(2))
      sha = match.group(3)
    else:
      commit_distance = None
      sha = None
    super().__init__(s)
    self.commit_distance = commit_distance
    self.sha = sha

  def __str__(self):
    s = super().__str__()
    if self.commit_distance and self.sha:
      s += '-{}-g{}'.format(self.commit_distance, self.sha)
    return s

  def __lt__(self, other):
    if super().__lt__(other):
      return True
    if super().__eq__(other):
      return (self.commit_distance or 0) < (other.commit_distance or 0)
    return False

  def __gt__(self, other):
    return other < self and other != self

  def __eq__(self, other):
    if super().__eq__(other):
      return (self.commit_distance, self.sha) == (other.commit_distance, other.sha)
    return False

  def __ne__(self, other):
    return not self == other

  @property
  def pep440_compliant(self):
    return self.sha is None


def parse_version(version_string: str) -> Version:
  return Version(version_string)


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
