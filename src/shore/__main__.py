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

from fnmatch import fnmatch
from nr.proxy import proxy_decorator
from nr.stream import Stream
from shore import __version__
from shore.core.plugins import (
  CheckResult,
  FileToRender,
  IMonorepoPlugin,
  IPackagePlugin,
  VersionRef,
  write_to_disk)
from shore.mapper import mapper
from shore.model import Monorepo, ObjectCache, Package, VersionSelector
from shore.plugins.core import get_monorepo_interdependency_version_refs
from shore.util import git as _git
from shore.util.changelog import ChangelogEntry, ChangelogManager
from shore.util.classifiers import get_classifiers
from shore.util.license import get_license_metadata, wrap_license_text
from shore.util.resources import walk_package_resources
from shore.util.version import get_commit_distance_version, parse_version, bump_version, Version
from termcolor import colored
from typing import Any, Dict, Iterable, List, Optional, Union
import click
import io
import jinja2
import json
import logging
import nr.fs
import os
import pkg_resources
import re
import shlex
import shutil
import subprocess
import sys
import textwrap
import yaml

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


def _commit_distance_version(subject: [Monorepo, Package]) -> Version:
  if isinstance(subject, Package) and subject.monorepo \
      and subject.monorepo.mono_versioning:
    subject = subject.monorepo
  return get_commit_distance_version(
    subject.directory,
    subject.version,
    subject.get_tag(subject.version)) or subject.version


def _md_term_stylize(text: str) -> str:
  def _code(m):
    return colored(m.group(1), 'cyan')
  def _issue_ref(m):
    return colored(m.group(0), 'yellow', attrs=['bold'])
  text = re.sub(r'`([^`]+)`', _code, text)
  text = re.sub(r'#\d+', _issue_ref, text)
  return text


def _editor_open(filename: str):
  editor = shlex.split(os.getenv('EDITOR', 'vim'))
  return subprocess.call(editor + [filename])


def _edit_text(text: str) -> str:
  """
  Opens an editor for the user to modify *text*.
  """

  with nr.fs.tempfile('.yml', dir=os.getcwd(), text=True) as fp:
    fp.write(text)
    fp.close()
    res = _editor_open(fp.name)
    if res != 0:
      sys.exit(res)
    with open(fp.name) as src:
      return src.read()


def _load_subject(allow_none: bool = False) -> Union[Monorepo, Package, None]:
  package, monorepo = None, None
  if os.path.isfile('package.yaml'):
    package = Package.load('package.yaml', _cache)
  if os.path.isfile('monorepo.yaml'):
    monorepo = Monorepo.load('monorepo.yaml', _cache)
  if package and monorepo:
    raise RuntimeError('found package.yaml and monorepo.yaml in the same '
      'directory')
  if not allow_none and not package and not monorepo:
    logger.error('no package.yaml or monorepo.yaml in current directory')
    exit(1)
  return package or monorepo


@click.group()
@click.option('-C', '--change-directory')
@click.option('-v', '--verbose', is_flag=True)
@click.version_option(version=__version__)
def cli(change_directory, verbose):
  logging.basicConfig(
    format='[%(levelname)s:%(name)s]: %(message)s' if verbose else '%(message)s',
    level=logging.DEBUG if verbose else logging.INFO)

  if change_directory:
    os.chdir(change_directory)


@cli.command()
@click.argument('output_type', type=click.Choice(['json', 'text', 'notice']))
@click.argument('license_name')
def license(output_type, license_name):
  """ Print license information, full text or short notice. """

  data = get_license_metadata(license_name)
  if output_type == 'json':
    print(json.dumps(data(), sort_keys=True))
  elif output_type == 'text':
    print(wrap_license_text(data['license_text']))
  elif ouutput_type == 'notice':
    print(wrap_license_text(data['standard_notice'] or data['license_text']))
  else:
    raise RuntimeError(output_type)


