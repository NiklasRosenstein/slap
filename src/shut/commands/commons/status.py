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

import os
import sys
import typing as t

from nr.utils.git import Git
from termcolor import colored

from shut.model import AbstractProjectModel, MonorepoModel, Project, serialize


def get_commits_since_last_tag(subject: AbstractProjectModel) -> t.Tuple[str, t.Optional[int]]:
  version = subject.get_version()
  assert version, 'require version to get commits since last tag'
  tag = subject.get_tag(version)
  ref = Git().rev_parse(tag)
  if not ref:
    return tag, None
  else:
    return tag, len(Git().rev_list(tag + '..HEAD', subject.get_directory()))


class PackageStatus(t.NamedTuple):
  #: The tag for the package.
  tag: str

  #: The number of commits that the #tag is behind the current package state. This is `0` if the
  #: tag is up to date with the latest commit on the package, and `None` if the #tag does not
  #: exist.
  behind: t.Optional[int]


def get_status(project: Project) -> t.Dict[str, PackageStatus]:
  assert project.subject, "No subject"

  items: t.List[AbstractProjectModel]
  names: t.List[str]
  if isinstance(project.subject, MonorepoModel):
    monorepo_dir = project.subject.get_directory()
    if not project.packages:
      sys.exit('error: monorepo has no packages')
    items = sorted(project.packages, key=lambda x: x.name)
    names = [os.path.normpath(os.path.relpath(x.get_directory(), monorepo_dir)) for x in items]
  else:
    items = [project.subject]
    names = [project.subject.get_name()]

  result = {}
  for item, name in zip(items, names):
    tag, num_commits = get_commits_since_last_tag(item)
    result[name] = PackageStatus(tag, num_commits)

  return result


def print_status(status: t.Dict[str, PackageStatus]) -> None:
  """
  The latest version is taken from the current version number in the package
  configuration file. Git is then queried for the tag and the commit distance
  to the current revision.
  """


  width = max(map(len, status)) if status else 0

  for name, info in status.items():
    tag, num_commits = info
    if num_commits is None:
      item_info = colored('tag "{}" not found'.format(tag), 'red')
    elif num_commits == 0:
      item_info = colored('no commits', 'green') + ' since "{}"'.format(tag)
    else:
      item_info = colored('{} commit(s)'.format(num_commits), 'yellow') + ' since "{}"'.format(tag)
    print('{}: {}'.format(name.rjust(width), item_info))


def jsonify_status(project: Project, status: t.Dict[str, t.Any], include_config: bool) -> t.List[t.Dict[str, t.Any]]:
  result = []
  for package_name, status_info in status.items():
    result.append({'name': package_name, 'tag': status_info.tag, 'behind': status_info.behind})
    if include_config:
      result[-1]['package'] = serialize(project[package_name])
  return result
