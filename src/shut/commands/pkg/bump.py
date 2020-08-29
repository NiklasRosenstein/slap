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

import os
import logging
import sys
from typing import Iterable

import click

from shut.commands.commons.bump import make_bump_command, VersionBumpData, VersionRef
from shut.model import PackageModel, Project
from shut.model.version import get_commit_distance_version, parse_version, Version
from . import pkg
from .checks import check_package
from .update import update_package

logger = logging.getLogger(__name__)


class PackageBumpData(VersionBumpData[PackageModel]):

  def loaded(self) -> None:
    project = self.project
    if project.monorepo and project.monorepo.release.single_version:
      if self.args.force:
        logger.warning(
          'forcing version bump on individual package version that is usually managed '
          'by the monorepo.')
        return
      print('error: cannot bump package version managed by monorepo.', file=sys.stderr)
      exit(1)

  def run_checks(self) -> int:
    return check_package(self.obj, self.args.warnings_as_errors)

  def update(self, new_version: Version) -> Iterable[str]:
    self.obj.version = new_version
    vfiles = update_package(self.obj, dry=self.args.dry, indent=1)
    return vfiles.abspaths(self.obj.get_directory())

  def get_snapshot_version(self) -> Version:
    project = self.project
    if project.monorepo and project.monorepo.release.single_version:
      subject = project.monorepo
    else:
      subject = self.obj
    return get_commit_distance_version(
      subject.directory,
      subject.version,
      subject.get_tag(subject.get_version())) or subject.get_version()


pkg.command()(make_bump_command(PackageBumpData, PackageModel))
