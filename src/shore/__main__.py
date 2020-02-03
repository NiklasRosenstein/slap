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

from nr.stream import Stream
from shore.core.plugins import (
  FileToRender,
  IMonorepoPlugin,
  IPackagePlugin,
  write_to_disk)
from shore.util.resources import walk_package_resources
from shore.model import Monorepo, ObjectCache, Package
from termcolor import colored
from typing import Iterable, Union
import argparse
import jinja2
import logging
import os
import pkg_resources
import subprocess
import sys

_cache = ObjectCache()
logger = logging.getLogger(__name__)


def _get_author_info_from_git():
  try:
    name = subprocess.getoutput('git config user.name')
    email = subprocess.getoutput('git config user.email')
  except FileNotFoundError:
    return None
  if not name and not email:
    return None
  return '{} <{}>'.format(name, email)


def _load_subject(parser) -> Union[Monorepo, Package, None]:
  package, monorepo = None, None
  if os.path.isfile('package.yaml'):
    package = Package.load('package.yaml', _cache)
  if os.path.isfile('monorepo.yaml'):
    monorepo = Monorepo.load('package.yaml', _cache)
  if package and monorepo:
    raise RuntimeError('found package.yaml and monorepo.yaml in the same '
      'directory')
  if not package and not monorepo:
    parser.error('no package.yaml or monorepo.yaml in current directory')
  return package or monorepo


def get_argument_parser(prog=None):
  parser = argparse.ArgumentParser(prog=prog)
  parser.add_argument('-C', '--change-directory', metavar='DIR')
  parser.add_argument('-v', '--verbose', action='store_true')
  subparser = parser.add_subparsers(dest='command')

  new = subparser.add_parser('new')
  new.add_argument('name')
  new.add_argument('directory', nargs='?')
  new.add_argument('--version')
  new.add_argument('--author')
  new.add_argument('--license')
  new.add_argument('--modulename')
  new.add_argument('--monorepo', action='store_true')

  check = subparser.add_parser('check')
  check.add_argument('--treat-warnings-as-errors', action='store_true')

  bump = subparser.add_parser('bump')
  bump.add_argument('--patch', action='store_true')
  bump.add_argument('--minor', action='store_true')
  bump.add_argument('--major', action='store_true')
  bump.add_argument('--version')
  bump.add_argument('--show', action='store_true')
  bump.add_argument('--dry', action='store_true')

  update = subparser.add_parser('update')
  update.add_argument('--dry', action='store_true')

  build = subparser.add_parser('build')
  build.add_argument('target', nargs='?')
  build.add_argument('--all', action='store_true')
  build.add_argument('--directory')

  publish = subparser.add_parser('publish')
  publish.add_argument('target', nargs='?')
  publish.add_argument('--all', action='store_true')
  publish.add_argument('--test', action='store_true')
  publish.add_argument('--build-directory')

  return parser


def main(argv=None, prog=None):
  parser = get_argument_parser(prog)
  args = parser.parse_args(argv)
  if not args.command:
    parser.print_usage()
    return 0

  logging.basicConfig(
    format='[%(levelname)s:%(name)s]: %(message)s' if args.verbose else '%(message)s',
    level=logging.DEBUG if args.verbose else logging.INFO)

  if args.command in ('build', 'publish'):
    # Convert relative to absolute paths before changing directory.
    for attr in ('directory', 'build_directory'):
      if getattr(args, attr, None):
        setattr(args, attr, os.path.abspath(getattr(args, attr)))
  if args.change_directory:
    os.chdir(args.change_directory)

  return globals()['_' + args.command](parser, args)


def _new(parser, args):

  if not args.directory:
    args.directory = args.name

  if not args.author:
    args.author = _get_author_info_from_git()

  env_vars = {
    'name': args.name,
    'version': args.version,
    'author': args.author,
    'license': args.license,
    'modulename': args.modulename
  }

  def _render_template(template_string, **kwargs):
    assert isinstance(template_string, str), type(template_string)
    return jinja2.Template(template_string).render(**(kwargs or env_vars))

  def _render_file(fp, filename):
    content = pkg_resources.resource_string('shore', filename).decode()
    fp.write(_render_template(content))

  def _render_namespace_file(fp):
    fp.write("__path__ = __import__('pkgutil').extend_path(__path__, __name__)\n")

  def _get_files() -> Iterable[FileToRender]:
    # Render the template files to the target directory.
    for source_filename in walk_package_resources('shore', 'templates/new'):
      # Expand variables in the filename.
      filename = _render_template(source_filename, name=args.name.replace('.', '/'))
      dest = os.path.join(args.directory, filename)
      yield FileToRender(
        None,
        os.path.normpath(dest),
        lambda _, fp: _render_file(fp, 'templates/new/' + source_filename))

    # Render namespace supporting files.
    parts = []
    for item in args.name.split('.')[:-1]:
      parts.append(item)
      dest = os.path.join(args.directory, 'src', *parts, '__init__.py')
      yield FileToRender(
        None,
        os.path.normpath(dest),
        lambda _, fp: _render_namespace_file(fp))

    # TODO (@NiklasRosenstein): Render the license file if it does not exist.

  for file in _get_files():
    logger.info(file.name)
    write_to_disk(file)


