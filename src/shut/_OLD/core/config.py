
import dataclasses
import typing as t

from databind.core.annotations import alias, fieldinfo

from shut.plugins.remote_plugin import RemotePlugin


@dataclasses.dataclass
class ProjectConfig:
  source_directory: t.Annotated[str | None, alias('source-directory')] = None
  remote: RemotePlugin | None = None
  typed: bool | None = None
  extras: t.Annotated[dict[str, t.Any], fieldinfo(flat=True)] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class GlobalConfig:
  author: str | None = None
