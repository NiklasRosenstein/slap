
import dataclasses
import os
import re
import sys
import textwrap
import typing as t
from pathlib import Path

import databind.json
from databind.core.annotations import alias
from nr.util.plugins import load_plugins

from shut.console.command import Command, IO, argument, option
from shut.console.application import Application
from shut.plugins.application_plugin import ApplicationPlugin
from shut.plugins.release_plugin import ReleasePlugin, VersionRef, ENTRYPOINT as RELEASE_PLUGIN_ENTRYPOINT

if t.TYPE_CHECKING:
  from poetry.core.semver.version import Version


def match_version_ref_pattern(filename: Path, pattern: str) -> VersionRef:
  """ Matches a regular expression in the given file and returns the location of the match. The *pattern*
  should contain at least one capturing group. The first capturing group is considered the one that contains
  the version number exactly.

  :param filename: The file of which the contents will be checked against the pattern.
  :param pattern: The regular expression that contains at least one capturing group.
  """

  compiled_pattern = re.compile(pattern, re.M | re.S)
  if not compiled_pattern.groups:
    raise ValueError(
      f'pattern must contain at least one capturing group (filename: {filename!r}, pattern: {pattern!r})'
    )

  with open(filename) as fp:
    match = compiled_pattern.search(fp.read())
    if match:
      return VersionRef(filename, match.start(1), match.end(1), match.group(1))

  raise ValueError(f'pattern {pattern!r} does not match in file {filename!r}')


@dataclasses.dataclass
class VersionRefConfig:
  file: str
  pattern: str


@dataclasses.dataclass
class ReleaseConfig:
  branch: str = 'develop'
  commit_message: t.Annotated[str, alias('commit-message')] = 'release {version}'
  tag_format: t.Annotated[str, alias('tag-format')] = '{version}'
  references: list[VersionRefConfig] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class VersionRefConfigMatcherPlugin(ReleasePlugin):
  """ This plugin matches a list of #VersionRefConfig definitions and returns the matched version references. This
  plugin is used to match the `tool.shut.release.references` config option and is always used. It should not be
  registered in the `shut.plugins.release` entrypoint group.
  """

  PYPROJECT_CONFIG = VersionRefConfig('pyproject.toml', r'^version\s*=\s*[\'"]?(.*?)[\'"]')

  references: list[VersionRefConfig]

  def get_version_refs(self, io: 'IO') -> list[VersionRef]:
    results = []
    for config in [self.PYPROJECT_CONFIG] + self.references:
      pattern = config.pattern.replace('{version}', r'(.*)')
      version_ref = match_version_ref_pattern(Path(config.file), pattern)
      if version_ref is not None:
        results.append(version_ref)
    return results


@dataclasses.dataclass
class SourceCodeVersionMatcherPlugin(ReleasePlugin):
  """ This plugin searches for a `__version__` key in the source code of the project and return it as a version
  reference. Based on the Poetry configuration (considering `tool.poetry.packages` and searching in the `src/`
  folder if it exists), the following source files will be checked:

  * `__init__.py`
  * `__about__.py`
  * `_version.py`

  Note that configuring `tool.poetry.packages` is needed for the detection to work correctly with PEP420
  namespace packages.
  """

  VERSION_REGEX = r'^__version__\s*=\s*[\'"]([^\'"]+)[\'"]'
  FILENAMES = ['__init__.py', '__about__.py', '_version.py']

  #: The `tool.poetry.packages` configuration from `pyproject.toml`.
  packages_conf: list[dict[str, t.Any]] | None = None

  def get_version_refs(self, io: 'IO') -> list[VersionRef]:
    results = []
    for directory in self.get_package_roots():
      for filename in self.FILENAMES:
        path = directory / filename
        if path.exists():
          version_ref = match_version_ref_pattern(path, self.VERSION_REGEX)
          if version_ref:
            results.append(version_ref)
            break
    if not results:
      message = '<fg=yellow>warning: unable to detect <b>__version__</b> in a source file'
      if not self.packages_conf:
        message += ' (if your package is a PEP420 namespacepackage, configure <info>tool.poetry.packages</info>)'
      io.write_error_line(message + '</fg>')
    return results

  def get_package_roots(self) -> list[Path]:
    """ Tries to identify the package roots that may contain source files with a `__version__`. """

    src_dir = Path('.')
    if (sub_dir := src_dir / 'src').is_dir():
      src_dir = sub_dir

    results = []
    if self.packages_conf:
      for conf in self.packages_conf:
        results.append(src_dir / conf['include'])
    else:
      for item in src_dir.iterdir():
        if item.is_dir():
          results.append(item)

    return results


