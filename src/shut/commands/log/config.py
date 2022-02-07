
import abc
import dataclasses
import typing as t
from pathlib import Path

from databind.core.annotations import alias, union

from shut.application import Application
from shut.changelog.changelog_manager import DEFAULT_VALID_TYPES, ChangelogManager, ChangelogValidator

ENTRYPOINT = 'shut.commands.log.config.RemoteProvider'


class RemoteDetector(abc.ABC):

  @abc.abstractmethod
  def detect_changelog_validator(self, app: Application) -> ChangelogValidator | None: ...


@union(union.Subtypes.entrypoint(ENTRYPOINT))
class RemoteProvider(abc.ABC):

  @abc.abstractmethod
  def get_changelog_validator(self, app: Application) -> ChangelogValidator: ...


@dataclasses.dataclass
class LogConfig:
  directory: Path = Path('.changelog')
  valid_types: t.Annotated[list[str] | None, alias('valid-types')] = \
    dataclasses.field(default_factory=lambda: list(DEFAULT_VALID_TYPES))
  remote: RemoteProvider | None = None


def get_changelog_manager(app: Application) -> ChangelogManager:
  import databind.json
  config = databind.json.load(app.raw_config().get('log', {}), LogConfig)

  validator: ChangelogValidator | None = None
  if config.remote:
    validator = config.remote.get_changelog_validator(app)
  else:
    for plugin_name, plugin in app.plugins.group(RemoteDetector, RemoteDetector):
      if (validator := plugin.detect_changelog_validator(app)):
        break

  return ChangelogManager(config.directory, validator, None, valid_types=config.valid_types)
