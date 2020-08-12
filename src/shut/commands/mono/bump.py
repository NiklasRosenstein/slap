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
from shut.model import MonorepoModel, Project
from shut.model.version import get_commit_distance_version, parse_version, Version
from . import mono
from .checks import check_monorepo
from .update import update_monorepo

logger = logging.getLogger(__name__)


class MonorepoBumpdata(VersionBumpData[MonorepoModel]):

  def run_checks(self) -> int:
    return check_monorepo(self.obj, self.args.warnings_as_errors)

  def update(self) -> None:
    update_monorepo(self.obj, dry=self.args.dry)

  def get_snapshot_version(self) -> Version:
    return get_commit_distance_version(
      self.obj.directory,
      self.obj.version,
      self.obj.get_tag(self.obj.version)) or self.obj.version


mono.command()(make_bump_command(MonorepoBumpdata, MonorepoModel))
