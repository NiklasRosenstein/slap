
from __future__ import annotations

import abc
import copy
import dataclasses
import datetime
import typing as t
import uuid
from pathlib import Path

from databind.core.settings import Alias
from nr.util.weak import weak_property


if t.TYPE_CHECKING:
  from poetry.core.semver.version import Version  # type: ignore[import]
  from slap.repository import RepositoryHost


def is_url(s: str) -> bool:
  return s.startswith('http://') or s.startswith('https://')


@dataclasses.dataclass
class ChangelogEntry:
  id: str
  type: str
  description: str
  author: str | None = None
  authors: list[str] | None = None
  pr: str | None = None
  issues: list[str] | None = None

  def get_authors(self) -> list[str]:
    result = []
    if self.author is not None:
      result.append(self.author)
    if self.authors is not None:
      result += self.authors
    return result


@dataclasses.dataclass
class Changelog:
  entries: list[ChangelogEntry] = dataclasses.field(default_factory=list)
  release_date: t.Annotated[datetime.date | None, Alias("release-date")] = None


class ChangelogDeser(abc.ABC):

  @abc.abstractmethod
  def load(self, fp: t.TextIO, filename: str) -> Changelog: ...

  def save(self, changelog: Changelog, fp: t.TextIO, filename: str) -> None:
    fp.write(self.dump(changelog))

  @abc.abstractmethod
  def dump(self, changelog: Changelog) -> str: ...

  @abc.abstractmethod
  def dump_entry(self, entry: ChangelogEntry) -> str: ...


class TomlChangelogDeser(ChangelogDeser):

  def load(self, fp: t.TextIO, filename: str) -> Changelog:
    import databind.json
    import tomli
    return databind.json.load(tomli.loads(fp.read()), Changelog, filename=filename)

  def dump(self, changelog: Changelog) -> str:
    import databind.json
    from databind.core.settings import SerializeDefaults
    import tomli_w
    data = databind.json.dump(changelog, Changelog, settings=[SerializeDefaults(False)])
    return tomli_w.dumps(t.cast(dict, data))

  def dump_entry(self, entry: ChangelogEntry) -> str:
    import databind.json
    from databind.core.settings import SerializeDefaults
    import tomli_w
    return tomli_w.dumps(t.cast(dict, databind.json.dump(entry, ChangelogEntry, settings=[SerializeDefaults(False)])))


class ManagedChangelog:

  _manager: 'ChangelogManager' = weak_property('_ManagedChangelog__manager')

  def __init__(self, manager: 'ChangelogManager', path: Path, version: str | None) -> None:
    from poetry.core.semver.version import Version

    assert version is None or isinstance(version, str), type(version)

    self.path = path
    self.version = Version.parse(version) if version else None
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

    if self.version:
      raise RuntimeError('cannot release already released changelog')

    content = copy.deepcopy(self.content)
    content.release_date = datetime.date.today()
    target = self._manager.version(version)
    target.save(content)
    self.path.unlink()


@dataclasses.dataclass
class ChangelogManager:
  """ Manages a directory of changelogs. """

  #: The directory in which the changelog files can be found.
  directory: Path

  #: An instance for validation and normalization of issue and PR references.
  repository_host: RepositoryHost | None

  #: The name of the file that contains the unreleased changes.
  unreleased_fn: str = '_unreleased.toml'

  #: The template to describe the filenames of released changedlogs.
  version_fn_template: str = '{version}.toml'

  #: A list of strings that represent the valid choices of changelog entry types.
  valid_types: list[str] | None = None

  #: The de/serializer for changelogs.
  deser: ChangelogDeser = dataclasses.field(default_factory=TomlChangelogDeser)

  #: If enabled, write operations to the changelog directory are disabled.
  readonly: bool = False

  def _load(self, file: Path) -> Changelog:
    with file.open('r') as fp:
      return self.deser.load(fp, str(file))

  def _save(self, changelog: Changelog, file: Path) -> None:
    if self.readonly:
      raise RuntimeError(f'"{self.directory}" is readonly')
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open('w') as fp:
      self.deser.save(changelog, fp, str(file))

  def unreleased(self) -> ManagedChangelog:
    return ManagedChangelog(self, self.directory / self.unreleased_fn, None)

  def version(self, version: str) -> ManagedChangelog:
    return ManagedChangelog(self, self.directory / self.version_fn_template.format(version=version), version)

  def all(self) -> list[ManagedChangelog]:
    if not self.directory.exists():
      return []
    changelogs = []
    for path in self.directory.iterdir():
      if path.suffix == '.toml' and path.name != self.unreleased_fn:
        changelogs.append(ManagedChangelog(self, path, path.stem))
    changelogs.sort(key=lambda c: t.cast('Version', c.version), reverse=True)
    unreleased = self.unreleased()
    if unreleased.exists():
      changelogs.insert(0, unreleased)
    return changelogs

  def make_entry(
    self,
    change_type: str,
    description: str,
    author: str,
    pr: str | None,
    issues: list[str] | None,
  ) -> ChangelogEntry:
    """ Creates a new #ChangelogEntry and validates it. If the parameters of the changelog are invalid, a
    #InvalidChangelogEntryException is raised. A random unique ID is generated for the changelog. The *pr*
    and *issues* parameters may be issue IDs if a #remote is configured that supports the conversion. If no
    author is specified, it will be read from the *author* option or otherwise obtained via the #RepositoryHost,
    if available. """

    if self.valid_types is not None and change_type not in self.valid_types:
      raise ValueError(f'invalid change type: {change_type}')

    if pr is not None and self.repository_host:
      pr = self.repository_host.get_pull_request_by_reference(pr).url
    if issues is not None and self.repository_host:
      issues = [self.repository_host.get_issue_by_reference(i).url or i for i in issues]

    changelog_id = str(uuid.uuid4())
    return ChangelogEntry(
      id=changelog_id,
      type=change_type,
      description=description,
      author=author,
      pr=pr,
      issues=issues or None
    )

  def validate_entry(self, entry: ChangelogEntry) -> None:
    if self.valid_types is not None and entry.type not in self.valid_types:
      raise ValueError(f'invalid change type: {entry.type}')
    if entry.authors is not None and entry.author is not None:
      raise ValueError(f'entry has "author" and "authors", only one should be present')
    if not entry.get_authors():
      raise ValueError(f'entry has no "author" or "authors"')
    if not all(entry.get_authors()):
      raise ValueError(f'empty string in author(s)')
    if self.repository_host:
      if entry.pr:
        entry.pr = self.repository_host.get_pull_request_by_reference(entry.pr).url
      if entry.issues:
        entry.issues = [self.repository_host.get_issue_by_reference(issue).url for issue in entry.issues]