@cli.command('classifiers')
@click.argument('q', required=False)
def classifiers(q):
  """ Search for package classifiers on PyPI. """

  for classifier in get_classifiers():
    if not q or q.strip().lower() in classifier.lower():
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
@click.option('--force', '-f', is_flag=True)
def new(**args):
  """ Initialize a new project or repository. """

  if not args['directory']:
    args['directory'] = args['name']

  if not args['author']:
    args['author'] = _get_author_info_from_git()

  env_vars = {
    'name': args['name'],
    'version': args['version'],
    'author': args['author'],
    'license': args['license'],
    'modulename': args['modulename'],
    'name_on_disk': args['modulename'] or args['name'],
  }

  name_on_disk = args['modulename'] or args['name']

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
      dest = os.path.join(args['directory'], filename)
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
      dest = os.path.join(args['directory'], 'src', *parts, '__init__.py')
      yield FileToRender(
        None,
        os.path.normpath(dest),
        lambda _, fp: _render_namespace_file(fp))
      dest = os.path.join(args['directory'], 'src', 'test', *parts, '__init__.py')
      yield FileToRender(
        None,
        os.path.normpath(dest),
        lambda _, fp: fp.write('pass\n'))

    # TODO (@NiklasRosenstein): Render the license file if it does not exist.

  def _get_monorepo_files() -> Iterable[FileToRender]:
    yield from _get_template_files('templates/monorepo')

  if args['monorepo']:
    files = _get_monorepo_files()
  else:
    files = _get_package_files()

  for file in files:
    if os.path.isfile(file.name) and not args['force']:
      print(colored('Skip ' + file.name, 'yellow'))
      continue
    print(colored('Write ' + file.name, 'cyan'))
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


@cli.command('check')
@click.option('--treat-warnings-as-errors', is_flag=True)
def checks(treat_warnings_as_errors):
  """ Run checks. """

  subject = _load_subject()
  if not _run_checks(subject, treat_warnings_as_errors):
    exit(1)
  exit(0)


@cli.command('update')
@click.option('--skip-checks', is_flag=True)
@click.option('--dry', is_flag=True)
@click.option('--stage', is_flag=True, help='Stage changed files in Git.')
def update(skip_checks, dry, stage):
  """ (Re-)render files managed shore. """

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

  if stage:
    _git.add([f.name for f in files])


@cli.command('verify')
@click.option('--tag', '-t', help='Specify the tag from CI checks to match with the tag produced by shore.')
@click.option('--tag-check', type=click.Choice(['require', 'if-present', 'skip', 'ignore']), default='if-present')
@click.option('--update-check', type=click.Choice(['require', 'skip', 'ignore']), default='require')
def verify(tag, tag_check, update_check):
  """ Check whether "update" would change any files. """

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
    if isinstance(subject, Monorepo) and not subject.mono_versioning:
      # Tagging workflows on mono-repos without mono-versioning are not supported.
      return; yield
    if subject.get_tag(subject.version) == tag:
      yield subject

  status = 0

  subject = _load_subject()

  if update_check != 'skip':
    files = _run_for_subject(subject, _virtual_update)
    files = Stream.concat(files).collect()
    if files:
      logger.warning('❌ %s file(s) would be changed by an update.', len(files))
      if update_check != 'ignore':
        status = 1
    else:
      logger.info('✔ no files would be changed by an update.')
    for file in files:
      logger.warning('  %s', os.path.relpath(file))

  if tag_check != 'skip':
    if tag_check == 'require' and not tag:
      logger.error('❌ the specified tag is an empty string')
      status = 1
    elif tag:
      matches = _run_for_subject(subject, _tag_matcher)
      matches = Stream.concat(matches).collect()
      if len(matches) == 0:
        # TODO (@NiklasRosenstein): If we matched the {name} portion of the
        #   tag_format (if present) we could find which package (or monorepo)
        #   the tag was intended for.
        logger.error('❌ tag %s did not match any of the available subjects', tag)
        if tag_check != 'ignore':
          status = 1
      elif len(matches) > 1:
        logger.error('❌ tag matches multiple subjects: %s', tag)
        for match in matches:
          logger.error('  %s', match.name)
        if tag_check != 'ignore':
          status = 1
      else:
        logger.info('✔ tag %s matches %s', tag, matches[0].name)

  exit(status)


