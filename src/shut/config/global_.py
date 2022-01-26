
import dataclasses
import typing as t

from shut.plugins.remote_plugin import RemotePlugin


@dataclasses.dataclass
class GlobalConfig:
  author: str | None = None
  remote: RemotePlugin | None = None