def _check(parser, args):
  subject = _load_subject(parser)
  checks = []
  for plugin in subject.get_plugins():
    checks.extend(plugin.get_checks(subject))
  colors = {'ERROR': 'red', 'WARNING': 'magenta', 'INFO': None}
  status = 0
  for check in checks:
    level = colored(check.level.name, colors[check.level.name])
    print('{}: {}'.format(level, check.message))
    if check.level == check.Level.ERROR or (
        args.treat_warnings_as_errors and
        check.level == check.Level.WARNING):
      status = 1
  if not checks:
    logger.info('looking good 👌')
  logger.debug('exiting with status %s', status)
  return status


def _update(parser, args):
  subject = _load_subject(parser)
  files = []
  for plugin in subject.get_plugins():
    files.extend(plugin.get_files(subject))

  logger.info('rendering %s file(s)', len(files))
  for file in files:
    logger.info('  %s', os.path.relpath(file.name))
    if not args.dry:
      write_to_disk(file)


def _bump(parser, args):
  subject = _load_subject(parser)
  options = (args.patch, args.minor, args.major, args.version, args.show)
  if sum(map(bool, options)) == 0:
    parser.error('no operation specified')
  elif sum(map(bool, options)) > 1:
    parser.error('multiple operations specified')

  version_refs = []
  for plugin in subject.get_plugins():
    version_refs.extend(plugin.get_version_refs(subject))

  if not version_refs:
    parser.error('no version refs found 👎')
    return 1

  if args.show:
    for ref in version_refs:
      print('{}: {}'.format(os.path.relpath(ref.filename), ref.value))
    return 0

  # Ensure the version is the same accross all refs.
  current_version = version_refs[0].value
  different = [x for x in version_refs if x.value != current_version]
  if different:
    logging.error('inconsistent versions across files need to be fixed first.')
    return 1

  # TODO (@NiklasRosenstein): Support four parts (hotfix)
  nums = tuple(map(int, current_version.split('.')))
  assert len(nums) == 3, "version number must consist of 3 parts"

  if args.patch:
    new_version = (nums[0], nums[1], nums[2] + 1)
  elif args.minor:
    new_version = (nums[0], nums[1] + 1, 0)
  elif args.major:
    new_version = (nums[0] + 1, 0, 0)
    new_version[0] += 1
  elif args.version:
    new_version = tuple(map(int, args.version.split('.')))
    assert len(nums) == 3, "version number must consist of 3 parts"
  else:
    raise RuntimeError('what happened?')

  if new_version < nums:
    parser.error('new version {} is lower than currenet version {}'.format(
      '.'.join(map(str, new_version)), '.'.join(map(str, nums))))
  if new_version == nums:
    parser.error('new version is equal to current version {}'.format(
      '.'.join(map(str, nums))))

  new_version = '.'.join(map(str, new_version))

  # The replacement below does not work if the same file is listed multiple
  # times so let's check for now that every file is listed only once.
  n_files = set(os.path.normpath(os.path.abspath(ref.filename))
                for ref in version_refs)
  assert len(n_files) == len(version_refs), "multiple version refs in one "\
    "file is not currently supported."

  logger.info('bumping {} version reference(s)'.format(
    len(version_refs), current_version, new_version))
  for ref in version_refs:
    assert ref.value == current_version
    logger.info('  {}: {} → {}'.format(os.path.relpath(ref.filename), ref.value, new_version))
    if not args.dry:
      with open(ref.filename) as fp:
        contents = fp.read()
      contents = contents[:ref.start] + new_version + contents[ref.end:]
      with open(ref.filename, 'w') as fp:
        fp.write(contents)


_entry_main = lambda: sys.exit(main())

if __name__ == '__main__':
  _entry_main()