def _get_version_refs(subject) -> List[VersionRef]:
  def _get(subject):
    for plugin in subject.get_plugins():
      yield plugin.get_version_refs(subject)

  if isinstance(subject, Monorepo) and subject.mono_versioning:
    version_refs = Stream.concat(_run_for_subject(subject, _get))
  else:
    version_refs = _get(subject)
  return Stream.concat(version_refs).collect()


@cli.command('bump')
@click.argument('version', required=False)
@click.option('--major', is_flag=True)
@click.option('--minor', is_flag=True)
@click.option('--patch', is_flag=True)
@click.option('--post', is_flag=True)
@click.option('--snapshot', is_flag=True)
@click.option('--tag', is_flag=True)
@click.option('--dry', is_flag=True)
@click.option('--skip-checks', is_flag=True)
@click.option('--force', '-f', is_flag=True)
@click.option('--allow-lower', is_flag=True)
@click.option('--push', is_flag=True)
@click.option('--update', is_flag=True)
@click.option('--publish')
def bump(**args):
  """ Bump version numbers. Either supply a target "version" (may require --force
  if the specified version is lower than the current) or specify one of the --major,
  --minor, --patch, --post or --snapshot flags.

  The "version" argument can also be one of the strings "major", "minor", "patch",
  "post" or "git" which is only for backwards compatibility and will be removed in a
  future version of shore.
  """

  subject = _load_subject()
  changelog_manager = ChangelogManager(subject.changelog_directory, mapper)

  bump_flags = ('major', 'minor', 'patch', 'post', 'snapshot')
  bump_args = ['--' + k for k in bump_flags if args[k]]
  if args['version']:
    bump_args.insert(0, '<version>')
  if len(bump_args) > 1:
    logger.error('incompatible arguments: ' + ', '.join(bump_args))
    exit(1)
  elif not bump_args:
    flags = ', '.join('--' + k for k in bump_flags)
    logger.error('missing arguments: specify a <version> or one of ' + flags)
    exit(1)

  # Warn for deprecated behavior.
  if args['version'] in ('post', 'patch', 'minor', 'major', 'git'):
    use_flag = '--' + args['version']
    if use_flag == '--git':
      use_flag = '--snapshot'
    logger.warning('Support for the %r argument is deprecated and will be removed in a '
      'future version of Shore. Please use the %s flag instead.', args['version'], use_flag)

  if not args['skip_checks']:
    _run_checks(subject, True)

  if args['push'] and not args['tag']:
    logger.error('--push needs --tag')
    exit(1)

  if isinstance(subject, Package) and subject.monorepo \
      and subject.monorepo.mono_versioning:
    if args['force']:
      logger.warning('forcing version bump on individual package version '
        'that is usually managed by the monorepo.')
    else:
      logger.error('cannot bump individual package version if managed by monorepo.')
      exit(1)

  version_refs = _get_version_refs(subject)
  if not version_refs:
    logger.error('no version refs found')
    exit(1)

  # Ensure the version is the same accross all refs.
  is_inconsistent = any(parse_version(x.value) != subject.version for x in version_refs)
  if is_inconsistent and not args['force']:
    logger.error('inconsistent versions across files need to be fixed first.')
    exit(1)
  elif is_inconsistent:
    logger.warning('inconsistent versions across files were found.')

  current_version = subject.version
  pep440_version = True
  if args['version'] == 'post' or args['post']:
    new_version = bump_version(current_version, 'post')
  elif args['version'] == 'patch' or args['patch']:
    new_version = bump_version(current_version, 'patch')
  elif args['version'] == 'minor' or args['minor']:
    new_version = bump_version(current_version, 'minor')
  elif args['version'] == 'major' or args['major']:
    new_version = bump_version(current_version, 'major')
  elif args['version'] == 'git' or args['snapshot']:
    new_version = _commit_distance_version(subject)
    args['allow_lower'] = True
  else:
    new_version = parse_version(args['version'])

  if not new_version.pep440_compliant:
    logger.warning('version "{}" is not PEP440 compliant.'.format(new_version))

  if new_version < current_version and not (args['force'] or args['allow_lower']):
    logger.error('version {} is lower than current version {}'.format(
      new_version, current_version))
    exit(1)
  # Comparing as strings to include the prerelease/build number in the
  # comparison.
  if str(new_version) == str(current_version) and not args['force']:
    logger.warning('new version {} is equal to current version {}'.format(
      new_version, current_version))
    exit(0)

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

  # For monorepos using mono-versioning, we may need to bump cross-package references.
  if isinstance(subject, Monorepo) and subject.mono_versioning:
    version_sel_refs = list(get_monorepo_interdependency_version_refs(subject, new_version))
    logger.info('bumping %d monorepo inter-dependency requirement(s)', len(version_sel_refs))
    for group_key, refs in Stream.groupby(version_sel_refs, lambda r: r.filename, collect=list):
      logger.info('  %s:', os.path.relpath(group_key))
      with open(group_key) as fp:
        content = fp.read()
      offset = 0
      for ref in refs:
        logger.info('    %s %s → %s', ref.package, ref.sel, ref.new_sel)
        content = content[:ref.start - offset] + ref.new_sel + content[ref.end - offset:]
        offset += len(ref.sel) - len(ref.new_sel)
      if not args['dry']:
        with open(group_key, 'w') as fp:
          fp.write(content)

    if args['tag'] and version_sel_refs:
      logger.warning('bump requires an update in order to automatically tag')
      args['update'] = True

  changed_files = [x.filename for x in version_refs]

  # Rename the unreleased changelog if it exists.
  if changelog_manager.unreleased.exists():
    changed_files.append(changelog_manager.unreleased.filename)
    if args['dry']:
      changelog = changelog_manager.version(new_version)
    else:
      changelog = changelog_manager.release(new_version)
    changed_files.append(changelog.filename)
    logger.info('release staged changelog (%s → %s)', changelog_manager.unreleased.filename,
      changelog.filename)

  if args['update']:
    _cache.clear()
    try:
      update(['--stage'])
    except SystemExit as exc:
      if exc.code != 0:
        raise

  if args['tag']:
    if any(f.mode == 'A' for f in _git.porcelain()):
      logger.error('cannot tag with non-empty staging area')
      exit(1)

    tag_name = subject.get_tag(new_version)
    logger.info('tagging %s', tag_name)

    if not args['dry']:
      _git.add(changed_files)
      _git.commit('({}) bump version to {}'.format(subject.name, new_version), allow_empty=True)
      _git.tag(tag_name, force=args['force'])

    if not args['dry'] and args['push']:
      _git.push(_git.current_branch(), tag_name)

  if args['publish']:
    _cache.clear()
    publish([args['publish']])


