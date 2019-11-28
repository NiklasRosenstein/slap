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

from ..util.decorators import with_contexter
import json
import os
import textwrap


def get_default_entry_file(package):
  name = package.package.name.replace('-', '_')
  parts = name.split('.')
  prefix = os.sep.join(parts[:-1])
  for filename in [parts[-1] + '.py', os.path.join(parts[-1], '__init__.py')]:
    filename = os.path.join('src', prefix, filename)
    if os.path.isfile(os.path.join(package.directory, filename)):
      return filename
  raise EnvironmentError('Entry file for package "{}" could not be determined'
                         .format(package.package.name))


def find_readme_file(directory):
  preferred = {
    'README.md': 'text/markdown',
    'README.rst': 'text/x-rst',
    'README.txt': 'text/plain',
    'README': 'text/plain'
  }
  choices = []
  for name in os.listdir(directory):
    if name in preferred:
      return name, preferred[name]
    if name.startswith('README.'):
      choices.append(name)
  if choices:
    return sorted(choices)[0], 'text/plain'
  return None


def render_monorepo(monorepo):
  pass


def render_package(package):
  render_setup_file(package)


@with_contexter()
def render_setup_file(ctx, package):
  if not package.package.entry_file:
    package.package.entry_file = get_default_entry_file(package)

  filename = os.path.join(package.directory, 'setup.py')
  fp = ctx << open(filename, 'w')

  # Write the header/imports.
  fp.write(textwrap.dedent('''
    import io
    import re
    import setuptools
    import sys
  '''))

  # Write the hepler that extracts the version number from the entry file.
  fp.write(textwrap.dedent('''
    with io.open({entrypoint_file!r}, encoding='utf8') as fp:
      version = re.search(r"__version__\s*=\s*'(.*)'", fp.read()).group(1)
  ''').format(entrypoint_file=package.package.entry_file))

  # Write the part that reads the readme for the long description.
  readme_file, readme_content_type = find_readme_file(package.directory)
  if readme_file:
    fp.write(textwrap.dedent('''
      with io.open({readme!r}, encoding='utf8') as fp:
        long_description = fp.read()
    ''').format(readme=readme_file))
  else:
    fp.write(textwrap.dedent('''
      long_description = {long_description!r}
    '''.format(long_description=package.package.long_description)))
    readme_content_type = 'text/plain'

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
      python_requires = {python_requires!r},
      entry_points = {entry_points}
    )
  ''').format(
    package=package.package,
    description=package.package.description.replace('\n\n', '%%%%').replace('\n', ' ').replace('%%%%', '\n').strip(),
    long_description_content_type=readme_content_type,
    tests_require=tests_require,
    python_requires=package.requirements.python.to_setuptools(),
    entry_points=textwrap.indent(json.dumps(package.entrypoints, indent=2), '  ').lstrip(),
    include_package_data=False,#package.package_data != [],
  ))
