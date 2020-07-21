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

from shore.util.ast import load_module_members
from shore.plugins._util import find_readme_file

from .author import Author
from .changelog import ChangelogConfiguration
from .linter import LinterConfiguration
from .release import ReleaseConfiguration
from .requirements import Requirement
from .version import Version
from nr.databind.core import Field, FieldName, Struct
from typing import Dict, List, Optional
import ast
import os


class PackageData(Struct):
  name = Field(str)
  modulename = Field(str, default=None)
  version = Field(Version, default=None)
  author = Field(Author)
  description = Field(str, default=None)
  license = Field(str, default=None)
  url = Field(str, default=None)
  readme = Field(str, default=None)
  wheel = Field(bool, default=True)
  universal = Field(bool, default=None)
  typed = Field(bool, default=False)
  requirements = Field(List[Requirement], default=list)
  test_requirements = Field(List[Requirement], FieldName('test-requirements'), default=list)
  extra_requirements = Field(Dict[str, List[Requirement]], FieldName('extra-requirements'), default=dict)
  source_directory = Field(str, FieldName('source-directory'), default='src')
  exclude = Field(List[str], default=lambda: ['test', 'tests', 'docs'])
  entrypoints = Field(Dict[str, List[str]], default=dict)
  classifiers = Field(List[str], default=list)
  keywords = Field(List[str], default=list)
  # TODO: Data files

  def get_modulename(self) -> str:
    return self.modulename or self.name.replace('-', '_')


class InstallConfiguration(Struct):
  hooks = Field(dict(
    before_install=Field(List[str], FieldName('before-install'), default=list),
    after_install=Field(List[str], FieldName('after-install'), default=list),
    before_develop=Field(List[str], FieldName('before-develop'), default=list),
    after_develop=Field(List[str], FieldName('after-develop'), default=list),
  ), default=Field.DEFAULT_CONSTRUCT)


class PackageModel(Struct):
  filename = Field(str, hidden=True, default=None)
  unknown_keys = Field(List[str], hidden=True, default=list)
  data = Field(PackageData, FieldName('package'))
  changelog = Field(ChangelogConfiguration, default=Field.DEFAULT_CONSTRUCT)
  install = Field(InstallConfiguration, default=Field.DEFAULT_CONSTRUCT)
  linter = Field(LinterConfiguration, default=Field.DEFAULT_CONSTRUCT)
  release = Field(ReleaseConfiguration, default=Field.DEFAULT_CONSTRUCT)

  def get_python_package_metadata(self) -> 'PythonPackageMetadata':
    return PythonPackageMetadata(
      os.path.join(os.path.dirname(self.filename), self.data.source_directory),
      self.data.get_modulename())

  def get_readme(self) -> Optional[str]:
    """
    Returns the absolute path to the README for this package.
    """

    directory = os.path.dirname(__file__)

    if self.data.readme:
      return os.path.abspath(os.path.join(directory, self.readme))

    return find_readme_file(directory)


class PythonPackageMetadata:

  def __init__(self, source_directory: str, modulename: str) -> None:
    self.source_directory = source_directory
    self.modulename = modulename
    self._filename = None
    self._author = None
    self._version = None

  @property
  def filename(self) -> str:
    """
    Returns the file that contains the package metadata in the Python source code. This is
    usually the module filename, the package `__init__.py` or `__version__.py`.
    """

    if self._filename:
      return self._filename

    parts = self.modulename.split('.')
    prefix = os.sep.join(parts[:-1])
    choices = [
      parts[-1] + '.py',
      os.path.join(parts[-1], '__version__.py'),
      os.path.join(parts[-1], '__init__.py'),
    ]
    for filename in choices:
      filename = os.path.join(self.source_directory, prefix, filename)
      if os.path.isfile(filename):
        self._filename = filename
        return filename

    raise ValueError('Entry file for package "{}" could not be determined'
                     .format(self.modulename))

  @property
  def package_directory(self) -> str:
    """
    Returns the Python package directory. Raises a #ValueError if this metadata represents
    just a single Python module.
    """

    dirname, basename = os.path.split(self.filename)
    if basename not in ('__init__.py', '__version__.py'):
      raise ValueError('this package is in module-only form')

    return dirname

  @property
  def author(self) -> str:
    if not self._author:
      self._load_metadata()
    return self._author

  @property
  def version(self) -> str:
    if not self._version:
      self._load_metadata()
    return self._version

  def _load_metadata(self) -> None:
    members = load_module_members(self.filename)

    author = None
    version = None

    if '__version__' in members:
      try:
        version = ast.literal_eval(members['__version__'])
      except ValueError as exc:
        version = '<Non-literal expression>'

    if '__author__' in members:
      try:
        author = ast.literal_eval(members['__author__'])
      except ValueError as exc:
        author = '<Non-literal expression>'

    self._author = author
    self._version = version
