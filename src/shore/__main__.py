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
from shore import __version__
from shore.core.plugins import (
  CheckResult,
  FileToRender,
  IMonorepoPlugin,
  IPackagePlugin,
  write_to_disk)
from shore.model import Monorepo, ObjectCache, Package
from shore.util import git as _git
from shore.util.ci import get_ci_version
from shore.util.classifiers import get_classifiers
from shore.util.license import get_license_metadata, wrap_license_text
from shore.util.resources import walk_package_resources
from shore.util.version import parse_version, bump_version
from termcolor import colored
from typing import Any, Dict, Iterable, List, Optional, Union
import click
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


def _report_conflict(parser, args, *opts: str):
  """ Checks if any two of the specified *opts* is present in *args*. If so,
  a parser error will indicate the conflicting options. """

  has_opts = set(k for k in opts if getattr(args, k))
  if len(has_opts) > 1:
    parser.error('conflicting options: {}'.format(
      ' and '.join('--' + k for k in has_opts)))


def _load_subject() -> Union[Monorepo, Package, None]:
  package, monorepo = None, None
  if os.path.isfile('package.yaml'):
    package = Package.load('package.yaml', _cache)
  if os.path.isfile('monorepo.yaml'):
    monorepo = Monorepo.load('monorepo.yaml', _cache)
  if package and monorepo:
    raise RuntimeError('found package.yaml and monorepo.yaml in the same '
      'directory')
  if not package and not monorepo:
    logger.error('no package.yaml or monorepo.yaml in current directory')
    exit(1)
  return package or monorepo


@click.group()
@click.option('-C', '--change-directory')
@click.option('-v', '--verbose')
@click.option('--version', is_flag=True)
def cli(change_directory, verbose, version):
  if version:
    print(__version__)
    exit(0)

  logging.basicConfig(
    format='[%(levelname)s:%(name)s]: %(message)s' if verbose else '%(message)s',
    level=logging.DEBUG if verbose else logging.INFO)

  if change_directory:
    os.chdir(change_directory)


@cli.command()
@click.argument('output_type', type=click.Choice(['json', 'text', 'notice']))
@click.argument('license_name')
def license(output_type, license_name):
  data = get_license_metadata(license_name)
  if output_type == 'json':
    print(json.dumps(data(), sort_keys=True))
  elif output_type == 'text':
    print(wrap_license_text(data['license_text']))
  elif ouutput_type == 'notice':
    print(wrap_license_text(data['standard_notice'] or data['license_text']))
  else:
    raise RuntimeError(output_type)


@cli.group()
def classifiers():
  pass


@classifiers.command('search')
@click.argument('q')
def search_classifiers(q):
  for classifier in get_classifiers():
    if q.strip().lower() in classifier.lower():
      print(classifier)


