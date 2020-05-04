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
from shore.util import git as _git
from typing import Optional, Union
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


def get_commit_distance_version(repo_dir: str, version: Version, latest_tag: str) -> Optional[Version]:
  """
  This function creates a string which describes the version of the
  monorepo or package that includes the commit distance and SHA revision
  number.

  For a mono repository, the full commit distance is used. The same is true
  for a single package. For a package inside a mono repository that does not
  apply mono versioning, the packages' local commit distance is used.

  This is close to what `git describe --tags` does. An example version number
  generated by this function is: `0.1.0+24.gd9ade3f`. If the working state is
  dirty, `.dirty` will be appended to the local version.

  Notes:

  - If there is no commit distance from the *latest_tag* to the current
    state of the repository, this function returns None.
  - The version returned by this function is a PEP440 local version that
    cannot be used for packages when submitting them to PyPI.
  - If the tag for the version of *subject* does not exist on the repository,
    it will fall back to 0.0.0 as the version number which is treated as
    "the beginning of the repository", even if no tag for this version exists.

    Todo: We could try to find the previous tag for this subject and use that.
  """

  if _git.rev_parse(latest_tag):
    distance = len(_git.rev_list(latest_tag + '..HEAD', repo_dir))
  else:
    logger.warning('tag "%s" does not exist', latest_tag)
    version = Version('0.0.0')
    distance = len(_git.rev_list('HEAD', repo_dir))

  if distance == 0:
    return None

  suffix = ''
  if _git.has_diff(repo_dir):
    suffix = '.dirty'

  rev = _git.rev_parse('HEAD', repo_dir)
  return parse_version(str(version) + '+{}.g{}{}'.format(distance, rev[:7], suffix))
