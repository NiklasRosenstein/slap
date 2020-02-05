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

from nr.proxy import proxy_decorator
from nr.stream import Stream
from shore.core.plugins import (
  CheckResult,
  FileToRender,
  IMonorepoPlugin,
  IPackagePlugin,
  write_to_disk)
from shore.model import Monorepo, ObjectCache, Package
from shore.util import git as _git
from shore.util.license import get_license_metadata, wrap_license_text
from shore.util.resources import walk_package_resources
from termcolor import colored
from typing import Any, Dict, Iterable, List, Optional, Union
import argparse
import io
import jinja2
import json
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
    monorepo = Monorepo.load('monorepo.yaml', _cache)
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

  license_ = subparser.add_parser('license')
  license_.add_argument('license_name')
  license_.add_argument('--json', action='store_true')
  license_.add_argument('--text', action='store_true')
  license_.add_argument('--notice', action='store_true')

  new = subparser.add_parser('new')
  new.add_argument('name')
  new.add_argument('directory', nargs='?')
  new.add_argument('--version')
  new.add_argument('--author')
  new.add_argument('--license')
  new.add_argument('--modulename')
  new.add_argument('--monorepo', action='store_true')

  checks = subparser.add_parser('checks')
  checks.add_argument('--all', action='store_true')
  checks.add_argument('--treat-warnings-as-errors', action='store_true')

  bump = subparser.add_parser('bump')
  bump.add_argument('--patch', action='store_true')
  bump.add_argument('--minor', action='store_true')
  bump.add_argument('--major', action='store_true')
  bump.add_argument('--version')
  bump.add_argument('--force', action='store_true')
  bump.add_argument('--tag', action='store_true')
  bump.add_argument('--dry', action='store_true')
  bump.add_argument('--show', action='store_true')

  update = subparser.add_parser('update')
  update.add_argument('--skip-checks', action='store_true')
  update.add_argument('--all', action='store_true')
  update.add_argument('--dry', action='store_true')

  verify = subparser.add_parser('verify')
  verify.add_argument('--all')
  verify.add_argument('--tag')

  build = subparser.add_parser('build')
  build.add_argument('target', nargs='?')
  build.add_argument('--all', action='store_true')
  build.add_argument('--directory', default='build')

  publish = subparser.add_parser('publish')
  publish.add_argument('target', nargs='?')
  publish.add_argument('--all', action='store_true')
  publish.add_argument('--test', action='store_true')
  publish.add_argument('--build-directory', default='build')

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


def _license(parser, args):
  @proxy_decorator(deref=True, lazy=True)
  def data():
    return get_license_metadata(args.license_name)

  if args.json:
    print(json.dumps(data(), sort_keys=True))
  elif args.text:
    print(wrap_license_text(data['license_text']))
  elif args.notice:
    print(wrap_license_text(data['standard_notice'] or data['license_text']))
  else:
    parser.print_usage()


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


def _run_for_subject(subject: Union[Package, Monorepo], func, all: bool) -> List[Any]:
  if all:
    if not isinstance(subject, Monorepo):
      parser.error('--all can only be used in a monorepo context')
    subjects = [subject] + list(subject.get_packages())
    return [func(x) for x in subjects]
  else:
    return [func(subject)]


def _color_subject_name(subject: Union[Package, Monorepo]) -> str:
    color = 'blue' if isinstance(subject, Monorepo) else 'cyan'
    return colored(subject.name, color)


def _run_checks(subject, all: bool, treat_warnings_as_errors: bool=False):
  def _collect_checks(subject):
    return Stream.concat(x.get_checks(subject) for x in subject.get_plugins())
  checks = Stream.concat(_run_for_subject(subject, _collect_checks, all)).collect()
  if not checks:
    logger.info('✔ no checks triggered')
    return 0

  max_level = max(x.level for x in checks)
  if max_level == CheckResult.Level.INFO:
    status = 0
  elif max_level == CheckResult.Level.WARNING:
    status = 1 if treat_warnings_as_errors else 0
  elif max_level ==  CheckResult.Level.ERROR:
    status = 1
  else:
    assert False, max_level

  logger.info('%s %s check(s) triggered', '❌' if status != 0 else '✔',
    len(checks))

  colors = {'ERROR': 'red', 'WARNING': 'magenta', 'INFO': None}
  for check in checks:
    level = colored(check.level.name, colors[check.level.name])
    print('  {} ({}): {}'.format(level, _color_subject_name(check.on), check.message))

  logger.debug('exiting with status %s', status)
  return 1


def _checks(parser, args):
  subject = _load_subject(parser)
  return _run_checks(subject, args.all, args.treat_warnings_as_errors)


def _update(parser, args):
  def _collect_files(subject):
    return Stream.concat(x.get_files(subject) for x in subject.get_plugins())

  subject = _load_subject(parser)
  if not args.skip_checks:
    _run_checks(subject, args.all)

  files = _run_for_subject(subject, _collect_files, args.all)
  files = Stream.concat(files).collect()

  logger.info('⚪ rendering %s file(s)', len(files))
  for file in files:
    logger.info('  %s', os.path.relpath(file.name))
    if not args.dry:
      write_to_disk(file)


