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

import contextlib
import io
import os
from typing import TYPE_CHECKING, Any, BinaryIO, Callable, ContextManager, IO, Iterable, Optional, Set, TextIO, Union, cast, overload
from typing_extensions import Literal, Protocol


class OpenerFunc(Protocol):
  def __call__(self, filename: str, mode: str, *, encoding: Optional[str] = None) -> ContextManager[IO]: ...


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

  def add_static(self, filename: str, content: Union[str, bytes], encoding: Optional[str] = None) -> None:
    """
    Stage static content for rendering into a file with the given *filename*. If the content is text,
    the file will be written in text mode with the specified *encoding*.
    """

    self.add_dynamic(filename, lambda fp: fp.write(content), text=isinstance(content, str), encoding=encoding)  # type: ignore

  @overload
  def add_dynamic(
    self,
    filename: str,
    render_func: Callable[[TextIO], Any],
    text: 'Literal[True]' = True,
    inplace: 'Literal[False]' = False,
    encoding: Optional[str] = None,
  ) -> None: ...

  @overload
  def add_dynamic(
    self,
    filename: str,
    render_func: Callable[[TextIO, Optional[TextIO]], Any],
    text: 'Literal[True]' = True,
    inplace: 'Literal[True]' = True,
    encoding: Optional[str] = None,
  ) -> None: ...

  @overload
  def add_dynamic(
    self,
    filename: str,
    render_func: Callable[[BinaryIO], Any],
    text: 'Literal[False]' = False,
    inplace: 'Literal[False]' = False,
    encoding: Optional[str] = None,
  ) -> None: ...

  @overload
  def add_dynamic(
    self,
    filename: str,
    render_func: Callable[[BinaryIO, Optional[BinaryIO]], Any],
    text: 'Literal[False]' = False,
    inplace: 'Literal[True]' = True,
    encoding: Optional[str] = None,
  ) -> None: ...

  def add_dynamic(
    self,
    filename: str,
    render_func: Callable[..., Any],
    text: bool = True,
    inplace: bool = False,
    encoding: Optional[str] = None,
  ) -> None:
    """
    Stage a function to write to a file with the given *filename*. The function will be invoked when the
    file is actually written to disk (or to memory, see #get_modified_files()).

    If *inplace* is set to #True, the *render_func* must accept two arguments, where the first is the output
    file and the second is the current file, if it exists. Otherwise, *render_func* must accept only one
    argument (the output file).
    """

    if encoding and not text:
      raise ValueError(f'encoding and text=False are not compatible')

    self._files.append({
      'filename': filename,
      'render_func': render_func,
      'text': text,
      'inplace': inplace,
      'encoding': encoding,
    })

  def write_all(
    self,
    parent_directory: str = None,
    on_write: Callable = None,
    on_skip: Callable = None,
    overwrite: bool = False,
    create_directories: bool = True,
    dry: bool = False,
    open_func: 'OpenerFunc' = None,
  ) -> None:
    """
    Writes all files to disk. Relative files will be written relative to the
    *parent_directory*.
    """

    if open_func is None:
      open_func = cast('OpenerFunc', open)

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
        encoding_kwarg = {'encoding': file_['encoding']} if file_['encoding'] else {}
        if file_['inplace']:
          src: Optional[TextIO] = None
          if exists:
            with open(filename, 'r' + mode, **encoding_kwarg) as raw_src:
              src = io.StringIO(raw_src.read())
          with open_func(filename, 'w' + mode, **encoding_kwarg) as dst:
            if exists:
              assert src is not None
              file_['render_func'](dst, src)
            else:
              file_['render_func'](dst, None)
        else:
          with open_func(filename, 'w' + mode, **encoding_kwarg) as dst:
            file_['render_func'](dst)

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
    def opener(filename, mode, **kw):
      fp: Union[io.BytesIO, io.StringIO] = io.BytesIO() if 'b' in mode else io.StringIO()
      yield fp
      if not os.path.isfile(filename):
        modified_files.add(filename)
      else:
        with open(filename, mode.replace('w', 'r'), **kw) as src:
          if fp.getvalue() != src.read():
            modified_files.add(filename)

    self.write_all(parent_directory, open_func=opener, overwrite=True, dry=False)
    return {os.path.relpath(f, parent_directory) for f in modified_files}