class ReleaseCommand(Command):

  name = "release"
  description = (
    "Bumps the version number in pyproject.toml and in other places."
  )

  arguments = [
    argument("version", "The target version number or rule to apply to the current version.", True),
  ]

  options = [
    option("tag", "t", "Create a Git tag after the version numbers were updated."),
    option("push", "p", "Push the changes to the Git remote repository."),
    option("remote", "r", "The Git remote to push to (only when <info>--push</info> is specified)", False),
    option("dry", "d", "Do not commit changes to disk."),
    option("force", "f", "Force tag creation and push."),
    option("validate", None, "Instead of bumping the version, validate that all version references are consistent.\n"
      "If the <info>version</info> argument is specified, all version references must match it.\n"),
    option("no-branch-check", None, "Do not validate the current Git branch matches the configured release branch."),
    option("no-worktree-check", None, "Do not check the worktree state."),
  ]

  help = textwrap.dedent("""
    The release command bumps the version number in <info>pyproject.toml</info>, much like the version
    command, but also in other places. Optionally, it will create a Git tag and push the changes to the
    remote repository.
  """)

  # TODO (@NiklasRosenstein): Support "git" rule for bumping versions

  def __init__(self, app: Application):
      super().__init__()
      self._app = app

  def _validate_options(self) -> int:
    """ Internal. Ensures that the combination of provided options make sense. """

    if self.option("dry") and self.option("validate"):
      self.line_error('error: --dry cannot be combined with --validate', 'error')
      return 1
    if self.option("tag") and self.option("validate"):
      self.line_error('error: --tag cannot be combined with --validate', 'error')
      return 1
    if self.option("push") and not self.option("tag"):
      self.line_error('error: --push can only be combined with --tag', 'error')
      return 1
    if self.option("force") and not self.option("tag"):
      self.line_error('error: --force can only be combined with --tag and --push', 'error')
      return 1
    if self.option("remote") is not None and not self.option("push"):
      self.line_error('error: --remote can only be combined with --push', 'error')
      return 1

    self.io.input.set_option("remote", self.option("remote") or "origin")

    if self.option("tag") and not self.is_git_repository:
      self.line_error('error: not in a git repository, cannot use --tag', 'error')
      return 1
    if self.option("push") and not self.is_git_repository:
      self.line_error('error: not in a git repository, cannot use --push', 'error')
      return 1
    if self.option("push") and (remote := self.option("remote")) not in {r.name for r in self.git.remotes()}:
      self.line_error(f'error: git remote "{remote}" does not exist', 'error')
      return 1

    return 0

  def _get_raw_tool_config(self) -> dict[str, t.Any]:
    """ Internal. Get the raw `tool` config from the pyproject config. """

    return self._app.load_pyproject().get('tool', {})

  def _load_config(self) -> ReleaseConfig:
    """ Internal. Extracts the `tool.shut.release` config from the pyproject config. """

    data = self._app.config.get('release', {})
    return databind.json.load(data, ReleaseConfig)

  def _load_plugins(self) -> list[ReleasePlugin]:
    """ Internal. Loads the plugins to be used in the run of `poetry release`.

    If `SHUT_RELEASE_NO_PLUGINS` is set in the environment, no plugins will be loaded from entrypoints.
    """

    tool = self._get_raw_tool_config()

    plugins: list[ReleasePlugin] = [
      VersionRefConfigMatcherPlugin(self.config.references),
      SourceCodeVersionMatcherPlugin(tool.get('poetry', {}).get('packages')),
    ]

    if os.getenv('SHUT_RELEASE_NO_PLUGINS') is not None:
      return plugins

    return plugins + load_plugins(RELEASE_PLUGIN_ENTRYPOINT, ReleasePlugin)

  def _show_version_refs(self, version_refs: list[VersionRef], status_line: str = '') -> None:
    """ Internal. Prints the version references to the terminal. """

    self.line(f'<b>version references:</b> {status_line}')
    max_length = max(len(str(ref.file)) for ref in version_refs)
    for ref in version_refs:
      self.line(f'  <fg=cyan>{str(ref.file).ljust(max_length)}</fg> {ref.value}')

  def _validate_version_refs(self, version_refs: list[VersionRef], version: str | None) -> int:
    """ Internal. Verifies the consistency of the given version references. This is used when `--validate` is set. """

    versions = set(ref.value for ref in version_refs)
    if len(versions) > 1:
      self._show_version_refs(version_refs, '<error>inconsistencies detected</error>')
      return 1
    if version is not None:
      Version.parse(version)
      if version not in versions:
        self._show_version_refs(version_refs, f'<error>expected <b>{version}</b>, but got</error>')
        return 1
    self._show_version_refs(version_refs, '<comment>in good shape</comment>')
    return 0

  def _check_on_release_branch(self) -> bool:
    """ Internal. Checks if the current Git branch matches the configured release branch. """

    from nr.util.git import NoCurrentBranchError

    if not self.is_git_repository or self.option("no-branch-check"):
      return True

    try:
      current_branch = self.git.get_current_branch_name()
    except NoCurrentBranchError:
      self.line_error(f'error: not currently on a Git branch', 'error')
      return False

    if current_branch != self.config.branch:
      self.line_error(
        f'error: current branch is <b>{current_branch}</b> but must be on the '
          f'release branch (<b>{self.config.branch}</b>)', 'error'
      )
      return False
    return True

  def _check_clean_worktree(self, required_files: list[Path]) -> bool:
    """ Internal. Checks that the Git work state is clean and that all the *required_files* are tracked in the repo. """

    if not self.is_git_repository or self.option("no-worktree-check"):
      return True

    queried_files = {f.resolve() for f in required_files}
    tracked_files = {Path(f).resolve() for f in self.git.get_files()}
    if (untracked_files := queried_files - tracked_files):
      self.line_error('error: some of the files with version references are not tracked by Git', 'error')
      for fn in untracked_files:
        self.line_error(f'  · {fn}', 'error')
      return False

    file_status = list(self.git.get_status())
    if any(f.mode[1] != ' ' for f in file_status):
      self.line_error('error: found untracked changes in worktree', 'error')
      return False
    if any(f.mode[0] not in ' ?' for f in file_status):
      self.line(
        '<fg=yellow>found modified files in the staging area. these files will be committed into the release tag.</fg>'
      )
      if not self.confirm('continue anyway?'):
        return False

    return True

  def _bump_version(self, version_refs: list[VersionRef], version: str, dry: bool) -> tuple[str, list[Path]]:
    """ Internal. Replaces the version reference in all files with the specified *version*. """

    from nr.util import Stream
    from shut.util.text import substitute_ranges
    from poetry.core.semver.version import Version

    self.line(f'bumping <b>{len(version_refs)}</b> version reference{"" if len(version_refs) == 1 else "s"}')

    current_version = Version.parse(self._get_raw_tool_config()['poetry']['version'])
    target_version = str(self._increment_version(current_version, version))
    changed_files: list[Path] = []

    for filename, refs in Stream(version_refs).groupby(lambda r: r.file, lambda it: list(it)):
      if len(refs) == 1:
        ref = refs[0]
        self.line(f'  <fg=cyan>{ref.file}</fg>: {ref.value} → {target_version}')
      else:
        self.line(f'  <fg=cyan>{ref.file}</fg>:')
        for ref in refs:
          self.line(f'    {ref.value} → {target_version}')

      with open(filename) as fp:
        content = fp.read()

      content = substitute_ranges(
        content,
        ((ref.start, ref.end, str(target_version)) for ref in refs),
      )

      changed_files.append(filename)
      if not dry:
        with open(filename, 'w') as fp:
          fp.write(content)

    # Delegate to the plugins to perform any remaining changes.
    for plugin in self.plugins:
      try:
        changed_files.extend(plugin.bump_to_version(target_version, dry, self.io))
      except:
        self.line_error(f'error with {type(plugin).__name__}.bump_version()', 'error')
        raise

    return target_version, changed_files

  def _create_tag(self, target_version: str, changed_files: list[Path], dry: bool, force: bool) -> str:
    """ Internal. Used when --tag is specified to create a Git tag. """

    assert self.is_git_repository

    # TODO (@NiklasRosenstein): If this step errors, revert the changes made by the command so far?

    if '{version}' not in self.config.tag_format:
      self.line_error('<info>tool.shut.release.tag-format<info> must contain <info>{version}</info>', 'error')
      sys.exit(1)
    tag_name = self.config.tag_format.replace('{version}', target_version)
    self.line(f'tagging <fg=cyan>{tag_name}</fg>')

    if not dry:
      commit_message = self.config.commit_message.replace('{version}', target_version)
      self.git.add([str(f) for f in changed_files])
      self.git.commit(commit_message, allow_empty=True)
      self.git.tag(tag_name, force=force)

    return tag_name

  def _push_to_remote(self, tag_name: str, remote: str, dry: bool, force: bool) -> None:
    """ Internal. Push the current branch and the tag to the remote repository. Use when `--push` is set. """

    assert self.is_git_repository

    branch = self.git.get_current_branch_name()

    self.line(f'pushing <fg=cyan>{branch}</fg>, <fg=cyan>{tag_name}</fg> to <info>{remote}</info>')

    if not dry:
      self.git.push(remote, branch, tag_name, force=force)

  def _increment_version(self, version: "Version", rule: str) -> "Version":
    """ Internal. Increment a version according to a rule. This is mostly copied from the Poetry `VersionCommand`. """

    from poetry.core.semver.version import Version

    if rule in {"major", "premajor"}:
      new = version.next_major()
      if rule == "premajor":
        new = new.first_prerelease()
    elif rule in {"minor", "preminor"}:
      new = version.next_minor()
      if rule == "preminor":
        new = new.first_prerelease()
    elif rule in {"patch", "prepatch"}:
      new = version.next_patch()
      if rule == "prepatch":
        new = new.first_prerelease()
    elif rule == "prerelease":
      if version.is_unstable():
        assert version.pre
        new = Version(version.epoch, version.release, version.pre.next())
      else:
        new = version.next_patch().first_prerelease()
    else:
      new = Version.parse(rule)

    return new

  def handle(self) -> int:
    """ Entrypoint for the command."""

    from nr.util import Stream
    from nr.util.git import Git

    self.git = Git()
    self.is_git_repository = self.git.is_repository()

    if (err := self._validate_options()) != 0:
      return err

    self.config = self._load_config()
    self.plugins = self._load_plugins()
    version_refs = Stream(plugin.get_version_refs(self.io) for plugin in self.plugins).concat().collect()
    version = self.argument("version")

    if self.option("validate"):
      return self._validate_version_refs(version_refs, version)

    if version is not None:
      if self.option("tag") and not self._check_on_release_branch():
        return 1
      if self.option("tag") and not self._check_clean_worktree([x.file for x in version_refs]):
        return 1
      if self.option("dry"):
        self.line('note: --dry mode enabled, no changes will be commited to disk', 'comment')
      target_version, changed_files = self._bump_version(version_refs, version, self.option("dry"))
      if self.option("tag"):
        tag_name = self._create_tag(target_version, changed_files, self.option("dry"), self.option("force"))
        if self.option("push"):
          self._push_to_remote(tag_name, self.option("remote"), self.option("dry"), self.option("force"))

    else:
      self.line_error(
        '<error>error: no action implied, specify a <info>version</info> argument or the <info>--validate</info> option'
      )
      return 1

    return 0


class ReleaseCommandPlugin(ApplicationPlugin):

  def activate(self, app: Application):
    app.cleo.add(ReleaseCommand(app))
