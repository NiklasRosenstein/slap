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

from nr.interface import implements
from .base import IRenderer, FileToRender
from .util import get_default_entry_file, find_readme_file, Readme
import json
import textwrap


@implements(IRenderer)
class SetuptoolsRenderer(object):

  def files_for_package(self, package):
    yield FileToRender('setup.py', self._render_setup, package)

  def _render_setup(self, fp, package):
    # Write the header/imports.
    fp.write(textwrap.dedent('''
      import io
      import re
      import setuptools
      import sys
    '''))

    # Write the hepler that extracts the version number from the entry file.
    entry_file = package.package.entry_file or get_default_entry_file(package)
    fp.write(textwrap.dedent('''
      with io.open({entrypoint_file!r}, encoding='utf8') as fp:
        version = re.search(r"__version__\s*=\s*'(.*)'", fp.read()).group(1)
    ''').format(entrypoint_file=entry_file))

    # Write the part that reads the readme for the long description.
    readme = find_readme_file(package.directory)
    if readme:
      fp.write(textwrap.dedent('''
        with io.open({readme!r}, encoding='utf8') as fp:
          long_description = fp.read()
      ''').format(readme=readme.file))
    else:
      fp.write(textwrap.dedent('''
        long_description = {long_description!r}
      '''.format(long_description=package.package.long_description)))
      readme = Readme(None, 'text/plain')

    # Write the install requirements.
    def format_reqs(reqs): return [x.to_setuptools() for x in reqs]
    fp.write('\n')
    fp.write('requirements = {!r}\n'.format(format_reqs(package.requirements.required)))
    for os_name in package.requirements.platforms:
      fp.write('if sys.platform.startswith({!r}):\n'.format(os_name))
      fp.write('  requirements += {!r}\n'.format(format_reqs(package.requirements.platforms[os_name])))
    if package.requirements.test:
      fp.write('test_requirements = {!r}\n'.format(format_reqs(package.requirements.test)))
      tests_require = 'test_requirements'
    else:
      tests_require = '[]'

    # TODO (@NiklasRosenstein): package data

    # Write the setup function.
    fp.write(textwrap.dedent('''
      setuptools.setup(
        name = {package.name!r},
        version = version,
        author = {package.author.name!r},
        author_email = {package.author.email!r},
        description = {description!r},
        long_description = long_description,
        long_description_content_type = {long_description_content_type!r},
        url = {package.url!r},
        license = {package.license!r},
        packages = setuptools.find_packages('src'),
        package_dir = {{'': 'src'}},
        include_package_data = {include_package_data!r},
        install_requires = requirements,
        tests_require = {tests_require},
        python_requires = None, # TODO: {python_requires!r},
        entry_points = {entry_points}
      )
    ''').format(
      package=package.package,
      description=package.package.description.replace('\n\n', '%%%%').replace('\n', ' ').replace('%%%%', '\n').strip(),
      long_description_content_type=readme.content_type,
      tests_require=tests_require,
      python_requires=package.requirements.python.to_setuptools() if package.requirements.python else None,
      entry_points=textwrap.indent(json.dumps(package.entrypoints, indent=2), '  ').lstrip(),
      include_package_data=False,#package.package_data != [],
    ))
