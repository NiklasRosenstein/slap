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

import io
from typing import Iterable, Tuple, Union

SubstRange = Tuple[int, int, str]


def substitute_ranges(text: str, ranges: Iterable[SubstRange], is_sorted: bool = False) -> str:
  """
  Replaces parts of *text* using the specified *ranges* and returns the new text. Ranges
  must not overlap. *is_sorted* can be set to `True` if the input *ranges* are already
  sorted from lowest to highest starting index to optimize the function.
  """

  if not is_sorted:
    ranges = sorted(ranges, key=lambda x: x[0])

  out = io.StringIO()
  max_start_index = 0
  max_end_index = 0
  for index, (istart, iend, subst) in enumerate(ranges):
    if iend < istart:
      raise ValueError(f'invalid range at index {index}: (istart: {istart!r}, iend: {iend!r})')
    if istart < max_end_index:
      raise ValueError(f'invalid range at index {index}: overlap with previous range')

    subst = str(subst)
    out.write(text[max_end_index:istart])
    out.write(subst)
    max_start_index, max_end_index = istart, iend

  out.write(text[max_end_index:])
  return out.getvalue()


def indent_text(text: str, indent: Union[str, int]) -> str:
  """
  Indents the *text* by *indent*.
  """

  if isinstance(indent, int):
    indent = ' ' * indent
  return '\n'.join(indent + l for l in text.splitlines())
