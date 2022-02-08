
import abc
import dataclasses
import datetime
import typing as t
import uuid
from pathlib import Path

from nr.util.weak import weak_property

from .model import Changelog, ChangelogEntry

DEFAULT_VALID_TYPES = ['breaking change', 'docs', 'feature', 'fix', 'hygiene', 'improvement']

def is_url(s: str) -> bool:
  return s.startswith('http://') or s.startswith('https://')


class ChangelogDeser(abc.ABC):

  @abc.abstractmethod
  def load(self, fp: t.TextIO, filename: str) -> Changelog: ...

  @abc.abstractmethod
  def save(self, changelog: Changelog, fp: t.TextIO, filename: str) -> None: ...


class TomlChangelogDeser(ChangelogDeser):

  def load(self, fp: t.TextIO, filename: str) -> Changelog:
    import databind.json
    import tomli
    return databind.json.load(tomli.loads(fp.read()), Changelog, filename=filename)

  def save(self, changelog: Changelog, fp: t.TextIO, filename: str) -> None:
    import databind.json
    import tomli_w
    fp.write(tomli_w.dumps(t.cast(dict, databind.json.dump(changelog, Changelog))))


class ChangelogValidator(abc.ABC):

  @abc.abstractmethod
  def normalize_pr_reference(self, pr: str) -> str:
    """ This method is called to accept a pull request ID or URL, validate it and ensure that it is in a normalized
    form. For example, the canonical form of a GitHub pull request ID might be to represent it as a full URL. """

  @abc.abstractmethod
  def normalize_issue_reference(self, issue: str) -> str:
    """ Sames as {@link normalize_pr_reference()} but for issues. """

  @abc.abstractmethod
  def normalize_author(self, author: str) -> str:
    """ Called to normalize the author name that was specified. """

  @staticmethod
  def null() -> 'ChangelogValidator':
    return NullChangelogValidator()


class NullChangelogValidator(ChangelogValidator):

  def normalize_pr_reference(self, pr: str) -> str:
    return pr

  def normalize_issue_reference(self, issue: str) -> str:
    return issue

  def normalize_author(self, author: str) -> str:
    return author


class ManagedChangelog:

  _manager: 'ChangelogManager' = weak_property('_ManagedChangelog__manager')

  def __init__(self, manager: 'ChangelogManager', path: Path, version: str | None) -> None:
    self.path = path
    self.version = version
    self._manager = manager
    self._content: Changelog | None = None

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


@dataclasses.dataclass
class ChangelogManager:
  """ Manages a directory of changelogs. """

  #: The directory in which the changelog files can be found.
  directory: Path

  #: An instance for validation and normalization of issue and PR references.
  validator: ChangelogValidator

  #: The preferred author to use if no author is specified in {@link make_entry()}.
  author: str | None = None

  #: The name of the file that contains the unreleased changes.
  unreleased_fn: str = '_unreleased.toml'

  #: The template to describe the filenames of released changedlogs.
  version_fn_template: str = '{version}.toml'

  #: A list of strings that represent the valid choices of changelog entry types.
  valid_types: list[str] | None = dataclasses.field(default_factory=lambda: DEFAULT_VALID_TYPES[:])

  #: The de/serializer for changelogs.
  deser: ChangelogDeser = dataclasses.field(default_factory=TomlChangelogDeser)

  def _load(self, file: Path) -> Changelog:
    with file.open('r') as fp:
      return self.deser.load(fp, str(file))

  def _save(self, changelog: Changelog, file: Path) -> None:
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open('w') as fp:
      self.deser.save(changelog, fp, str(file))

  def unreleased(self) -> ManagedChangelog:
    return ManagedChangelog(self, self.directory / self.unreleased_fn, None)

  def version(self, version: str) -> ManagedChangelog:
    return ManagedChangelog(self, self.directory / self.version_fn_template.format(version=version), version)

  def all(self) -> t.Iterator[ManagedChangelog]:
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

    author = author or self.author
    if not author:
      raise ValueError('no author specified')
    author = self.validator.normalize_author(author)

    if self.valid_types is not None and change_type not in self.valid_types:
      raise ValueError(f'invalid change type: {change_type}')

    if pr is not None:
      pr = self.validator.normalize_pr_reference(pr)
    if issues is not None:
      issues = [self.validator.normalize_issue_reference(i) for i in issues]

    changelog_id = str(uuid.uuid4())
    return ChangelogEntry(changelog_id, change_type, description, author, pr, issues or None)

  def validate_entry(self, entry: ChangelogEntry) -> None:
    if self.valid_types is not None and entry.type not in self.valid_types:
      raise ValueError(f'invalid change type: {entry.type}')
    if entry.authors is not None and entry.author is not None:
      raise ValueError(f'entry has "author" and "authors", only one should be present')
    if not entry.get_authors():
      raise ValueError(f'entry has no "author" or "authors"')
    if not all(entry.get_authors()):
      raise ValueError(f'empty string in author(s)')
    if entry.pr:
      self.validator.normalize_pr_reference(entry.pr)
    for issue_url in entry.issues or []:
      self.validator.normalize_issue_reference(issue_url)