@cli.command('status')
def status():
  """ Print the release status. """

  subject = _load_subject()

  def _get_commits_since_last_tag(subject):
    tag = subject.get_tag(subject.version)
    ref = _git.rev_parse(tag)
    if not ref:
      return tag, None
    else:
      return tag, len(_git.rev_list(tag + '..HEAD', subject.directory))

  items = [subject]
  if isinstance(subject, Monorepo):
    items.extend(sorted(subject.get_packages(), key=lambda x: x.name))
    if not subject.version:
      items.remove(subject)
  width = max(len(x.local_name) for x in items)

  for item in items:
    tag, num_commits = _get_commits_since_last_tag(item)
    if num_commits is None:
      item_info = colored('tag "{}" not found'.format(tag), 'red')
    elif num_commits == 0:
      item_info = colored('no commits', 'green') + ' since "{}"'.format(tag)
    else:
      item_info = colored('{} commit(s)'.format(num_commits), 'yellow') + ' since "{}"'.format(tag)
    print('{}: {}'.format(item.local_name.rjust(width), item_info))


@cli.command()
@click.option('--tag', '-t', is_flag=True)
@click.option('--snapshot', '-s', is_flag=True)
def version(tag, snapshot):
  """ Print the current package or repository version. """

  subject = _load_subject()
  version = _commit_distance_version(subject) if snapshot else subject.version
  if tag:
    print(subject.get_tag(version))
  else:
    print(version)


