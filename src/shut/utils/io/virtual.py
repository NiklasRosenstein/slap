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

import contextlib
import io
import os
from typing import Any, Callable, ContextManager, IO, Iterable, Optional, Set, Union


class VirtualFiles:
  """
  Represents a collection of files that are represented virtually either by static
  text or a function that can render the contents into a file-like object. The files
  can then be written to disk in one go.
  """

  def __init__(self):
    self._files = []

  def update(self, other: 'VirtualFiles', prefix: Optional[str] = None) -> None:
    for item in other._files:
      item = dict(item)
      if prefix:
        item['filename'] = os.path.join(prefix, item['filename'])
      self._files.append(item)

  def add_static(self, filename: str, content: Union[str, bytes]) -> None:
    def _write(fp):
      fp.write(content)
    self.add_dynamic(filename, _write, text=isinstance(content, str))

  def add_dynamic(
    self,
    filename: str,
    render_func: Callable,
    *args: Any,
    text: bool = True,
    inplace: bool = False,
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
    parent_directory: str = None,
    on_write: Callable = None,
    on_skip: Callable = None,
    overwrite: bool = False,
    create_directories: bool = True,
    dry: bool = False,
    open_func: Callable[[str, str], ContextManager[IO]] = None,

  ) -> None:
    """
    Writes all files to disk. Relative files will be written relative to the
    *parent_directory*.
    """

    if open_func is None:
      open_func = open

    for file_, filename in zip(self._files, self.abspaths(parent_directory)):
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
          os.makedirs(os.path.dirname(filename) or '.', exist_ok=True)
        if file_['inplace']:
          with open_func(filename, 'w' + mode) as dst:
            if exists:
              # TODO: This needs to use an atomic file actually..
              with open(filename, 'r' + mode) as src:
                file_['render_func'](dst, src, *file_['args'])
            else:
              file_['render_func'](dst, None, *file_['args'])
        else:
          with open_func(filename, 'w' + mode) as dst:
            file_['render_func'](dst, *file_['args'])

  def abspaths(self, parent_directory: str = None) -> Iterable[str]:
    """
    Returns all paths in this virtual fileset joined with *parent_directory*.
    """

    for file_ in self._files:
      yield os.path.normpath(os.path.join(parent_directory or '.', file_['filename']))

  def get_modified_files(self, parent_directory: str) -> Set[str]:
    """
    Returns a set of the files that would be modified by writing the virtual files to disk.
    """

    modified_files = set()

    @contextlib.contextmanager
    def opener(filename, mode):
      fp = io.BytesIO() if 'b' in mode else io.StringIO()
      yield fp
      if not os.path.isfile(filename):
        modified_files.add(filename)
      else:
        with open(filename, mode.replace('w', 'r')) as src:
          if fp.getvalue() != src.read():
            modified_files.add(filename)

    self.write_all(parent_directory, open_func=opener, overwrite=True, dry=False)
    return {os.path.relpath(f, parent_directory) for f in modified_files}
