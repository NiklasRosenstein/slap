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

from pliz.core.plugins import FileToRender, IPlugin, Options, Option
from nr.interface import implements, override
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


@implements(IPlugin)
class InitRenderer(object):
  """ Renders a template for packages. """

  _DIRECTORY = 'templates/init'

  def __init__(self, options):
    self._options = options

  @override
  @classmethod
  def get_options(self):  # type: () -> Options
    return Options({
      'name': Option(),
      'version': Option(default=None),
      'license': Option(default=None),
      'in': Option(default=None),
    })

  @override
  def get_files_to_render(self, _context):
    for source_filename in resource_walk('pliz', self._DIRECTORY):
      filename = self._render_template(source_filename, name=self.config['name'].replace('.', '/'))
      dest = os.path.join(self.config['in'] or self.config['name'], filename)
      yield FileToRender(os.path.normpath(dest), self._render_file,
        self._DIRECTORY + '/' + source_filename)
    # Add namespace supporting files.
    def render_namespace(_current, fp):
      fp.write("__path__ = __import__('pkgutil').extend_path(__path__, __name__)\n")
    parts = []
    for item in self.config['name'].split('.')[:-1]:
      parts.append(item)
      dest = os.path.join(self.config['in'] or self.config['name'], 'src', *parts, '__init__.py')
      yield FileToRender(os.path.normpath(dest), render_namespace)

  @override
  def perform_checks(self, context):
    return; yield

  def _render_template(self, template_string, **kwargs):
    assert isinstance(template_string, str), type(template_string)
    return jinja2.Template(template_string).render(**(kwargs or self.config))

  def _render_file(self, _current, fp, filename):
    content = pkg_resources.resource_string('pliz', filename).decode()
    fp.write(self._render_template(content))
