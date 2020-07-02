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

from nr.utils.git import Git
from shore.model import Monorepo, Package
from termcolor import colored
from typing import Union


def get_commits_since_last_tag(subject: Union[Monorepo, Package]):
  tag = subject.get_tag(subject.version)
  ref = Git().rev_parse(tag)
  if not ref:
    return tag, None
  else:
    return tag, len(Git().rev_list(tag + '..HEAD', subject.directory))


def print_status(subject: Union[Monorepo, Package]) -> None:
  """
  Prints the release status of a package or the packages in a monorepo.
  """

  items = [subject]

  if isinstance(subject, Monorepo):
    items.extend(sorted(subject.get_packages(), key=lambda x: x.name))
    if not subject.version:
      items.remove(subject)

  width = max(len(x.local_name) for x in items)

  for item in items:
    tag, num_commits = get_commits_since_last_tag(item)
    if num_commits is None:
      item_info = colored('tag "{}" not found'.format(tag), 'red')
    elif num_commits == 0:
      item_info = colored('no commits', 'green') + ' since "{}"'.format(tag)
    else:
      item_info = colored('{} commit(s)'.format(num_commits), 'yellow') + ' since "{}"'.format(tag)
    print('{}: {}'.format(item.local_name.rjust(width), item_info))