def _verify(parser, args):
  def _virtual_update(subject) -> Iterable[str]:
    files = Stream.concat(x.get_files(subject) for x in subject.get_plugins())
    for file in files:
      if not os.path.isfile(file.name):
        yield file.name
        continue
      fp = io.StringIO()
      write_to_disk(file, fp=fp)
      with io.open(file.name, newline='') as on_disk:
        if fp.getvalue() != on_disk.read():
          yield file.name

  def _tag_matcher(subject) -> Iterable[Union[Monorepo, Package]]:
    if isinstance(subject, Monorepo):
      # Shore does not support tagging workflows for monorepos yet.
      return; yield
    if subject.get_tag(subject.version) == args.tag:
      yield subject

  status = 0

  subject = _load_subject(parser)
  files = _run_for_subject(subject, _virtual_update, args.all)
  files = Stream.concat(files).collect()
  if files:
    logger.warning('❌ %s file(s) would be changed by an update.', len(files))
    status = 1
  else:
    logger.info('✔ no files would be changed by an update.')
  for file in files:
    logger.warning('  %s', os.path.relpath(file))

  if args.tag:
    matches = _run_for_subject(subject, _tag_matcher, args.all)
    matches = Stream.concat(matches).collect()
    if len(matches) == 0:
      # TODO (@NiklasRosenstein): If we matched the {name} portion of the
      #   tag_format (if present) we could find which package (or monorepo)
      #   the tag was intended for.
      logger.error('❌ unexpected tag: %s', args.tag)
      status = 1
    elif len(matches) > 1:
      logger.error('❌ tag matches multiple subjects: %s', args.tag)
      for match in matches:
        logger.error('  %s', match.name)
      status = 1
    else:
      logger.info('✔ tag %s matches %s', args.tag, matches[0].name)

  return status


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
  if different and not args.force:
    logger.error('inconsistent versions across files need to be fixed first.')
    return 1
  elif different:
    logger.warning('found inconsistent versions across files.')

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

  if new_version < nums and not args.force:
    parser.error('new version {} is lower than currenet version {}'.format(
      '.'.join(map(str, new_version)), '.'.join(map(str, nums))))
  if new_version == nums and not args.force:
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
    logger.info('  {}: {} → {}'.format(os.path.relpath(ref.filename), ref.value, new_version))
    if not args.dry:
      with open(ref.filename) as fp:
        contents = fp.read()
      contents = contents[:ref.start] + new_version + contents[ref.end:]
      with open(ref.filename, 'w') as fp:
        fp.write(contents)

  if args.tag:
    if any(f.mode == 'A' for f in _git.porcelain()):
      logger.error('cannot tag with non-empty staging area')
      return 1

    tag_name = subject.get_tag(new_version)
    logger.info('tagging {}'.format(tag_name))

    if not args.dry:
      changed_files = [x.filename for x in version_refs]
      _git.add(changed_files)
      if any(x.mode == 'A' for f in _git.porcelain()):
        # The files may not have changed if the version did not actually
        # update but --force was used (the goal of this is usually to end
        # up here for the tagging).
        _git.commit('bump version to {}'.format(new_version))
      _git.tag(tag_name, force=args.force)


def _filter_targets(targets: Dict[str, Any], target: str) -> Dict[str, Any]:
  return {
    k: v for k, v in targets.items()
    if target == k or k.startswith(target + ':')}


def _build(parser, args):
  subject = _load_subject(parser)
  targets = subject.get_build_targets()

  if args.target:
    targets = _filter_targets(targets, args.target)
    if not targets:
      logging.error('no build targets matched "{}"'.format(args.target))
      return 1

  if not targets:
    logging.info('no build targets')
    return 0

  os.makedirs(args.directory, exist_ok=True)
  for target_id, target in targets.items():
    logger.info('building target %s', colored(target_id, 'blue'))
    target.build(args.directory)


def _publish(parser, args):
  subject = _load_subject(parser)
  builds = subject.get_build_targets()
  publishers = subject.get_publish_targets()

  if args.target:
    publishers = _filter_targets(publishers, args.target)
    if not publishers:
      logger.error('no publish targets matched "{}"'.format(args.target))
      return 1

  if not publishers:
    logging.info('no publish targets')

  def _needs_build(build):
    for filename in build.get_build_artifacts():
      if not os.path.isfile(os.path.join(args.build_directory, filename)):
        return True
    return False

  def _run_publisher(name, publisher):
    try:
      logging.info('collecting builds for "{}" ...'.format(name))
      required_builds = {}
      for selector in publisher.get_build_selectors():
        selector_builds = _filter_targets(builds, selector)
        if not selector_builds:
          logger.error('selector "%s" could not be satisfied', selector)
          return False
        required_builds.update(selector_builds)

      for target_id, build in required_builds.items():
        if _needs_build(build):
          logger.info('building target %s', colored(target_id, 'blue'))
          os.makedirs(args.build_directory, exist_ok=True)
          build.build(args.build_directory)
        else:
          logger.info('skipping target %s', colored(target_id, 'blue'))

      publisher.publish(required_builds.values(), args.test, args.build_directory)
    except:
      logger.exception('error while running publisher "%s"', name)

  for key, publisher in publishers.items():
    _run_publisher(key, publisher)


_entry_main = lambda: sys.exit(main())

if __name__ == '__main__':
  _entry_main()
