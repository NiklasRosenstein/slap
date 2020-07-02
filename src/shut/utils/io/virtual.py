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

from typing import Any, Callable, Union
import os


class VirtualFiles:
  """
  Represents a collection of files that are represented virtually either by static
  text or a function that can render the contents into a file-like object. The files
  can then be written to disk in one go.
  """

  def __init__(self):
    self._files = []

  def add_static(self, filename: str, content: Union[str, bytes]) -> None:
    def _write(fp):
      fp.write(content)
    self.add_dynamic(filename, _write, text=isinstance(content, str))

  def add_dynamic(
    self,
    filename: str,
    render_func: Callable,
    *args: Any,
    text: bool=True,
    inplace: bool=False,
  ) -> None:
    self._files.append({
      'filename': filename,
      'render_func': render_func,
      'args': args,
      'text': text,
      'inplace': inplace,
    })

  def write_all(
    self,
    parent_directory: str=None,
    on_write: Callable=None,
    on_skip: Callable=None,
    overwrite: bool=False,
    create_directories: bool=True,
    dry: bool=False,
  ) -> None:
    for file_ in self._files:
      filename = os.path.normpath(os.path.join(parent_directory or '.', file_['filename']))
      exists = os.path.isfile(filename)
      if exists and not overwrite:
        if on_skip:
          on_skip(filename)
        continue
      if on_write:
        on_write(filename)
      if not dry:
        mode = '' if file_['text'] else 'b'
        if create_directories:
          os.makedirs(os.path.dirname(filename), exist_ok=True)
        if file_['inplace']:
          with open(filename, 'w' + mode) as dst:
            if exists:
              with open(filename, 'r' + mode) as src:
                file_['render_func'](dst, src, *file_['args'])
            else:
              file_['render_func'](dst, None, *file_['args'])
        else:
          with open(filename, 'w' + mode) as dst:
            file_['render_func'](dst, *file_['args'])
