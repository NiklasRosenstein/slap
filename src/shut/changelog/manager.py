
import dataclasses
import datetime
import typing as t
import uuid
from pathlib import Path

from nr.util.weak import weak_property

from .changelog import Changelog, ChangelogEntry
from .deser import ChangelogDeser, TomlChangelogDeser
from shut.plugins.remote_plugin import VcsRemote

DEFAULT_VALID_TYPES = ['breaking change', 'docs', 'feature', 'fix', 'hygiene', 'improvement']

def is_url(s: str) -> bool:
  return s.startswith('http://') or s.startswith('https://')



@dataclasses.dataclass
class ChangelogManager:
  """ Manages a directory of changelogs. """

  directory: Path
  remote: VcsRemote | None = None
  author: str | None = None
  deser: ChangelogDeser = dataclasses.field(default_factory=TomlChangelogDeser)
  unreleased_fn: str = '_unreleased.toml'
  version_fn_template: str = '{version}.toml'
  valid_types: list[str] | None = dataclasses.field(default_factory=lambda: DEFAULT_VALID_TYPES[:])

  def _load(self, file: Path) -> Changelog:
    with file.open('r') as fp:
      return self.deser.load(fp, str(file))

  def _save(self, changelog: Changelog, file: Path) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open('w') as fp:
      self.deser.save(changelog, fp, str(file))

  def unreleased(self) -> 'ManagedChangelog':
    return ManagedChangelog(self, self.directory / self.unreleased_fn, None)

  def version(self, version: str) -> 'ManagedChangelog':
    return ManagedChangelog(self, self.directory / self.version_fn_template.format(version=version), version)

  def all(self) -> t.Iterator['ManagedChangelog']:
    for path in self.directory.iterdir():
      if path.suffix == '.toml':
        yield ManagedChangelog(self, path, path.name if path.name != self.unreleased_fn else None)

  def make_entry(
    self,
    change_type: str,
    description: str,
    author: str | None,
    pr: str | None,
    issues: list[str] | None,
  ) -> ChangelogEntry:
    """ Creates a new #ChangelogEntry and validates it. If the parameters of the changelog are invalid, a
    #InvalidChangelogEntryException is raised. A random unique ID is generated for the changelog. The *pr*
    and *issues* parameters may be issue IDs if a #remote is configured that supports the conversion. If no
    author is specified, it will be read from the *author* option or otherwise obtained via the #VcsRemote,
    if available. """

    if not author:
      if self.author:
        author = self.author
      elif self.remote:
        author = self.remote.get_recommended_author()
      if not author:
        raise ValueError('no author specified')

    if self.valid_types is not None and change_type not in self.valid_types:
      raise ValueError(f'invalid change type: {change_type}')

    if pr is not None:
      if not is_url(pr):
        pr = self.remote.get_pull_request_url_from_id(pr)
      if not self.remote.validate_pull_request_url(pr):
        raise ValueError(f'invalid pr: {pr}')

    if issues is not None:
      issues = list(issues)
      for idx, issue in enumerate(issues):
        if not is_url(issue):
          issue = self.remote.get_issue_url_from_id(issue)
        if not self.remote.validate_issue_url(issue):
          raise ValueError(f'invalid issue: {issue}')
        issues[idx] = issues

    changelog_id = str(uuid.uuid4())
    return ChangelogEntry(changelog_id, change_type, description, author, pr, issues or None)

  def validate_entry(self, entry: ChangelogEntry) -> None:
    if entry.type not in self.config.valid_types:
      raise ValueError(f'invalid change type: {entry.type}')
    remote = self.shut_app.project_config.remote
    if entry.pr and remote and not remote.validate_pull_request_url(entry.pr):
      raise ValueError(f'invalid pr: {entry.pr}')
    for issue_url in entry.issues or []:
      if remote and not remote.validate_issue_url(issue_url):
        raise ValueError(f'invalid issue: {issue_url}')


class ManagedChangelog:

  def __init__(self, manager: ChangelogManager, path: Path, version: str | None) -> None:
    self.path = path
    self.version = version
    self._manager = manager
    self._content: Changelog | None = None

  _manager: ChangelogManager = weak_property('_ManagedChanlog__manager')

  @property
  def content(self) -> Changelog:
    return self.load()

  def exists(self) -> bool:
    return self.path.exists()

  def load(self, reload: bool = False) -> Changelog:
    if self._content is None or reload:
      self._content = self._manager._load(self.path)
    return self._content

  def save(self, changelog: Changelog | None) -> None:
    if changelog is None:
      if self._content is None:
        raise RuntimeError(f'ManagedChangelog.content was not loaded and no "changelog" parameter was provided')
      changelog = self._content
    if changelog.release_date is None and self.path.name != self._manager.unreleased_fn:
      raise RuntimeError(f'changelog without release date must be the unreleased changelog (but is {self.path.name})')
    if changelog.release_date is not None and self.path.name == self._manager.unreleased_fn:
      raise RuntimeError(f'changelog with release date must be a version (but is {self.path.name})')
    self._manager._save(changelog, self.path)

  def release(self, version: str) -> None:
    """ Releases the changelog as the specified version. """

    if not self.version:
      raise RuntimeError('cannot release already released changelog')

    old_path = self.path
    self.path = self._manager.directory / self._manager.version_fn_template.format(version=version)
    self.content.release_date = datetime.date.today()
    self.save(None)
    old_path.unlink(missing_ok=True)
