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

import abc
import logging
import os
import sys
from typing import Iterable, Generic, Optional, T, Type

import click
from databind.core import datamodel
from nr.utils.git import Git

from shut.commands import project
from shut.model import AbstractProjectModel, Project
from shut.model.version import bump_version, parse_version, Version
from shut.update import get_version_refs, VersionRef

logger = logging.getLogger(__name__)


@datamodel
class Args:
  version: Optional[Version]
  major: bool
  minor: bool
  patch: bool
  post: bool
  snapshot: bool
  tag: bool
  push: bool
  dry: bool
  warnings_as_errors: bool
  skip_checks: bool
  skip_update: bool
  force: bool
  allow_lower: bool = False


class VersionBumpData(Generic[T], metaclass=abc.ABCMeta):

  def __init__(self, args: Args, project: Project, obj: T) -> None:
    self.args = args
    self.project = project
    self.obj = obj

  def post_init(self) -> None:
    pass

  @abc.abstractmethod
  def run_checks(self) -> int:
    pass

  @abc.abstractmethod
  def get_snapshot_version(self) -> Version:
    pass

  @abc.abstractmethod
  def update(self) -> None:
    pass


def make_bump_command(
  data_class: Type[VersionBumpData[AbstractProjectModel]],
  model_type: Type[AbstractProjectModel],
) -> click.Command:

  @click.argument('version', type=parse_version, required=False)
  @click.option('--major', is_flag=True, help='bump the major number')
  @click.option('--minor', is_flag=True, help='bump the minor number')
  @click.option('--patch', is_flag=True, help='bump the patch number')
  @click.option('--post', is_flag=True, help='bump the post-release number')
  @click.option('--snapshot', is_flag=True, help='update the version number by appending the Git commit distance and shasum (note: not compatible with publishing to PyPI)')
  @click.option('--tag', is_flag=True, help='create a commit and Git tag after bumping the version')
  @click.option('--push', is_flag=True, help='push the new commit and tag to the Git "origin" remote')
  @click.option('--dry', is_flag=True, help='do not write changes to disk')
  @click.option('-w', '--warnings-as-errors', is_flag=True, help='treat check warnings as errors')
  @click.option('--skip-checks', is_flag=True, help='skip running checks before bumping')
  @click.option('--skip-update', is_flag=True, help='skip update after bumping')
  @click.option('--force', '-f', is_flag=True, help='force target version (allowing you to "bump" '
    'the same or a lower version). the flag will also result in force adding a Git tag and force '
    'pushing to the remote repository if the respective options as set (--tag and --push).')
  def bump(**kwargs):
    args = Args(**kwargs)
    data = data_class(args, project, project.load_or_exit(expect=model_type))
    do_bump(args, data)

  return bump


def do_bump(args: Args, data: VersionBumpData[AbstractProjectModel]) -> None:
  # Validate arguments.
  if args.push and not args.tag:
    sys.exit('error: --push can only be used with --tag')

  bump_args = 'version major minor patch post snapshot'.split()
  provided_args = {k for k in bump_args if getattr(args, k)}
  if len(provided_args) > 1:
    sys.exit('error: conflicting options: {}'.format(provided_args))
  elif not provided_args:
    # TODO(NiklasRosenstein): Bump based on changelog
    sys.exit('error: missing version argument or bump option')

  # Run checks.
  if not args.skip_checks:
    res = data.run_checks()
    if res != 0:
      sys.exit('error: checks failed')

  version_refs = list(get_version_refs(data.obj))
  if not version_refs:
    sys.exit('error: no version refs found')

  # Ensure the version is the same accross all refs.
  current_version = data.obj.get_version()
  is_inconsistent = any(parse_version(x.value) != current_version for x in version_refs)
  if is_inconsistent:
    if not args.force:
      sys.exit('error: inconsistent versions across files need to be fixed first.')
    logger.warning('inconsistent versions across files were found.')

  # Bump the current version number.
  if args.post:
    new_version = bump_version(current_version, 'post')
  elif args.patch:
    new_version = bump_version(current_version, 'patch')
  elif args.minor:
    new_version = bump_version(current_version, 'minor')
  elif args.major:
    new_version = bump_version(current_version, 'major')
  elif args.snapshot:
    new_version = data.get_snapshot_version()
    if new_version < current_version:
      # The snapshot version number can be considered lower, so we'll allow it.
      args.allow_lower = True
  else:
    new_version = parse_version(args.version)

  if not new_version.pep440_compliant:
    logger.warning(f'version "{new_version}" is not PEP440 compliant.')

  # The new version cannot be lower than the current one, unless forced.
  if new_version < current_version and not (args.force or args.allow_lower):
    sys.exit(f'version "{new_version}" is lower than current version "{current_version}"')
  if str(new_version) == str(current_version) and not args.force:
    # NOTE(NiklasRosenstein): Comparing as strings to include pre-release and build number.
    logger.warning(f'new version "{new_version}" is equal to current version')
    exit(0)

  # The substitution logic below does not work if the same file is listed multiple
  # times so let's check for now that every file is listed only once.
  n_files = set(os.path.normpath(os.path.abspath(ref.filename))
                for ref in version_refs)
  assert len(n_files) == len(version_refs), "multiple version refs in one file is not currently supported."

  # Bump version references.
  print(f'bumping {len(version_refs)} version reference(s)')
  for ref in version_refs:
    print(f'  {os.path.relpath(ref.filename)}: {ref.value} → {new_version}')
    if not args.dry:
      with open(ref.filename) as fp:
        contents = fp.read()
      contents = contents[:ref.start] + str(new_version) + contents[ref.end:]
      with open(ref.filename, 'w') as fp:
        fp.write(contents)

  changed_files = [x.filename for x in version_refs]

  # TODO(NiklasRosenstein): For single-versioned mono repositories, bump inter dependencies.

  # TODO(NiklasRosenstein): Release staged changelogs.

  if not args.skip_update:
    print()
    data.update()

  if args.tag:
    print()
    git = Git()
    if any(f.mode == 'A' for f in git.porcelain()):
      logger.error('cannot tag with non-empty staging area')
      exit(1)

    tag_name = data.obj.get_tag(new_version)
    print(f'tagging {tag_name}')

    if not args.dry:
      git.add(changed_files)
      git.commit('({}) bump version to {}'.format(data.obj.get_name(), new_version), allow_empty=True)
      git.tag(tag_name, force=args.force)

    if not args.dry and args.push:
      git.push('origin', git.get_current_branch_name(), tag_name, force=args.force)
