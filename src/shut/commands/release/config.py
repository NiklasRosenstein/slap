
import dataclasses
import typing as t

from databind.core.annotations import alias


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
