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

from . import pkg
from shore.core.plugins import FileToRender, write_to_disk
from shore.util.resources import walk_package_resources
from termcolor import colored
from typing import Iterable, Optional
import click
import jinja2
import os
import pkg_resources
import subprocess


def load_author_from_git() -> Optional[str]:
  """
  Returns a string formatted as "name <mail>" from the Git `user.name` and `user.email`
  configuration values. Returns `None` if Git is not configured.
  """

  try:
    name = subprocess.getoutput('git config user.name')
    email = subprocess.getoutput('git config user.email')
  except FileNotFoundError:
    return None
  if not name and not email:
    return None
  return '{} <{}>'.format(name, email)


@pkg.command()
@click.argument('target_directory', required=False)
@click.option('--project-name', metavar='name', required=True, help='The name of the project as it would appear on PyPI.')
@click.option('--module-name', metavar='fqn', help='The name of the main Python module (this may be a dotted module name). Defaults to the package name (hyphens replaced with underscores).')
@click.option('--author', metavar='"name <mail>"', help='The name of the author to write into the package configuration file. Defaults to the name and email from the Git config.')
@click.option('--version', metavar='x.y.z', help='The version number to start counting from. Defaults to "0.0.0" (stands for "unreleased").')
@click.option('--license', metavar='name', help='The name of the license to use for the project. A LICENSE.txt file will be created.')
@click.option('--dry', is_flag=True, help='Do not write files to disk.')
@click.option('-f', '--force', is_flag=True, help='Overwrite files if they already exist.')
def bootstrap(
  target_directory,
  project_name,
  module_name,
  author,
  version,
  license,
  dry,
  force,
):
  """
  Create files for a new Python package. If the *target_directory* is specified, the files will
  be written to that directory. Otherwise the value of the --project-name argument will be used
  as the target directory.
  """

  if not target_directory:
    target_directory = project_name
  if not author:
    author = load_author_from_git()

  env_vars = {
    'name': project_name,
    'version': version,
    'author': author,
    'license': license,
    'modulename': module_name,
    'name_on_disk': module_name or project_name,
  }

  name_on_disk = module_name or project_name

  def _render_template(template_string, **kwargs):
    assert isinstance(template_string, str), type(template_string)
    return jinja2.Template(template_string).render(**(kwargs or env_vars))

  def _render_file(fp, filename):
    content = pkg_resources.resource_string('shore', filename).decode()
    fp.write(_render_template(content))

  def _render_namespace_file(fp):
    fp.write("__path__ = __import__('pkgutil').extend_path(__path__, __name__)\n")

  def _get_template_files(template_path) -> Iterable[FileToRender]:
    # Render the template files to the target directory.
    for source_filename in walk_package_resources('shore', template_path):
      # Expand variables in the filename.
      name = name_on_disk.replace('-', '_').replace('.', '/')
      filename = _render_template(source_filename, name=name)
      dest = os.path.join(target_directory, filename)
      yield FileToRender(
        None,
        os.path.normpath(dest),
        lambda _, fp: _render_file(fp, template_path + '/' + source_filename))

  def _get_package_files() -> Iterable[FileToRender]:
    yield from _get_template_files('templates/package')

    # Render namespace supporting files.
    parts = []
    for item in name_on_disk.replace('-', '_').split('.')[:-1]:
      parts.append(item)
      dest = os.path.join(target_directory, 'src', *parts, '__init__.py')
      yield FileToRender(
        None,
        os.path.normpath(dest),
        lambda _, fp: _render_namespace_file(fp))
      dest = os.path.join(target_directory, 'src', 'test', *parts, '__init__.py')
      yield FileToRender(
        None,
        os.path.normpath(dest),
        lambda _, fp: fp.write('pass\n'))

    # TODO (@NiklasRosenstein): Render the license file if it does not exist.

  def _get_monorepo_files() -> Iterable[FileToRender]:
    yield from _get_template_files('templates/monorepo')

  #if args['monorepo']:
  #  files = _get_monorepo_files()
  files = _get_package_files()

  for file in files:
    if os.path.isfile(file.name) and not force:
      print(colored('Skip ' + file.name, 'yellow'))
      continue
    print(colored('Write ' + file.name, 'cyan'))
    if not dry:
      write_to_disk(file)