@cli.command()
@click.argument('name')
@click.argument('directory', required=False)
@click.option('--author')
@click.option('--version')
@click.option('--license')
@click.option('--modulename')
@click.option('--monorepo', is_flag=True)
@click.option('--dry', is_flag=True)
@click.option('-f/--force', is_flag=True)
def new(**args):
  if not args['directory']:
    args['directory'] = args['name']

  if not args['author']:
    args['author'] = _get_author_info_from_git()

  env_vars = {
    'name': args['name'],
    'version': args['version'],
    'author': args['author'],
    'license': args['license'],
    'modulename': args['modulename']
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
      filename = _render_template(source_filename, name=args['name'].replace('.', '/'))
      dest = os.path.join(args['directory'], filename)
      yield FileToRender(
        None,
        os.path.normpath(dest),
        lambda _, fp: _render_file(fp, 'templates/new/' + source_filename))

    # Render namespace supporting files.
    parts = []
    for item in args['name'].split('.')[:-1]:
      parts.append(item)
      dest = os.path.join(args['directory'], 'src', *parts, '__init__.py')
      yield FileToRender(
        None,
        os.path.normpath(dest),
        lambda _, fp: _render_namespace_file(fp))

    # TODO (@NiklasRosenstein): Render the license file if it does not exist.

  for file in _get_files():
    if os.path.isfile(file.name) and not args['force']:
      print(colored('Skip ' + file.name, 'yellow'))
      continue
    print(colored('Write ' + file.name, 'blue'))
    if not args['dry']:
      write_to_disk(file)


def _run_for_subject(subject: Union[Package, Monorepo], func) -> List[Any]:
  if isinstance(subject, Monorepo):
    subjects = [subject] + sorted(subject.get_packages(), key=lambda x: x.name)
    return [func(x) for x in subjects]
  else:
    return [func(subject)]


def _color_subject_name(subject: Union[Package, Monorepo]) -> str:
    color = 'blue' if isinstance(subject, Monorepo) else 'cyan'
    return colored(subject.name, color)


def _run_checks(subject, treat_warnings_as_errors: bool=False):
  def _collect_checks(subject):
    return Stream.concat(x.get_checks(subject) for x in subject.get_plugins())
  checks = Stream.concat(_run_for_subject(subject, _collect_checks)).collect()
  if not checks:
    logger.info('✔ no checks triggered')
    return True

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
  return False


@cli.command()
@click.option('--treat-warnings-as-errors', is_flag=True)
def checks(treat_warnings_as_errors):
  subject = _load_subject()
  if not _run_checks(subject, treat_warnings_as_errors):
    exit(1)
  exit(0)


@cli.command()
@click.option('--skip-checks', is_flag=True)
@click.option('--dry', is_flag=True)
def update(skip_checks, dry):
  def _collect_files(subject):
    return Stream.concat(x.get_files(subject) for x in subject.get_plugins())

  subject = _load_subject()
  if not skip_checks:
    _run_checks(subject, True)

  files = _run_for_subject(subject, _collect_files)
  files = Stream.concat(files).collect()

  logger.info('⚪ rendering %s file(s)', len(files))
  for file in files:
    logger.info('  %s', os.path.relpath(file.name))
    if not dry:
      write_to_disk(file)


@cli.command()
@click.option('--tag')
def verify(tag):
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
    if subject.get_tag(subject.version) == tag:
      yield subject

  status = 0

  subject = _load_subject()
  files = _run_for_subject(subject, _virtual_update)
  files = Stream.concat(files).collect()
  if files:
    logger.warning('❌ %s file(s) would be changed by an update.', len(files))
    status = 1
  else:
    logger.info('✔ no files would be changed by an update.')
  for file in files:
    logger.warning('  %s', os.path.relpath(file))

  if tag:
    matches = _run_for_subject(subject, _tag_matcher)
    matches = Stream.concat(matches).collect()
    if len(matches) == 0:
      # TODO (@NiklasRosenstein): If we matched the {name} portion of the
      #   tag_format (if present) we could find which package (or monorepo)
      #   the tag was intended for.
      logger.error('❌ unexpected tag: %s', tag)
      status = 1
    elif len(matches) > 1:
      logger.error('❌ tag matches multiple subjects: %s', tag)
      for match in matches:
        logger.error('  %s', match.name)
      status = 1
    else:
      logger.info('✔ tag %s matches %s', tag, matches[0].name)

  exit(status)


@cli.command()
@click.argument('type', type=click.Choice(
  ['major', 'minor', 'patch', 'post', 'ci', 'show', 'get-single-version', 'status']),
  required=False)
@click.option('--version')
@click.option('--tag', is_flag=True)
@click.option('--dry', is_flag=True)
@click.option('--skip-checks', is_flag=True)
@click.option('-f/--force', is_flag=True)
def bump(**args):
  if not args['type'] and not args['version']:
    logger.error('conflict arguments: --version and type')
    exit(1)
  if not args['type'] and not args['version']:
    logger.error('missing arguments: specify type or --version')
    exit(1)

  subject = _load_subject()

  if not args['type'] not in ('get-single-version',) and not args['skip_checks']:
    _run_checks(subject, True)

  if isinstance(subject, Package) and subject.monorepo \
      and subject.monorepo.mono_versioning:
    if args['force']:
      logger.warning('forcing version bump on individual package version '
        'that is usually managed by the monorepo.')
    else:
      parser.error('cannot bump individual package version if managed by monorepo.')

  def _get_version_refs(subject):
    for plugin in subject.get_plugins():
      yield plugin.get_version_refs(subject)

  if isinstance(subject, Monorepo) and subject.mono_versioning:
    version_refs = Stream.concat(_run_for_subject(subject, _get_version_refs))
  else:
    version_refs = _get_version_refs(subject)
  version_refs = Stream.concat(version_refs).collect()

  if not version_refs:
    parser.error('no version refs found')
    exit(1)

  if args['type'] == 'show':
    for ref in version_refs:
      print('{}: {}'.format(os.path.relpath(ref.filename), ref.value))
    exit(0)

  # Ensure the version is the same accross all refs.
  is_inconsistent = any(parse_version(x.value) != subject.version for x in version_refs)
  if is_inconsistent and not args['force']:
    logger.error('inconsistent versions across files need to be fixed first.')
    exit(1)
  elif is_inconsistent and args['type'] == 'get-single-version':
    logger.error('no single consistent version found.')
    exit(1)
  elif is_inconsistent:
    logger.warning('inconsistent versions across files were found.')

  if args['type'] == 'get-single-version':
    print(subject.version)
    exit(0)

  current_version = subject.version
  if args['type'] == 'post':
    new_version = bump_version(current_version, 'post')
  elif args['type'] == 'patch':
    new_version = bump_version(current_version, 'patch')
  elif args['type'] == 'minor':
    new_version = bump_version(current_version, 'minor')
  elif args['type'] == 'major':
    new_version = bump_version(current_version, 'major')
  elif args['type'] == 'ci':
    new_version = get_ci_version(subject)
  elif args['version']:
    new_version = parse_version(args['version'])
  else:
    raise RuntimeError('what happened?')

  if new_version < current_version and not args['force']:
    parser.error('new version {} is lower than currenet version {}'.format(
      new_version, current_version))
  # Comparing as strings to include the prerelease/build number in the
  # comparison.
  if str(new_version) == str(current_version) and not args['force']:
    parser.error('new version {} is equal to current version {}'.format(
      new_version, current_version))

  # The replacement below does not work if the same file is listed multiple
  # times so let's check for now that every file is listed only once.
  n_files = set(os.path.normpath(os.path.abspath(ref.filename))
                for ref in version_refs)
  assert len(n_files) == len(version_refs), "multiple version refs in one "\
    "file is not currently supported."

  logger.info('bumping %d version reference(s)', len(version_refs))
  for ref in version_refs:
    logger.info('  %s: %s → %s', os.path.relpath(ref.filename), ref.value, new_version)
    if not args['dry']:
      with open(ref.filename) as fp:
        contents = fp.read()
      contents = contents[:ref.start] + str(new_version) + contents[ref.end:]
      with open(ref.filename, 'w') as fp:
        fp.write(contents)

  if args['tag']:
    if any(f.mode == 'A' for f in _git.porcelain()):
      logger.error('cannot tag with non-empty staging area')
      exit(1)

    tag_name = subject.get_tag(new_version)
    logger.info('tagging %s', tag_name)

    if not args['dry']:
      changed_files = [x.filename for x in version_refs]
      _git.add(changed_files)
      if any(x.mode == 'M' for x in _git.porcelain()):
        # The files may not have changed if the version did not actually
        # update but --force was used (the goal of this is usually to end
        # up here for the tagging).
        _git.commit('({}) bump version to {}'.format(subject.name, new_version))
      _git.tag(tag_name, force=args['force'])


@cli.command()
def status():
  """ Shows the number of commits since the last release. """

  subject = _load_subject()
  width = max(_run_for_subject(subject, lambda s: len(s.name)))
  def _status(subject):
    tag = subject.get_tag(subject.version)
    ref = _git.rev_parse(tag)
    if not ref:
      status = colored('tag "{}" not found'.format(tag), 'red')
    else:
      count = len(_git.rev_list(tag + '..HEAD', subject.directory))
      if count == 0:
        status = colored('no commits', 'green') + ' since "{}"'.format(tag)
      else:
        status = colored('{} commit(s)'.format(count), 'yellow') + ' since "{}"'.format(tag)
    print(subject.name.rjust(width), status)
  _run_for_subject(subject, _status)
  exit(0)


def _filter_targets(targets: Dict[str, Any], target: str) -> Dict[str, Any]:
  return {
    k: v for k, v in targets.items()
    if target == k or k.startswith(target + ':')}


@cli.command()
@click.argument('target', nargs=-1)
@click.option('--build-dir', default='build',
  help='Override the build directory. Defaults to ./build')
def build(**args):
  subject = _load_subject()
  targets = subject.get_build_targets()

  if args['target']:
    targets = _filter_targets(targets, args['target'])
    if not targets:
      logging.error('no build targets matched "%s"', args['target'])
      exit(1)

  if not targets:
    logging.info('no build targets')
    exit(0)

  os.makedirs(args['build_dir'], exist_ok=True)
  for target_id, target in targets.items():
    logger.info('building target %s', colored(target_id, 'blue'))
    target.build(args['build_dir'])


@cli.command()
@click.argument('target', nargs=-1)
@click.option('--build-dir', default='build',
  help='Override the build directory. Defaults to ./build')
@click.option('--test', is_flag=True,
  help='Publish to a test repository instead.')
@click.option('--rebuild/--no-rebuild', default=True,
  help='Rebuild or not rebuild existing build artifacts. Defaults to rebuild.')
def publish(**args):
  subject = _load_subject()
  builds = subject.get_build_targets()
  publishers = subject.get_publish_targets()

  if subject.get_private():
    logger.error('"%s" is marked private, publish prevented.', subject.name)
    exit(1)

  if args['target']:
    publishers = _filter_targets(publishers, args['target'])
    if not publishers:
      logger.error('no publish targets matched "%s"', args['target'])
      exit(1)

  if not publishers:
    logging.info('no publish targets')

  def _needs_build(build):
    for filename in build.get_build_artifacts():
      if not os.path.isfile(os.path.join(args['build_dir'], filename)):
        return True
    return False

  def _run_publisher(name, publisher):
    try:
      logging.info('collecting builds for "%s" ...', name)
      required_builds = {}
      for selector in publisher.get_build_selectors():
        selector_builds = _filter_targets(builds, selector)
        if not selector_builds:
          logger.error('selector "%s" could not be satisfied', selector)
          return False
        required_builds.update(selector_builds)

      for target_id, build in required_builds.items():
        if not args['rebuild'] and not _needs_build(build):
          logger.info('skipping target %s', colored(target_id, 'blue'))
        else:
          logger.info('building target %s', colored(target_id, 'blue'))
          os.makedirs(args['build_dir'], exist_ok=True)
          build.build(args['build_dir'])

      publisher.publish(required_builds.values(), args['test'], args['build_dir'])
      return True
    except:
      logger.exception('error while running publisher "%s"', name)
      return False

  status = 0
  for key, publisher in publishers.items():
    if not _run_publisher(key, publisher):
      status = 1

  logger.debug('exit with status code %s', status)
  exit(status)


_entry_point = lambda: sys.exit(cli())

if __name__ == '__main__':
  _entry_point()
