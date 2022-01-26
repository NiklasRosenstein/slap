
import abc

from databind.core.annotations import union


@union(
  union.Subtypes.entrypoint('shut.config.remote.RemotePlugin')
)