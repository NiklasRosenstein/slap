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
import shutil
import sys
from typing import Iterable, List, Optional

from shut.model import PackageModel
from shut.model.target import TargetId
from shut.utils.io.sp import subprocess_trimmed_call
from .core import Builder, BuilderProvider, register_builder_provider


class SetuptoolsBuilder(Builder):
  """
  Internal. Implements building a Python package.
  """

  _FORMATS_MAP = {
    'zip': '.zip',
    'gztar': '.tar.gz',
    'bztar': '.tar.bz2',
    'ztar': '.tar.Z',
    'tar': '.tar'
  }

  def __init__(
    self,
    id_: TargetId,
    description: str,
    output_files: List[str],
    package_directory: str,
    build_type: str,
    args: List[str],
  ) -> None:
    self._id = id_
    self.description = description
    self.output_files = output_files
    self.package_directory = package_directory
    self.build_type = build_type
    self.args = args

  def __repr__(self):
    return f'SetuptoolsBuilder(id={self.id!r}, build_type={self.build_type!r}, args={self.args!r})'

  @classmethod
  def wheel(
    cls,
    id_: TargetId,
    description: str,
    package: PackageModel,
  ) -> 'SetuptoolsBuilder':
    py = 'py2.py3' if package.is_universal() else ('py' + sys.version[0])
    filename = f'{package.name.replace("-", "_")}-{package.version}-{py}-none-any.whl'
    return cls(id_, description, [filename], package.get_directory(), 'bdist_wheel', [])

  @classmethod
  def sdist(
    cls,
    id_: TargetId,
    description: str,
    formats: List[str],
    package: PackageModel,
  ) -> 'SetuptoolsBuilder':
    assert formats
    return cls(
      id_,
      description,
      [f'{package.name}-{package.version}{cls._FORMATS_MAP[f]}' for f in formats],
      package.get_directory(),
      'sdist',
      ['--format', ','.join(formats)],
    )

  # Builder Overrides

  def get_description(self) -> Optional[str]:
    return self.description

  def get_outputs(self) -> Iterable[str]:
    return self.output_files

  def build(self, build_directory: str, verbose: bool) -> bool:
    # TODO: Can we change the distribution output directory with an option?
    python = os.getenv('PYTHON', sys.executable)
    dist_directory = os.path.join(self.package_directory, 'dist')
    dist_exists = os.path.exists(dist_directory)
    command = [python, 'setup.py', self.build_type] + self.args

    res = subprocess_trimmed_call(command, cwd=self.package_directory)
    if res != 0:
      return False

    # Make sure the files end up in the correct directory.
    for filename in self.output_files:
      src = next(filter(os.path.isfile, [
        os.path.join(dist_directory, filename),
        os.path.join(dist_directory, filename.lower())]), None)
      if not src:
        raise RuntimeError('{} not produced by setup.py {}'.format(filename, self.build_type))
      dst = os.path.join(build_directory, filename)
      if src != dst:
        if os.path.isfile(dst):
          os.remove(dst)
        os.rename(src, dst)

    # Cleanup after yourself.
    if not dist_exists:
      shutil.rmtree(dist_directory)

    return True

  # Target Overrides

  @property
  def id(self) -> TargetId:
    return self._id


class SetuptoolsBuilderProvider(BuilderProvider[PackageModel]):

  # BuilderProvider Overrides

  def get_builders(self, package: PackageModel) -> Iterable[Builder]:
    yield SetuptoolsBuilder.sdist(
      TargetId('setuptools', 'sdist'),
      'Build a source distribute',
      ['gztar'],
      package,
    )

    if package.wheel:
      yield SetuptoolsBuilder.wheel(
        TargetId('setuptools', 'wheel'),
        'Build a Python wheel.',
        package,
      )


register_builder_provider(PackageModel, SetuptoolsBuilderProvider)
