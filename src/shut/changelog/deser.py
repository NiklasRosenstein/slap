
import abc
import typing as t

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
