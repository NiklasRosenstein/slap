
import dataclasses
import datetime
import typing as t

from databind.core.annotations import alias


@dataclasses.dataclass
class ChangelogEntry:
  id: str
  type: str
  description: str
  author: str
  pr: str | None = None
  issues: list[str] | None = None


@dataclasses.dataclass
class Changelog:

  entries: list[ChangelogEntry] = dataclasses.field(default_factory=list)
  release_date: t.Annotated[datetime.date | None, alias("release-date")] = None
