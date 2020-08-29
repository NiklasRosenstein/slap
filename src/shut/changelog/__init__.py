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

"""
This package provides the programmatic interface to read, process and write YAML
changelog files.

One changelog file is created per version. The name of the file is the version that
the changelog is for. There may be an "_unreleased.yml" changelog file at any point
in time that contains the logs for the next to-be-released version.

The changelog can be used to determine if the next version of a package requires a
major or minor bump, or if only the patch or build number needs to be incremented.
This is achieved by assigning a keyword to every changelog, and that keyword indicates
the type of change and whether it is breaking an API.
"""

import abc
from typing import Any, Generic, Optional, Type, TypeVar

T = TypeVar('T')


class _ChangelogBase(Generic[T], metaclass=abc.ABCMeta):
  """
  Base class for datamodels subclasses that represent the deserialized form of a changelog in
  a specific version. A newer version should reference the predecessor in the #Supersedes
  class-level attribute and implement the #adapt() method in order to automatically support
  migrating to the next version.
  """

  Supersedes: Optional[Type[T]] = None

  @classmethod
  def migrate(cls, older_changelog: Any) -> '_ChangelogBase':
    if not cls.Supersedes:
      raise TypeError('reached {}, unsure how to migrate from {!r}'.format(
        cls.__module__, type(older_changelog).__name__))
    if not isinstance(older_changelog, cls.Supersedes):
      older_changelog = cls.Supersedes.migrate(older_changelog)
    return cls.adapt(older_changelog)

  @classmethod
  def adapt(cls, older_changelog: T) -> '_ChangelogBase':
    raise NotImplementedError
