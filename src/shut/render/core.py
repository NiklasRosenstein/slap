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


class FileToRender(object):
  """
  Represents a file that can be rendered to disk on-demand.

  # Arguments
  filename: The file on disk that should be rendered.
  render_func: The function that will be called to render the file's contents. The
    function must accept a file-like object as it's first argument. If *convolutional*
    is set to `True`, it must also accept an additional file-like object that represents
    the current contents of the file, or None if the file did not previously exist on
    disk.
  args: Additional positional arguments for *render_func*.
  convolutional: Whether *render_func* accepts a second file-like object argument.
  encoding: The encoding of the file object to pass.
  kwargs: Additional keyword arguments for *render_func*.
  """

  def __init__(
    self,
    filename: str,
    render_callback: Callable,
    *args: Any,
    convolutional: bool = False,
    encoding: str = None,
    **kwargs: Any,
  ) -> None:
    super(FileToRender, self).__init__()
    self.filename =
    self.name = nr.fs.norm(nr.fs.join(directory or '.', name))
    self.encoding = kwargs.pop('encoding', self.encoding)
    self._callable = callable
    self._args = args
    self._kwargs = kwargs

  def with_chmod(self, chmod):
    self.chmod = chmod
    return self

  @override
  def render(self, current, dst):
    return self._callable(current, dst, *self._args, *self._kwargs)
