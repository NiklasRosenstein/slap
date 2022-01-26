
import abc
import datetime
import typing as t
from pathlib import Path

from nr.util.weak import weak_property

from .changelog import Changelog


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


class ChangelogManager:
  """ Manages a directory of changelogs. """

  UNRELEASED = '_unreleased.toml'
  VERSIONED = '{version}.toml'

  def __init__(self, directory: Path, deser: ChangelogDeser) -> None:
    self.directory = directory
    self.deser = deser

  def _load(self, file: Path) -> Changelog:
    with file.open('r') as fp:
      return self.deser.load(fp, str(file))

  def _save(self, changelog: Changelog, file: Path) -> None:
    file.mkdir(parents=True, exist_ok=True)
    with file.open('w') as fp:
      self.deser.save(changelog, fp, str(file))

  def unreleased(self) -> 'ManagedChangelog':
    return ManagedChangelog(self, self.directory / self.UNRELEASED, None)

  def version(self, version: str) -> 'ManagedChangelog':
    return ManagedChangelog(self, self.directory / self.VERSIONED.format(version=version), version)


class ManagedChangelog:

  def __init__(self, manager: ChangelogManager, path: Path, version: str | None) -> None:
    self.path = path
    self.version = version
    self._manager = manager
    self._content: Changelog | None = None

  _manager: ChangelogManager = weak_property('_manager')

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
    self._manager._save(changelog, self.path)

  def release(self, version: str) -> None:
    """ Releases the changelog as the specified version. """

    if not self.version:
      raise RuntimeError('cannot release already released changelog')

    self.path = self._manager.directory / self._manager.VERSIONED.format(version=version)
    self.content.release_date = datetime.date.today()
    self.save(None)
