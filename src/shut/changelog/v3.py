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
The V2 of changelogs.
"""

import datetime
from dataclasses import dataclass
from typing import List, Optional
from . import _ChangelogBase, v2


@dataclass
class Changelog(_ChangelogBase[v2.Changelog]):
  Supersedes = v2.Changelog  # _ChangelogBase
  Entry = v2.Entry

  changes: List[v2.Entry]
  release_date: Optional[datetime.date] = None

  @classmethod
  def adapt(cls, v2_changelog: _ChangelogBase) -> 'Changelog':
    assert isinstance(v2_changelog, v2.Changelog)
    return cls(release_date=None, changes=list(v2_changelog))