@cli.command()
@click.argument('args', nargs=-1)
def git(args):
  """ Shortcut for running git commands with a version range since the last
  tag of the current package or repo.

  This is effectively a shortcut for

  \b
    git $1 `shore versions -ct`..HEAD $@ -- .
  """

  subject = _load_subject()
  tag = subject.get_tag(subject.version)
  command = ['git', args[0]] + [tag + '..HEAD'] + list(args[1:]) + ['--', '.']
  exit(subprocess.call(command))


def _filter_targets(targets: Dict[str, Any], target: str) -> Dict[str, Any]:
  result = {}
  for key, value in targets.items():
    if fnmatch(key, target) or fnmatch(key, target + ':*'):
      result[key] = value
  return result


@cli.command()
@click.argument('target')
@click.option('--build-dir', default='build',
  help='Override the build directory. Defaults to ./build')
def build(**args):
  """ Build distributions. """

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
    logger.info('building target %s', colored(target_id, 'cyan'))
    target.build(args['build_dir'])


@cli.command()
@click.argument('target', required=False)
@click.option('-l', '--list', is_flag=True)
@click.option('-a', '--all', is_flag=True)
@click.option('--build-dir', default='build',
  help='Override the build directory. Defaults to ./build')
@click.option('--test', is_flag=True,
  help='Publish to a test repository instead.')
@click.option('--build/--no-build', default=True,
  help='Always build artifacts before publishing. Enabled by default.')
@click.option('--skip-existing', is_flag=True)
def publish(**args):
  """ Publish a source distribution to PyPI. """

  subject = _load_subject()
  builds = subject.get_build_targets()
  publishers = subject.get_publish_targets()

  if args['all'] and isinstance(subject, Monorepo) and not subject.mono_versioning:
    logger.error('publish -a,--all not allowed for Monorepo without mono-versioning')
    exit(1)

  if args['target']:
    publishers = _filter_targets(publishers, args['target'])
    if not publishers:
      logger.error('no publish targets matched "%s"', args['target'])
      exit(1)

  if args['list']:
    if publishers:
      print('Publish targets for', colored(subject.name, 'cyan') + ':')
      for target in publishers:
        print('  ' + colored(target, 'yellow'))
    else:
      print('No publish targets for', colored(subject.name, 'cyan') + '.')
    exit(0)

  if not publishers or (not args['target'] and not args['all']):
    logging.info('no publish targets')
    exit(1)

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
        if not args['build'] and not _needs_build(build):
          logger.info('skipping target %s', colored(target_id, 'cyan'))
        else:
          logger.info('building target %s', colored(target_id, 'cyan'))
          os.makedirs(args['build_dir'], exist_ok=True)
          build.build(args['build_dir'])

      publisher.publish(
        required_builds.values(),
        args['test'],
        args['build_dir'],
        args['skip_existing'])
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


@cli.command()
@click.argument('version', type=parse_version, required=False)
@click.option('--reformat', is_flag=True, help='Reformat the changelog.')
@click.option('-n', '--new', metavar='type,…',
  help='Create a new entry. The argument for this option is the changelog type(s). '
       '(usually a subset of {}).'.format(', '.join(ChangelogManager.TYPES)))
@click.option('-m', '--message', metavar='text',
  help='The changelog entry description. Only with --new. If this is not provided, the EDITOR '
       'will be opened to allow editing the changelog entry.')
