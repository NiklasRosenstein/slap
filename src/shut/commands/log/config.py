
import dataclasses
import typing as t

from databind.core.annotations import alias

from shut.application import Application
from shut.changelog.changelog_manager import DEFAULT_VALID_TYPES, ChangelogManager


@dataclasses.dataclass
class LogConfig:
  directory: str = '.changelog'
  valid_types: t.Annotated[list[str] | None, alias('valid-types')] = dataclasses.field(default_factory=lambda: list(DEFAULT_VALID_TYPES))


def get_changelog_manager(app: Application) -> ChangelogManager:
  import databind.json
  config = databind.json.load(app.raw_config().get('log', {}), LogConfig)

  from shut.changelog.changelog_manager import ChangelogValidator
  validator = None#ChangelogValidator()  # TODO (@NiklasRosenstein): Create correct changelog validator

  return ChangelogManager(config.directory, validator, None, valid_types=config.valid_types)
