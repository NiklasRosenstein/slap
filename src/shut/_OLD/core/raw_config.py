
""" Provides the {@link ShutProject} class that serves as an access point for the Shut and Pyproject configuration. """

import enum
import typing as t
from pathlib import Path

from .toml_config import TomlConfig


class RawConfigSource(enum.Enum):
  PYPROJECT = 'pyproject.toml'
  STANDALONE = 'shut.toml'
  GLOBAL = '~/.config/shut/config.toml'


class RawConfig:
  """ Provides an access point for the Shut and the Pyproject configuration. """

  def __init__(self, directory: Path) -> None:
    self._directory = Path(directory)
    self._pyproject = TomlConfig(self._directory / RawConfigSource.PYPROJECT.value, RawConfigSource.PYPROJECT)
    self._standalone = TomlConfig(self._directory / RawConfigSource.STANDALONE.value, RawConfigSource.STANDALONE)
    self._global = TomlConfig(Path(RawConfigSource.GLOBAL.value).expanduser(), RawConfigSource.GLOBAL)

  @property
  def directory(self) -> Path:
    return self._directory

  @property
  def pyproject(self) -> TomlConfig:
    return self._pyproject

  @property
  def standalone(self) -> TomlConfig:
    return self._standalone

  @property
  def global_(self) -> TomlConfig:
    return self._global

  @property
  def source(self) -> TomlConfig | None:
    if self._standalone:
      return self._standalone
    if self._pyproject:
      return self._pyproject
    return None

  @property
  def source_type(self) -> RawConfigSource:
    if self._standalone:
      return RawConfigSource.STANDALONE
    if self._pyproject:
      return RawConfigSource.PYPROJECT
    return None

  @property
  def raw_config(self) -> dict[str, t.Any]:
    if self._standalone:
      return self._standalone.value()
    if self._pyproject:
      return self._pyproject.value().setdefault('tool', {}).setdefault('shut', {})
    return {}
