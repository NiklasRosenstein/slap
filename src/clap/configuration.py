
from __future__ import annotations

import logging
import typing as t
from pathlib import Path

from clap.util.toml_file import TomlFile

if t.TYPE_CHECKING:
  from nr.util.functional import Once

logger = logging.getLogger(__name__)


class Configuration:
  """ Represents the configuration stored in a directory, which is either read from `clap.toml` or `pyproject.toml`. """

  #: The directory of the project. This is the directory where the `clap.toml` or `pyproject.toml` configuration
  #: would usually reside in, but the existence of neither is absolutely required.
  directory: Path

  #: Points to the `pyproject.toml` file in the project and can be used to conveniently check for its existence
  #: or to access its contents.
  pyproject_toml: TomlFile

  #: Points to the `clap.toml` file in the project and can be used to conveniently check for its existence
  #: or to access its contents.
  slam_toml: TomlFile

  #: Use this to access the Clap configuration, automatically loaded from either `clap.toml` or the `tool.clap`
  #: section in `pyproject.toml`. The attribute is a #Once instance, thus it needs to be called to retrieve
  #: the contents. This is the same as #get_raw_configuration(), but is more efficient.
  raw_config: Once[dict[str, t.Any]]

  def __init__(self, directory: Path) -> None:
    from nr.util.functional import Once
    self.directory = directory
    self.pyproject_toml = TomlFile(directory / 'pyproject.toml')
    self.slam_toml = TomlFile(directory / 'clap.toml')
    self.raw_config = Once(self.get_raw_configuration)

  def __repr__(self) -> str:
    return f'{type(self).__name__}(directory="{self.directory}")'

  def get_raw_configuration(self) -> dict[str, t.Any]:
    """ Loads the raw configuration data for Clap from either the `clap.toml` configuration file or `pyproject.toml`
    under the `[clap.tool]` section. If neither of the files exist or the section in the pyproject does not exist,
    an empty dictionary will be returned. """

    if self.slam_toml.exists():
      logger.debug(
        'Reading configuration for <subj>%s</subj> from <val>%s</val>',
        self, self.slam_toml.path
      )
      return self.slam_toml.value()
    if self.pyproject_toml.exists():
      logger.debug(
        'Reading configuration for <subj>%s</subj> from <val>%s</val>',
        self, self.pyproject_toml.path
      )
      return self.pyproject_toml.value().get('tool', {}).get('clap', {})
    return {}
