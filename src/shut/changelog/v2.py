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
The V3 of changelogs.
"""

from . import _ChangelogBase, v1
from nr.databind.core import Collection, Field, FieldName, Struct
import enum


class Type(enum.Enum):
  fix = 0
  improvement = 1
  change = 3
  refactor = 4
  feature = 5
  docs = 6
  tests = 7


class Entry(Struct):
  Type = Type

  type_ = Field(Type, FieldName('type'))
  component = Field(str)
  description = Field(str)
  fixes = Field([str])

  @classmethod
  def from_v1(cls, v1_entry: v1.Entry) -> 'Entry':
    try:
      type_ = Type[v1_entry.types[0].strip().lower()]
    except KeyError:
      type_ = Type.change
    return cls(
      type_=type_,
      component=v1_entry.components[0],
      description=v1_entry.description,
      fixes=list(map(str, v1_entry.issues)),
    )


class Changelog(_ChangelogBase, Collection, list):
  Supersedes = v1.Changelog  # _ChangelogBase
  item_type = Entry  # Collection
  Entry = Entry

  @classmethod
  def adapt(cls, v1_changelog: v1.Changelog) -> 'Changelog':
    return cls(map(Entry.from_v1, v1_changelog))
