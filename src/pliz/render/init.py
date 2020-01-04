# -*- coding: utf8 -*-
# Copyright (c) 2019 Niklas Rosenstein
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

from .base import Option, BaseRenderer, FileToRender
import jinja2
import os
import pkg_resources
import posixpath


def resource_walk(module, directory, _joinwith=''):
  for name in pkg_resources.resource_listdir(module, directory):
    relative_path = posixpath.join(_joinwith, name)
    try:
      yield from resource_walk(module, directory + '/' + name, relative_path)
    except NotADirectoryError:
      yield relative_path


class InitRenderer(BaseRenderer):
  """ Renders a template for packages. """

  options = [
    Option('name'),
    Option('version', default=None),
    Option('license', default=None),
    Option('in', default=None)
  ]

  _directory = 'templates/init'

  def files(self):
    for source_filename in resource_walk('pliz', self._directory):
      filename = self._render_template(source_filename)
      dest = os.path.join(self.config['in'] or self.config['name'], filename)
      yield FileToRender(os.path.normpath(dest), self._render_file,
        self._directory + '/' + source_filename)

  def _render_template(self, template_string):
    assert isinstance(template_string, str), type(template_string)
    return jinja2.Template(template_string).render(**self.config)

  def _render_file(self, _current, fp, filename):
    content = pkg_resources.resource_string('pliz', filename).decode()
    fp.write(self._render_template(content))
