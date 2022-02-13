
import dataclasses
import datetime
import typing as t

from databind.core.annotations import alias


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
  release_date: t.Annotated[datetime.date | None, alias("release-date")] = None
