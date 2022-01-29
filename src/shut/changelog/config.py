
import dataclasses
import typing as t

from databind.core.annotations import alias



@dataclasses.dataclass
class ChangelogConfig:
  directory: str = '.changelog'
  valid_types: t.Annotated[list[str], alias('valid-types')] = dataclasses.field(default_factory=lambda: DEFAULT_VALID_TYPES[:])
