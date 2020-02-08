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

from . import git
from shore.model import Monorepo, Package
from shore.util.version import parse_version, Version
from typing import Union


def get_ci_version(subject: [Monorepo, Package]) -> Version:
  """ Given a monorepo or package, this function attempts to determine the
  best description of the version given the Git commit history.

  The version string returned by this function is usually the subject's
  current version concatenated with a build version that describes the
  commit distance from the tag of the subject's current version to the
  HEAD as well as the commit SHA.

  If there is no tag for the subject's current version, the build version
  will instead contain the commit distance from the beginning of the
  repository and the distance is prefixed with "HEAD".

  NOTE: ^^^ Wishful thinking, but PEP440 😔. ^^^ """

  tag = subject.get_tag(subject.version.base_version)
  #ref = git.rev_parse('HEAD')[:7]
  if git.rev_parse(tag):
    distance = len(git.rev_list(tag + '..HEAD'))
    flavor = '.post{}'.format(distance)
  else:
    # TODO: We may want to look at the previous tag to determine how many
    #   commits have been created since.
    distance = len(git.rev_list('HEAD'))
    flavor = '.post0.dev{}'.format(distance)

  return parse_version(subject.version.base_version + flavor)
