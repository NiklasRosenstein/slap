
import dataclasses
import typing as t

from databind.core.annotations import alias, fieldinfo


@dataclasses.dataclass
class ProjectConfig:
  source_directory: t.Annotated[str | None, alias('source-directory')] = None
  extras: t.Annotated[dict[str, t.Any], fieldinfo(flat=True)] = dataclasses.field(default_factory=dict)