@click.option('-c', '--components', metavar='name', help='The component for the changelog entry.')
@click.option('-i', '--issues', metavar='issue,…', help='Issues related to this changelog.')
@click.option('-e', '--edit', is_flag=True, help='Edit the staged changelog file in EDITOR.')
def changelog(**args):
  """
  Show or create changelog entries.
  """

  if (args['version'] or args['reformat']) and args['new']:
    logger.error('unsupported combination of arguments')
    sys.exit(1)

  subject = _load_subject(allow_none=True)
  if subject:
    manager = ChangelogManager(subject.changelog_directory, mapper)
  else:
    manager = ChangelogManager(Package.changelog_directory.default, mapper)

  def _split(s: Optional[str]) -> List[str]:
    return list(filter(bool, map(str.strip, (s or '').split(','))))

  if args['new']:

    # Warn about bad changelog types.
    for entry_type in _split(args['new']):
      if entry_type not in manager.TYPES:
        logger.warning('"%s" is not a well-known changelog entry type.', entry_type)

    entry = ChangelogEntry(
      _split(args['new']),
      _split(args['issues']),
      _split(args['components']),
      args['message'] or '')

    # Allow the user to edit the entry if no description is provided or the
    # -e,--edit option was set.
    if not entry.description or args['edit']:
      serialized = yaml.safe_dump(mapper.serialize(entry, ChangelogEntry), sort_keys=False)
      entry = mapper.deserialize(yaml.safe_load(_edit_text(serialized)), ChangelogEntry)

    print(entry)
    # Validate the entry contents (need a description and at least one type and component).
    if not entry.types or not entry.description or not entry.components:
      logger.error('changelog entries need at least one type and component and a description')
      sys.exit(1)

    created = not manager.unreleased.exists()
    manager.unreleased.add_entry(entry)
    manager.unreleased.save(create_directory=True)
    message = ('Created' if created else 'Updated') + ' "{}"'.format(manager.unreleased.filename)
    print(colored(message, 'cyan'))
    sys.exit(0)

  if args['edit']:
    if not manager.unreleased.exists():
      logger.error('no staged changelog')
      sys.exit(1)
    sys.exit(_editor_open(manager.unreleased.filename))

  # Load the changelog for the specified version or the current staged entries.
  changelog = manager.version(args['version']) if args['version'] else manager.unreleased
  if not changelog.exists():
    print('No changelog for {}.'.format(colored(str(args['version'] or 'unreleased'), 'yellow')))
    sys.exit(0)

  if args['reformat']:
    changelog.save()
    sys.exit(0)

  def _fmt_issue(i):
    if str(i).isdigit():
      return '#' + str(i)
    return i

  def _fmt_issues(entry):
    if not entry.issues:
      return None
    return '(' + ', '.join(colored(_fmt_issue(i), 'yellow', attrs=['underline']) for i in entry.issues) + ')'

  def _fmt_types(entry):
    return ', '.join(colored(f, attrs=['bold']) for f in entry.types)

  def _fmt_components(entry):
    if len(entry.components) <= 1:
      return None
    return '(' + ', '.join(colored(f, 'red', attrs=['bold', 'underline']) for f in entry.components[1:]) + ')'

  if hasattr(shutil, 'get_terminal_size'):
    width = shutil.get_terminal_size((80, 23))[0]
  else:
    width = 80

  # Explode entries by component.
  for component, entries in Stream.groupby(changelog.entries, lambda x: x.components[0], collect=list):

    maxw = max(len(', '.join(x.types)) for x in entries)
    print(colored(component or 'No Component', 'red', attrs=['bold', 'underline']))
    for entry in entries:
      lines = textwrap.wrap(entry.description, width - (maxw + 4))
      suffix_fmt = ' '.join(filter(bool, (_fmt_issues(entry), _fmt_components(entry))))
      lines[-1] += ' ' + suffix_fmt
      delta = maxw - len(', '.join(entry.types))
      print('  {}'.format(colored((_fmt_types(entry) + ':') + ' ' * delta, attrs=['bold'])), _md_term_stylize(lines[0]))
      for line in lines[1:]:
        print('  {}{}'.format(' ' * (maxw+2), _md_term_stylize(line)))


_entry_point = lambda: sys.exit(cli())

if __name__ == '__main__':
  _entry_point()
